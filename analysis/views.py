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
from django.db.models import Q
from forms import *
from models import *
from utils import fits, upload, astrometry, photometry, calibration, general
import pyfits
from astropy.time import Time


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
    files = FITSFile.objects.filter(uploaded_by=request.user).exclude(process_status='COMPLETE').order_by('upload_time')

    return render(request, "base_process.html", {'files': files})


@login_required
def process_observation(request, file_id):
    """
    Let the user enter the details of their observation
    :param request:
    :return:
    """

    # See if this FITS file actually exists in our database
    try:
        fits_file = FITSFile.objects.get(pk=file_id)
    except (ObjectDoesNotExist, ValueError):
        raise Http404

    if fits_file.uploaded_by != request.user:
        raise PermissionDenied

    # Let the user sort out their header cards for the device they are using if they go here
    # (We don't want a seperate header cards button when this will be a rare thing)
    if fits_file.process_status == 'DEVICESETUP':
        redirect('process_devicesetup', file_id=file_id)

    if fits_file.process_status != 'UPLOADED':
        return render(request, "base_process_ooo.html")

    if request.method == "POST":
        form = ObservationForm(request.POST)
        if form.is_valid():
            obs = form.save(commit=False)
            obs.user = request.user
            obs.fits = fits_file
            obs.save()

            fits_file.process_status = 'OBSERVATION'
            fits_file.save()

            observations = Observation.objects.filter(device=form.cleaned_data['device'])

            if len(observations) > 1:
                return redirect('process')
            else:
                fits_file.process_status = 'DEVICESETUP'
                fits_file.save()
                return redirect('process_devicesetup', file_id=file_id)
        else:
            return render(request, "base_process_observation.html", {'form': form, 'file_id': file_id})
    else:
        form = ObservationForm()
        form.fields['device'].queryset = ImagingDevice.objects.filter(user=request.user)

        return render(request, "base_process_observation.html", {'form': form, 'file_id': file_id})


@login_required
def process_devicesetup(request, file_id):
    """
    Let the user set up some header card settings for the device if they haven't done it before
    :param request:
    :param device_id: The ID of the device
    :param file_id: The ID of the file we are working on
    :return:
    """

    fits_file = get_object_or_404(FITSFile, pk=file_id)

    if fits_file.uploaded_by != request.user:
        raise PermissionDenied

    if fits_file.process_status != 'DEVICESETUP':
        return render(request, "base_process_ooo.html")

    # Get the observation corresponding to our FITS file
    observation = get_object_or_404(Observation, fits=fits_file)

    observations = Observation.objects.filter(device=observation.device)

    device = observation.device

    if len(observations) > 1:
        # In case the user decides to close their browser and use another file for device setup, then we need to free
        # this one from being used in the device setup stage
        fits_file.process_status = 'OBSERVATION'
        fits_file.save()
        return redirect('process')

    if request.method == 'POST':
        form = HeaderKeyChoiceForm(request.POST)
        device.filter_card = form.data['filter']
        device.date_card = form.data['date']
        device.exptime_card = form.data['exposure_time']
        device.date_format = form.data['date_format']
        device.save()

        # Okay now we can make it look like we've finished sorting out the observation
        fits_file.process_status = 'OBSERVATION'
        fits_file.save()

        return redirect('process')

    hdulist = fits.get_hdu_list(os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid),
                                             fits_file.fits_filename))

    form = HeaderKeyChoiceForm()
    hdulist[0].header['NONE'] = 'NONE'
    # Set up the choices of all the header keys. These need to be in a tuple :(
    choices = tuple(zip(hdulist[0].header.keys(), hdulist[0].header.keys()))

    # The form by default has no values for the choices, so add them here
    form.fields['date'].choices = choices
    form.fields['filter'].choices = choices
    form.fields['exposure_time'].choices = choices

    return render(request, "base_process_devicesetup.html", {'form': form})


