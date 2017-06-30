# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-06-30 12:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0006_auto_20170630_1052'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fitsheader',
            name='airmass',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='aptarea',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='aptdia',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='ccd_temp',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='cd1_1',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='cd1_2',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='cd2_1',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='cd2_2',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='cdelt1',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='cdelt2',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='crval1',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='crval2',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='exp_tot',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='exposure',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='exptime',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='focallen',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='focussz',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='focustem',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='jd',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='jd_ave',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='jd_helio',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='objctalt',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='objctaz',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='objctha',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='set_temp',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='xbinning',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='xpixsz',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='ybinning',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
        migrations.AlterField(
            model_name='fitsheader',
            name='ypixsz',
            field=models.DecimalField(decimal_places=18, max_digits=36),
        ),
    ]
