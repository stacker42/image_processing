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
    url(r'^process/$', views.process, name="process"),
    url(r'^process/header/(?P<file_id>[0-9]+)/$', views.process_header, name="process_header"),
    url(r'^process/devicesetup/(?P<file_id>[0-9]+)/$', views.process_devicesetup, name="process_devicesetup"),
    url(r'^process/header/modify/(?P<file_id>[0-9]+)/$', views.process_header_modify,
        name="process_header_modify"),
    url(r'^process/observation/(?P<file_id>[0-9]+)/$', views.process_observation, name='process_observation'),
    url(r'^process/astrometry/(?P<file_id>[0-9]+)/$', views.process_astrometry, name='process_astrometry'),
    url(r'^process/photometry/(?P<file_id>[0-9]+)/$', views.process_photometry, name='process_photometry'),
    url(r'^process/calibration/(?P<file_id>[0-9]+)/$', views.process_calibration, name='process_calibration'),
    url(r'^process/calibration/retry/(?P<file_id>[0-9]+)/$', views.process_calibration_retry,
        name='process_calibration_retry'),
    url(r'^add/object/$', views.add_object, name='add_object'),
    url(r'^add/device/$', views.add_device, name='add_device'),
    url(r'^modify/object/(?P<id>[0-9]+)$', views.modify_object, name='modify_object'),
    url(r'^modify/device/(?P<id>[0-9]+)$', views.modify_device, name='modify_device'),
    url(r'^accounts/profile/$', views.accounts_profile, name='accounts_profile'),
    url(r'^objects/$', views.objects, name='objects'),
    url(r'^upload(?:/(?P<qquuid>\S+))?', views.UploadView.as_view(), name='upload'),
    url(r'^accounts/', include('registration.backends.default.urls')),
    url(r'^manage/files/$', views.manage_files, name='manage_files'),
    url(r'delete/file/(?P<file_id>[0-9]+)/$', views.delete_file, name='delete_file'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.ASTROMETRY_URL, document_root='temporary/astrometry/') + static(settings.PLOTS_URL, document_root='data/plots')
