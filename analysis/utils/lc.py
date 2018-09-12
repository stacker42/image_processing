import numpy
from ..models import Photometry
from ..forms import LightcurveSearchForm
from astropy.coordinates import SkyCoord
from astropy import units as u
import numpy
from operator import itemgetter
from scipy.spatial import distance_matrix
from scipy.cluster.hierarchy import linkage, fcluster
import scipy.spatial.distance as ssd
from django.shortcuts import render
from django.conf import settings


def index_stars(coords, radius, dec, request, form=LightcurveSearchForm()):
    """
    Get the lightcurve data for a set of coordinates
    :param coords:
    :param radius:
    :param dec:
    :param form:
    :return:
    """
    # Get all stars within radius
    stars = Photometry.objects.raw(
        "SELECT * FROM photometry WHERE alpha_j2000 BETWEEN %s-(%s/3600 / COS(%s * PI() / 180)) AND "
        "%s+(%s/3600 / COS(%s * PI() / 180)) AND delta_j2000 BETWEEN %s-%s/3600 AND %s+%s/3600;",
        [coords.ra.degree, radius, dec, coords.ra.degree, radius, dec, dec,
         radius, dec, radius])

    lightcurve_data = {}

    lightcurve_data['stars'] = []
    lightcurve_data['filters'] = []
    for star in stars:
        if star.observation.orignal_filter.upper() in settings.HA_FILTERS:
            lightcurve_data['stars'].append({'date': star.observation.date,
                                             'calibrated_magnitude': star.calibrated_magnitude,
                                             'alpha_j2000': float(star.alpha_j2000),
                                             'delta_j2000': float(star.delta_j2000),
                                             'calibrated_error': star.calibrated_error,
                                             'id': star.id,
                                             'filter': 'HA',
                                             'original_filter': star.observation.orignal_filter,
                                             'x': star.x,
                                             'y': star.y,
                                             'magnitude_rms_error': star.magnitude_rms_error,
                                             'fwhm_world': star.fwhm_world,
                                             'observation_id': star.observation_id,
                                             'user_id': star.observation.user_id,
                                             'target': star.observation.target,
                                             'flags': star.flags,
                                             'magnitude': star.magnitude,
                                             'device_id': star.observation.device_id,
                                             'fits_id': star.observation.fits.id})
            lightcurve_data['filters'].append('HA')
        else:
            lightcurve_data['stars'].append({'date': star.observation.date,
                                             'calibrated_magnitude': star.calibrated_magnitude,
                                             'alpha_j2000': float(star.alpha_j2000),
                                             'delta_j2000': float(star.delta_j2000),
                                             'calibrated_error': star.calibrated_error,
                                             'id': star.id,
                                             'filter': star.observation.filter,
                                             'original_filter': star.observation.orignal_filter,
                                             'x': star.x,
                                             'y': star.y,
                                             'magnitude_rms_error': star.magnitude_rms_error,
                                             'fwhm_world': star.fwhm_world,
                                             'observation_id': star.observation_id,
                                             'user_id': star.observation.user_id,
                                             'target': star.observation.target,
                                             'flags': star.flags,
                                             'magnitude': star.magnitude,
                                             'device_id': star.observation.device_id,
                                             'fits_id': star.observation.fits.id})
            lightcurve_data['filters'].append(star.observation.filter)

    # No stars for the coords? Then we can't continue
    if len(lightcurve_data['stars']) == 0:
        return None, None

    # Get rid of duplicates
    lightcurve_data['filters'] = list(set(lightcurve_data['filters']))

    # Build up some lists of stars, co-ordinates and magnitudes
    stars_for_filter = sorted(lightcurve_data['stars'], key=itemgetter('calibrated_magnitude'), reverse=True)
    coord_list = numpy.array(
        [map(itemgetter('alpha_j2000'), stars_for_filter), map(itemgetter('delta_j2000'), stars_for_filter)])
    mag_list = numpy.array(map(itemgetter('calibrated_magnitude'), stars_for_filter))

    sep = distance_matrix(numpy.transpose(coord_list), numpy.transpose(coord_list))

    square = ssd.squareform(sep * 3600.)

    linkage_of_square = linkage(square, 'single')

    clusters = fcluster(linkage_of_square, 3, criterion='distance')

    median_ra = numpy.zeros(int(numpy.max(clusters)), dtype=float)
    median_dec = numpy.zeros(int(numpy.max(clusters)), dtype=float)
    median_mag = numpy.zeros(int(numpy.max(clusters)), dtype=float)

    lightcurve_data['seperated'] = {}
    lightcurve_data['medianmag'] = {}

    array_stars = numpy.asarray(lightcurve_data['stars'])

    lightcurve_data['count'] = {}
    lightcurve_data['median_mag_filters'] = {}

    # Build up the lists of indexed stars
    for i in range(0, len(median_ra)):
        check_in_index_array = numpy.where(clusters == i + 1)
        median_ra[i] = numpy.median(coord_list[0][check_in_index_array[0]])
        median_dec[i] = numpy.median(coord_list[1][check_in_index_array[0]])
        median_mag[i] = numpy.min(mag_list[check_in_index_array[0]])
        key = str(median_ra[i]) + " " + str(median_dec[i])
        lightcurve_data['seperated'][key] = []

        lightcurve_data['seperated'][key] = array_stars[check_in_index_array[0]]
        lightcurve_data['medianmag'][key] = median_mag[i]
        lightcurve_data['count'][key] = len(lightcurve_data['seperated'][key])
        lightcurve_data['median_mag_filters'][key] = {}
        for f in lightcurve_data['filters']:
            lightcurve_data['median_mag_filters'][key][f] = numpy.median(numpy.array(map(itemgetter('calibrated_magnitude'), filter(lambda x: x['filter'] == f, lightcurve_data['seperated'][key]))))

    #user_choices_sc = sorted(SkyCoord(lightcurve_data['seperated'].keys(), unit=u.degree))

    #print user_choices_sc

    user_choices = lightcurve_data['seperated'].keys()

    return lightcurve_data, user_choices
