# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-08-22 14:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0008_auto_20170721_1500'),
    ]

    operations = [
        migrations.AddField(
            model_name='object',
            name='cf_B_original',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='object',
            name='cf_CV_original',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='object',
            name='cf_I_original',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='object',
            name='cf_R_original',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='object',
            name='cf_SZ_original',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='object',
            name='cf_U_original',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='object',
            name='cf_V_original',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]