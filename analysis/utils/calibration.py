import matplotlib
from matplotlib import figure
matplotlib.use('Agg')

import numpy
from django.conf import settings
from astropy.io import ascii
from astropy.coordinates import SkyCoord, match_coordinates_sky
import astropy.units as u
import matplotlib.pyplot as plt
from scipy.signal import medfilt
from scipy import optimize
from analysis.models import FITSFile, Observation, Photometry, TemporaryPhotometry
import os
import pyfits

SKIP_ROWS_IN_CAT = 9  # number of rows to skip in photometry tables
POS_OFFSET = 3  # off-set in arcsec to be considered match (in ra and dec)n ----- change this to 1


def fitfunc_cal(p, mag_s):
    """
    Polynomial fitting function for a magnitude
    :param p:
    :param mag_s:
    :return:
    """
    # some exponential function
    # z = mag_s + p[0] + p[1] * numpy.exp(p[2]*(mag_s))
    # some polynomials of various degrees
    # z = mag_s + p[0] + p[1] * mag_s + p[2] * (mag_s**2) + p[3] * (mag_s**3) + p[4] * (mag_s**4)
    # the Hill Function
    # z = p[0] + (p[1] * (mag_s**p[2])) / ((p[3]**p[2]) + (mag_s**p[2]))
    # the photofunction
    # z = mag_s + p[0] + p[1]*numpy.log10(10**(p[2]*(mag_s-p[3])) + 1.) + 0.0*p[4]
    # the photofunction + polynomial
    z = p[0] + p[1] * numpy.log10(10 ** (p[2] * (mag_s - p[3])) + 1.) + p[4] * mag_s + p[5] * (mag_s ** 2) + \
        p[6] * (mag_s ** 3) + p[7] * (mag_s ** 4)
    return z


def errfunc_cal(p, mag_m, mag_s):
    """
    weight error function by inverse square of magnitudes to ensure no systematic
    off sets at bright mags
    :param p:
    :param mag_m:
    :param mag_s:
    :return:
    """
    err = (mag_m - fitfunc_cal(p, mag_s)) / (mag_s - 8) / (mag_s - 8)
    # print "p", p
    return err


def array_format(myarray, arr_format):
    """
    Format an array for output - by putting a space between items
    :param myarray:
    :param arr_format:
    :return:
    """
    string = ''
    for item in myarray:
        string += arr_format % item + ' '
    return string


