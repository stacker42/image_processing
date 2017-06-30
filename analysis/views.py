# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import shutil

import os
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, ValidationError, PermissionDenied
from django.http import Http404
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from forms import UploadFileForm
from models import *
from utils import fits, upload, astrometry


@login_required
def home(request):
    """
    Let the user upload files
    :param request:
    :return:
    """
    return render(request, "base_upload.html")


@login_required
def unprocessed_uploads(request):
    """
    Let the user check their list of unprocessed uploads
    :param request:
    :return:
    """
    unprocessed = UnprocessedUpload.objects.filter(user=request.user)
    return render(request, "base_unprocessed.html", {'unprocessed': unprocessed})

@login_required
def process(request):
    """
    Redirect the user to the appropriate processing stage for their file
    :param request:
    :return:
    """
    current_stage = getattr(request.session, 'current_stage')
    if current_stage is 1:
        redirect('process_add', getattr(request.session, 'file_id'))
    elif current_stage is 2:
        redirect('process_astrometry', getattr(request.session, 'file_id'))
    elif current_stage is 3:
        redirect('process_photometry', getattr(request.session, 'file_id'))
    elif current_stage is 4:
        redirect('process_calibration', getattr(request.session, 'file_id'))
    else:
        redirect('home')


@login_required
def process_header(request, uuid):
    """
    Lets the user check the header information in a given file, based on UUID
    User has the option to delete the file, if the header is not correct, or
    to proceed onto the next stage
    :param uuid: The UUID of the file to check
    :return:
    """

    if request.method == "POST":
        # User wants to delete the file
        try:
            file = UnprocessedUpload.objects.get(uuid=uuid)
        except (ObjectDoesNotExist, ValidationError):
            raise Http404

        # Don't let other users delete files they didn't upload!
        if file.user == request.user:
            file.delete()
            upload.handle_deleted_file(str(uuid))

            return redirect('unprocessed_uploads')
        else:
            raise PermissionDenied

    try:
        file = UnprocessedUpload.objects.get(uuid=uuid)
    except (ObjectDoesNotExist, ValidationError):
        raise Http404

    # Only users of the file can process the header
    if file.user != request.user:
        raise PermissionDenied

    header = fits.get_header(os.path.join(settings.UPLOAD_DIRECTORY, str(file.uuid), file.filename))

    # Set the users current stage in processing their file
    request.session['current_stage'] = 1
    request.session['file_id'] = str(file.uuid)

    return render(request, "base_process_header.html", {'header': header, 'uuid': str(file.uuid)})


@login_required
def process_add(request, uuid):
    """
    Add a file and its header information to the database, now we know it's valid
    :param request:
    :param uuid: The UUID of the temporary file
    :return:
    """

    try:
        unprocessed_file = UnprocessedUpload.objects.get(uuid=uuid)
    except (ObjectDoesNotExist, ValidationError):
        raise Http404

    # First lets check that the user has permission to work with this file
    if not request.user == unprocessed_file.user:
        raise PermissionDenied

    inhdulist = fits.get_hdu_list(os.path.join(settings.UPLOAD_DIRECTORY, str(unprocessed_file.uuid), unprocessed_file.filename))

    header = FITSHeader()

    # Iterate through all the header values and add these to the database
    for key, value in zip(inhdulist[0].header.keys(), inhdulist[0].header.values()):
        # We have to replace the - in the keys becuase it's not supported by Python or the database.
        # All keys are also lowercase in the model.
        setattr(header, key.lower().replace("-", "_"), value)

    header.save()

    # Set up a meta object. We're just going to leave these values blank at the moment until we know the locations
    meta = FITSMeta()

    meta.fits_filename = ''
    meta.catalog_filename = ''
    meta.uploaded_by = unprocessed_file.user
    meta.upload_time = unprocessed_file.upload_time
    meta.process_stage = 2

    meta.save()

    fits_file = FITSFile()

    fits_file.header = header
    fits_file.meta = meta

    fits_file.save()

    # Make a new directory for the file and put it into this new directory.
    os.mkdir(os.path.join(settings.FITS_DIRECTORY, str(fits_file.id)))
    shutil.move(os.path.join(settings.UPLOAD_DIRECTORY, str(unprocessed_file.uuid), unprocessed_file.filename), os.path.join(settings.FITS_DIRECTORY, str(fits_file.id), unprocessed_file.filename))
    upload.handle_deleted_file(str(unprocessed_file.uuid))

    meta.fits_filename = unprocessed_file.filename

    meta.save()

    # Seeing as we don't need the reference to the unprocessed file any more, delete it.
    unprocessed_file.delete()

    # Set the current stage of the processing
    fits_file.meta.process_stage = 2

    fits_file.meta.save()

    return render(request, "base_process_progress.html", {'next_stage': 'process_astrometry', 'file_id': fits_file.id})


@login_required
def process_astrometry(request, file_id):
    """
    Run the astrometry process for a particular file based on its ID
    :param request:
    :param file_id: The ID of the file to process
    :return:
    """
    try:
        fits_file = FITSFile.objects.get(pk=file_id)
    except ObjectDoesNotExist:
        raise Http404

    if fits_file.meta.process_stage > 2:
        render(request, "base_process_already.html")

    if request.user.id is not fits_file.meta.uploaded_by.id:
        raise PermissionDenied

    # Run the astrometry process for the file
    astrometry.do_astrometry(os.path.join(settings.FITS_DIRECTORY, str(fits_file.id), fits_file.meta.fits_filename), str(fits_file.id))

    return render(request, "base_process_message.html")


@login_required
def process_photomertry(request, file_id):
    """
    Run the photometry prpcess for a particular file based on its ID
    :param request:
    :param file_id: The ID of the file to process
    :return:
    """
    if request.session['current_stage'] is not 3:
        redirect('process')

    request.session['current_stage'] = 4


class UploadView(View):
    """ View which will handle all upload requests sent by Fine Uploader.
    See: https://docs.djangoproject.com/en/dev/topics/security/#user-uploaded-content-security

    Handles POST and DELETE requests.

    This view was created by FineUploader.
    """

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super(UploadView, self).dispatch(*args, **kwargs)

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

    def delete(self, request, *args, **kwargs):
        """A DELETE request. If found, deletes a file with the corresponding
        UUID from the server's filesystem.
        """
        qquuid = kwargs.get('qquuid', '')
        if qquuid:
            try:
                upload.handle_deleted_file(qquuid)
                return upload.make_response(content=json.dumps({'success': True}))
            except Exception, e:
                return upload.make_response(status=400,
                                            content=json.dumps({
                        'success': False,
                        'error': '%s' % repr(e)
                    }))
        return upload.make_response(status=404,
                                    content=json.dumps({
                'success': False,
                'error': 'File not present'
            }))

