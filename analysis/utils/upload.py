import hashlib
import os
import os.path
import shutil
import time

from django.conf import settings
from django.http import HttpResponse

from analysis.models import FITSFile
from analysis.utils.fits import get_header


def check_valid_file(path, uuid):
    """
    Check that the FITS reader can actually read the file. If not, then delete it.
    :param path: The full path to the file
    :param uuid: The UUID of the file
    """
    try:
        get_header(path)
        return True
    except (IOError, ValueError):
        handle_deleted_file(uuid)
        return False


# combine_chunks, save_upload, handle_upload and handled_deleted_file are based on the examples given by FineUploader
# See: https://github.com/FineUploader/server-examples/tree/master/python/django-fine-uploader


def combine_chunks(total_parts, total_size, source_folder, dest, uuid):
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

    return check_valid_file(dest, uuid)


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


def handle_upload(f, fileattrs, request):
    """
    Handle a chunked or non-chunked upload. Add information about the unprocessed upload to the database.
    """
    fn = ''.join(fileattrs['qqfilename'].split())
    chunked = False
    dest_folder = os.path.join(settings.UPLOAD_DIRECTORY, fileattrs['qquuid'])
    dest = os.path.join(dest_folder, fn)

    # Chunked
    # Only chunks are saved here
    if fileattrs.get('qqtotalparts') and int(fileattrs['qqtotalparts']) > 1:
        chunked = True
        dest_folder = os.path.join(settings.CHUNKS_DIRECTORY, fileattrs['qquuid'])
        dest = os.path.join(dest_folder, fn, str(fileattrs['qqpartindex']))
    # Will save whole upload if not chunked, or just the chunk

    if not chunked:
        # If the file is whole, then put its information into the database, and save it
        save_upload(f, dest)
        if check_valid_file(dest, fileattrs['qquuid']):
            upload = FITSFile()
            upload.uuid = fileattrs['qquuid']
            upload.fits_filename = fn
            upload.uploaded_by = request.user
            upload.upload_time = time.time()
            upload.sha256 = hashlib.sha256(open(dest, 'r').read()).hexdigest()
            upload.process_status = 'UPLOADED'
            upload.save()
        else:
            return False  # not a valid file
    else:
        # If the file is chunked, then at this stage, we only want to save the next chunk to disk in the chunk
        # directory
        save_upload(f, dest)

    # If the last chunk has been sent, combine the parts.
    if chunked and (fileattrs['qqtotalparts'] - 1 == fileattrs['qqpartindex']):
        # Save to disk
        if combine_chunks(fileattrs['qqtotalparts'],
                          fileattrs['qqtotalfilesize'],
                          source_folder=os.path.dirname(dest),
                          dest=os.path.join(settings.UPLOAD_DIRECTORY, fileattrs['qquuid'], fn),
                          uuid=fileattrs['qquuid']):
            # save to db
            upload = FITSFile()
            upload.uuid = fileattrs['qquuid']
            upload.fits_filename = fn
            upload.uploaded_by = request.user
            upload.upload_time = time.time()
            upload.sha256 = hashlib.sha256(
                open(os.path.join(settings.UPLOAD_DIRECTORY, fileattrs['qquuid'], fn),
                     'r').read()).hexdigest()
            upload.process_status = 'UPLOADED'
            upload.save()

            shutil.rmtree(os.path.dirname(os.path.dirname(dest)))
        else:
            # not a valid file
            return False

    return True


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
