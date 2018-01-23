from astropy.io import fits


def get_hdu_list(path):
    """
    Get the list of the header and data units
    :param path: The path to the FITS file
    :return: list of FITS header and data units
    """
    hdu_list = fits.open(path)
    return hdu_list


def get_header(path):
    """
    Get the header from a specified FITS file in human readable format
    :param path: The path to the FITS file
    :return: FITS header in human readable format
    """

    return repr(get_hdu_list(path)[0].header)