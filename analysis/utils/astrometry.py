import fits
import os
import pyfits
import shutil
from django.conf import settings
import subprocess
from subprocess import CalledProcessError

fitscard_imagetype = 'IMAGETYP'  # name of FITS Header Card that identifies the image type i.e. bias, dark, flat, science
fitscard_filter = 'FILTER'  # name of FITS Header Card that contains the filter name used in the observations
fitscard_exptime = 'EXPTIME'  # name of FITS Header Card that contains the exposure time used in the observations
fitscard_ccdtemp = 'CCD-TEMP'  # name of FITS Header Card that contains the CCD temperature used in the observations
fitscard_objdec = 'OBJCTDEC'  # name of FITS Header Card that contains the Declination of the telescope during observations
fitscard_objra = 'OBJCTRA'  # name of FITS Header Card that contains the Right Ascention of the telescope during observations
fitscard_naxis1 = 'NAXIS1'  # name of FITS Header Card that contains the number o CCD pixels along axis1
fitscard_naxis2 = 'NAXIS2'  # name of FITS Header Card that contains the number o CCD pixels along axis2
fitscard_pierside = 'PIERSIDE'  # name of FITS Header Card that contains the Pier Side of the telescope during observations
fitscard_jd = 'JD'  # name of FITS Header Card that contains the Julian Date during observations


