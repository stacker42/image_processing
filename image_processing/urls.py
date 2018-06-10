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
from django.contrib.auth.views import password_reset_confirm, password_reset_complete, password_change, password_change_done


urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^$', views.lightcurve, name="home"),
    url(r'^ul/$', views.ul, name="ul"),
    url(r'^process/$', views.process, name="process"),
    url(r'^process/metadata/(?P<file_id>[0-9]+)/$', views.process_metadata, name="process-metadata"),
    url(r'^process/devicesetup/(?P<file_id>[0-9]+)/$', views.process_devicesetup, name="process_devicesetup"),
    url(r'^process/metadata/modify/(?P<file_id>[0-9]+)/$', views.process_metadata_modify,
        name="process-metadata-modify"),
    url(r'^process/observation/(?P<file_id>[0-9]+)/$', views.process_observation, name='process_observation'),
    url(r'^process/astrometry/(?P<file_id>[0-9]+)/$', views.process_astrometry, name='process_astrometry'),
    #url(r'^process/photometry/(?P<file_id>[0-9]+)/$', views.process_photometry, name='process_photometry'),
    url(r'^process/calibration/(?P<file_id>[0-9]+)/$', views.process_calibration, name='process_calibration'),
    url(r'^process/calibration/retry/(?P<file_id>[0-9]+)/$', views.process_calibration_retry,
        name='process_calibration_retry'),
    url(r'^process/reprocess/(?P<file_id>[0-9]+)/$', views.process_reprocess, name='process_reprocess'),
    url(r'^add/object/$', views.add_object, name='add_object'),
    url(r'^add/device/$', views.add_device, name='add_device'),
    url(r'^modify/object/(?P<id>[0-9]+)$', views.modify_object, name='modify_object'),
    url(r'^modify/device/(?P<id>[0-9]+)$', views.modify_device, name='modify_device'),
    url(r'^accounts/profile/$', views.accounts_profile, name='accounts_profile'),
    url(r'^objects/$', views.objects, name='objects'),
    url(r'^upload(?:/(?P<qquuid>\S+))?', views.UploadView.as_view(), name='upload'),
    url(r'^accounts/', include('registration.backends.default.urls')),
    url(r'^accounts/password/reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
        password_reset_confirm, name='password_reset_confirm'),
    url(r'^accounts/password/reset/complete/$', password_reset_complete, name='password_reset_complete'),
    url(r'^manage/files/$', views.manage_files, name='manage_files'),
    url(r'delete/file/(?P<file_id>[0-9]+)/$', views.delete_file, name='delete_file'),

    url(r'lightcurve/$', views.lightcurve, name='lightcurve'),
    url(r'lightcurve/download/$', views.lightcurve_download, name='lightcurve_download'),

    url(r'^captcha/', include('captcha.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.ASTROMETRY_URL, document_root='temporary/astrometry/') + static(settings.PLOTS_URL, document_root='data/plots')
