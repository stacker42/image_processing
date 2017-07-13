# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import shutil
import os
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.decorators import method_decorator
from django.core.exceptions import ObjectDoesNotExist, ValidationError, PermissionDenied
from django.http import Http404
from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from forms import UploadFileForm, ObjectForm, ObservationForm, HeaderForm, ImagingDeviceForm
from models import *
from utils import fits, upload, astrometry, photometry, calibration
import pyfits


@login_required
def home(request):
    """
    Let the user upload files
    :param request:
    :return:
    """
    return render(request, "base_upload.html")


@login_required
def process(request):
    """
    Let the user continue processing their files
    :param request:
    :return:
    """
    unprocessed = UnprocessedUpload.objects.filter(user=request.user)
    files = FITSFile.objects.filter(uploaded_by=request.user).exclude(process_status='COMPLETE')

    return render(request, "base_process.html", {'unprocessed': unprocessed, 'files': files})


@login_required
def process_header(request, uuid):
    """
    Lets the user check the header information in a given file, based on UUID
    User has the option to delete the file, if the header is not correct, or
    to proceed onto the next stage
    :param uuid: The UUID of the file to check
    :return:
    """

    REQUIRED_HEADER_KEYS = [
        'NAXIS1', 'NAXIS2', 'EXPTIME', 'FILTER', 'DATE-OBS'
    ]

    if request.method == "POST":
        try:
            unprocessed_file = UnprocessedUpload.objects.get(uuid=uuid)
        except (ObjectDoesNotExist, ValidationError):
            raise Http404

        if request.POST.get('delete') == "true":
            # Don't let other users delete files they didn't upload!
            if unprocessed_file.user == request.user:
                unprocessed_file.delete()
                upload.handle_deleted_file(str(uuid))

                return redirect('home')
            else:
                raise PermissionDenied
        else:
            # Need to add the files to the database
            # First lets check that the user has permission to work with this file
            if not request.user == unprocessed_file.user:
                raise PermissionDenied

            inhdulist = fits.get_hdu_list(
                os.path.join(settings.UPLOAD_DIRECTORY, str(unprocessed_file.uuid), unprocessed_file.filename))

            if not set(REQUIRED_HEADER_KEYS).issubset(inhdulist[0].header.keys()):
                    return render(request, "base_process_header.html", {'header': repr(inhdulist[0].header),
                                                                        'uuid': str(unprocessed_file.uuid),
                                                                        'missing_key': True,
                                                                        'required': REQUIRED_HEADER_KEYS})

            header = {}

            # Iterate through all the header values and add these to a dictionary
            for key, value in zip(inhdulist[0].header.keys(), inhdulist[0].header.values()):
                header[key] = value

            fits_file = FITSFile()

            fits_file.header = json.dumps(header)
            fits_file.fits_filename = ''
            fits_file.catalog_filename = ''
            fits_file.uploaded_by = unprocessed_file.user
            fits_file.upload_time = unprocessed_file.upload_time

            fits_file.save()

            # Make a new directory for the file and put it into this new directory.
            os.mkdir(os.path.join(settings.FITS_DIRECTORY, str(fits_file.id)))
            shutil.move(os.path.join(settings.UPLOAD_DIRECTORY, str(unprocessed_file.uuid), unprocessed_file.filename),
                        os.path.join(settings.FITS_DIRECTORY, str(fits_file.id), unprocessed_file.filename))
            upload.handle_deleted_file(str(unprocessed_file.uuid))

            fits_file.fits_filename = unprocessed_file.filename

            fits_file.save()

            # Seeing as we don't need the reference to the unprocessed file any more, delete it.
            unprocessed_file.delete()

            # Set the current stage of the processing
            fits_file.process_status = 'HEADER'

            fits_file.save()

            return redirect('process')

    unprocessed_file = get_object_or_404(UnprocessedUpload, uuid=uuid)

    # Only users of the file can process the header
    if unprocessed_file.user != request.user:
        raise PermissionDenied

    hdulist = fits.get_hdu_list(os.path.join(settings.UPLOAD_DIRECTORY, str(unprocessed_file.uuid),
                                             unprocessed_file.filename))

    header_text = repr(hdulist[0].header)

    if not set(REQUIRED_HEADER_KEYS).issubset(hdulist[0].header.keys()):
        return render(request, "base_process_header.html", {'header': header_text,
                                                            'uuid': str(unprocessed_file.uuid),
                                                            'missing_key': True, 'required': REQUIRED_HEADER_KEYS})

    return render(request, "base_process_header.html", {'header': header_text, 'uuid': str(unprocessed_file.uuid),
                                                        'missing_key': False})