@login_required
def process_header(request, file_id):
    """
    Lets the user check the header information in a given file, based on UUID
    User has the option to delete the file, if the header is not correct, or
    to proceed onto the next stage.

    Also checks if a file has already been uploaded by checking SHA256 hashes. Note: This checks the original hash
    from upload and not from the current file which may have been modified by the platform, and therefore have a
    different hash.

    :param uuid: The UUID of the file to check
    :return:
    """

    fits_file = get_object_or_404(FITSFile, pk=file_id)

    if not request.user == fits_file.uploaded_by:
        raise PermissionDenied

    if request.method == "POST":

        if request.POST.get('delete') == "true":
            upload.handle_deleted_file(str(fits_file.uuid))
            observation = Observation.objects.get(fits=fits_file)
            observation.delete()
            fits_file.delete()

            return redirect('home')
        else:
            # Need to set some information for the observation
            # First lets check that the user has permission to work with this file

            inhdulist = fits.get_hdu_list(
                os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid), fits_file.fits_filename))

            observation = Observation.objects.get(fits=fits_file)
            device = observation.device

            # Convert whatever format the date is in the header to Julian
            date = Time(inhdulist[0].header[device.date_card])
            observation.date = date.jd

            observation.exptime = inhdulist[0].header[device.exptime_card]
            observation.filter = inhdulist[0].header[device.filter_card]

            general.process_header_db(inhdulist, fits_file)
            return redirect('process')

    # Only users of the file can process the header
    if fits_file.uploaded_by != request.user:
        raise PermissionDenied

    fits_hashes = FITSFile.objects.values('sha256').exclude(id=fits_file.id)

    # Check if the file already exists on the system, and if it does, don't let the user go any furthur
    # (make them delete the file)
    if fits_file.sha256 in fits_hashes:
       return render(request, "base_process_duplicate.html", {'fits_file': fits_file})

    hdulist = fits.get_hdu_list(os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid),
                                             fits_file.fits_filename))

    header_text = repr(hdulist[0].header)

    observation = Observation.objects.get(fits=fits_file)
    device = observation.device

    valid = True

    try:
        dateval = hdulist[0].header[device.date_card]
    except KeyError:
        # If the user chose NONE for the card, then we'll just put nothing here, and force them to change it
        valid = False
        dateval = ''
    try:
        exptimeval = hdulist[0].header[device.exptime_card]
    except KeyError:
        # If the user chose NONE for the card, then we'll just put nothing here, and force them to change it
        valid = False
        exptimeval = ''

    try:
        filterval = hdulist[0].header[device.filter_card]
    except KeyError:
        # If the user chose NONE for the card, then we'll just put nothing here, and force them to change it
        valid = False
        filterval = ''

    return render(request, "base_process_header.html", {'header': header_text, 'file_id': file_id, 'device': device,
                                                        'date': dateval, 'exptime': exptimeval, 'filter': filterval,
                                                        'valid': valid})


def process_header_modify(request, file_id):
    """
    Modify (or ideally add) the required header cards to the FITS file so we'll be able to analyse it
    :param request:
    :param uuid: The UUID of the FITS file
    :return:
    """

    # See if this FITS file actually exists in our database
    fits_file = get_object_or_404(FITSFile, pk=file_id)

    if not request.user == fits_file.uploaded_by:
        raise PermissionDenied

    if request.method == "POST":
        # make changes to the file
        form = HeaderForm(request.POST)
        if form.is_valid():
            # Need to set some information for the observation
            # First lets check that the user has permission to work with this file

            observation = Observation.objects.get(fits=fits_file)

            # Convert whatever format the date is in the header to Julian
            date = Time(form.cleaned_data['date'])
            observation.date = date.jd

            observation.exptime = form.cleaned_data['exptime']
            observation.filter = form.cleaned_data['filter']

            inhdulist = fits.get_hdu_list(
                os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid), fits_file.fits_filename))

            general.process_header_db(inhdulist, fits_file)
            return redirect('process')
        else:
            return render(request, "base_process_header_modify.html", {'form': form})
    else:
        initial_values = {'exptime': request.GET.get('exptime'), 'date': request.GET.get('date'),
                          'filter': request.GET.get('filter')}

        form = HeaderForm(initial=initial_values)

        return render(request, "base_process_header_modify.html", {'form': form})


