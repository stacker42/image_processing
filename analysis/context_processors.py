from django.conf import settings


def astrometry_images(request):
    """
    Return the URL for the astrometry base image directory
    :param request:
    :return:
    """
    return {'ASTROMETRY_URL': settings.ASTROMETRY_URL}


def plots_images(request):
    """
    Return the URL for the plots base image directory
    :param request:
    :return:
    """
    return {'PLOTS_URL': settings.PLOTS_URL}
