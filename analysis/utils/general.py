import os
import shutil

from astropy.io import fits
from django.conf import settings
from django.db import connection
from django.shortcuts import HttpResponse

import upload
from analysis.forms import *
from astropy.coordinates import SkyCoord
import astropy.units as u


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


def process_metadata_db(inhdulist, fits_file, request):
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
        if not isinstance(value, fits.card.Undefined):
            header[key] = value

    fits_file.header = header

    observation = Observation.objects.get(fits=fits_file)

    filename = str(fits_file.id) + '_' + str(request.user.id) + '_' + str(observation.device.id) + '_' + \
               observation.target.name + '_' + observation.orignal_filter + '_' + str(observation.date) + '.fits'

    filename = ''.join(filename.split())

    shutil.move(os.path.join(settings.UPLOAD_DIRECTORY, str(fits_file.uuid), fits_file.fits_filename),
                os.path.join(settings.FITS_DIRECTORY, filename))
    # Delete the old temporary directory for this file
    upload.handle_deleted_file(str(fits_file.uuid))

    fits_file.original_filename = fits_file.fits_filename

    fits_file.fits_filename = filename

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
    if fits_file.catalogue_filename != '':
        if os.path.exists(os.path.join(settings.CATALOGUE_ORIGINAL_DIRECTORY, fits_file.catalogue_filename)):
            os.remove(os.path.join(settings.CATALOGUE_ORIGINAL_DIRECTORY, fits_file.catalogue_filename))

        if os.path.exists(os.path.join(settings.CATALOGUE_PROCESSED_DIRECTORY, fits_file.catalogue_filename)):
            os.remove(os.path.join(settings.CATALOGUE_PROCESSED_DIRECTORY, fits_file.catalogue_filename))

    if fits_file.fits_filename != '':
        if os.path.exists(os.path.join(settings.FITS_DIRECTORY, fits_file.fits_filename)):
            os.remove(os.path.join(settings.FITS_DIRECTORY, fits_file.fits_filename))

        if os.path.exists(os.path.join(settings.PLOTS_DIRECTORY, fits_file.fits_filename + '.png')):
            os.remove(os.path.join(settings.PLOTS_DIRECTORY, fits_file.fits_filename + '.png'))

    if os.path.exists(os.path.join(settings.ASTROMETRY_WORKING_DIRECTORY, str(fits_file.id))):
        shutil.rmtree(os.path.join(settings.ASTROMETRY_WORKING_DIRECTORY, str(fits_file.id)))


def copy_to_photometry(observation_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT observation_id, calibrated_magnitude, calibrated_error, magnitude_rms_error, x, y, alpha_j2000, delta_j2000, fwhm_world, flags, magnitude INTO photometry FROM photometry_temp WHERE observation_id = %s",
            observation_id)

def withinradius(star_to_check, ra, dec):
    """
    Check whether a star is within a radius of 3 arcseconds
    :param star_to_check: The star to check
    :param ra: RA bound
    :param dec: DEC bound
    :return: True or False
    """

    star_to_check_coords = SkyCoord(star_to_check['alpha_j2000'], star_to_check['delta_j200'], unit=u.degree, frame='icrs')

    #if (ra - 3/3600) <= star_to_check['alpha_j2000'] <= (ra + 3/3600) and (dec - 3/3600) <= star_to_check['delta_j2000'] <= (dec + 3/3600):
    #if star_to_check['alpha_j2000'] >= (ra - (3/3600)) and star_to_check['alpha_j2000'] <= (ra + (3/3600)) and star_to_check['delta_j2000'] >= (dec - (3/3600)) and star_to_check['delta_j2000'] <= (dec + (3/3600)):
    #    return True
    #else:
    #    return False