def j(p1, p2):
    """
    j - a shortcut for os.path.join
    :param path: The path to append to the working directory
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
    WORKING_DIRECTORY = j(settings.ASTROMETRY_WORKING_DIRECTORY, file_id)

    if not os.path.exists(WORKING_DIRECTORY):
        os.mkdir(WORKING_DIRECTORY)

    os.chdir(WORKING_DIRECTORY)

    os.putenv('PLPLOT_LIB', '/usr/share/plplot5.10.0/')

    # open the file
    inhdulist = fits.get_hdu_list(path)
    # add new WCS keywords
    inhdulist[0].header['CTYPE1'] = ('RA---TAN', 'TAN (gnomic) projection + SIP distortions')
    inhdulist[0].header['CTYPE2'] = ('DEC--TAN', 'TAN (gnomic) projection + SIP distortions')

    # get the pixel numbers and calculate the centre of the chip
    xnum = int(inhdulist[0].header[fitscard_naxis1] / 2)
    ynum = int(inhdulist[0].header[fitscard_naxis2] / 2)
    inhdulist[0].header['CRPIX1'] = (xnum, 'X reference pixel')
    inhdulist[0].header['CRPIX2'] = (ynum, 'Y reference pixel')

    # the CRVAL keywords need to be calculated
    # get the ra values
    checktarget = 0.0
    rac = 0.0
    decc = 0.0
    ra = inhdulist[0].header[fitscard_objra]
    ra = ra.split(' ')
    ra1 = float(ra[0])
    ra2 = float(ra[1])
    ra3 = float(ra[2])
    # get the dec values
    de = inhdulist[0].header[fitscard_objdec]
    de = de.split(' ')
    de1 = float(de[0])
    de2 = float(de[1])
    de3 = float(de[2])
    # print de1, de2, de3
    # get the sign for dec and make it a multiplier
    sign = de[0][0]
    if sign == "+":
        mult = 1.0
    elif sign == "-":
        mult = -1.0
    else:
        print "Something went wrong!"
    # work out the RA/DEC values
    rac = 15.0 * (ra1 + ra2 / 60.0 + ra3 / 3600.0)
    decc = mult * (mult * de1 + de2 / 60.0 + de3 / 3600.0)
    # print rac, decc
    inhdulist[0].header['CRVAL1'] = (rac, 'RA  of reference point')
    inhdulist[0].header['CRVAL2'] = (decc, 'DEC of reference point')

    # set pixel scale
    scale = 2.65556E-04
    if inhdulist[0].header[fitscard_pierside] == 'WEST':
        factor = 1.0
    elif inhdulist[0].header[fitscard_pierside] == 'EAST':
        factor = -1.0

    # write the WCS keywords
    inhdulist[0].header['CDELT1'] = (-scale, 'no comment  ')
    inhdulist[0].header['CDELT2'] = (scale, 'no comment  ')
    inhdulist[0].header['CD1_1'] = (-factor * scale, 'Transformation matrix')
    inhdulist[0].header['CD1_2'] = (0.0, 'no comment')
    inhdulist[0].header['CD2_1'] = (0.0, 'no comment')
    inhdulist[0].header['CD2_2'] = (factor * scale, 'no comment')

    # define the list of astrometric catalogues and bands to use
    listofcats = ['2MASS', 'USNO-B1', 'PPMX', 'NOMAD-1', 'DENIS-3', 'USNO-A1', 'USNO-A2', 'GSC-1.3', 'GSC-2.2',
                  'GSC-2.3', 'UCAC-1', 'UCAC-2', 'UCAC-3', 'SDSS-R3', 'SDSS-R5', 'SDSS-R6', 'SDSS-R7']

    listofbands = ['DEFAULT', 'REDDEST', 'BLUEST']

    # write out file and then run the astrometry software
    if os.path.exists(j(WORKING_DIRECTORY, "wcsprep.fits")):
        os.remove(j(WORKING_DIRECTORY, "wcsprep.fits"))
    pyfits.writeto(j(WORKING_DIRECTORY, "wcsprep.fits"), inhdulist[0].data, inhdulist[0].header)

    # loop over all catalogues and bands until a working astrometric solution has been found
    cat = 0
    band = 0
    solution_found = False
    while solution_found is False:
        catused = listofcats[cat]
        bandused = listofbands[band]
        shutil.copy(os.path.join(WORKING_DIRECTORY, "wcsprep.fits"), j(WORKING_DIRECTORY, "test.fits"))

        sex_command = ['sex', '-c', j(settings.CONFIGS_DIRECTORY, 'default_wcs.sex'), j(WORKING_DIRECTORY, 'test.fits'),
                       '-CATALOG_NAME', j(WORKING_DIRECTORY, 'test.cat'), '-PARAMETERS_NAME',
                       j(settings.CONFIGS_DIRECTORY, 'default_wcs.param'), '-FILTER_NAME',
                       j(settings.CONFIGS_DIRECTORY, 'default.conv')]
        subprocess.check_output(sex_command)

        scamp_command = ['scamp', j(WORKING_DIRECTORY, 'test.cat'), '-c', j(settings.CONFIGS_DIRECTORY, 'scamp.conf'),
                         '-ASTREF_CATALOG', catused, '-ASTREF_BAND', bandused]

        scamp_failed = False
        try:
            scamp_output = subprocess.check_output(scamp_command)
        except CalledProcessError:
            # Wrong sky zone - no solution found...
            scamp_failed = True
            solution_found = False

        missfits_command = ['missfits', '-c', j(settings.CONFIGS_DIRECTORY, 'default.missfits'),
                            j(WORKING_DIRECTORY, 'test.fits'), '-HEADER_SUFFIX', '\'.head\'', '-WRITE_XML', 'N']
        subprocess.check_output(missfits_command)

        shutil.move(j(WORKING_DIRECTORY, "test.fits"), j(WORKING_DIRECTORY, "astro.fits"))
        # Cleanup files dropped by sextractor and SCAMP
        os.remove(j(WORKING_DIRECTORY, 'test.fits.back'))
        os.remove(j(WORKING_DIRECTORY, 'test.cat'))

        # if whole output contains 'wrong sky zone'
        # SDSS-R3, DENIS-3 force and test

        if not scamp_failed:
            os.remove(j(WORKING_DIRECTORY, 'test.head'))
            if '\x1b[01;31mtest.cat' in scamp_output:
                print "no solution found"
                solution_found = False
            else:
                print "solution found"
                solution_found = True

        if cat <= len(listofcats):
            cat = cat + 1
        if cat == len(listofcats):
            cat = 0
            if band <= len(listofbands):
                band = band + 1
            if band <= len(listofbands):
                print "No Astrometric solution found!"
                catused = 'none'
                bandused = 'none'
                solution_found = 1

    # update fits header of solved image with the catalogue info
    inhdulist = fits.get_hdu_list(j(WORKING_DIRECTORY, 'astro.fits'))  # astro.fits
    inhdulist[0].header['AST_CAT'] = (catused, 'Astrometric Catalogue used for WCS')
    inhdulist[0].header['AST_BAND'] = (bandused, 'Astrometric Band used for WCS')
    pyfits.writeto(j(WORKING_DIRECTORY, "astro1.fits"), inhdulist[0].data, inhdulist[0].header)

    shutil.move(j(WORKING_DIRECTORY, "astro1.fits"), path)

    os.chdir(settings.BASE_DIR)

    # Cleanup files we made earlier
    #shutil.rmtree(WORKING_DIRECTORY)