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

    class Meta:
        model = Object
        fields = ('number', 'name', 'ra', 'dec', 'max_use', 'cal_offset')
        labels = {'number': 'Unique object number', 'ra': 'Right Ascension ([±]HH MM SS)', 'dec':
                  'Declination ([±]HH MM SS)', 'max_use': 'Maximum calibration magnitude',
                  'cal_offset': 'Calibration offset'}


class ObservationForm(forms.ModelForm):
    # We have to do this so we can filter by user in the queryset
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(ObservationForm, self).__init__(*args, **kwargs)
        self.fields['device'].queryset = ImagingDevice.objects.filter(user=self.user)

    class Meta:
        model = Observation
        fields = ('target', 'device')
        labels = {'target': 'Target of observation', 'device': 'Device used'}


class HeaderForm(forms.Form):
    EXPTIME = forms.FloatField(label="Exposure time (EXPTIME)")
    FILTER = forms.CharField(max_length=255, label="Filter (FILTER)")
    DATE_OBS = forms.CharField(max_length=255, label="Date of observation [2017-01-05T17:10:02] (DATE-OBS)")


class ImagingDeviceForm(forms.ModelForm):
    class Meta:
        model = ImagingDevice
        fields = ('name', 'scale')
        labels = {'name': 'Name of your device', 'scale': 'Pixel scale'}
