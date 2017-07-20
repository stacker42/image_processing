from django import template
import datetime


register = template.Library()


def timestamp_to_human(value):
    """
    Convert a UNIX timestamp to something human readable
    :param value: The timestamp
    :return: A human readable date
    """
    return datetime.datetime.utcfromtimestamp(value)

register.filter('timestamp_to_human', timestamp_to_human)
