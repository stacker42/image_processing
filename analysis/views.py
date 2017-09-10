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

    if not request.user.is_staff:
        files_list = FITSFile.objects.filter(uploaded_by=request.user).filter(~Q(process_status='COMPLETE') &
                                                                         ~Q(process_status='FAILED') &
                                                                         ~Q(process_status='FAILED_USER')
                                                                         ).order_by('upload_time')
    else:
        files_list = FITSFile.objects.filter(~Q(process_status='COMPLETE') &
                                        ~Q(process_status='FAILED') &
                                        ~Q(process_status='FAILED_USER')
                                        ).order_by('upload_time')

    paginator = Paginator(files_list, 100)

    page = request.GET.get('page')
    try:
        files = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        files = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        files = paginator.page(paginator.num_pages)

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

    if (fits_file.uploaded_by != request.user) and (not request.user.is_staff):
        raise PermissionDenied

    print fits_file.process_status

    # Let the user sort out their header cards for the device they are using if they go here
    # (We don't want a seperate header cards button when this will be a rare thing)
    if fits_file.process_status == 'DEVICESETUP':
        return redirect('process_devicesetup', file_id=file_id)

    if fits_file.process_status != 'UPLOADED':
        return render(request, "base_process_ooo.html")

    if request.method == "POST":
        form = ObservationForm(request.POST)
        if form.is_valid():
            obs = form.save(commit=False)  # Don't save object to DB just yet... we need to add more info
            obs.user = fits_file.uploaded_by
            obs.fits = fits_file
            obs.save()

            fits_file.process_status = 'OBSERVATION'
            fits_file.save()

            observations_count = Observation.objects.filter(device=form.cleaned_data['device']).count()

            # If more than one observation has been made with this device, then go to the next stage
            if observations_count > 1:
                return redirect('process')
            else:
                # Otherwise... we need to set up some header cards for the device
                fits_file.process_status = 'DEVICESETUP'
                fits_file.save()
                return redirect('process_devicesetup', file_id=file_id)
        else:
            return render(request, "base_process_observation.html", {'form': form, 'file_id': file_id})
    else:
        form = ObservationForm()
        if not request.user.is_staff:
            form.fields['device'].queryset = ImagingDevice.objects.filter(user=request.user)
        else:
            form.fields['device'].queryset = ImagingDevice.objects.all()

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

    if (fits_file.uploaded_by != request.user) and (not request.user.is_staff):
        raise PermissionDenied

    if fits_file.process_status != 'DEVICESETUP':
        return render(request, "base_process_ooo.html")

    # Get the observation corresponding to our FITS file
    observation = get_object_or_404(Observation, fits=fits_file)

    #observations = Observation.objects.filter(device=observation.device)

    device = observation.device

    # The following is actually problematic and can cause no device setup to take place - so commented out for now
    # if len(observations) > 1:
    #     # In case the user decides to close their browser and use another file for device setup, then we need to free
    #     # this one from being used in the device setup stage
    #     fits_file.process_status = 'OBSERVATION'
    #     fits_file.save()
    #     return redirect('process')

    if request.method == 'POST':
        form = MetadataKeyChoiceForm(request.POST)
        # Get the cards that they chose from the form and put them in the database for this particular device
        device.filter_card = form.data['filter']
        device.date_card = form.data['date']
        device.exptime_card = form.data['exposure_time']
        device.date_format = form.data['date_format']
        # Only actually add a time card if they chose date and time seperated
        if form.data['date_format'] == 'DATETIMESEP':
                device.time_card = form.data['time']
        device.save()

        # Okay now we can make it look like we've finished sorting out the observation
        fits_file.process_status = 'OBSERVATION'
        fits_file.save()

        return redirect('process')

    hdulist = fits.get_hdu_list(os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid),
                                             fits_file.fits_filename))

    form = MetadataKeyChoiceForm()
    # Add a NONE key to the header so it presents as one of the choices for users.
    # (We don't add it to the actual header)
    hdulist[0].header['NONE'] = 'NONE'
    # Set up the choices of all the header keys. These need to be in a tuple :(
    choices = tuple(zip(hdulist[0].header.keys(), hdulist[0].header.keys()))

    # The form by default has no values for the choices, so add them here
    form.fields['date'].choices = choices
    form.fields['time'].choices = choices
    form.fields['filter'].choices = choices
    form.fields['exposure_time'].choices = choices

    return render(request, "base_process_devicesetup.html", {'form': form})