def process_header_modify(request, uuid):
    """
    Modify (or ideally add) the required header cards to the FITS file so we'll be able to analyse it
    :param request:
    :param uuid: The UUID of the FITS file
    :return:
    """

    try:
        unprocessed_file = UnprocessedUpload.objects.get(uuid=uuid)
    except (ObjectDoesNotExist, ValidationError):
        raise Http404

    if request.method == "POST":
        # make changes to the file
        form = HeaderForm(request.POST)
        if form.is_valid():
            inhdulist = fits.get_hdu_list(os.path.join(settings.UPLOAD_DIRECTORY, uuid, unprocessed_file.filename))

            for k in form.cleaned_data.keys():
                inhdulist[0].header[k.replace('_', '-')] = form.cleaned_data[k]

            pyfits.update(os.path.join(settings.UPLOAD_DIRECTORY, uuid, unprocessed_file.filename),
                           inhdulist[0].data, inhdulist[0].header)

            print 'about to redirect'

            return redirect('process_header', uuid=uuid)

        else:
            return render(request, "base_process_headerextra.html", {'form': form})
    else:
        inhdulist = fits.get_hdu_list(
            os.path.join(settings.UPLOAD_DIRECTORY, str(unprocessed_file.uuid), unprocessed_file.filename))

        header = inhdulist[0].header

        initial_values = {'EXPTIME': '', 'DATE-OBS': '', 'FILTER': ''}

        # Add initial values to the form, if they exist in the header (and its likely that at least one won't)
        for k in initial_values.keys():
            try:
                # We replace here as we can't use hyphens in Python variable names
                initial_values[k.replace('-', '_')] = header[k]
            except KeyError:
                initial_values[k.replace('-', '_')] = ''

        form = HeaderForm(initial=initial_values)

        return render(request, "base_process_headerextra.html", {'form': form})


@login_required
def process_observation(request):
    """
    Let the user enter the details of their observation
    :param request:
    :return:
    """
    file_id = request.GET.get('file_id')

    fits_file = get_object_or_404(FITSFile, pk=file_id)

    if fits_file.uploaded_by != request.user:
        raise PermissionDenied

    if fits_file.process_status != 'HEADER':
        return render(request, "base_process_ooo.html")

    if request.method == "POST":
        form = ObservationForm(request.POST)
        if form.is_valid():
            obs = form.save(commit=False)
            obs.user = request.user
            obs.fits = fits_file

            h = json.loads(fits_file.header)

            obs.time = h['DATE-OBS']
            obs.filter = h['FILTER']
            obs.save()

            fits_file.process_status = 'OBSERVATION'
            fits_file.save()

            return redirect('process')
        else:
            return render(request, "base_process_observation.html", {'form': form, 'file_id': file_id})
    else:
        form = ObservationForm(user=request.user)

        return render(request, "base_process_observation.html", {'form': form, 'file_id': file_id})


@login_required
def process_astrometry(request):
    """
    Run the astrometry process for a particular file based on its ID
    :param request:
    :return:
    """

    file_id = request.GET.get('file_id')

    fits_file = get_object_or_404(FITSFile, pk=file_id)

    if fits_file.process_status != 'OBSERVATION':
        return render(request, "base_process_ooo.html")

    if request.user != fits_file.uploaded_by:
        raise PermissionDenied

    # Run the astrometry process for the file
    astrometry.do_astrometry(os.path.join(settings.FITS_DIRECTORY, str(fits_file.id), fits_file.fits_filename),
                             str(fits_file.id))

    fits_file.process_status = 'ASTROMETRY'

    fits_file.save()

    return redirect('process')


@login_required
def process_photometry(request):
    """
    Run the photometry prpcess for a particular file based on its ID
    :param request:
    :return:
    """

    file_id = request.GET.get('file_id')

    fits_file = get_object_or_404(FITSFile, pk=file_id)

    if fits_file.process_status != 'ASTROMETRY':
        return render(request, "base_process_ooo.html")

    if request.user != fits_file.uploaded_by:
        raise PermissionDenied

    photometry.do_photometry(fits_file.fits_filename, fits_file.id)

    fits_file.catalogue_filename = fits_file.fits_filename + '.cat'

    fits_file.process_status = 'PHOTOMETRY'

    fits_file.save()

    return redirect('process')


