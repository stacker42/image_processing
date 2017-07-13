# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User


# class FITSHeader(models.Model):
#     """
#     Stores the header information of a FITS file
#     """
#     simple = models.CharField(max_length=1)
#     bitpix = models.IntegerField(blank=True, null=True)
#     naxis = models.IntegerField(blank=True, null=True)
#     naxis1 = models.IntegerField(blank=True, null=True)
#     naxis2 = models.IntegerField(blank=True, null=True)
#     date_obs = models.CharField(max_length=255, blank=True, null=True)
#     exptime = models.FloatField(blank=True, null=True)
#     exposure = models.FloatField(blank=True, null=True)
#     set_temp = models.FloatField(blank=True, null=True)
#     ccd_temp = models.FloatField(blank=True, null=True)
#     xpixsz = models.FloatField(blank=True, null=True)
#     ypixsz = models.FloatField(blank=True, null=True)
#     xbinning = models.FloatField(blank=True, null=True)
#     ybinning = models.FloatField(blank=True, null=True)
#     xorgsubf = models.IntegerField(blank=True, null=True)
#     yorgsubf = models.IntegerField(blank=True, null=True)
#     filter = models.CharField(max_length=255, blank=True, null=True)
#     imagetyp = models.CharField(max_length=255, blank=True, null=True)
#     focallen = models.FloatField(blank=True, null=True)
#     aptdia = models.FloatField(blank=True, null=True)
#     aptarea = models.FloatField(blank=True, null=True)
#     swcreate = models.CharField(max_length=255, blank=True, null=True)
#     swserial = models.CharField(max_length=255, blank=True, null=True)
#     focuspos = models.IntegerField(blank=True, null=True)
#     focussz = models.FloatField(blank=True, null=True)
#     focustem = models.FloatField(blank=True, null=True)
#     object = models.CharField(max_length=255, blank=True, null=True)
#     objctra = models.CharField(max_length=255, blank=True, null=True)
#     objctdec = models.CharField(max_length=255, blank=True, null=True)
#     objctalt = models.FloatField(blank=True, null=True)
#     objctaz = models.FloatField(blank=True, null=True)
#     objctha = models.FloatField(blank=True, null=True)
#     pierside = models.CharField(max_length=255, blank=True, null=True)
#     sitelat = models.CharField(max_length=255, blank=True, null=True)
#     sitelong = models.CharField(max_length=255, blank=True, null=True)
#     jd = models.FloatField(blank=True, null=True)
#     jd_helio = models.FloatField(blank=True, null=True)
#     airmass = models.FloatField(blank=True, null=True)
#     telescop = models.CharField(max_length=255, blank=True, null=True)
#     instrume = models.CharField(max_length=255, blank=True, null=True)
#     observer = models.CharField(max_length=255, blank=True, null=True)
#     notes = models.CharField(max_length=255, blank=True, null=True)
#     flipstat = models.CharField(max_length=255, blank=True, null=True)
#     swowner = models.CharField(max_length=255, blank=True, null=True)
#     usedbias = models.CharField(max_length=255, blank=True, null=True)
#     useddark = models.CharField(max_length=255, blank=True, null=True)
#     usedflat = models.CharField(max_length=255, blank=True, null=True)
#     ctype1 = models.CharField(max_length=255, blank=True, null=True)
#     ctype2 = models.CharField(max_length=255, blank=True, null=True)
#     crpix1 = models.IntegerField(blank=True, null=True)
#     crpix2 = models.IntegerField(blank=True, null=True)
#     crval1 = models.FloatField(blank=True, null=True)
#     crval2 = models.FloatField(blank=True, null=True)
#     cdelt1 = models.FloatField(blank=True, null=True)
#     cdelt2 = models.FloatField(blank=True, null=True)
#     cd1_1 = models.FloatField(blank=True, null=True)
#     cd1_2 = models.FloatField(blank=True, null=True)
#     cd2_1 = models.FloatField(blank=True, null=True)
#     cd2_2 = models.FloatField(blank=True, null=True)
#     history = models.CharField(max_length=1000, blank=True, null=True)
#     comment = models.CharField(max_length=1000, blank=True, null=True)
#     equinox = models.CharField(max_length=255, blank=True, null=True)
#     radesys = models.CharField(max_length=255, blank=True, null=True)
#     cunit1 = models.CharField(max_length=255, blank=True, null=True)
#     cunit2 = models.CharField(max_length=255, blank=True, null=True)
#     pv1_0 = models.CharField(max_length=255, blank=True, null=True)
#     pv1_1 = models.CharField(max_length=255, blank=True, null=True)
#     pv1_2 = models.CharField(max_length=255, blank=True, null=True)
#     pv1_3 = models.CharField(max_length=255, blank=True, null=True)
#     pv1_4 = models.CharField(max_length=255, blank=True, null=True)
#     pv1_5 = models.CharField(max_length=255, blank=True, null=True)
#     pv1_6 = models.CharField(max_length=255, blank=True, null=True)
#     pv1_7 = models.CharField(max_length=255, blank=True, null=True)
#     pv1_8 = models.CharField(max_length=255, blank=True, null=True)
#     pv1_9 = models.CharField(max_length=255, blank=True, null=True)
#     pv1_10 = models.CharField(max_length=255, blank=True, null=True)
#     pv2_0 = models.CharField(max_length=255, blank=True, null=True)
#     pv2_1 = models.CharField(max_length=255, blank=True, null=True)
#     pv2_2 = models.CharField(max_length=255, blank=True, null=True)
#     pv2_3 = models.CharField(max_length=255, blank=True, null=True)
#     pv2_4 = models.CharField(max_length=255, blank=True, null=True)
#     pv2_5 = models.CharField(max_length=255, blank=True, null=True)
#     pv2_6 = models.CharField(max_length=255, blank=True, null=True)
#     pv2_7 = models.CharField(max_length=255, blank=True, null=True)
#     pv2_8 = models.CharField(max_length=255, blank=True, null=True)
#     pv2_9 = models.CharField(max_length=255, blank=True, null=True)
#     pv2_10 = models.CharField(max_length=255, blank=True, null=True)
#     froupno = models.IntegerField(blank=True, null=True)
#     astirms1 = models.CharField(max_length=255, blank=True, null=True)
#     astirms2 = models.CharField(max_length=255, blank=True, null=True)
#     astrrms1 = models.CharField(max_length=255, blank=True, null=True)
#     astrrms2 = models.CharField(max_length=255, blank=True, null=True)
#     astinst = models.IntegerField(blank=True, null=True)
#     flxscale = models.CharField(max_length=255, blank=True, null=True)
#     magzerop = models.CharField(max_length=255, blank=True, null=True)
#     photirms = models.CharField(max_length=255, blank=True, null=True)
#     photlink = models.CharField(max_length=255, blank=True, null=True)
#     ast_cat = models.CharField(max_length=255, blank=True, null=True)
#     ast_band = models.CharField(max_length=255, blank=True, null=True)
#     n_stack = models.IntegerField(blank=True, null=True)
#     exp_tot = models.FloatField(blank=True, null=True)
#     jd_ave = models.FloatField(blank=True, null=True)
#
#     class Meta:
#         db_table = "fits_header"