@login_required
def process_metadata(request, file_id):
    """
    Lets the user check the header information in a given file, based on UUID
    User has the option to delete the file, if the header is not correct, or
    to proceed onto the next stage.

    Also checks if a file has already been uploaded by checking SHA256 hashes. Note: This checks the original hash
    from upload and not from the current file which may have been modified by the platform, and therefore have a
    different hash.

    :param file_id: The ID of the file to check
    :return:
    """

    fits_file = get_object_or_404(FITSFile, pk=file_id)

    if (fits_file.uploaded_by != request.user) and (not request.user.is_staff):
        raise PermissionDenied

    if request.method == "POST":

        if request.POST.get('delete') == "true":
            # User has requested to delete the FITS file, so we will do so
            upload.handle_deleted_file(str(fits_file.uuid))
            observation = Observation.objects.get(fits=fits_file)
            observation.delete()
            fits_file.delete()

            return redirect('process')
        else:
            # Need to set some information for the observation
            # First lets check that the user has permission to work with this file

            inhdulist = fits.get_hdu_list(
                os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid), fits_file.fits_filename))

            observation = Observation.objects.get(fits=fits_file)
            device = observation.device

            # Get the filter we actually want to use from the form thats submitted. Don't bother with whats in the
            # header now, we know its something we can support. Narrow down the option.
            observation.filter = request.POST.get('used_filter')

            if device.date_format == 'MJD':
                date = inhdulist[0].header[device.date_card] + 2400000.5
            elif device.date_format == 'JD':
                date = inhdulist[0].header[device.date_card]
            elif device.date_format == 'DATETIME':
                date = Time(inhdulist[0].header[device.date_card]).jd
            elif device.date_format == 'DATETIMESEP':
                time = inhdulist[0].header[device.time_card]
                date = inhdulist[0].header[device.date_card]
                date = Time(date + "T" + time).jd

            # Convert whatever format the date is in the header to Julian and store this
            observation.date = float(date)

            observation.exptime = inhdulist[0].header[device.exptime_card]

            observation.orignal_filter = inhdulist[0].header[device.filter_card]

            observation.save()

            general.process_metadata_db(inhdulist, fits_file, request)

            observation.save()
            return redirect('process')

    if fits_file.process_status != 'OBSERVATION':
        return render(request, "base_process_ooo.html")

    fits_hashes = FITSFile.objects.exclude(id=fits_file.id).values_list('sha256', flat=True)

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
        # Use date card from the device
        dateval = hdulist[0].header[device.date_card]
    except KeyError:
        # If the user chose NONE for the card, then we'll just put nothing here, and force them to change it
        valid = False
        dateval = ''
    try:
        # Use exposure time card from device
        exptimeval = hdulist[0].header[device.exptime_card]
    except KeyError:
        # If the user chose NONE for the card, then we'll just put nothing here, and force them to change it
        valid = False
        exptimeval = ''

    try:
        # Use filter card from device
        filterval = hdulist[0].header[device.filter_card]
    except KeyError:
        # If the user chose NONE for the card, then we'll just put nothing here, and force them to change it
        valid = False
        filterval = ''

    used_filter = general.get_used_filter(filterval)

    found = []
    for f in os.listdir(os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(observation.target.number))):
        if f[3:].strip('.cat') != used_filter:
            found.append(False)
        else:
            found.append(True)

    if True not in found:
        target_supported_filter = False
        valid = False
    else:
        target_supported_filter = True

    if device.time_card is not None:
        try:
            timeval = hdulist[0].header[device.time_card]
        except KeyError:
            valid = False
            timeval = ''
    else:
        timeval = 'N/A'

    return render(request, "base_process_metadata.html", {'header': header_text, 'file_id': file_id, 'device': device,
                                                        'date': dateval, 'exptime': exptimeval, 'filter': filterval,
                                                        'valid': valid, 'time': timeval, 'used_filter': used_filter,
                                                        'all_filters': settings.ALL_FILTERS,
                                                        'target_supported_filter': target_supported_filter})