@login_required
def process_calibration(request):
    """
    Run the calibration for a particular file based on its ID
    :param request:
    :return:
    """

    file_id = request.GET.get('file_id')

    fits_file = get_object_or_404(FITSFile, pk=file_id)

    if request.user != fits_file.uploaded_by:
        raise PermissionDenied

    if fits_file.process_status != 'PHOTOMETRY':
        return render(request, "base_process_ooo.html")

    calibration.do_calibration(file_id)

    fits_file.process_status = 'COMPLETE'

    fits_file.save()

    return redirect('process')


@login_required
@permission_required('is_staff', raise_exception=True)  # Only let staff users add objects
def add_object(request):
    """
    Add a new object/target to the database (as long as the user is 'staff') with its catalog
    :param request:
    :return:
    """

    if request.method == "POST":
        form = ObjectForm(request.POST)
        # Check the user has specified a catalog file and the rest of the form is valid
        if ('catfile' in request.FILES) and (form.is_valid()):
            cat_file = request.FILES.get('catfile')
            if not os.path.exists(os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(form.cleaned_data['number']))):
                path = os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(form.cleaned_data['number']) + '.cat')
                with open(path, 'w') as f:
                    f.write(cat_file.read())
                    f.close()
                form.save()
                newform = ObjectForm()
                return render(request, "base_add_object.html", {'form': newform})
            else:
                return render(request, "base_add_object.html", {'form': form})
        else:
            return render(request, "base_add_object.html", {'form': form})
    else:
        form = ObjectForm()

        return render(request, "base_add_object.html", {'form': form})


@login_required
def add_device(request):
    """
    Add a new imaging device
    :param request:
    :return:
    """
    if request.method == "POST":
        form = ImagingDeviceForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            device.user = request.user
            device.save()
        else:
            return render(request, "base_add_device.html", {'form': form})
    else:
        form = ImagingDeviceForm()

        return render(request, "base_add_device.html", {'form': form})


@login_required
@permission_required('is_staff', raise_exception=True)  # Only let staff users add objects
def modify_object(request, id):
    """
    Modify the attributes of a given object
    :param request:
    :param id: The ID of the object
    :return:
    """
    object = get_object_or_404(Object, pk=id)

    if request.method == "POST":
        form = ObjectForm(request.POST, instance=object)
        if form.is_valid():
            form.save()
        else:
            return render(request, "base_add_object.html", {'form': form})
    else:
        form = ObjectForm(instance=object)

        return render(request, "base_add_object.html", {'form': form})


@login_required
def modify_device(request, id):
    """
    Modify the attributes of a given device
    :param request:
    :param id: The ID of the device
    :return:
    """
    imaging_device = get_object_or_404(ImagingDevice, pk=id)

    if imaging_device.user != request.user:
        raise PermissionDenied

    if request.method == "POST":
        form = ImagingDeviceForm(request.POST, instance=imaging_device)
        if form.is_valid():
            form.save()
        else:
            return render(request, "base_add_device.html", {'form': form})
    else:
        form = ImagingDeviceForm(instance=imaging_device)

        return render(request, "base_add_object.html", {'form': form})


@login_required
def accounts_profile(request):
    """
    User profile page
    :param request:
    :return:
    """

    devices = ImagingDevice.objects.filter(user=request.user)
    processed_files = FITSFile.objects.filter(uploaded_by=request.user).filter(process_status='COMPLETE')

    return render(request, "base_accounts_profile.html", {'devices': devices, 'processed_files': processed_files})


@login_required
def objects(request):
    """
    List of all objects that can be chosen
    :param request:
    :return:
    """

    objects = Object.objects.all()

    return render(request, "base_objects.html", {'objects': objects})


class UploadView(View):
    """ View which will handle all upload requests sent by Fine Uploader.

    Handles POST and DELETE requests.

    This view was created by FineUploader, modified by Will Furnell
    """

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super(UploadView, self).dispatch(*args, **kwargs)

    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        """A POST request. Validate the form and then handle the upload
        based ont the POSTed data. Does not handle extra parameters yet.
        """
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            if upload.handle_upload(request.FILES['qqfile'], form.cleaned_data, request):
                return upload.make_response(content=json.dumps({'success': True}))
            else:
                return upload.make_response(status=400,
                                            content=json.dumps({
                                               'success': False,
                                               'error': 'Invalid file'
                                           }))
        else:
            return upload.make_response(status=400,
                                        content=json.dumps({
                    'success': False,
                    'error': '%s' % repr(form.errors)
                }))

