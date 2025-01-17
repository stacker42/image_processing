# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-19 10:14
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0002_auto_20170718_1357'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagingdevice',
            name='time_card',
            field=models.CharField(blank=True, max_length=9, null=True),
        ),
        migrations.AlterField(
            model_name='fitsfile',
            name='process_status',
            field=models.CharField(choices=[('UPLOADED', 'Uploaded'), ('DEVICESETUP', 'Device setup'), ('HEADER', 'Header check'), ('OBSERVATION', 'Add observation details'), ('ASTROMETRY', 'Astrometry'), ('PHOTOMETRY', 'Photometry'), ('CALIBRATION', 'Calibration'), ('COMPLETE', 'Processing complete'), ('FAILED', 'Processing failed'), ('FAILED_USER', 'User invoked processing failed'), ('CHECK_ASTROMETRY', 'Check whether astrometry was successful'), ('CHECK_PHOTOMETRY', 'Check whether astrometry was successful'), ('CHECK_CALIBRATION', 'Check whether astrometry was successful')], max_length=255),
        ),
    ]
