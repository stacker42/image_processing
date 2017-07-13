# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import shutil
import os
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.decorators import method_decorator
from django.core.exceptions import ObjectDoesNotExist, ValidationError, PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import Http404
from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from forms import UploadFileForm, ObjectForm, ObservationForm, HeaderForm, ImagingDeviceForm
from models import *
from utils import fits, upload, astrometry, photometry, calibration
import pyfits
from django.db.models import Q


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
    unprocessed = UnprocessedUpload.objects.filter(user=request.user).order_by('upload_time')
    files = FITSFile.objects.filter(uploaded_by=request.user).exclude(process_status='COMPLETE').order_by('upload_time')

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
        'EXPTIME', 'FILTER', 'DATE-OBS'
    ]

    if request.method == "POST":
        # See if this FITS file actually exists in our database
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

    # See if this FITS file actually exists in our database
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

    # See if this FITS file actually exists in our database
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

    # See if this FITS file actually exists in our database
    try:
        fits_file = FITSFile.objects.get(pk=file_id)
    except (ObjectDoesNotExist, ValueError):
        raise Http404

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
        form = ObservationForm()
        form.fields['device'].queryset = ImagingDevice.objects.filter(user=request.user)

        return render(request, "base_process_observation.html", {'form': form, 'file_id': file_id})


@login_required
def process_astrometry(request):
    """
    Run the astrometry process for a particular file based on its ID
    :param request:
    :return:
    """

    file_id = request.GET.get('file_id')

    # See if this FITS file actually exists in our database
    try:
        fits_file = FITSFile.objects.get(pk=file_id)
    except (ObjectDoesNotExist, ValueError):
        raise Http404

    if fits_file.process_status == 'CHECK_ASTROMETRY' and request.method == "POST" and \
                    request.user == fits_file.uploaded_by:
        # The results of the user choice whether the action was successful or not.

        # They say it was successful!
        if request.POST.get('correct') == 'true':
            fits_file.process_status = 'ASTROMETRY'
            fits_file.save()
            return redirect('process')
        else:
            # They say it wasn't successful, so set the status to failed on user command
            fits_file.process_status = 'FAILED_USER'
            fits_file.save()
            return redirect('process')

    if fits_file.process_status == 'CHECK_ASTROMETRY':
        return render(request, "base_process_astrometry.html", {'file': fits_file})

    if fits_file.process_status != 'OBSERVATION':
        return render(request, "base_process_ooo.html")

    if request.user != fits_file.uploaded_by:
        raise PermissionDenied

    # Run the astrometry process for the file
    astrometry.do_astrometry(os.path.join(settings.FITS_DIRECTORY, str(fits_file.id), fits_file.fits_filename),
                             str(fits_file.id))

    fits_file.process_status = 'CHECK_ASTROMETRY'

    fits_file.save()

    return render(request, "base_process_astrometry.html", {'file': fits_file})


@login_required
def process_photometry(request):
    """
    Run the photometry prpcess for a particular file based on its ID
    :param request:
    :return:
    """

    file_id = request.GET.get('file_id')

    # See if this FITS file actually exists in our database
    try:
        fits_file = FITSFile.objects.get(pk=file_id)
    except (ObjectDoesNotExist, ValueError):
        raise Http404

    if fits_file.process_status != 'ASTROMETRY':
        return render(request, "base_process_ooo.html")

    if request.user != fits_file.uploaded_by:
        raise PermissionDenied

    # Run the photometry process for this file
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

    # See if this FITS file actually exists in our database
    try:
        fits_file = FITSFile.objects.get(pk=file_id)
    except (ObjectDoesNotExist, ValueError):
        raise Http404

    if request.user != fits_file.uploaded_by:
        raise PermissionDenied

    if fits_file.process_status == 'CHECK_CALIBRATION' and request.method == "POST" and \
                    request.user == fits_file.uploaded_by:
        # The results of the users choice whether the action was successful or not.
        # The action was successful!
        if request.POST.get('correct') == 'true':
            fits_file.process_status = 'COMPLETE'
            fits_file.save()
            return redirect('process')
        else:
            # Set the action to have failed, by user command
            fits_file.process_status = 'FAILED_USER'
            fits_file.save()
            return redirect('process')

    if fits_file.process_status == 'CHECK_CALIBRATION':
        return render(request, "base_process_calibration.html", {'file': fits_file})

    if fits_file.process_status != 'PHOTOMETRY':
        return render(request, "base_process_ooo.html")

    # Run the calibration process for this file
    calibration.do_calibration(file_id)

    fits_file.process_status = 'CHECK_CALIBRATION'

    fits_file.save()

    return render(request, "base_process_calibration.html", {'file': fits_file})


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
                # Write the catalog file to disk under the new name
                with open(path, 'w') as f:
                    f.write(cat_file.read())
                    f.close()
                form.save()
                # Give the user a fresh form
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
            return redirect('accounts_profile')
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
    try:
        object = Object.objects.get(pk=id)
    except (ObjectDoesNotExist, ValueError):
        raise Http404

    if request.method == "POST":
        form = ObjectForm(request.POST, instance=object)
        if form.is_valid():
            form.save()
            return redirect('objects')
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
            return redirect('accounts_profile')
        else:
            return render(request, "base_add_device.html", {'form': form})
    else:
        form = ImagingDeviceForm(instance=imaging_device)

        return render(request, "base_add_device.html", {'form': form})


