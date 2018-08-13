import os
import shutil
import subprocess
import sys

from astropy.io import fits
from django.conf import settings

from analysis.models import Observation


def j(p1, p2):
    """
    j - a shortcut for os.path.join
    :param p1: path 1
    :param p2: path 2
    :return: The new path
    """
    return os.path.join(p1, p2)


def do_astrometry(path, file_id):
    """
    Run the astrometry process on a single file.
    Uses sextractor, SCAMP, and missfits

    :param path: Path to the file
    :param file_id: The ID of the file
    :return:
    """
    fitscard_naxis1 = 'NAXIS1'  # name of FITS Header Card that contains the number o CCD pixels along axis1
    fitscard_naxis2 = 'NAXIS2'  # name of FITS Header Card that contains the number o CCD pixels along axis2

    # Set up our working directory
    WORKING_DIRECTORY = j(settings.ASTROMETRY_WORKING_DIRECTORY, file_id)

    # Create it if it doesn't exist yet
    if not os.path.exists(WORKING_DIRECTORY):
        os.mkdir(WORKING_DIRECTORY)
    # Use change directory into it
    os.chdir(WORKING_DIRECTORY)

    if settings.ASTROMETRY_BINARY_PATH not in sys.path:
        sys.path.append(settings.ASTROMETRY_BINARY_PATH)  # Add the astrometry.net binaries to our PATH

    # open the file
    inhdulist = fits.open(path)
    # add new WCS keywords
    inhdulist[0].header['CTYPE1'] = ('RA---TAN', 'TAN (gnomic) projection + SIP distortions')
    inhdulist[0].header['CTYPE2'] = ('DEC--TAN', 'TAN (gnomic) projection + SIP distortions')

    # get the pixel numbers and calculate the centre of the chip
    xnum = int(inhdulist[0].header[fitscard_naxis1] / 2)
    ynum = int(inhdulist[0].header[fitscard_naxis2] / 2)
    inhdulist[0].header['CRPIX1'] = (xnum, 'X reference pixel')
    inhdulist[0].header['CRPIX2'] = (ynum, 'Y reference pixel')

    observation = Observation.objects.get(fits_id=file_id)

    # the CRVAL keywords need to be calculated
    # get the ra values
    ra = observation.target.ra
    ra = ra.split(' ')
    ra1 = float(ra[0])
    ra2 = float(ra[1])
    ra3 = float(ra[2])
    # get the dec values
    de = observation.target.dec
    de = de.split(' ')
    de1 = float(de[0])
    de2 = float(de[1])
    de3 = float(de[2])
    # get the sign for dec and make it a multiplier
    sign = de[0][0]
    if sign == "+":
        mult = 1.0
    elif sign == "-":
        mult = -1.0
    else:
        pass
    # work out the RA/DEC values
    rac = 15.0 * (ra1 + ra2 / 60.0 + ra3 / 3600.0)
    decc = mult * (mult * de1 + de2 / 60.0 + de3 / 3600.0)

    inhdulist[0].header['CRVAL1'] = (rac, 'RA  of reference point')
    inhdulist[0].header['CRVAL2'] = (decc, 'DEC of reference point')

    try:
        fits.writeto(os.path.join(WORKING_DIRECTORY, 'in.fits'), inhdulist[0].data, inhdulist[0].header,
                     output_verify='ignore')
    except IOError:
        # This means that the astrometry crashed in the past, but the file exists here. We'll just continue as normal
        pass

    # Actually solve the image using the astrometry.net solve-field command
    # We downsample and guess field to try and speed things up a bit. Don't go lower than 2 - causes problems
    solve_command = [settings.ASTROMETRY_BINARY_PATH + 'solve-field', 'in.fits', '--guess-scale', '--downsample', '2',
                     '--overwrite', '--cpulimit', '600', '--ra', str(rac), '--dec', str(decc), '--radius', '1.0']

    try:
        subprocess.check_output(solve_command)
    except subprocess.CalledProcessError:
        return False

    try:
        # Move our solved image to the location of the exiting image
        shutil.move(j(WORKING_DIRECTORY, "in.new"), path)
    except IOError:
        # The astrometry failed
        return False

    # Make a JPEG that we can show the user in their browser
    imagemagick_command = ['convert', 'in-objs.png', '-resize', '40%', 'in-objs.jpg']

    try:
        subprocess.check_output(imagemagick_command)
    except subprocess.CalledProcessError:
        return False

    # Change back to our Django base directory as we're going to delete this one soon
    os.chdir(settings.BASE_DIR)

    # # Cleanup files we made earlier
    # shutil.rmtree(WORKING_DIRECTORY)
    return True
