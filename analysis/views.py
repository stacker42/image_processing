# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import os
import shutil
from decimal import *

from astropy.time import Time
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from forms import *
from models import *
from utils import fits, upload, astrometry, photometry, calibration, general, lc

from plotly.offline import plot
import plotly.graph_objs as go
import csv
from astropy.coordinates import SkyCoord
from astropy.coordinates.name_resolve import NameResolveError
from astropy import units as u
from django.db.models import Sum
import itertools

@login_required
def ul(request):
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

        user_id_filter = request.GET.get('user')

        if user_id_filter is None:
            files_list = FITSFile.objects.filter(~Q(process_status='COMPLETE') &
                                                 ~Q(process_status='FAILED') &
                                                 ~Q(process_status='FAILED_USER')
                                                 ).order_by('upload_time')
        else:
            files_list = FITSFile.objects.filter(~Q(process_status='COMPLETE') &
                                                 ~Q(process_status='FAILED') &
                                                 ~Q(process_status='FAILED_USER') &
                                                 Q(uploaded_by_id=user_id_filter)).order_by('upload_time')

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

    choose_user_form = ChooseUserForm()

    return render(request, "base_process.html", {'files': files, 'choose_user_form': choose_user_form})


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
            return render(request, "base_process_observation.html", {'form': form, 'file': fits_file})
    else:
        form = ObservationForm()
        if not request.user.is_staff:
            form.fields['device'].queryset = ImagingDevice.objects.filter(user=request.user)
        else:
            form.fields['device'].queryset = ImagingDevice.objects.all()

        return render(request, "base_process_observation.html", {'form': form, 'file': fits_file})


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

    # observations = Observation.objects.filter(device=observation.device)

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
    hdulist[0].verify('silentfix')

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

    return render(request, "base_process_devicesetup.html", {'form': form, 'device': device})


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

            inhdulist[0].verify('silentfix')

            header = inhdulist[0].header

            observation = Observation.objects.get(fits=fits_file)
            device = observation.device

            # Get the filter we actually want to use from the form thats submitted. Don't bother with whats in the
            # header now, we know its something we can support. Narrow down the option.
            observation.filter = request.POST.get('used_filter')

            if device.date_format == 'MJD':
                date = header[device.date_card] + 2400000.5
            elif device.date_format == 'JD':
                date = header[device.date_card]
            elif device.date_format == 'DATETIME':
                date = Time(inhdulist[0].header[device.date_card]).jd
            elif device.date_format == 'DATETIMESEP':
                time = header[device.time_card]
                date = header[device.date_card]
                date = Time(date + "T" + time).jd

            # Convert whatever format the date is in the header to Julian and store this
            try:
                observation.date = float(date)
            except ValueError:
                # The user has probably chosen the wrong datatype here...
                return render(request, "base_error.html", {'message': "The date that you have chosen couldn't be "
                                                                      "converted properly. Are you sure that you chose "
                                                                      "the right date type (JD, MJD, Date & Time etc.) "
                                                                      "for the data in the file?"})

            observation.exptime = header[device.exptime_card]

            observation.orignal_filter = header[device.filter_card]

            observation.save()

            general.process_metadata_db(header, fits_file, request)

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

    hdulist[0].verify('silentfix')

    header = hdulist[0].header

    header_text = repr(header).encode('utf-8')

    observation = Observation.objects.get(fits=fits_file)
    device = observation.device

    valid = True

    try:
        # Use date card from the device
        dateval = str(header[device.date_card])
    except KeyError:
        # If the user chose NONE for the card, then we'll just put nothing here, and force them to change it
        valid = False
        dateval = ''
    try:
        # Use exposure time card from device
        exptimeval = str(header[device.exptime_card])
    except KeyError:
        # If the user chose NONE for the card, then we'll just put nothing here, and force them to change it
        valid = False
        exptimeval = ''

    try:
        # Use filter card from device
        filterval = str(header[device.filter_card])
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
            timeval = header[device.time_card]
        except KeyError:
            valid = False
            timeval = ''
    else:
        timeval = 'N/A'

    return render(request, "base_process_metadata.html", {'header': header_text, 'file_id': file_id, 'device': device,
                                                          'date': dateval, 'exptime': exptimeval, 'filter': filterval,
                                                          'valid': valid, 'time': timeval, 'used_filter': used_filter,
                                                          'all_filters': settings.ALL_FILTERS,
                                                          'target_supported_filter': target_supported_filter,
                                                          'file': fits_file})


