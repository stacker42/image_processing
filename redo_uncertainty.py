import os

from django.core.wsgi import get_wsgi_application

os.environ['DJANGO_SETTINGS_MODULE'] = 'image_processing.settings'
application = get_wsgi_application()

import numpy
from analysis.utils.calibration import fitfunc_cal

from analysis.models import Observation, Photometry, FITSFile
from astropy.io import ascii
from astropy.io import fits
from django.conf import settings
import astropy.units as u
from astropy.coordinates import SkyCoord, match_coordinates_sky

SKIP_ROWS_IN_CAT = 9  # number of rows to skip in photometry tables
POS_OFFSET = 3  # off-set in arcsec to be considered match (in ra and dec)n ----- change this to 1

observations = Observation.objects.all()

for o in observations:

    if o.id > 5000:
        continue

    print "Working on observation " + str(o.id) + "..."

    phots = Photometry.objects.filter(observation=o)
    param_cal_arrformat = o.calibration_parameters
    param_cal = numpy.array(param_cal_arrformat.split(" ")[:-1])
    param_cal = param_cal.astype(numpy.float32)
    fits_file = o.fits

    uncalibrated_magnitudes = phots.filter(flags=0.0).values_list('magnitude', flat=True)

    if len(uncalibrated_magnitudes) == 0:
        continue

    max_use = numpy.max(uncalibrated_magnitudes)
    max_use = float(max_use) + 0.000000000001
    min_use = numpy.min(uncalibrated_magnitudes)
    min_use = float(min_use) - 0.000000000001

    edge_dist = 10
    # the calibration offset to get instrumental into apparent mag
    # needs to be calculated at some stage, start with gettting from db
    cal_offset = o.target.cal_offset

    # Read in the first catalogue and create arrays with the data contained within it
    mastercat = ascii.read(os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(o.target.number),
                                        'cf_' + o.filter + '.cat'))

    num_m = numpy.array(mastercat['NUMBER'])
    num_m = num_m.astype(numpy.float32)

    mag_m = numpy.array(mastercat['MAG_AUTO'])
    # add the calibration offset to the master photometry
    mag_m = mag_m.astype(numpy.float32) + cal_offset

    mage_m = numpy.array(mastercat['MAGERR_AUTO'])
    mage_m = mage_m.astype(numpy.float32)

    ra_m = numpy.array(mastercat['ALPHA_J2000'])
    ra_m = ra_m.astype(numpy.float32)

    de_m = numpy.array(mastercat['DELTA_J2000'])
    de_m = de_m.astype(numpy.float32)

    fwhm_m = numpy.array(mastercat['FWHM_WORLD'])
    fwhm_m = fwhm_m.astype(numpy.float32)

    flag_m = numpy.array(mastercat['FLAGS'])
    flag_m = flag_m.astype(numpy.float32)

    # replace the 99 values for objects without photometry to zero
    check99 = numpy.where(mag_m == 99)
    mag_m[check99[0]] = 0.0
    check99 = numpy.where(mage_m == 99)
    mage_m[check99[0]] = 0.0

    # make coordcatalogue for the master table
    # cat_master = ICRS(ra_m, de_m, unit=(u.degree, u.degree))
    cat_master = SkyCoord(ra_m, de_m, frame='icrs', unit=u.degree)

    # read in FITS header of corresponding image and get observing date
    # which is stored in header 'TIMETIME' by the 'change_header.py' program
    data, header = fits.getdata(os.path.join(settings.FITS_DIRECTORY, fits_file.fits_filename),
                                header=True)
    time = header['DATE-OBS']

    # get pixel numbers to check if star is near the edge
    xpix = header['NAXIS1']
    ypix = header['NAXIS2']

    # Read in the second catalogue and create arrays with the data contained within it
    secondcat = ascii.read(os.path.join(settings.CATALOGUE_ORIGINAL_DIRECTORY, fits_file.catalogue_filename))

    num_2 = secondcat['NUMBER']
    num_2 = num_2.astype(numpy.float32)

    mag_2 = secondcat['MAG_AUTO']
    mag_2 = mag_2.astype(numpy.float32)

    mage_2 = secondcat['MAGERR_AUTO']
    mage_2 = mage_2.astype(numpy.float32)

    ra_2 = secondcat['ALPHA_J2000']
    ra_2 = ra_2.astype(numpy.float64)

    de_2 = secondcat['DELTA_J2000']
    de_2 = de_2.astype(numpy.float64)

    fwhm_2 = secondcat['FWHM_WORLD']
    fwhm_2 = fwhm_2.astype(numpy.float64)

    flag_2 = secondcat['FLAGS']
    flag_2 = flag_2.astype(numpy.float32)

    x_2 = secondcat['X_IMAGE']
    x_2 = x_2.astype(numpy.float32)

    y_2 = secondcat['Y_IMAGE']
    y_2 = y_2.astype(numpy.float32)

    # find min/max RA/DEC values of the 2nd frame
    RA_MIN = numpy.min(ra_2) + 0.01
    RA_MAX = numpy.max(ra_2) - 0.01
    DE_MIN = numpy.min(de_2) + 0.01
    DE_MAX = numpy.max(de_2) - 0.01

    # replace the 99 values for objects without photometry to -99
    edge_2 = numpy.zeros(len(num_2), dtype=float)
    check99 = numpy.where(mag_2 == 99)
    mag_2[check99[0]] = -99
    check99 = numpy.where(mage_2 == 99)
    mage_2[check99[0]] = -99
    # replace the magnitudes and errors of stars within edge_dist pix from the edge by -99
    # or (y_2 < edge_dist) or (ypix-y_2 < edge_dist) or (xpix-x_2 < edge_dist))
    check_edge = numpy.where(x_2 < edge_dist)
    edge_2[check_edge[0]] = 1.
    mag_2[check_edge[0]] = -99
    mage_2[check_edge[0]] = -99
    check_edge = numpy.where(y_2 < edge_dist)
    edge_2[check_edge[0]] = 1.
    mag_2[check_edge[0]] = -99
    mage_2[check_edge[0]] = -99
    check_edge = numpy.where(xpix - x_2 < edge_dist)
    edge_2[check_edge[0]] = 1.
    mag_2[check_edge[0]] = -99
    mage_2[check_edge[0]] = -99
    check_edge = numpy.where(ypix - y_2 < edge_dist)
    edge_2[check_edge[0]] = 1.
    mag_2[check_edge[0]] = -99
    mage_2[check_edge[0]] = -99

    # make coordcatalogue for the catalogue
    # cat_2 = ICRS(ra_2, de_2, unit=(u.degree, u.degree))
    cat_2 = SkyCoord(ra_2, de_2, frame='icrs', unit=u.degree)

    # match the catalogue to the master table
    idx, d2d, d3d = match_coordinates_sky(cat_master, cat_2)

    # get the coordinate matches and determine the position off-set
    # in ra, de, and total
    matches = cat_2[idx]
    dra = (matches.ra - cat_master.ra).arcsec
    dde = (matches.dec - cat_master.dec).arcsec

    # make the other matches for flags, etc.
    match_mag = mag_2[idx]
    match_mage = mage_2[idx]
    match_ra = ra_2[idx]
    match_de = de_2[idx]
    match_fwhm = fwhm_2[idx]
    match_flag = flag_2[idx]
    match_edge = edge_2[idx]
    match_d2d = d2d.arcsec

    # take the matches within a given distance (no flags) and determine photometry
    # offset of catalogue to master table
    check = numpy.where((match_mag > min_use) & (match_mag < max_use) & (match_d2d < POS_OFFSET)
                        & (flag_m < 10) & (match_flag < 10))

    # determine the median photometric offset as start for the fitting
    med_offset = numpy.median(mag_m[check[0]] - match_mag[check[0]])

    # do the fitting
    # but remove outliers +-0.3mag based on the above med_offset
    if o.orignal_filter.upper() in settings.HA_FILTERS:
        check = numpy.where((numpy.absolute(mag_m - match_mag - med_offset) < 0.75) & (match_mag > min_use) & (match_mag < max_use) & (match_d2d < POS_OFFSET) & (flag_m < 10) & (match_flag < 10))
    else:
        check = numpy.where((match_mag > min_use) & (match_mag < max_use) & (match_d2d < POS_OFFSET) & (flag_m < 10) & (match_flag < 10))

    min_use = numpy.min(match_mag[check[0]])

    max_use = numpy.max(match_mag[check[0]])

    cal_mag = fitfunc_cal(param_cal, match_mag[:])
    diff_mag = mag_m[check[0]] - cal_mag[check[0]]

    # fill in the main arrays with the data from the catalogue,
    # but only for good matches, and use corrected magnitudes
    mag_array = numpy.zeros(len(mag_2), dtype=float)

    mag_array[:] = fitfunc_cal(param_cal, mag_2[:])

    # All stars in mag_array that are too bright
    check_flag_bright = numpy.where(mag_array < fitfunc_cal(param_cal, min_use))
    flag_2[check_flag_bright[0]] = flag_2[check_flag_bright[0]] + 256

    # All stars in mag_array that are too faint
    check_flag_faint = numpy.where(mag_array > fitfunc_cal(param_cal, max_use))
    flag_2[check_flag_faint[0]] = flag_2[check_flag_faint[0]] + 512

    # All stars in mag_array that are in the right place, but don't have the right flag
    check_flag_middle = numpy.where((mag_array > fitfunc_cal(param_cal, max_use)) &
                                    (mag_array < fitfunc_cal(param_cal, min_use)) & (flag_2 != 0))
    flag_2[check_flag_middle[0]] = flag_2[check_flag_middle[0]] + 1024

    # All stars that are just right (with some that aren't too...)
    check_flag_error = numpy.where((mag_array < fitfunc_cal(param_cal, max_use)) &
                                   (mag_array > fitfunc_cal(param_cal, min_use)))

    # Create array for uncertainties
    uncertainty_stars = numpy.zeros(len(mag_2), dtype=float)

    for i in check_flag_error[0]:
        # Get all stars within 1 magnitude of the star we are looking at
        check_within_1mag = numpy.where(
            (cal_mag[check[0]] > mag_array[i] - 0.75) & (cal_mag[check[0]] < mag_array[i] + 0.75))

        if len(check_within_1mag[0]) > 0:
            rms = 3.0 * numpy.nanmedian(numpy.absolute(diff_mag[check_within_1mag[0]]))

            check_within_1mag_2 = numpy.where((numpy.abs(diff_mag[check_within_1mag[0]]) < rms))

            rms = numpy.nanstd(diff_mag[check_within_1mag[0][check_within_1mag_2[0]]])

            uncertainty_stars[i] = rms

            phot = Photometry.objects.filter(observation=o, x=x_2[i], y=y_2[i], fwhm_world=fwhm_2[i], magnitude_rms_error=mage_2[i], flags=flag_2[i])

            if len(phot) == 1:
                phot[0].calibrated_error = rms
                phot[0].save()

    print "Observation " + str(o.id) + " complete"
