from __future__ import print_function

import pymysql.cursors
import argparse
import numpy
from astropy.coordinates import SkyCoord
from astropy import units as u
from operator import itemgetter
from scipy.spatial import distance_matrix
from scipy.cluster.hierarchy import linkage, fcluster
import scipy.spatial.distance as ssd

USER = 'sps_student'
PASSWORD = 'sps_student'


class NoStarsException(Exception):
    pass

HA_FILTERS = ['HA, ''A', 'A-BAND', 'HA-BAND', 'H-BAND', 'H BAND', 'HA BAND', 'H-ALPHA', 'H ALPHA']

def index_stars(coords, radius, dec):
    """
    Get the lightcurve data for a set of coordinates
    :param coords:
    :param radius:
    :param dec:
    :param form:
    :return:
    """
    with connection.cursor() as cursor:
        # Get all stars within radius
        sql = "SELECT * FROM photometry WHERE alpha_j2000 BETWEEN %s-(%s/3600 / COS(%s * PI() / 180)) AND %s+(%s/3600 / COS(%s * PI() / 180)) AND delta_j2000 BETWEEN %s-%s/3600 AND %s+%s/3600;"

        cursor.execute(sql, (coords.ra.degree, radius, dec, coords.ra.degree, radius, dec, dec, radius, dec, radius))

        stars = cursor.fetchall()

        print(stars)

    lightcurve_data = {}

    lightcurve_data['stars'] = []
    lightcurve_data['filters'] = []
    for star in stars:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM observations WHERE id = %s"
            cursor.execute(sql, (star['observation_id']))
            observation = cursor.fetchone()
        if observation['orignal_filter'].upper() in HA_FILTERS:
            lightcurve_data['stars'].append({'date': observation['date'],
                                             'calibrated_magnitude': star['calibrated_magnitude'],
                                             'alpha_j2000': float(star['alpha_j2000']),
                                             'delta_j2000': float(star['delta_j2000']),
                                             'calibrated_error': star['calibrated_error'],
                                             'id': star['id'],
                                             'filter': 'HA',
                                             'original_filter': observation['orignal_filter'],
                                             'x': star['x'],
                                             'y': star['y'],
                                             'magnitude_rms_error': star['magnitude_rms_error'],
                                             'fwhm_world': star['fwhm_world'],
                                             'observation_id': observation['id'],
                                             'user_id': observation['user_id'],
                                             'target': observation['target_id'],
                                             'flags': star['flags'],
                                             'magnitude': star['magnitude'],
                                             'device_id': observation['device_id'],
                                             'fits_id': observation['fits_id']})
            lightcurve_data['filters'].append('HA')
        else:
            lightcurve_data['stars'].append({'date': observation['date'],
                                             'calibrated_magnitude': star['calibrated_magnitude'],
                                             'alpha_j2000': float(star['alpha_j2000']),
                                             'delta_j2000': float(star['delta_j2000']),
                                             'calibrated_error': star['calibrated_error'],
                                             'id': star['id'],
                                             'filter': observation['filter'],
                                             'original_filter': observation['orignal_filter'],
                                             'x': star['x'],
                                             'y': star['y'],
                                             'magnitude_rms_error': star['magnitude_rms_error'],
                                             'fwhm_world': star['fwhm_world'],
                                             'observation_id': observation['id'],
                                             'user_id': observation['user_id'],
                                             'target': observation['target_id'],
                                             'flags': star['flags'],
                                             'magnitude': star['magnitude'],
                                             'device_id': observation['device_id'],
                                             'fits_id': observation['fits_id']})
            lightcurve_data['filters'].append(observation['filter'])

    # No stars for the coords? Then we can't continue
    if len(lightcurve_data['stars']) == 0:
        raise NoStarsException("No stars for input co-ordinates")

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

    user_choices = lightcurve_data['seperated'].keys()

    return lightcurve_data, user_choices


parser = argparse.ArgumentParser(description='Get lightcurve data')
parser.add_argument('coords', metavar='C', type=str, help='FK5 co-ordinates')
parser.add_argument('radius', metavar='R', type=float, help='radius')
args = parser.parse_args()

# Connect to the database
connection = pymysql.connect(host='localhost',
                             user=USER,
                             password=PASSWORD,
                             db='imageportal',
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)

# From here on out its the same setup as the website lightcurve plotting and download

coords = SkyCoord(args.coords, frame='fk5', unit=u.degree)

# Covert whatever we have got to FK5
coords = coords.transform_to('fk5')

radius = args.radius

if radius:
    radius = radius
else:
    radius = 5

if coords.dec.degree == 90:
    dec = 89.99999
else:
    dec = coords.dec.degree

lightcurve_data, user_choices = index_stars(coords, radius, dec)


for cluster in lightcurve_data['seperated']:
    for star in lightcurve_data['seperated'][cluster]:
        print([star['id'], star['calibrated_magnitude'], star['calibrated_error'], star['magnitude_rms_error'], star['x'],
             star['y'], star['alpha_j2000'], star['delta_j2000'], star['fwhm_world'], star['flags'], star['magnitude'],
             star['observation_id'], star['filter'], star['original_filter'],
             star['date'], star['user_id'], star['device_id'], star['target'], star['fits_id']])