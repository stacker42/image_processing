import os
import os.path
import shutil
from django.conf import settings
from django.http import HttpResponse


# combine_chunks, save_upload, handle_upload and handled_deleted_file are based on the examples given by FineUploader
# See: https://github.com/FineUploader/server-examples/tree/master/python/django-fine-uploader

def combine_chunks(total_parts, total_size, source_folder, dest):
    """ Combine a chunked file into a whole file again. Goes through each part
    , in order, and appends that part's bytes to another destination file.

    Chunks are stored in media/chunks
    Uploads are saved in media/uploads
    """

    if not os.path.exists(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))

    with open(dest, 'wb+') as destination:
        for i in xrange(total_parts):
            part = os.path.join(source_folder, str(i))
            with open(part, 'rb') as source:
                destination.write(source.read())


def save_upload(f, path):
    """ Save an upload. Django will automatically "chunk" incoming files
    (even when previously chunked by fine-uploader) to prevent large files
    from taking up your server's memory. If Django has chunked the file, then
    write the chunks, otherwise, save as you would normally save a file in
    Python.

    Uploads are stored in media/uploads
    """
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, 'wb+') as destination:
        if hasattr(f, 'multiple_chunks') and f.multiple_chunks():
            for chunk in f.chunks():
                destination.write(chunk)
        else:
            destination.write(f.read())


def handle_upload(f, fileattrs):
    """ Handle a chunked or non-chunked upload.
    """

    chunked = False
    dest_folder = os.path.join(settings.UPLOAD_DIRECTORY, fileattrs['qquuid'])
    dest = os.path.join(dest_folder, fileattrs['qqfilename'])

    # Chunked
    if fileattrs.get('qqtotalparts') and int(fileattrs['qqtotalparts']) > 1:
        chunked = True
        dest_folder = os.path.join(settings.CHUNKS_DIRECTORY, fileattrs['qquuid'])
        dest = os.path.join(dest_folder, fileattrs['qqfilename'], str(fileattrs['qqpartindex']))
    save_upload(f, dest)

    # If the last chunk has been sent, combine the parts.
    if chunked and (fileattrs['qqtotalparts'] - 1 == fileattrs['qqpartindex']):
        combine_chunks(fileattrs['qqtotalparts'],
                             fileattrs['qqtotalfilesize'],
                             source_folder=os.path.dirname(dest),
                             dest=os.path.join(settings.UPLOAD_DIRECTORY, fileattrs['qquuid'], fileattrs['qqfilename']))

        shutil.rmtree(os.path.dirname(os.path.dirname(dest)))


def handle_deleted_file(uuid):
    """ Handles a filesystem delete based on UUID."""

    loc = os.path.join(settings.UPLOAD_DIRECTORY, uuid)
    shutil.rmtree(loc)

def make_response(status=200, content_type='text/plain', content=None):
    """ Construct a response to an upload request.
    Success is indicated by a status of 200 and { "success": true }
    contained in the content.

    Also, content-type is text/plain by default since IE9 and below chokes
    on application/json. For CORS environments and IE9 and below, the
    content-type needs to be text/html.
    """
    response = HttpResponse()
    response.status_code = status
    response['Content-Type'] = content_type
    response.content = content
    return response