def process_metadata_modify(request, file_id):
    """
    Modify (or ideally add) the required header cards to the FITS file so we'll be able to analyse it
    :param request:
    :param file_id: The ID of the FITS file
    :return:
    """

    # See if this FITS file actually exists in our database
    fits_file = get_object_or_404(FITSFile, pk=file_id)

    if (request.user != fits_file.uploaded_by) and (not request.user.is_staff):
        raise PermissionDenied

    if request.method == "POST":
        # make changes to the file
        form = MetadataForm(request.POST)
        if form.is_valid():
            # Need to set some information for the observation
            # First lets check that the user has permission to work with this file

            observation = Observation.objects.get(fits=fits_file)

            if form.cleaned_data['date_format'] == 'MJD':
                date = form.cleaned_data['date'] + str(2400000.5)
            elif form.cleaned_data['date_format'] == 'JD':
                date = form.cleaned_data['date']
            elif form.cleaned_data['date_format'] == 'DATETIME':
                date = Time(form.cleaned_data['date']).jd
            elif form.cleaned_data['date_format'] == 'DATETIMESEP':
                time = form.cleaned_data['time']
                date = form.cleaned_data['date']
                date = Time(date + "T" + time).jd

            observation.date = float(date)

            observation.exptime = form.cleaned_data['exptime']

            used_filter = general.get_used_filter(form.cleaned_data['filter'])

            if used_filter is None:
                form.add_error('filter', "You must choose a valid filter")
                return render(request, "base_process_metadata_modify.html", {'form': form})

            found = []
            for f in os.listdir(os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(observation.target.number))):
                if f[3:].replace('.cat', '') != used_filter:
                    found.append(False)
                else:
                    found.append(True)

            if True not in found:
                form.add_error('filter', "You must choose a filter supported by your target")
                return render(request, "base_process_metadata_modify.html", {'form': form})

            observation.filter = used_filter
            observation.orignal_filter = form.cleaned_data['filter']

            inhdulist = fits.get_hdu_list(
                os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid), fits_file.fits_filename))

            observation.save()

            general.process_metadata_db(inhdulist, fits_file, request)

            observation.save()
            return redirect('process')
        else:
            return render(request, "base_process_metadata_modify.html", {'form': form})
    else:
        # The values that we might have grabbed from the header will be in the GET variables. If there's nothing there,
        # then the initial data will just be blank, which is intentional
        initial_values = {'exptime': request.GET.get('exptime'), 'date': request.GET.get('date'),
                          'filter': request.GET.get('filter')}

        form = MetadataForm(initial=initial_values)

        return render(request, "base_process_metadata_modify.html", {'form': form})


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
            (request.user == fits_file.uploaded_by or request.user.is_staff):
        # The results of the user choice whether the action was successful or not.

        # They say it was successful!
        if request.POST.get('correct') == 'true':
            fits_file.process_status = 'ASTROMETRY'
            fits_file.save()
            # Remove temporary astrometry directory
            shutil.rmtree(os.path.join(settings.ASTROMETRY_WORKING_DIRECTORY, str(fits_file.id)))
            return redirect('process')
        else:
            # They say it wasn't successful, so set the status to failed on user command
            fits_file.process_status = 'FAILED_USER'
            fits_file.save()
            return redirect('process')

    if (request.user != fits_file.uploaded_by) and (not request.user.is_staff):
        raise PermissionDenied

    if fits_file.process_status == 'CHECK_ASTROMETRY':
        return render(request, "base_process_astrometry.html", {'file': fits_file})

    if fits_file.process_status != 'METADATA':
        return render(request, "base_process_ooo.html")

    # Run the astrometry process for the file
    if astrometry.do_astrometry(os.path.join(settings.FITS_DIRECTORY, fits_file.fits_filename),
                             str(fits_file.id)):

        # Let the user check whether astrometry was successful
        fits_file.process_status = 'CHECK_ASTROMETRY'
    else:
        # Astrometry failed during execution
        fits_file.process_status = 'FAILED'

    fits_file.save()

    return render(request, "base_process_astrometry.html", {'file': fits_file})


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

    if (request.user != fits_file.uploaded_by) and (not request.user.is_staff):
        raise PermissionDenied

    if fits_file.process_status == 'CHECK_CALIBRATION' and request.method == "POST" and \
            (request.user == fits_file.uploaded_by or request.user.is_staff):
        # The results of the users choice whether the action was successful or not.
        # The action was successful!
        if request.POST.get('correct') == 'true':
            observation = Observation.objects.get(fits=fits_file)
            temp_photometry_objects = TemporaryPhotometry.objects.filter(observation=observation)

            # Using a raw SQL query here
            general.copy_to_photometry(observation.id)

            temp_photometry_objects.delete()
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
        return render(request, "base_process_calibration.html", {'file': fits_file, 'form': form, 'success': True})

    if fits_file.process_status != 'ASTROMETRY':
        return render(request, "base_process_ooo.html")

    # Run the photometry
    photometry.do_photometry(fits_file.fits_filename, file_id)

    fits_file.catalogue_filename = fits_file.fits_filename + '.cat'

    fits_file.save()

    # Run the calibration process for this file
    success, reason = calibration.do_calibration(file_id, min_use=0, max_use=0)

    # Let the user check the results of the calibration
    fits_file.process_status = 'CHECK_CALIBRATION'

    fits_file.save()

    form = RedoCalibrationForm()
    return render(request, "base_process_calibration.html", {'file': fits_file, 'form': form, 'success': success,
                                                             'reason': reason})


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

    if (request.user != fits_file.uploaded_by) and (not request.user.is_staff):
        raise PermissionDenied

    if fits_file.process_status == 'CHECK_CALIBRATION' and request.method == "POST" and \
            (request.user == fits_file.uploaded_by or request.user.is_staff):
        # User is giving us some parameters to retry the calibration with.
        form = RedoCalibrationForm(request.POST)

        if form.is_valid():

            # Get rid of the earlier graph
            if os.path.exists(os.path.join(settings.PLOTS_DIRECTORY, str(fits_file.id))):
                shutil.rmtree(os.path.join(settings.PLOTS_DIRECTORY, str(fits_file.id)))

            observation = Observation.objects.get(fits=fits_file)
            TemporaryPhotometry.objects.filter(observation=observation).delete()

            # Re-do calibration with values that the user has entered
            success, reason = calibration.do_calibration(file_id, max_use=form.cleaned_data['max_use'],
                                       min_use=form.cleaned_data['min_use'])

            fits_file.process_status = 'CHECK_CALIBRATION'

            fits_file.save()

            return render(request, "base_process_calibration.html", {'file': fits_file, 'form': form,
                                                                     'success': success, 'reason': reason})
        else:
            return render(request, "base_process_calibration.html", {'file': fits_file, 'form': form})
    else:
        return redirect('process_calibration', file_id=file_id)