@login_required
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

            try:
                observation.date = float(date)
            except ValueError:
                # The user has probably chosen the wrong datatype here...
                form.add_error('date_format', "The date that you have chosen couldn't be converted properly. Are you "
                                              "sure that you chose the right date type for the data?")

                return render(request, "base_process_metadata_modify.html", {'form': form, 'file': fits_file})

            observation.exptime = form.cleaned_data['exptime']

            used_filter = general.get_used_filter(form.cleaned_data['filter'])

            if used_filter is None:
                form.add_error('filter', "You must choose a valid filter")
                return render(request, "base_process_metadata_modify.html", {'form': form, 'file': fits_file})

            found = []
            for f in os.listdir(os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(observation.target.number))):
                if f[3:].replace('.cat', '') != used_filter:
                    found.append(False)
                else:
                    found.append(True)

            if True not in found:
                form.add_error('filter', "You must choose a filter supported by your target")
                return render(request, "base_process_metadata_modify.html", {'form': form, 'file': fits_file})

            observation.filter = used_filter
            observation.orignal_filter = form.cleaned_data['filter']

            inhdulist = fits.get_hdu_list(
                os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid), fits_file.fits_filename))

            inhdulist[0].verify('silentfix')

            header = inhdulist[0].header

            observation.save()

            general.process_metadata_db(header, fits_file, request)

            observation.save()
            return redirect('process')
        else:
            return render(request, "base_process_metadata_modify.html", {'form': form, 'file': fits_file})
    else:
        # The values that we might have grabbed from the header will be in the GET variables. If there's nothing there,
        # then the initial data will just be blank, which is intentional
        initial_values = {'exptime': request.GET.get('exptime'), 'date': request.GET.get('date'),
                          'filter': request.GET.get('filter'), 'date_format': request.GET.get('date_format')}

        form = MetadataForm(initial=initial_values)

        return render(request, "base_process_metadata_modify.html", {'form': form, 'file': fits_file})


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

            # This is not ideal - but we REALLY don't want to copy over the primary key to the new table,
            # as it WILL conflict with previous entries.

            temp_photometry_objects = TemporaryPhotometry.objects.filter(observation=observation).values()
            phots = []

            for p in temp_photometry_objects:
                del p['id']
                phots.append(Photometry(**p))

            Photometry.objects.bulk_create(phots)

            TemporaryPhotometry.objects.filter(observation=observation).delete()
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


@csrf_exempt
@login_required
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

        if fits_file.original_filename != '' and fits_file.original_filename is not None and fits_file.original_filename != ' ':
            fits_file.fits_filename = fits_file.original_filename

        general.delete_folders(fits_file)

        fits_file.process_status = 'UPLOADED'

        fits_file.save()

        return redirect('process')
    else:
        raise PermissionDenied


@csrf_exempt
@login_required
def process_reprocess_photometry(request, file_id):
    """
    Allow a user to re-process a file from the astrometry stage
    :param request:
    :param file_id: The ID of the file to reprocess
    :return:
    """
    fits_file = get_object_or_404(FITSFile, pk=file_id)

    if (request.user != fits_file.uploaded_by) and (not request.user.is_staff):
        raise PermissionDenied

    if request.method == "POST":
        try:
            observation = Observation.objects.get(fits=fits_file)
            TemporaryPhotometry.objects.filter(observation=observation).delete()
            Photometry.objects.filter(observation=observation).delete()
        except ObjectDoesNotExist:
            pass  # We don't care if they don't exist, we're deleting them anyway

        fits_file.process_status = 'ASTROMETRY'

        fits_file.save()

        return redirect('process')
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
                    path = os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(form.cleaned_data['number']),
                                        catalog_file + '.cat')
                    # Write the catalog file to disk under the new name
                    with open(path, 'w') as f:
                        f.write(cat_file.read())
                        f.close()

                    # Add information about this file to the database
                    setattr(object, catalog_file + '_original', cat_file.name)

                    object.save()

            return redirect('objects')

        else:
            return render(request, "base_modify_object.html",
                          {'form': form, 'object': object, 'catalog_files_and_names': catalog_files_and_names})
    else:
        form = ObjectForm(instance=object)
        form.fields['number'].disabled = True  # We disable editing the object number because it will mess up everything

        return render(request, "base_modify_object.html",
                      {'form': form, 'object': object, 'catalog_files_and_names': catalog_files_and_names})


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
    # Users can filter the results they get by either the user uploaded, the status, or both
    user_id_filter = request.GET.get('user')
    status_filter = request.GET.get('status')

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

    if user_id_filter is None and status_filter is None:
        files_list = FITSFile.objects.all().order_by(order_by)
    elif user_id_filter is not None and status_filter is None:
        files_list = FITSFile.objects.filter(uploaded_by_id=user_id_filter).order_by(order_by)
    elif user_id_filter is None and status_filter is not None:
        files_list = FITSFile.objects.filter(process_status=status_filter).order_by(order_by)
    else:
        files_list = FITSFile.objects.filter(process_status=status_filter, uploaded_by_id=user_id_filter).order_by(
            order_by)

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

    choose_status_form = ChooseStatusForm()
    choose_user_form = ChooseUserForm()

    return render(request, "base_manage_files.html", {'files': files, 'choose_status_form': choose_status_form,
                                                      'choose_user_form': choose_user_form})


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
    processed_files = FITSFile.objects.filter(uploaded_by=request.user) \
        .filter(Q(process_status='COMPLETE') | Q(process_status='FAILED') | Q(process_status='FAILED_USER')) \
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


