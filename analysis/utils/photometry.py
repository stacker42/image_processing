import os
import subprocess

from django.conf import settings


def do_photometry(filename, file_id):
    """
    Do the photometry on a specified FITS file, and put the result into the photometry directory.
    Uses sextractor for this.

    :param filename: Name of the file
    :param file_id: The ID of the file
    """
    sex_command = ['sex', os.path.join(settings.FITS_DIRECTORY, filename), '-c',
                   os.path.join(settings.CONFIGS_DIRECTORY, 'default_phot.sex'), '-CATALOG_NAME',
                   os.path.join(settings.CATALOGUE_ORIGINAL_DIRECTORY, filename + ".cat"), '-PARAMETERS_NAME',
                   os.path.join(settings.CONFIGS_DIRECTORY, 'default_phot.param'), '-FILTER_NAME',
                   os.path.join(settings.CONFIGS_DIRECTORY, 'default.conv')]
    subprocess.check_output(sex_command)
