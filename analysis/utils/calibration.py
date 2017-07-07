import matplotlib
matplotlib.use('Agg')

import numpy
from django.conf import settings
from astropy.io import ascii
from astropy.coordinates import SkyCoord, match_coordinates_sky
import astropy.units as u
import matplotlib.pyplot as plt
from scipy.signal import medfilt
from scipy import optimize
from analysis.models import FITSFile, Observation, Photometry
import os
import pyfits



# Global variables

SKIP_ROWS_IN_CAT = 9  # number of rows to skip in photometry tables
POS_OFFSET = 1  # off-set in arcsec to be considered match (in ra and dec)n ----- change this to 1


# define functions for model of photometri calibration
def fitfunc_cal(p, mag_s):
    # some exponential function
    # z = mag_s + p[0] + p[1] * numpy.exp(p[2]*(mag_s))
    # some polynomials of various degrees
    # z = mag_s + p[0] + p[1] * mag_s + p[2] * (mag_s**2) + p[3] * (mag_s**3) + p[4] * (mag_s**4)
    # the Hill Function
    # z = p[0] + (p[1] * (mag_s**p[2])) / ((p[3]**p[2]) + (mag_s**p[2]))
    # the photofunction
    # z = mag_s + p[0] + p[1]*numpy.log10(10**(p[2]*(mag_s-p[3])) + 1.) + 0.0*p[4]
    # the photofunction + polynomial
    z = mag_s + p[0] + p[1] * numpy.log10(10 ** (p[2] * (mag_s - p[3])) + 1.) + p[4] * mag_s + p[5] * (mag_s ** 2) + p[
                                                                                                                         6] * (
                                                                                                                     mag_s ** 3) + \
        p[7] * (mag_s ** 4)
    return z


def errfunc_cal(p, mag_m, mag_s):
    # weight error function by inverse square of magnitudes to ensure no systematic
    # off sets at bright mags
    err = (mag_m - fitfunc_cal(p, mag_s)) / (mag_s - 8) / (mag_s - 8)
    # print "p", p
    return err


def array_format(myarray, format):
    string = ''
    for item in myarray:
        string += format % item + ' '
    return string

# mastercat = ascii.read(settings.MASTER_CATALOGUE_FILE)


