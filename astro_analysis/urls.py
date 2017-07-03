"""astro_analysis URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from analysis import views
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^$', views.home, name="home"),
    url(r'^unprocessed_uploads/$', views.unprocessed_uploads, name="unprocessed_uploads"),
    url(r'^process/header/(?P<uuid>[0-9A-Za-z_\-]+)/$', views.process_header, name="process_header"),
    url(r'process/astrometry/(?P<file_id>[0-9]+)?/$', views.process_astrometry, name='process_astrometry'),
    url(r'process/photometry/(?P<file_id>[0-9]+)?/$', views.process_photometry, name='process_photometry'),
    url(r'process/calibration/(?P<file_id>[0-9]+)?/$', views.process_calibration, name='process_calibration'),
    url(r'process/status/(?P<file_id>[0-9A-Za-z_\-]+)?/$', views.process_status, name='process_status'),
    url(r'^upload(?:/(?P<qquuid>\S+))?', views.UploadView.as_view(), name='upload'),
    url(r'^accounts/', include('registration.backends.default.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