def process_reprocess(request, file_id):
    """
    Allow a user to re-process a file from the beginning (the header check)
    :param request:
    :param file_id: The ID of the file to reprocess
    :return:
    """
    fits_file = get_object_or_404(FITSFile, pk=file_id)

    if (request.user != fits_file.uploaded_by) and (not request.user.is_staff):
        raise PermissionDenied

    if request.method == "POST":
        # Make sure the user definately wants to reprocess file. Hasn't accidentally done this.
        if request.POST.get('reprocess') == 'true':
            try:
                observation = Observation.objects.get(fits=fits_file)
                TemporaryPhotometry.objects.filter(observation=observation).delete()
                Photometry.objects.filter(observation=observation).delete()
                observation.delete()
            except ObjectDoesNotExist:
                pass  # We don't care if they don't exist, we're deleting them anyway

            if not os.path.exists(os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid))):
                os.mkdir(os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid)))

            # Move the FITS file back to an original temporary directory
            shutil.move(os.path.join(settings.FITS_DIRECTORY, fits_file.fits_filename),
                        os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid), fits_file.original_filename))

            fits_file.fits_filename = fits_file.original_filename

            general.delete_folders(fits_file)

            fits_file.process_status = 'UPLOADED'

            fits_file.save()

            return redirect('process')

        else:
            raise PermissionDenied
    else:
        raise PermissionDenied