@login_required
@permission_required('is_staff', raise_exception=True)
def manage_files(request):
    """
    Let administrators manage all uploads that have been made, and delete them/look at them if they have failed
    :param request:
    :return:
    """

    files_list = FITSFile.objects.all().order_by('upload_time').reverse()

    paginator = Paginator(files_list, 100)  # Show 25 contacts per page

    page = request.GET.get('page')
    try:
        files = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        files = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        files = paginator.page(paginator.num_pages)

    return render(request, "base_manage_files.html", {'files': files})

@login_required
def delete_file(request, file_id):
    """
    Let administrators delete any file, or users delete one of their own files. Will remove all information relating to
    it on disk and database
    :param request:
    :param file_id: The ID of the file
    :return:
    """

    if request.method == "POST":

        fits_file = get_object_or_404(FITSFile, pk=file_id)

        if (fits_file.uploaded_by != request.user) and (not request.user.is_staff):
            raise PermissionDenied

        try:
            observation = Observation.objects.get(fits=fits_file)
            photometry_objs = Photometry.objects.filter(observation=observation)
            for photometry in photometry_objs:
                photometry.delete()

            observation.delete()
        except ObjectDoesNotExist:
            pass  # We don't care if they don't exist, we're deleting them anyway

        # Remove all folders we drop during analysis
        if os.path.exists(os.path.join(settings.CATALOGUE_DIRECTORY, str(fits_file.id))):
            shutil.rmtree(os.path.join(settings.CATALOGUE_DIRECTORY, str(fits_file.id)))

        if os.path.exists(os.path.join(settings.FITS_DIRECTORY, str(fits_file.id))):
            shutil.rmtree(os.path.join(settings.FITS_DIRECTORY, str(fits_file.id)))

        if os.path.exists(os.path.join(settings.PLOTS_DIRECTORY, str(fits_file.id))):
            shutil.rmtree(os.path.join(settings.PLOTS_DIRECTORY, str(fits_file.id)))

        if os.path.exists(os.path.join(settings.ASTROMETRY_WORKING_DIRECTORY, str(fits_file.id))):
            shutil.rmtree(os.path.join(settings.ASTROMETRY_WORKING_DIRECTORY, str(fits_file.id)))

        # Finally, delete the file from the DB
        fits_file.delete()

        return render(request, "base_delete_file.html")
    else:
        # We don't want users to go directly to this page, they should have to do it via a POST request so they don't
        # accidentally delete anything
        raise Http404


@login_required
def accounts_profile(request):
    """
    User profile page
    :param request:
    :return:
    """

    devices = ImagingDevice.objects.filter(user=request.user)
    processed_files = FITSFile.objects.filter(uploaded_by=request.user)\
        .filter(Q(process_status='COMPLETE') | Q(process_status='FAILED') | Q(process_status='FAILED_USER'))\
        .order_by('upload_time').reverse()

    paginator = Paginator(processed_files, 100)

    page = request.GET.get('page')
    try:
        processed_files = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        processed_files = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        processed_files = paginator.page(paginator.num_pages)

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


def test(request):

    return render(request, "base_process_astrometry.html")


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

