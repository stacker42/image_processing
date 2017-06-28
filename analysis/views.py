# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.http import HttpResponse, HttpRequest
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
import utils
from forms import UploadFileForm
import json

def home(request):
    """
    Let the user upload files
    :param request:
    :return:
    """
    return render(request, "base_upload.html")


def check_file(request, file_to_check):
    """
    Checks the header information in a given file, based on upload UUID
    :param file_to_check: The UUID of the file to check
    :return:
    """


def test(request):
    return HttpResponse(request.session.get('files'))


class UploadView(View):
    """ View which will handle all upload requests sent by Fine Uploader.
    See: https://docs.djangoproject.com/en/dev/topics/security/#user-uploaded-content-security

    Handles POST and DELETE requests.

    This view was created by FineUploader. Modifications by Will Furnell.
    """

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super(UploadView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        """A POST request. Validate the form and then handle the upload
        based ont the POSTed data. Does not handle extra parameters yet.
        """
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            utils.handle_upload(request.FILES['qqfile'], form.cleaned_data)
            return utils.make_response(content=json.dumps({ 'success': True }))
        else:
            return utils.make_response(status=400,
                content=json.dumps({
                    'success': False,
                    'error': '%s' % repr(form.errors)
                }))

    def delete(self, request, *args, **kwargs):
        """A DELETE request. If found, deletes a file with the corresponding
        UUID from the server's filesystem.
        """
        qquuid = kwargs.get('qquuid', '')
        if qquuid:
            try:
                utils.handle_deleted_file(qquuid)
                return utils.make_response(content=json.dumps({ 'success': True }))
            except Exception, e:
                return utils.make_response(status=400,
                    content=json.dumps({
                        'success': False,
                        'error': '%s' % repr(e)
                    }))
        return utils.make_response(status=404,
            content=json.dumps({
                'success': False,
                'error': 'File not present'
            }))