@login_required
@permission_required('is_staff', raise_exception=True)  # Only let staff users add objects
def add_object(request):
    """
    Add a new object/target to the database (as long as the user is 'staff') with its catalog
    :param request:
    :return:
    """

    catalog_files = ['cf_CV', 'cf_U', 'cf_B', 'cf_V', 'cf_R', 'cf_I', 'cf_SZ']

    if request.method == "POST":
        form = ObjectForm(request.POST)
        # Check the user has specified a catalog file and the rest of the form is valid
        if form.is_valid():

            submitted_cats = {}

            # Get all possible catalog files the user could have submitted
            for catalog_file in catalog_files:
                submitted_cats[catalog_file] = request.FILES.get(catalog_file)

            if all(item is None for item in submitted_cats.values()):  # If all items in catalog_files are None...
                form.add_error('number', 'You need to select at least one catalog file')
                return render(request, "base_add_object.html", {'form': form})

            if not os.path.exists(os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(form.cleaned_data['number']))):
                os.mkdir(os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(form.cleaned_data['number'])))

                object = form.save()

                # Go though all possible catalog file combinations and see if the user picked one. If they did, create
                # the file
                for name, cat_file in submitted_cats.iteritems():

                    # make sure we only try and write catalog files that users uploaded
                    if cat_file is not None:
                        path = os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(form.cleaned_data['number']),
                                            name + '.cat')
                        # Write the catalog file to disk under the new name
                        with open(path, 'w') as f:
                            f.write(cat_file.read())
                            f.close()

                        # Add information about this file to the database
                        setattr(object, name, True)
                        setattr(object, name + '_original', cat_file.name)

                object.save()

                return redirect('objects')
            else:
                form.add_error('number', 'Number is not unique')
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
            device_names = ImagingDevice.objects.filter(user=request.user).values_list('name', flat=True)
            # Make sure the device name is unique for this user
            if form.cleaned_data['name'] in device_names:
                form.add_error('name', 'Name must be unique per user')
                return render(request, "base_add_device.html", {'form': form})
            device = form.save(commit=False)  # Don't save just yet - need to add the user
            device.user = request.user
            device.save()
            return redirect('accounts_profile')
        else:
            return render(request, "base_add_device.html", {'form': form})
    else:
        form = ImagingDeviceForm()

        return render(request, "base_add_device.html", {'form': form})