@login_required
def process_astrometry(request, file_id):
    """
    Run the astrometry process for a particular file based on its ID
    :param request:
    :param file_id: The ID of the file we are processing
    :return:
    """

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
            shutil.rmtree(os.path.join(settings.ASTROMETRY_WORKING_DIRECTORY, str(fits_file.id)))
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
def process_photometry(request, file_id):
    """
    Run the photometry prpcess for a particular file based on its ID
    :param request:
    :param file_id: The ID of the file we are processing
    :return:
    """

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
def process_calibration(request, file_id):
    """
    Run the calibration for a particular file based on its ID
    :param request:
    :param file_id: The ID of the file we are processing
    :return:
    """

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
        form = RedoCalibrationForm()
        return render(request, "base_process_calibration.html", {'file': fits_file, 'form': form})

    if fits_file.process_status != 'PHOTOMETRY':
        return render(request, "base_process_ooo.html")

    # Run the calibration process for this file
    calibration.do_calibration(file_id, min_use=0, max_use=0)

    fits_file.process_status = 'CHECK_CALIBRATION'

    fits_file.save()

    form = RedoCalibrationForm()
    return render(request, "base_process_calibration.html", {'file': fits_file, 'form': form})


@login_required
def process_calibration_retry(request, file_id):
    """
    Let the user re-try the calibration with different min and max values
    :param request:
    :param file_id: The ID of the file we are recalibrating
    :return:
    """

    # See if this FITS file actually exists in our database
    try:
        fits_file = FITSFile.objects.get(pk=file_id)
    except (ObjectDoesNotExist, ValueError):
        raise Http404

    if request.user != fits_file.uploaded_by:
        raise PermissionDenied

    if fits_file.process_status == 'CHECK_CALIBRATION' and request.method == "POST" and \
                    request.user == fits_file.uploaded_by:
        # User is giving us some parameters to retry the calibration with.
        form = RedoCalibrationForm(request.POST)

        if form.is_valid():

            # Get rid of the earlier graph
            if os.path.exists(os.path.join(settings.PLOTS_DIRECTORY, str(fits_file.id))):
                shutil.rmtree(os.path.join(settings.PLOTS_DIRECTORY, str(fits_file.id)))

            observation = Observation.objects.get(fits=fits_file)
            Photometry.objects.filter(observation=observation).delete()

            calibration.do_calibration(file_id, max_use=form.cleaned_data['max_use'],
                                       min_use=form.cleaned_data['min_use'])

            fits_file.process_status = 'CHECK_CALIBRATION'

            fits_file.save()

            return render(request, "base_process_calibration.html", {'file': fits_file, 'form': form})
        else:
            return render(request, "base_process_calibration.html", {'file': fits_file, 'form': form})
    else:
        return redirect('process_calibration', file_id=file_id)


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

        # Make sure only the user who uploaded it or staff can delete it
        if (fits_file.uploaded_by != request.user) and (not request.user.is_staff):
            raise PermissionDenied

        try:
            observation = Observation.objects.get(fits=fits_file)
            Photometry.objects.filter(observation=observation).delete()
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
    # Get all the files that have been processed by a user, but only if they have been completed successfully or failed
    processed_files = FITSFile.objects.filter(uploaded_by=request.user)\
        .filter(Q(process_status='COMPLETE') | Q(process_status='FAILED') | Q(process_status='FAILED_USER'))\
        .order_by('-upload_time')

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
