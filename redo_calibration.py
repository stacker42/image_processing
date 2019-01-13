import os

from django.core.wsgi import get_wsgi_application

os.environ['DJANGO_SETTINGS_MODULE'] = 'image_processing.settings'
application = get_wsgi_application()

from analysis.models import Observation, Photometry, FITSFile, Object
from django.db import connection
from django.conf import settings

FILTERS_REDOCALIB = ['V', 'R', 'I', 'B']

objects = Object.objects.all()
for obj in objects:
    print "obj id: " + str(obj.number)
    for filt in FILTERS_REDOCALIB:
        print "filt: " + str(filt)
        with connection.cursor() as cursor:
            cursor.execute("UPDATE photometry, observations SET photometry.calibrated_magnitude = photometry.calibrated_magnitude + %s WHERE observations.target_id = %s AND observations.filter = %s AND photometry.observation_id = observations.id;", [settings.OFFSETS[obj.number][filt], obj.number, filt])