def do_calibration(file_id):

    fits_file = FITSFile.objects.get(pk=file_id)
    observation = Observation.objects.get(fits=fits_file)

    # read in the master catalogue and make individual arrays for the columns
    #mastercat = numpy.loadtxt(settings.MASTER_CATALOGUE_FILE, dtype='string', converters=None, usecols=None, unpack=False, skiprows=SKIP_ROWS_IN_CAT)

    mastercat = ascii.read(os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(observation.target.number) + '.cat'))

    max_use = observation.target.max_use  # maximum magnitude used to calibrate frames into each others system
    min_use = 0  # minimum magnitude used to calibrate frames into each others system
    edge_dist = 10
    # the calibration offset to get instrumental into apparent mag
    # needs to be calculated at some stage, start with defining it
    cal_offset = observation.target.cal_offset

    #num_m = numpy.array(mastercat[:, 0])
    num_m = numpy.array(mastercat['NUMBER'])
    num_m = num_m.astype(numpy.float32)

    #mag_m = numpy.array(mastercat[:, 1])
    mag_m = numpy.array(mastercat['MAG_AUTO'])
    # add the calibration offset to the master photometry
    mag_m = mag_m.astype(numpy.float32) + cal_offset


    #mage_m = numpy.array(mastercat[:, 2])
    mage_m = numpy.array(mastercat['MAGERR_AUTO'])
    mage_m = mage_m.astype(numpy.float32)


    #ra_m = numpy.array(mastercat[:, 5])
    ra_m = numpy.array(mastercat['ALPHA_J2000'])
    ra_m = ra_m.astype(numpy.float32)


    #de_m = numpy.array(mastercat[:, 6])
    de_m = numpy.array(mastercat['DELTA_J2000'])
    de_m = de_m.astype(numpy.float32)


    #fwhm_m = numpy.array(mastercat[:, 7])
    fwhm_m = numpy.array(mastercat['FWHM_WORLD'])
    fwhm_m = fwhm_m.astype(numpy.float32)


    #flag_m = numpy.array(mastercat[:, 8])
    flag_m = numpy.array(mastercat['FLAGS'])
    flag_m = flag_m.astype(numpy.float32)

    # replace the 99 values for objects without photometry to zero
    check99 = numpy.where(mag_m == 99)
    mag_m[check99[0]] = 0.0
    check99 = numpy.where(mage_m == 99)
    mage_m[check99[0]] = 0.0

    star_number = len(num_m)

    # make some arrays that are needed later
    #######################################
    mag_array = numpy.zeros(star_number, dtype=float)
    mage_array = numpy.zeros(star_number, dtype=float)
    ra_array = numpy.zeros(star_number, dtype=float)
    de_array = numpy.zeros(star_number, dtype=float)
    fwhm_array = numpy.zeros(star_number, dtype=float)
    flag_array = numpy.zeros(star_number, dtype=float)
    detection_count = numpy.zeros(star_number, dtype=float)
    time = ''
    # limiting magnitudes of each picture
    #maglim_array = numpy.zeros(file_number, dtype=float)
    maglim = 0
    # checks if the star is near the edge in any of the frames
    edge_array = numpy.zeros(star_number, dtype=float)
    # limiting coordinates of each picture
    #RA_MIN_array = numpy.zeros(file_number, dtype=float)
    #RA_MAX_array = numpy.zeros(file_number, dtype=float)
    #DE_MIN_array = numpy.zeros(file_number, dtype=float)
    #DE_MAX_array = numpy.zeros(file_number, dtype=float)
    RA_MIN = 0
    RA_MAX = 0
    DE_MIN = 0
    DE_MAX = 0
    # rms of calibration of photometry
    #rmscal_array = numpy.zeros(file_number, dtype=float)
    # Array to indicate if mags are detections (0), or lower/upper (-1,+1) limits
    photlim_array = numpy.zeros(star_number, dtype=float)

    # make coordcatalogue for the master table
    # cat_master = ICRS(ra_m, de_m, unit=(u.degree, u.degree))
    cat_master = SkyCoord(ra_m, de_m, frame='icrs', unit=u.degree)

    counter = 0

    # read in FITS header of corresponding image and get observing date
    # which is stored in header 'TIMETIME' by the 'change_header.py' program
    data, header = pyfits.getdata(os.path.join(settings.FITS_DIRECTORY, str(fits_file.id), fits_file.fits_filename),
                                  header=True)
    time = header['DATE-OBS']

    # get pixel numbers to check if star is near the edge
    xpix = header['NAXIS1']
    ypix = header['NAXIS2']

    secondcat = ascii.read(os.path.join(settings.CATALOGUE_DIRECTORY, str(fits_file.id), fits_file.catalogue_filename))
    #num_2 = numpy.array(secondcat[:, 0])
    num_2 = secondcat['NUMBER']
    num_2 = num_2.astype(numpy.float32)

    #mag_2 = numpy.array(secondcat[:, 1])
    mag_2 = secondcat['MAG_AUTO']
    mag_2 = mag_2.astype(numpy.float32)

    #mage_2 = numpy.array(secondcat[:, 2])
    mage_2 = secondcat['MAGERR_AUTO']
    mage_2 = mage_2.astype(numpy.float32)

    #ra_2 = numpy.array(secondcat[:, 5])
    ra_2 = secondcat['ALPHA_J2000']
    ra_2 = ra_2.astype(numpy.float64)

    #de_2 = numpy.array(secondcat[:, 6])
    de_2 = secondcat['DELTA_J2000']
    de_2 = de_2.astype(numpy.float64)

    #fwhm_2 = numpy.array(secondcat[:, 7])
    fwhm_2 = secondcat['FWHM_WORLD']
    fwhm_2 = fwhm_2.astype(numpy.float64)

    #flag_2 = numpy.array(secondcat[:, 8])
    flag_2 = secondcat['FLAGS']
    flag_2 = flag_2.astype(numpy.float32)

    #x_2 = numpy.array(secondcat[:, 3])
    x_2 = secondcat['X_IMAGE']
    x_2 = x_2.astype(numpy.float32)

    #y_2 = numpy.array(secondcat[:, 4])
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
    check_edge = numpy.where(
        x_2 < edge_dist)  # or (y_2 < edge_dist) or (ypix-y_2 < edge_dist) or (xpix-x_2 < edge_dist))
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

    print "#########################################"
    print "number of stars in catalogue:", len(num_2)

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
    match_flag = flag_2[idx]
    match_mag = mag_2[idx]
    match_mage = mage_2[idx]
    match_ra = ra_2[idx]
    match_de = de_2[idx]
    match_fwhm = fwhm_2[idx]
    match_flag = flag_2[idx]
    match_edge = edge_2[idx]

    print 'mag_m '
    print mag_m

    print 'min_use '
    print min_use

    print 'max_use '
    print max_use

    print 'dra '
    print dra

    print 'POS_OFFSET '
    print POS_OFFSET

    print 'dde '
    print dde

    print 'flag_m '
    print flag_m

    print 'match_flag '
    print match_flag

    print 'match_mag '
    print match_mag

    # take the matches within a given distance (no flags) and determine photometry
    # offset of catalogue to master table
    check = numpy.where((mag_m > min_use) & (mag_m < max_use) & (numpy.absolute(dra) < POS_OFFSET) & (
        numpy.absolute(dde) < POS_OFFSET) & (flag_m == 0) & (match_flag == 0) & ((mag_m - match_mag) < 5.))

    print '## check ##############################'

    print check

    print '#######################################'

    # check=numpy.where( (numpy.absolute(dra) < POS_OFFSET) & (numpy.absolute(dde) < POS_OFFSET ) & (flag_m <= 8) & (match_flag <= 8))
    starsused = len(check[0])

    # determine the median photometric offset as start for the fitting
    med_offset = numpy.median(mag_m[check[0]] - match_mag[check[0]])

    print '#### med offset ###################################'

    print med_offset

    print '###################################################'

    # do the fitting
    # but remove outliers +-0.3mag based on the above med_offset
    check = numpy.where(
        (numpy.absolute(mag_m - match_mag - med_offset) < 0.3) & (mag_m > min_use) & (mag_m < max_use) & (
            numpy.absolute(dra) < POS_OFFSET) & (numpy.absolute(dde) < POS_OFFSET) & (flag_m == 0) & (
            match_flag == 0) & (
            (mag_m - match_mag) < 5.))

    print '#### fitting check ####################################'

    print check

    print '#######################################################'

    # for photofunction + 4th order polynomial fit
    parameters = [med_offset, 0, 0, 0, 0, 0, 0, 0]
    # for Hill Function
    # parameters=[med_offset,0,1,20]
    numbers_fit = len(check[0])

    print "use ", numbers_fit, " stars for photometry fit"
    # only fit if there are enough stars for fit, i.e. 5
    if (numbers_fit > 5):

        # order the mags to median filter the M vs delta_M plot
        order = numpy.argsort(mag_m[check[0]])
        x = mag_m[check[0]][order]
        y = mag_m[check[0]][order] - match_mag[check[0]][order]
        yy = y
        for i in range(0, len(y)):
            # maybe in future change the filter size to number of stars within XX mag
            filsize = numpy.rint(numpy.rint(x[i] ** 2 / 100.) * 2 + 1)
            yy[i] = medfilt(y, filsize.astype(int))[i]
        param_cal, success = optimize.leastsq(errfunc_cal, parameters, args=(x, x - yy))
        print param_cal

        # med_offset = numpy.mean(mag_m[check[0]]-match_mag[check[0]])
        # print mag_m[check[0]]-match_mag[check[0]]
        rmscal = numpy.sqrt(numpy.nanmean((mag_m[check[0]] - match_mag[check[0]] - med_offset) ** 2))

        # plot the mags against each other for checking
        print "RMS, offset"
        print rmscal, med_offset

        os.mkdir(os.path.join(settings.PLOTS_DIRECTORY, str(fits_file.id)))

        rectangle1 = [0.1, 0.1, 0.8, 0.8]
        ax1 = plt.axes(rectangle1)
        plt.scatter(mag_m[check[0]], mag_m[check[0]] - match_mag[check[0]], s=5, c="black", edgecolor='black',
                    alpha=0.8)
        plt.scatter(mag_m[check[0]], mag_m[check[0]] - fitfunc_cal(param_cal, match_mag[check[0]]), s=5, c="red",
                    edgecolor='black', alpha=0.8)
        plt.scatter(mag_m[check[0]], 0 * mag_m[check[0]], s=5, c="blue", edgecolor='black', alpha=0.8)
        plt.scatter(mag_m[check[0]], med_offset + 0 * mag_m[check[0]], s=5, c="blue", edgecolor='black', alpha=0.8)

        plt.plot(x, yy, 'b-', lw=2)
        plt.plot(x, fitfunc_cal(param_cal, x) - x, 'r-', lw=2)
        # plt.show()
        # save the calibration plot
        plt.savefig(os.path.join(settings.PLOTS_DIRECTORY, str(fits_file.id), 'calibrationb_' + fits_file.fits_filename
                                 + '.png'), format='png',
                    bbox_inches='tight', dpi=600)
        plt.clf()

        # fill in the main arrays with the data from the catalogue,
        # but only for good matches, and use corrected magnitudes
    check = numpy.where((numpy.absolute(dra) < POS_OFFSET) & (numpy.absolute(dde) < POS_OFFSET))
    print '##############'
    print check[0]
    print '###############'

    # if the fit has been done
    if numbers_fit > 5:
        mag_array[check[0]] = fitfunc_cal(param_cal, match_mag[check[0]])
        # for the uncertainties we calculate the scatter of the matched stars with similar magnitude
        for i in check[0]:
            # select all stars within 1mag of star
            checkerr = numpy.where((numpy.absolute(dra) < POS_OFFSET) & (numpy.absolute(dde) < POS_OFFSET) & (
                mag_array[:] > 1.) & (numpy.abs(mag_array[i] - mag_array[:]) > 0) & (
                                       numpy.abs(mag_array[i] - mag_array[:]) < 0.5))
            # calculate the rms of these
            meanmag = numpy.mean(mag_array[checkerr[0]])
            mage_array[i] = 0.5 * numpy.sqrt(numpy.mean((mag_array[checkerr[0]] - meanmag) ** 2))
            # if there was no fit, just apply median offset
    if numbers_fit <= 10:
        mag_array[check[0]] = match_mag[check[0]] + med_offset
        # for the uncertainties we can just use the photometric errors
        mage_array[check[0]] = match_mage[check[0]]

    ra_array[check[0]] = match_ra[check[0]]
    de_array[check[0]] = match_de[check[0]]
    fwhm_array[check[0]] = match_fwhm[check[0]]
    flag_array[check[0]] = match_flag[check[0]]
    edge_array[check[0]] = match_edge[check[0]]

    # determine the limiting magnitude of each image
    binsies = numpy.zeros(80, dtype=numpy.float32).reshape(80)
    for i in range(0, 80):
        binsies[i] = i / 4.
    check = numpy.where(mag_array[:] > 0.0)
    hist, bin_edges = numpy.histogram((mag_array[check[0]]), bins=binsies)
    maglim = binsies[numpy.argmax(hist)]

    ################################
    # write out the photometric catalogue for each image
    # with the calibrated magnitudes and some additional
    # header information for easier access by further
    # software to analyse data

    # set filename for output catalogue
    phot_cal = os.path.join(settings.CATALOGUE_DIRECTORY, str(fits_file.id), fits_file.fits_filename + '_calibrated.cat')
    # open file for writing
    photcalfile = open(phot_cal, 'w')

    # write out the header info about file organisation
    photcalfile.write(("#   1 NUMBER                 Running object number \n") % ())
    photcalfile.write(
        ("#   2 MAG_CAL                Calibrated Kron-like elliptical aperture magnitude         [mag] \n") % ())
    photcalfile.write(
        ("#   3 MAGERR_AUTO            RMS error for AUTO magnitude                               [mag] \n") % ())
    photcalfile.write(
        ("#   4 X_IMAGE                Object position along x                                    [pixel] \n") % ())
    photcalfile.write(
        ("#   5 Y_IMAGE                Object position along y                                    [pixel] \n") % ())
    photcalfile.write(
        ("#   6 ALPHA_J2000            Right ascension of barycenter (J2000)                      [deg] \n") % ())
    photcalfile.write(
        ("#   7 DELTA_J2000            Declination of barycenter (J2000)                          [deg] \n") % ())
    photcalfile.write(
        ("#   8 FWHM_WORLD             FWHM assuming a gaussian core                              [deg] \n") % ())
    photcalfile.write(
        ("#   9 FLAGS                  Extraction flags    \n") % ())
    photcalfile.write(
        ("#  10 MAG_AUTO               Kron-like elliptical aperture magnitude                    [mag] \n") % ())
    # etc

    print 'num_2'
    print num_2
    print len(num_2)

    # write out some summary stats for the file
    photcalfile.write(("# Extra info in first line contains: \n") % ())
    photcalfile.write(("# a) Time of Observations [days] \n") % ())
    photcalfile.write(("# b) Number of detected stars \n") % ())
    photcalfile.write(("# c) Number of detected stars used for calibration \n") % ())
    photcalfile.write(("# d) Median Offset in calibration [mag] \n") % ())
    photcalfile.write(("# e) Limiting Magnitude [mag] \n") % ())
    photcalfile.write(("# f) Fit parameters in calibration \n") % ())
    if numbers_fit > 10:
        photcalfile.write("%12.4s %5.0s %5.0s %6.0s %6.3s %s \n" % (time, len(num_2), numbers_fit, med_offset, maglim,
                                                                    array_format(param_cal, '%s')))
    if numbers_fit <= 10:
        photcalfile.write("%12.4s %5.0s %5.0s %6.3s %6.3s \n" % (time, len(num_2), numbers_fit, med_offset, maglim))

        # write out the original catalogue but use calibrated mags instead of
        # mag_auto and add org mag_auto as column 10
        # if the fit has been done

    print 'num fit ' + str(numbers_fit)

    # With thanks to https://stackoverflow.com/questions/18383471/django-bulk-create-function-example for the
    # example on how to use the bulk_create function so we don't thrash the DB

    if numbers_fit > 10:
        phot_objects = [
            Photometry(
                calibrated_magnitude=fitfunc_cal(param_cal, mag_2[i]),
                magnitude_rms_error=mage_2[i],
                x=x_2[i],
                y=y_2[i],
                alpha_j2000=ra_2[i],
                delta_j2000=de_2[i],
                fwhm_world=fwhm_2[i],
                flags=flag_2[i],
                magnitude=mag_2[i],
                observation=observation,
            )
            for i in range(0, len(num_2))
        ]

        Photometry.objects.bulk_create(phot_objects)

    if numbers_fit <= 5:
        phot_objects = [
            Photometry(
                calibrated_magnitude=mag_2[i] + med_offset,
                magnitude_rms_error=mage_2[i],
                x=x_2[i],
                y=y_2[i],
                alpha_j2000=ra_2[i],
                delta_j2000=de_2[i],
                fwhm_world=fwhm_2[i],
                flags=flag_2[i],
                magnitude=mag_2[i],
                observation=observation,
            )
            for i in range(0, len(num_2))
        ]

        Photometry.objects.bulk_create(phot_objects)

    if numbers_fit > 10:
        for i in range(0, len(num_2)):
            print ("%5.0f %8.4f %6.4f %8.3f %8.3f %11.7f %11.7f %11.9f %3.0f %8.4f \n") % (i + 1, fitfunc_cal(param_cal, mag_2[i]), mage_2[i], x_2[i], y_2[i], ra_2[i], de_2[i], fwhm_2[i], flag_2[i], mag_2[i])
            photcalfile.write(("%5.0f %8.4f %6.4f %8.3f %8.3f %11.7f %11.7f %11.9f %3.0f %8.4f \n") % (i + 1, fitfunc_cal(param_cal, mag_2[i]), mage_2[i], x_2[i], y_2[i], ra_2[i], de_2[i], fwhm_2[i], flag_2[i], mag_2[i]))
            # if there was no fit, just apply median offset
    if numbers_fit <= 5:
        for i in range(0, len(num_2)):
            print ("%5.0f %8.4f %6.4f %8.3f %8.3f %11.7f %11.7f %11.9f %3.0f %8.4f \n") % (i + 1, mag_2[i] + med_offset, mage_2[i], x_2[i], y_2[i], ra_2[i], de_2[i], fwhm_2[i], flag_2[i], mag_2[i])
            photcalfile.write(("%5.0f %8.4f %6.4f %8.3f %8.3f %11.7f %11.7f %11.9f %3.0f %8.4f \n") % (i + 1, mag_2[i] + med_offset, mage_2[i], x_2[i], y_2[i], ra_2[i], de_2[i], fwhm_2[i], flag_2[i], mag_2[i]))

            # close file after writing
    photcalfile.close()

    ################################

    print "med_offset, starsused, mag_lim, date"
    print med_offset, starsused, maglim, time
