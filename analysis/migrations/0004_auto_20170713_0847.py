# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-13 08:47
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0003_imagingdevice'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='imagingdevice',
            name='naxis1',
        ),
        migrations.RemoveField(
            model_name='imagingdevice',
            name='naxis2',
        ),
        migrations.AddField(
            model_name='observation',
            name='device',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='analysis.ImagingDevice'),
            preserve_default=False,
        ),
    ]