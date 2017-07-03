from django.shortcuts import HttpResponse


def make_response(status=200, content_type='text/plain', content=None):
    """ Construct a response to a request.

    Also, content-type is text/plain by default since IE9 and below chokes
    on application/json.
    """
    response = HttpResponse()
    response.status_code = status
    response['Content-Type'] = content_type
    response.content = content
    return response