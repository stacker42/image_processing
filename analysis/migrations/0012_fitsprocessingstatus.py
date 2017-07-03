# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-03 13:31
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0011_auto_20170703_0858'),
    ]

    operations = [
        migrations.CreateModel(
            name='FITSProcessingStatus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('header', models.BooleanField()),
                ('add', models.BooleanField()),
                ('astrometry', models.BooleanField()),
                ('photometry', models.BooleanField()),
                ('calibration', models.BooleanField()),
                ('current', models.CharField(choices=[('HEADER', 'Header check'), ('IMPORT', 'Add to database'), ('ASTROMETRY', 'Astrometry'), ('PHTOMETRY', 'Photometry'), ('CALIBRATION', 'Calibration')], max_length=255)),
                ('file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='analysis.FITSFile')),
            ],
            options={
                'db_table': 'fits_processing_status',
            },
        ),
    ]
