# coding=utf-8
from django import forms
from analysis.models import Object, Observation


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

    class Meta:
        model = Observation
        fields = ('target',)
        labels = {'target': 'Target of observation'}
