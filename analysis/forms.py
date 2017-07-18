# coding=utf-8
from django import forms
from models import Object, Observation, ImagingDevice


class UploadFileForm(forms.Form):
    """ This form represents a basic request from Fine Uploader.
    The required fields will **always** be sent, the other fields are optional
    based on your setup.
    """
    qqfile = forms.FileField()
    qquuid = forms.CharField()
    qqfilename = forms.CharField()
    qqpartindex = forms.IntegerField(required=False)
    qqchunksize = forms.IntegerField(required=False)
    qqpartbyteoffset = forms.IntegerField(required=False)
    qqtotalfilesize = forms.IntegerField(required=False)
    qqtotalparts = forms.IntegerField(required=False)


class ObjectForm(forms.ModelForm):
    """
    A form for adding an object or modifying an existing one
    """
    class Meta:
        model = Object
        fields = ('number', 'name', 'ra', 'dec', 'cal_offset')
        labels = {'number': 'Unique object number', 'ra': 'Right Ascension ([±]HH MM SS)', 'dec':
                  'Declination ([±]HH MM SS)', 'cal_offset': 'Calibration offset'}


class ObservationForm(forms.ModelForm):
    """
    A form for adding a new observation or modifying an existing one
    """
    class Meta:
        model = Observation
        fields = ('target', 'device')
        labels = {'target': 'Target of observation', 'device': 'Device used'}


class HeaderForm(forms.Form):
    """
    A form to add missing information to the FITS header
    """
    DATE_FORMAT_CHOICES = (
        ('JD', 'Julian Date'),
        ('MJD', 'Modified Julian Date'),
        ('DATETIME', 'Date and Time')
    )
    exptime = forms.FloatField(label="Exposure time")
    filter = forms.CharField(max_length=255, label="Filter")
    date = forms.CharField(max_length=255, label="Date of observation")
    date_format = forms.ChoiceField(choices=DATE_FORMAT_CHOICES)


class HeaderKeyChoiceForm(forms.Form):
    DATE_FORMAT_CHOICES = (
        ('JD', 'Julian Date'),
        ('MJD', 'Modified Julian Date'),
        ('DATETIME', 'Date and Time')
    )
    date = forms.ChoiceField()
    date_format = forms.ChoiceField(choices=DATE_FORMAT_CHOICES)
    filter = forms.ChoiceField()
    exposure_time = forms.ChoiceField()


class ImagingDeviceForm(forms.ModelForm):
    """
    Form to add a new imaging device or to modify an exsting one
    """
    class Meta:
        model = ImagingDevice
        fields = ('name', 'scale', 'mirror_size', 'mirror_diameter', 'description')
        labels = {'name': 'Name of your device', 'scale': 'Pixel scale', 'mirror_size': 'Mirror size',
                  'mirror_diameter': 'Mirror diameter'}
        widgets = {'description': forms.Textarea}


class RedoCalibrationForm(forms.Form):
    """
    Form for users to re-do the calibration with their own max and min values
    """
    max_use = forms.FloatField(initial=0)
    min_use = forms.FloatField(initial=0)