def do_calibration(file_id, max_use, min_use):
    """
    Run the calibration on a particular file in the database. Put the calibrated magnitudes back into the database, and
    also write them out to a file.
    :param file_id: The ID of the file in the database
    :return:
    """

    fits_file = FITSFile.objects.get(pk=file_id)
    observation = Observation.objects.get(fits=fits_file)

    edge_dist = 10
    # the calibration offset to get instrumental into apparent mag
    # needs to be calculated at some stage, start with gettting from db
    cal_offset = observation.target.cal_offset

    # Read in the first catalogue and create arrays with the data contained within it
    mastercat = ascii.read(os.path.join(settings.MASTER_CATALOGUE_DIRECTORY, str(observation.target.number),
                                        'cf_' + observation.filter + '.cat'))

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
    data, header = pyfits.getdata(os.path.join(settings.FITS_DIRECTORY, fits_file.fits_filename),
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

    # If no max use is specified, then generate one
    if max_use == 0:
        # determine the maximum usable magnitude for the image
        binsies = numpy.zeros(80, dtype=numpy.float32).reshape(80)
        for i in range(0, 80):
            binsies[i] = i / 4.
        check = numpy.where(mag_2[:] > 0.0)
        hist, bin_edges = numpy.histogram(mag_2[check[0]], bins=binsies)
        max_use = binsies[numpy.argmax(hist)]

    # If no min use is specified then generate one
    if min_use == 0:
        check = numpy.where((flag_2[:] == 0) & (mag_2[:] > -50))
        min_use = numpy.min(mag_2[check[0]])

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
                        & (flag_m == 0) & (match_flag == 0))

    # check=numpy.where( (numpy.absolute(dra) < POS_OFFSET) & (numpy.absolute(dde) < POS_OFFSET ) & (flag_m <= 8) &
    # (match_flag <= 8))


    # determine the median photometric offset as start for the fitting
    med_offset = numpy.median(mag_m[check[0]] - match_mag[check[0]])

    # do the fitting
    # but remove outliers +-0.3mag based on the above med_offset
    check = numpy.where((match_mag > min_use) & (match_mag < max_use) & (match_d2d < POS_OFFSET) & (flag_m == 0) &
                        (match_flag == 0))

    starsused = len(check[0])

    try:
        min_use = numpy.min(match_mag[check[0]])

        print 'min use', min_use

        # commented out until better soloution is found
        # # determine the maximum usable magnitude for the image
        # binsies = numpy.zeros(80, dtype=numpy.float32).reshape(80)
        # for i in range(0, 80):
        #     binsies[i] = i / 4.
        # hist, bin_edges = numpy.histogram(match_mag[check[0]], bins=binsies)
        # max_use = binsies[numpy.argmax(hist)]

        max_use = numpy.max(match_mag[check[0]])

        #print 'hist ##########'
        #print hist
        #print '############'

    except ValueError:
        print 'no catalog matches!!'
        return False, "No stars in your photometry catalog matched with the master catalog. Are you sure you chose the" \
                      "right region?"

    # for photofunction + 4th order polynomial fit
    parameters = [med_offset, 0, 0, 0, 0, 0, 0, 0]
    # for Hill Function
    # parameters=[med_offset,0,1,20]
    numbers_fit = len(check[0])

    print "use ", numbers_fit, " stars for photometry fit"
    # only fit if there are enough stars for fit, i.e. 5
    if numbers_fit > 10:
        # order the mags to median filter the M vs delta_M plot
        order = numpy.argsort(match_mag[check[0]])
        x = match_mag[check[0]][order]
        y = mag_m[check[0]][order] - match_mag[check[0]][order]
        yy = y
        for i in range(0, len(y)):
            # maybe in future change the filter size to number of stars within yy mag
            filsize = numpy.rint(numpy.rint(x[i] ** 2 / 100.) * 2 + 1)
            yy[i] = medfilt(y, filsize.astype(int))[i]
        param_cal, success = optimize.leastsq(errfunc_cal, parameters, args=(y + x, x))
        print param_cal

        # med_offset = numpy.mean(mag_m[check[0]]-match_mag[check[0]])
        # print mag_m[check[0]]-match_mag[check[0]]
        rmscal = numpy.sqrt(numpy.nanmean((mag_m[check[0]] - match_mag[check[0]] - med_offset) ** 2))

        # plot the mags against each other for checking
        print "RMS, offset"
        print rmscal, med_offset


        fig = figure.Figure()

        axis1 = fig.add_subplot(211)

        # MedFilter line plot
        axis1.plot(x, yy, 'b-', lw=2, label='Median filtered data')
        # Fit function line plot
        # axis1.plot(x, mag_m[check[0]][order] - fitfunc_cal(param_cal, mag_m[check[0]][order] - yy) + med_offset, 'r-',
        # lw=2)

        # 0 line of blue dots
        axis1.scatter(match_mag[check[0]], med_offset + 0 * mag_m[check[0]], s=5, c="blue", edgecolor='black',
                      alpha=0.8, label='Zero line', lw=0.2)

        # Original data plot scatter
        axis1.scatter(match_mag[check[0]], mag_m[check[0]] - match_mag[check[0]], s=5, c="black", edgecolor='black',
                      alpha=0.8, label='Original data', lw=0.2)
        # Max use line
        axis1.axvline(x=max_use, c='green', label='max_use')

        # Min use line
        axis1.axvline(x=min_use, c='yellow', label='min_use')

        # Set the Y limits on the first figure
        ylim_min = numpy.min(mag_m[check[0]] - match_mag[check[0]]) - 0.05

        ylim_max = numpy.max(mag_m[check[0]] - match_mag[check[0]]) + 0.05

        # if ylim_min < -0.5:
        #     ylim_min = -0.5 + med_offset
        #
        # if ylim_max > 0.5:
        #     ylim_max = 0.5 + med_offset

        axis1.set_ylim((ylim_min, ylim_max))

        axis1.legend(loc='center', bbox_to_anchor=(0.5, -0.25), ncol=5, fontsize='x-small')

        axis1.set_ylabel('Offset [mag]')
        axis1.set_xlabel('Uncalibrated Magnitude [mag]')

        axis2 = fig.add_subplot(212)

        # Calibrated magnitudes
        cal_mag = fitfunc_cal(param_cal, match_mag[:])

        # Conditions for the dots to be plotted - magnitude less than 30 but greater than 5
        check_plot = numpy.where((cal_mag[:] < 30) & (cal_mag[:] > 5))

        # Scatter plot of calibrated magnitudes (sensible magnitudes)
        axis2.scatter(cal_mag[check_plot[0]], mag_m[check_plot[0]] - cal_mag[check_plot[0]], s=1, c="black",
                    edgecolor='black', alpha=0.8, label='Calibrated magnitudes (<30 & >5)', lw=0.2)

        # Set up some arrays to use later in the file writing stage, with good data
        mag_m_good = mag_m[check[0]]
        cal_mag_good = cal_mag[check[0]]
        diff_mag = mag_m[check[0]] - cal_mag[check[0]]
        diff_mag_2 = mag_m[check_plot[0]] - cal_mag[check_plot[0]]

        # Scatter plot of calibrated magnitudes between min and max mag
        axis2.scatter(cal_mag[check[0]], mag_m[check[0]] - cal_mag[check[0]], s=5, c="red",
                    edgecolor='black', alpha=0.8, label='Calibrated magnitudes', lw=0.2)


        # Zero line of blue dots
        axis2.scatter(cal_mag[check[0]], 0 * cal_mag[check[0]], s=5, c="blue", edgecolor='black', alpha=0.8,
                      label='Zero line', lw=0.2)

        # Max use line
        axis2.axvline(x=fitfunc_cal(param_cal, max_use), c='green', label='max_use')

        # Min use line
        axis2.axvline(x=fitfunc_cal(param_cal, min_use), c='yellow', label='min_use')

        # Set the X and Y limits of the lines on the second figure
        ylim_min = numpy.min(mag_m[check[0]] - cal_mag[check[0]]) - 0.05

        ylim_max = numpy.max(mag_m[check[0]] - cal_mag[check[0]]) + 0.05

        if ylim_min < -0.5:
            ylim_min = -0.5

        if ylim_max > 0.5:
            ylim_max = 0.5

        axis2.set_xlim((numpy.min(cal_mag[check[0]]) - 0.5, numpy.max(cal_mag[check[0]]) + 0.5))
        axis2.set_ylim((ylim_min, ylim_max))

        axis2.set_ylabel('Offset [mag]')
        axis2.set_xlabel('Calibrated Magnitude [mag]')

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

        # Iterate over all our stars to calculate the median and rms for them
        for i in check_flag_error[0]:
            # Get all stars within 1 magnitude of the star we are looking at
            check_within_1mag = numpy.where((cal_mag[check[0]] > mag_array[i] - 0.75) & (cal_mag[check[0]] < mag_array[i] + 0.75))

            if len(check_within_1mag[0]) > 0:
                # median = numpy.median(diff_mag[check_within_1mag[0]])

                rms = numpy.nanstd(diff_mag[check_within_1mag[0]])

                check_within_1mag_2 = numpy.where((numpy.abs(diff_mag[check_within_1mag[0]]) < 4.0 * rms))

                rms = numpy.nanstd(diff_mag[check_within_1mag[0][check_within_1mag_2[0]]])

                #print diff_mag[check_within_1mag[0][check_within_1mag_2[0]]]

                #print rms, mag_array[i]

                uncertainty_stars[i] = rms

        axis2.scatter(mag_array, uncertainty_stars, s=5., c="green", marker="o", edgecolor='black', lw=0.2, alpha=1, label='Uncertainty')

        axis2.scatter(mag_array, -uncertainty_stars, s=5., c="green", marker="o", edgecolor='black', lw=0.2, alpha=1)

        axis2.legend(loc='center', bbox_to_anchor=(0.5, -0.25), ncol=5, fontsize='x-small')

        # We've moved the image generation down here as we want to add the rms points to the graph too.
        fig.tight_layout()
        fig.set_size_inches(7, 8)

        # Save the calibration plot to the plots directory
        fig.savefig(os.path.join(settings.PLOTS_DIRECTORY, fits_file.fits_filename
                                 + '.png'), format='png', bbox_inches='tight', dpi=600)
        # Purge figure from memory
        fig.clf()
        plt.close()


        # determine the limiting magnitude of each image
        binsies = numpy.zeros(80, dtype=numpy.float32).reshape(80)
        for i in range(0, 80):
            binsies[i] = i / 4.
        check = numpy.where(cal_mag_good[:] > 0.0)
        hist, bin_edges = numpy.histogram((cal_mag_good[check[0]]), bins=binsies)
        maglim = binsies[numpy.argmax(hist)]

        ################################
        # write out the photometric catalogue for each image
        # with the calibrated magnitudes and some additional
        # header information for easier access by further
        # software to analyse data

        # set filename for output catalogue
        phot_cal = os.path.join(settings.CATALOGUE_PROCESSED_DIRECTORY,
                                fits_file.fits_filename + '.cat')
        # open file for writing
        photcalfile = open(phot_cal, 'w')

        # write out the header info about file organisation
        photcalfile.write("#   1 NUMBER                 Running object number \n" % ())
        photcalfile.write(
            "#   2 MAG_CAL                Calibrated Kron-like elliptical aperture magnitude         [mag] \n" % ())
        photcalfile.write(
            "#   2 MAG_CAL_ERR            Error of MAG_CAL                                           [mag] \n" % ())
        photcalfile.write(
            "#   4 X_IMAGE                Object position along x                                    [pixel] \n" % ())
        photcalfile.write(
            "#   5 Y_IMAGE                Object position along y                                    [pixel] \n" % ())
        photcalfile.write(
            "#   6 ALPHA_J2000            Right ascension of barycenter (J2000)                      [deg] \n" % ())
        photcalfile.write(
            "#   7 DELTA_J2000            Declination of barycenter (J2000)                          [deg] \n" % ())
        photcalfile.write(
            "#   8 FWHM_WORLD             FWHM assuming a gaussian core                              [deg] \n" % ())
        photcalfile.write(
            "#   9 FLAGS                  Extraction flags    \n" % ())
        photcalfile.write(
            "#  10 MAG_AUTO               Kron-like elliptical aperture magnitude                    [mag] \n" % ())
        photcalfile.write(
            "#  11 MAGERR_AUTO            RMS error for AUTO magnitude                               [mag] \n" % ())
        # etc

        # write out some summary stats for the file
        photcalfile.write("# Extra info in first line contains: \n" % ())
        photcalfile.write("# a) Time of Observations [days] \n" % ())
        photcalfile.write("# b) Number of detected stars \n" % ())
        photcalfile.write("# c) Number of detected stars used for calibration \n" % ())
        photcalfile.write("# d) Median Offset in calibration [mag] \n" % ())
        photcalfile.write("# e) Limiting Magnitude [mag] \n" % ())
        photcalfile.write("# f) Fit parameters in calibration \n" % ())

        photcalfile.write("%12.4s %5.0s %5.0s %6.0s %6.3s %s \n" % (time, len(num_2), numbers_fit, med_offset, maglim,
                                                                    array_format(param_cal, '%s')))

        observation.deteced_stars_calibration = numbers_fit
        observation.detected_stars = len(num_2)
        observation.med_offset = med_offset
        observation.limiting_magnitude = maglim
        observation.calibration_parameters = array_format(param_cal, '%s')

        observation.save()

        if str(med_offset) == 'nan':
            med_offset = 0

        # With thanks to https://stackoverflow.com/questions/18383471/django-bulk-create-function-example for the
        # example on how to use the bulk_create function so we don't thrash the DB

        phot_objects = [
            TemporaryPhotometry(
                calibrated_magnitude=fitfunc_cal(param_cal, mag_2[i]) if not numpy.isnan(fitfunc_cal(param_cal, mag_2[i])) else None,
                calibrated_error=uncertainty_stars[i] if not numpy.isnan(uncertainty_stars[i]) else None,
                magnitude_rms_error=mage_2[i] if not numpy.isnan(mage_2[i]) else None,
                x=x_2[i] if not numpy.isnan(x_2[i]) else None,
                y=y_2[i] if not numpy.isnan(y_2[i]) else None,
                alpha_j2000=ra_2[i] if not numpy.isnan(ra_2[i]) else None,
                delta_j2000=de_2[i] if not numpy.isnan(de_2[i]) else None,
                fwhm_world=fwhm_2[i] if not numpy.isnan(fwhm_2[i]) else None,
                flags=flag_2[i] if not numpy.isnan(flag_2[i]) else None,
                magnitude=mag_2[i] if not numpy.isnan(mag_2[i]) else None,
                observation=observation,
            )
            for i in range(0, len(num_2))
        ]

        TemporaryPhotometry.objects.bulk_create(phot_objects)

        for i in range(0, len(num_2)):
            photcalfile.write("%5.0f %8.4f %6.4f %8.3f %8.3f %11.7f %11.7f %11.9f %3.0f %8.4f %6.4f\n" %
                              (i + 1, fitfunc_cal(param_cal, mag_2[i]), uncertainty_stars[i], x_2[i], y_2[i], ra_2[i], de_2[i],
                               fwhm_2[i], flag_2[i], mag_2[i], mage_2[i]))

        # close file after writing
        photcalfile.close()

        ################################

        print "med_offset, starsused, mag_lim, date"
        print med_offset, starsused, maglim, time

        if numpy.average(uncertainty_stars) > 0.02:
            return 'warning', "Are you sure you chose the right filter? Uncertainty greater than 0.2 mag."

        return True, "Success"
    else:
        return False, "There were not enough stars to calibrate with"
