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

from forms import UploadFileForm, ObjectForm, ObservationForm
from models import *
from utils import fits, upload, astrometry, photometry, calibration


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
        'NAXIS1', 'NAXIS2', 'OBJCTRA', 'OBJCTDEC', 'EXPTIME', 'FILTER', 'IMAGETYP', 'JD', 'PIERSIDE', 'DATE-OBS'
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

            header = FITSHeader()

            # Iterate through all the header values and add these to the database
            for key, value in zip(inhdulist[0].header.keys(), inhdulist[0].header.values()):
                # We have to replace the - in the keys because it's not supported by Python or the database.
                # All keys are also lowercase in the model.
                setattr(header, key.lower().replace("-", "_"), value)

            header.save()

            fits_file = FITSFile()

            fits_file.header = header
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
            obs.time = fits_file.header.date_obs
            obs.filter = fits_file.header.filter
            obs.save()

            fits_file.process_status = 'OBSERVATION'
            fits_file.save()

            return redirect('process')
        else:
            return render(request, "base_process_observation.html", {'form': form, 'file_id': file_id})
    else:
        form = ObservationForm()

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

