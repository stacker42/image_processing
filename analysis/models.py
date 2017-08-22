# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User


class ImagingDevice(models.Model):
    """
    Stores attributes for a users imaging device
    """
    user = models.ForeignKey(User)
    name = models.CharField(max_length=255)
    scale = models.FloatField()
    date_card = models.CharField(max_length=9, blank=True, null=True)
    time_card = models.CharField(max_length=9, blank=True, null=True)
    filter_card = models.CharField(max_length=9, blank=True, null=True)
    exptime_card = models.CharField(max_length=9, blank=True, null=True)
    date_format = models.CharField(max_length=255, blank=True, null=True)
    description = models.CharField(max_length=10000, blank=True, null=True)
    mirror_diameter = models.FloatField()

    class Meta:
        db_table = 'imaging_devices'

    # What to show the user when viewing the object in a queryset
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
    cal_offset = models.FloatField()  # used in calibration
    cf_CV_original = models.CharField(max_length=255, null=True, blank=True)
    cf_U_original = models.CharField(max_length=255, null=True, blank=True)
    cf_B_original = models.CharField(max_length=255, null=True, blank=True)
    cf_V_original = models.CharField(max_length=255, null=True, blank=True)
    cf_R_original = models.CharField(max_length=255, null=True, blank=True)
    cf_I_original = models.CharField(max_length=255, null=True, blank=True)
    cf_SZ_original = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "objects"

    # What to show the user when viewing the object in a queryset
    def __str__(self):
        return '[' + str(self.number) + '] ' + self.name


class FITSFile(models.Model):
    """
    Stores a reference to the header of a FITS file, and some attributes
    """
    # The statuses that we can use
    STATUS_CHOICES = (
        ('UPLOADED', 'Uploaded'),
        ('DEVICESETUP', 'Device setup'),
        ('METADATA', 'Metadata check'),
        ('OBSERVATION', 'Add observation details'),
        ('ASTROMETRY', 'Astrometry'),
        ('CALIBRATION', 'Calibration'),
        ('COMPLETE', 'Processing complete'),
        ('FAILED', 'Processing failed'),
        ('FAILED_USER', 'User invoked processing failed'),
        ('CHECK_ASTROMETRY', 'Check whether astrometry was successful'),
        ('CHECK_CALIBRATION', 'Check whether calibration was successful'),
    )

    fits_filename = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    catalogue_filename = models.CharField(max_length=255)
    process_status = models.CharField(choices=STATUS_CHOICES, max_length=255)
    uploaded_by = models.ForeignKey(User)
    upload_time = models.IntegerField()
    header = models.CharField(max_length=10000)
    sha256 = models.CharField(max_length=64)
    uuid = models.UUIDField()

    class Meta:
        db_table = "fits_files"


# class UnprocessedUpload(models.Model):
#     """
#     Store all the uploads that haven't yet been processed, so the user can choose to process them at a later date.
#     Also makes things easier with resuming uploads - we only add to database once finally uploaded.
#     """
#     uuid = models.UUIDField(primary_key=True)
#     filename = models.FilePathField()
#     user = models.ForeignKey(User)
#     upload_time = models.IntegerField()
#     sha256 = models.CharField(max_length=64)
#
#     class Meta:
#         db_table = "unprocessed_uploads"


class Observation(models.Model):
    """
    Stores all the information about a specific observation
    """
    date = models.FloatField(blank=True, null=True)
    user = models.ForeignKey(User)
    filter = models.CharField(max_length=255, blank=True, null=True)
    orignal_filter = models.CharField(max_length=255, blank=True, null=True)
    exptime = models.FloatField(blank=True, null=True)
    fits = models.ForeignKey(FITSFile)
    target = models.ForeignKey(Object)
    device = models.ForeignKey(ImagingDevice)
    detected_stars = models.IntegerField(blank=True, null=True)
    limiting_magnitude = models.FloatField(blank=True, null=True)
    detected_stars_calibration = models.FloatField(blank=True, null=True)
    med_offset = models.FloatField(blank=True, null=True)
    calibration_parameters = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "observations"


class Photometry(models.Model):
    """
    Stores the photometry information for a specific object
    flags NOTE: Uses SExtractor flags, but extra added after 128.
    256 - Too bright to use
    512 - Too faint
    1024 - Something else caused a problem
    """
    observation = models.ForeignKey(Observation)
    calibrated_magnitude = models.FloatField()
    calibrated_error = models.FloatField()
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

