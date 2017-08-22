from django import template

register = template.Library()

# This snippet is from https://stackoverflow.com/a/24658162


@register.simple_tag
def query_transform(request, **kwargs):
    updated = request.GET.copy()
    for k, v in kwargs.iteritems():
        updated[k] = v

    return '?' + updated.urlencode()