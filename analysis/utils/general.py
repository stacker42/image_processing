from django.shortcuts import HttpResponse
from django.conf import settings
from analysis.models import *
from analysis.forms import *
import os
import fits
import shutil
from astropy.time import Time
from django.core.exceptions import PermissionDenied
import pyfits
import upload


def make_response(status=200, content_type='text/plain', content=None):
    """ Construct a response to a request.

    Also, content-type is text/plain by default since IE9 and below chokes
    on application/json.
    """
    response = HttpResponse()
    response.status_code = status
    response['Content-Type'] = content_type
    response.content = content
    return response


def process_metadata_db(inhdulist, fits_file):
    """
    Actually process the header and put all required information in the database, and move the file to its permanent
    location
    :param request:
    :param fits_file: A FITS file object
    :return:
    """

    header = {}

    # Iterate through all the header values and add these to a dictionary
    for key, value in zip(inhdulist[0].header.keys(), inhdulist[0].header.values()):
        # Don't add header cards that we can't read the value of
        if not isinstance(value, pyfits.card.Undefined):
            header[key] = value

    fits_file.header = header

    # Make a new directory for the file and put it into this new directory.
    os.mkdir(os.path.join(settings.FITS_DIRECTORY, str(fits_file.id)))
    shutil.move(os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid), fits_file.fits_filename),
                os.path.join(settings.FITS_DIRECTORY, str(fits_file.id), fits_file.fits_filename))
    # Delete the old temporary directory for this file
    upload.handle_deleted_file(str(fits_file.uuid))

    # Set the current stage of the processing
    fits_file.process_status = 'METADATA'

    fits_file.save()


def get_used_filter(filterval):
    """
    Get the filter that we will use for calibration
    :param filterval: The user entered filter name
    :return: The filter will will use
    """
    filterval = filterval.upper()
    if filterval in settings.CV_FILTERS:
        used_filter = 'CV'
    elif filterval in settings.U_FILTERS:
        used_filter = 'U'
    elif filterval in settings.B_FILTERS:
        used_filter = 'B'
    elif filterval in settings.V_FILTERS:
        used_filter = 'V'
    elif filterval in settings.R_FILTERS:
        used_filter = 'R'
    elif filterval in settings.I_FILTERS:
        used_filter = 'I'
    elif filterval in settings.SZ_FILTERS:
        used_filter = 'SZ'
    else:
        used_filter = None

    return used_filter


def delete_folders(fits_file):
    """
    Delete folders dropped during processing
    :param fits_file: A FITSFile object
    :return:
    """

    # Remove all folders we drop during analysis
    if os.path.exists(os.path.join(settings.CATALOGUE_DIRECTORY, str(fits_file.id))):
        shutil.rmtree(os.path.join(settings.CATALOGUE_DIRECTORY, str(fits_file.id)))

    if os.path.exists(os.path.join(settings.FITS_DIRECTORY, str(fits_file.id))):
        shutil.rmtree(os.path.join(settings.FITS_DIRECTORY, str(fits_file.id)))

    if os.path.exists(os.path.join(settings.PLOTS_DIRECTORY, str(fits_file.id))):
        shutil.rmtree(os.path.join(settings.PLOTS_DIRECTORY, str(fits_file.id)))

    if os.path.exists(os.path.join(settings.ASTROMETRY_WORKING_DIRECTORY, str(fits_file.id))):
        shutil.rmtree(os.path.join(settings.ASTROMETRY_WORKING_DIRECTORY, str(fits_file.id)))