@login_required
@permission_required('is_staff', raise_exception=True)  # Only let staff users edit objects
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

    catalog_files = ['cf_CV', 'cf_U', 'cf_B', 'cf_V', 'cf_R', 'cf_I', 'cf_SZ']

    catalog_files_and_names = {}

    for cat in catalog_files:
        original_filename = getattr(object, cat + '_original', False)
        if original_filename is not (None or ''):
            catalog_files_and_names[cat.replace('cf_', '')] = original_filename

    if request.method == "POST":
        post_data = request.POST.copy()
        post_data['number'] = object.number

        form = ObjectForm(post_data, instance=object)
        if form.is_valid():
            form.save()

            if not os.path.exists(os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(form.cleaned_data['number']))):
                os.mkdir(os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(form.cleaned_data['number'])))

            # Go though all possible catalog file combinations and see if the user picked one. If they did, create
            # the file
            for catalog_file in catalog_files:
                cat_file = request.FILES.get(catalog_file)

                # make sure we only try and write catalog files that the user uploaded
                if cat_file is not None:
                    print 'yooooooo'
                    path = os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(form.cleaned_data['number']),
                                        catalog_file + '.cat')
                    # Write the catalog file to disk under the new name
                    with open(path, 'w') as f:
                        f.write(cat_file.read())
                        f.close()

                    print catalog_file
                    print cat_file.name

                    # Add information about this file to the database
                    setattr(object, catalog_file + '_original', cat_file.name)

                    object.save()

            return redirect('objects')

        else:
            return render(request, "base_modify_object.html", {'form': form, 'object': object, 'catalog_files_and_names': catalog_files_and_names})
    else:
        form = ObjectForm(instance=object)
        form.fields['number'].disabled = True  # We disable editing the object number because it will mess up everything

        return render(request, "base_modify_object.html", {'form': form, 'object': object, 'catalog_files_and_names': catalog_files_and_names})


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
            return render(request, "base_modify_device.html", {'form': form})
    else:
        form = ImagingDeviceForm(instance=imaging_device)

        return render(request, "base_modify_device.html", {'form': form, 'device': imaging_device})


@login_required
@permission_required('is_staff', raise_exception=True)
def manage_files(request):
    """
    Let administrators manage all uploads that have been made, and delete them/look at them if they have failed
    :param request:
    :return:
    """

    sortby = request.GET.get('sortby')

    if sortby == 'name':
        order_by = 'fits_filename'
    elif sortby == 'name_rev':
        order_by = '-fits_filename'

    elif sortby == 'uploaded_by':
        order_by = 'uploaded_by'
    elif sortby == 'uploaded_by_rev':
        order_by = '-uploaded_by'

    elif sortby == 'time':
        order_by = 'upload_time'
    elif sortby == 'time_rev':
        order_by = '-upload_time'

    elif sortby == 'current_status':
        order_by = 'process_status'
    elif sortby == 'current_status_rev':
        order_by = '-process_status'

    else:
        order_by = '-upload_time'

    files_list = FITSFile.objects.all().order_by(order_by)

    paginator = Paginator(files_list, 100)

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
@csrf_exempt
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

        if fits_file.process_status in ['OBSERVATION', 'DEVICESETUP', 'UPLOADED']:
            # Fixes bug where we try and delete files that haven't been moved yet.
            upload.handle_deleted_file(str(fits_file.uuid))
            try:
                observation = Observation.objects.get(fits=fits_file)
                observation.delete()
            except ObjectDoesNotExist:
                pass  # We don't care if they don't exist, we're deleting them anyway
            fits_file.delete()
            return render(request, "base_delete_file.html")

        try:
            observation = Observation.objects.get(fits=fits_file)
            TemporaryPhotometry.objects.filter(observation=observation).delete()
            Photometry.objects.filter(observation=observation).delete()
            observation.delete()
        except ObjectDoesNotExist:
            pass  # We don't care if they don't exist, we're deleting them anyway

        general.delete_folders(fits_file)

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

    sortby = request.GET.get('sortby')

    if sortby == 'name':
        order_by = 'fits_filename'
    elif sortby == 'name_rev':
        order_by = '-fits_filename'

    if sortby == 'origname':
        order_by = 'original_filename'
    elif sortby == 'origname_rev':
        order_by = '-original_filename'

    elif sortby == 'time':
        order_by = 'upload_time'
    elif sortby == 'time_rev':
        order_by = '-upload_time'

    elif sortby == 'current_status':
        order_by = 'process_status'
    elif sortby == 'current_status_rev':
        order_by = '-process_status'

    else:
        order_by = '-upload_time'

    devices = ImagingDevice.objects.filter(user=request.user)
    # Get all the files that have been processed by a user, but only if they have been completed successfully or failed
    processed_files = FITSFile.objects.filter(uploaded_by=request.user)\
        .filter(Q(process_status='COMPLETE') | Q(process_status='FAILED') | Q(process_status='FAILED_USER'))\
        .order_by(order_by)

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