class ImagingDevice(models.Model):
    """
    Stores attributes for a users imaging device
    """
    user = models.ForeignKey(User)
    name = models.CharField(max_length=255)
    scale = models.FloatField()

    def __str__(self):
        return self.name


class Object(models.Model):
    """
    Represents an object that can be observed
    """
    number = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    ra = models.CharField(max_length=255)
    dec = models.CharField(max_length=255)
    max_use = models.FloatField()  # used in calibration
    cal_offset = models.FloatField()  # used in calibration

    class Meta:
        db_table = "objects"

    def __str__(self):
        return '[' + str(self.number) + '] ' + self.name


class FITSFile(models.Model):
    """
    Stores a reference to the header of a FITS file, and some attributes
    """
    STATUS_CHOICES = (
        ('HEADER', 'Header check'),
        ('OBSERVATION', 'Add observation details'),
        ('ASTROMETRY', 'Astrometry'),
        ('PHOTOMETRY', 'Photometry'),
        ('CALIBRATION', 'Calibration'),
        ('COMPLETE', 'Processing complete'),
        ('FAILED', 'Processing failed'),
        ('FAILED_USER', 'User invoked processing failed'),
        ('CHECK_ASTROMETRY', 'Check whether astrometry was successful'),
        ('CHECK_PHOTOMETRY', 'Check whether astrometry was successful'),
        ('CHECK_CALIBRATION', 'Check whether astrometry was successful'),
    )

    #header = models.ForeignKey(FITSHeader)
    fits_filename = models.CharField(max_length=255)
    catalogue_filename = models.CharField(max_length=255)
    process_status = models.CharField(choices=STATUS_CHOICES, max_length=255)
    uploaded_by = models.ForeignKey(User)
    upload_time = models.IntegerField()
    header = models.CharField(max_length=10000)

    class Meta:
        db_table = "fits_files"


class UnprocessedUpload(models.Model):
    """
    Store all the uploads that haven't yet been processed, so the user can choose to process them at a later date.
    Also makes things easier with resuming uploads - we only add to database once finally uploaded.
    """
    uuid = models.UUIDField(primary_key=True)
    filename = models.FilePathField()
    user = models.ForeignKey(User)
    upload_time = models.IntegerField()

    class Meta:
        db_table = "unprocessed_uploads"


class Observation(models.Model):
    """
    Stores all the information about a specific observation
    """
    time = models.DateTimeField()
    user = models.ForeignKey(User)
    filter = models.CharField(max_length=255)
    fits = models.ForeignKey(FITSFile)
    target = models.ForeignKey(Object)
    device = models.ForeignKey(ImagingDevice)

    class Meta:
        db_table = "observations"


class Photometry(models.Model):
    """
    Stores the photometry information for a specific object
    """
    observation = models.ForeignKey(Observation)
    calibrated_magnitude = models.FloatField()
    magnitude_rms_error = models.FloatField()
    x = models.FloatField()
    y = models.FloatField()
    alpha_j2000 = models.FloatField()
    delta_j2000 = models.FloatField()
    fwhm_world = models.FloatField()
    flags = models.CharField(max_length=10)
    magnitude = models.FloatField()

    class Meta:
        db_table = "photometry"