def lightcurve(request):
    """
    Let the user enter the RA and Dec for this lightcurve, and plot it!
    :param request:
    :return:
    """

    is_plot = request.GET.get('plot')
    offsets = request.GET.getlist('offset')
    eb = request.GET.get('errorbars')
    user_input = request.GET.get('user_input')

    if eb is not None and eb == "true":
        errorbars = True
    else:
        errorbars = False

    if user_input is not None:
        # Convert whatever the user has entered into some RA and DEC co-ords we can use
        form = LightcurveSearchForm(request.GET)
        if form.is_valid():
            if form.cleaned_data['input_type'] == "NAME":
                # Lookup using name
                try:
                    coords = SkyCoord.from_name(form.cleaned_data['user_input'])
                except (NameResolveError, AttributeError):
                    return render(request, "base_lightcurve.html",
                                  {'form': form, 'error': 'No stars found for given name / error with looking up name.'
                                                          'Try co-ordinates instead'})
            else:
                try:
                    if form.cleaned_data['units']:
                        # Check the units the user has specified, otherwise just use degrees
                        if form.cleaned_data['units'] == "HD":
                            unit1 = u.hour
                            unit2 = u.degree
                        else:
                            unit1 = u.degree
                            unit2 = u.degree
                        if form.cleaned_data['coordinate_frame']:
                            # If the user gave us a coordinate frame
                            coords = SkyCoord(form.cleaned_data['user_input'], frame=form.cleaned_data['coordinate_frame'], unit=(unit1, unit2))
                        else:
                            # Default to fk5
                            coords = SkyCoord(form.cleaned_data['user_input'], frame='fk5', unit=(unit1, unit2))
                    else:
                        if form.cleaned_data['coordinate_frame']:
                            coords = SkyCoord(form.cleaned_data['user_input'], frame=form.cleaned_data['coordinate_frame'],
                                          unit=u.degree)
                        else:
                            # Default to fk5
                            coords = SkyCoord(form.cleaned_data['user_input'], frame='fk5', unit=u.degree)
                except ValueError:
                    form = LightcurveSearchForm()

                    error = "Co-ordinates could not be found for the data that you entered, are you sure you chose the" \
                            " right data type? (co-ordinates instead of name)"

                    return render(request, "base_lightcurve.html", {'form': form, 'error': error})

            # Covert whatever we have got to FK5
            coords = coords.transform_to('fk5')

            if form.cleaned_data['radius']:
                radius = form.cleaned_data['radius']
            else:
                radius = 5

            # Can't divide by 0!
            if coords.dec.degree == 90:
                dec = 89.99999
            else:
                dec = coords.dec.degree

            request.session['lightcurve_data'] = {}

            lightcurve_data, user_choices = lc.index_stars(coords, radius, dec, request, form)

            if lightcurve_data is None and user_choices is None:
                return render(request, "base_lightcurve.html",
                              {'form': form, 'error': 'No stars found for given co-ordinates'})

            request.session['lightcurve_data'] = lightcurve_data

            return render(request, "base_lightcurve_stars.html", {'user_choices': user_choices, 'lightcurve_data': lightcurve_data})

    elif is_plot == '1':
        # User has chosen a star, now we will produce a plot

        choice = request.GET.get('choice')

        lightcurve_data = request.session.get('lightcurve_data')

        if lightcurve_data is None:
            return redirect('lightcurve' + "?user_input=" + choice + "&radius=5&coordinate_frame=fk5&input_type=COORD")

        filters = lightcurve_data['filters']

        colours = {'R': 'rgba(255, 0, 0, 1)', 'V': 'rgba(0, 255, 0, 1)', 'B': 'rgba(0, 0, 255, 1)',
                   'U': 'rgb(191, 0, 255)', 'I': 'rgba(0, 0, 0, 1)', 'SZ': 'rgb(255, 250, 0)', 'CV': 'rgb(250, 0, 255)',
                   'HA': 'rgb(255, 0, 229)'}

        traces = []

        filters_and_offsets = {}

        for f in filters:
            try:
                offset = 0
                # Change our offset string I:3 into filter I and offset 3
                for o in offsets:
                    if o.split(":")[0] == f:
                        offset = o.split(":")[1]
                        filters_and_offsets[f] = offset

                traces.append(
                    go.Scatter(
                        # Need to except KeyError and go onto the next filter here
                        x=[star['date'] for star in lightcurve_data['seperated'][choice] if star['filter'] == f and star['magnitude'] > 0 and star['calibrated_error'] != 0], # or calibrated_error = 0
                        y=[star['calibrated_magnitude'] + Decimal(offset) for star in lightcurve_data['seperated'][choice] if star['filter'] == f and star['magnitude'] > 0 and star['calibrated_error'] != 0],
                        error_y=dict(
                            type='data',
                            array=[star['calibrated_error'] for star in lightcurve_data['seperated'][choice] if star['filter'] == f and star['magnitude'] > 0 and star['calibrated_error'] != 0],
                            visible=errorbars,
                            color=colours[f],
                        ),
                        name=f + " [" + str(offset if offset < 0 else "+" + offset) + " mag]" if offset != 0 else f,
                        mode='markers',
                        marker=dict(
                            size=10,
                            color=colours[f],
                            line=dict(
                                width=2,
                                color='rgb(0, 0, 0)'
                            )
                        )

                    )
                )
            except KeyError as e:
                print e
                # We don't have any data for this choice for filter, so lets just go onto the next one!
                pass

        layout = dict(
            title='Lightcurve Plot',
            yaxis=dict(
                zeroline=False,
                title="Magnitude",
                autorange="reversed"
            ),
            xaxis=dict(
                zeroline=False,
                title="Time (JD)",
                tickformat="f"
            )
        )
        fig = dict(data=traces, layout=layout)

        p = plot(fig, output_type='div', show_link=False, config={'modeBarButtonsToRemove': ['sendDataToCloud']})

        return render(request, "base_lightcurve_plot.html", {'filters': filters,
                                                             'plot': p, 'filters_and_offsets': filters_and_offsets,
                                                             'errorbars': errorbars, 'choice': choice})

    else:
        form = LightcurveSearchForm()

        return render(request, "base_lightcurve.html", {'form': form})


