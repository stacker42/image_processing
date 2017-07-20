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