def lightcurve_download(request):
    """
    Download the data used to generate a lightcurve
    :param request:
    :return:
    """

    user_input = request.GET.get('user_input')
    input_type = request.GET.get('input_type')
    coordinate_frame = request.GET.get('coordinate_frame')
    radius = request.GET.get('radius')
    units = request.GET.get('units')

    if input_type == "NAME":
        # Lookup using name
        coords = SkyCoord.from_name(user_input)
    else:
        if units:
            # Check the units the user has specified, otherwise just use degrees
            if units == "HD":
                unit1 = u.hour
                unit2 = u.degree
            else:
                unit1 = u.degree
                unit2 = u.degree
            if coordinate_frame:
                # If the user gave us a coordinate frame
                coords = SkyCoord(user_input, frame=coordinate_frame,
                                  unit=(unit1, unit2))
            else:
                # Default to fk5
                coords = SkyCoord(user_input, frame='fk5', unit=(unit1, unit2))
        else:
            if coordinate_frame:
                coords = SkyCoord(user_input, frame=coordinate_frame,
                                  unit=u.degree)
            else:
                # Default to fk5
                coords = SkyCoord(user_input, frame='fk5', unit=u.degree)

    # Covert whatever we have got to FK5
    coords = coords.transform_to('fk5')

    if radius:
        radius = radius
    else:
        radius = 5

    if coords.dec.degree == 90:
        dec = 89.99999
    else:
        dec = coords.dec.degree

    lightcurve_data, user_choices = lc.index_stars(coords, radius, dec, request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="lightcurve_' + user_input + '.txt"'

    w = csv.writer(response, delimiter=" ".encode('utf-8'))
    w.writerow(['id', 'calibrated_magnitude', 'calibrated_error', 'magnitude_rms_error', 'x', 'y', 'alpha_j2000',
                'delta_j2000', 'fwhm_world', 'flags', 'magnitude', 'observation_id', 'filter', 'original_filter',
                'date', 'user_id', 'device_id', 'target', 'fits_id'])

    for cluster in lightcurve_data['seperated']:
        for star in lightcurve_data['seperated'][cluster]:
            w.writerow([star['id'], star['calibrated_magnitude'], star['calibrated_error'], star['magnitude_rms_error'], star['x'],
                    star['y'], star['alpha_j2000'], star['delta_j2000'], star['fwhm_world'], star['flags'], star['magnitude'],
                    star['observation_id'], star['filter'], star['original_filter'],
                    star['date'], star['user_id'], star['device_id'], star['target'], star['fits_id']])

    return response


def stats(request):
    """
    Statistics page showing information about uploads and data on this server
    :param request:
    :return:
    """
    # Number of observations for each object per filter
    # exposure times per object per filter
    #
    objs = Object.objects.all()
    filters = ['U', 'B', 'V', 'R', 'HA', 'I', 'SZ']
    traces_objcount = []
    traces_exptimes = []
    colours = {'R': 'rgba(255, 0, 0, 1)', 'V': 'rgba(0, 255, 0, 1)', 'B': 'rgba(0, 0, 255, 1)',
               'U': 'rgb(191, 0, 255)', 'I': 'rgba(0, 0, 0, 1)', 'SZ': 'rgb(255, 250, 0)', 'CV': 'rgb(250, 0, 255)',
               'HA': 'rgb(255, 0, 229)'}

    for filt in filters:
        x = []
        y_objcount = []
        y_exptimes = []
        for obj in objs:
            x.append(obj.name)
            if filt is 'HA':
                y_objcount.append(Observation.objects.filter(target=obj, orignal_filter__in=settings.HA_FILTERS).count())
                # Get the sum of all exptimes, and then flatten this using itertools, and then convert it back to a list
                exptime = Observation.objects.filter(target=obj, orignal_filter__in=settings.HA_FILTERS).aggregate(Sum('exptime'))['exptime__sum']
                if exptime is not None:
                    y_exptimes.append(exptime / 3600)
                else:
                    y_exptimes.append(0)
            else:
                y_objcount.append(Observation.objects.exclude(orignal_filter__in=settings.HA_FILTERS).filter(target=obj, filter=filt).count())
                # Get the sum of all exptimes, and then flatten this using itertools, and then convert it back to a list
                exptime = Observation.objects.exclude(orignal_filter__in=settings.HA_FILTERS).filter(target=obj, filter=filt).aggregate(Sum('exptime'))['exptime__sum']
                if exptime is not None:
                    y_exptimes.append(exptime / 3600)
                else:
                    y_exptimes.append(0)
        traces_objcount.append(
            go.Bar(
                x=x,
                y=y_objcount,
                name=filt,
                marker=dict(
                    color=colours[filt]
                )
            )
        )
        traces_exptimes.append(
            go.Bar(
                x=x,
                y=y_exptimes,
                name=filt,
                marker=dict(
                    color=colours[filt]
                )
            )
        )


    users = User.objects.all()
    x_userid = []
    y_uploads = []
    for user in users[2:]:
        x_userid.append(user.id)
        y_uploads.append(FITSFile.objects.filter(uploaded_by=user).count())
    trace_uploads = [
        go.Bar(
            x=x_userid,
            y=y_uploads,
        )
    ]

    layout_objcount = go.Layout(
        barmode='group',
        title='Number of observations',
        xaxis=dict(
            title='Object'
        ),
        yaxis=dict(
            title='Observations',
            type='log'
        )
    )

    layout_exptimes = go.Layout(
        barmode='group',
        title='Cumulative exposure times',
        xaxis=dict(
            title='Object'
        ),
        yaxis=dict(
            title='Exposure time (h)',
            type='log'
        )
    )

    layout_uploads = go.Layout(
        barmode='group',
        title='Uploads',
        xaxis=dict(
            title='User ID'
        ),
        yaxis=dict(
            title='Number of uploads',
            type='log'
        )
    )

    fig_objcount = dict(data=traces_objcount, layout=layout_objcount)
    fig_exptimes = dict(data=traces_exptimes, layout=layout_exptimes)
    fig_uploads = dict(data=trace_uploads, layout=layout_uploads)

    p_objcount = plot(fig_objcount, output_type='div', show_link=False, config={'modeBarButtonsToRemove': ['sendDataToCloud']})
    p_exptimes = plot(fig_exptimes, output_type='div', show_link=False, config={'modeBarButtonsToRemove': ['sendDataToCloud']})
    p_uploads = plot(fig_uploads, output_type='div', show_link=False, config={'modeBarButtonsToRemove': ['sendDataToCloud']})

    return render(request, "base_stats.html", {'p_objcount': p_objcount, 'p_exptimes': p_exptimes, 'p_uploads': p_uploads})