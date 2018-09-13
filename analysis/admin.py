# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

# Register your models here.

admin.site.register(ImagingDevice)
admin.site.register(FITSFile)
admin.site.register(Observation)
admin.site.register(Object)

UserAdmin.list_display = ('email', 'is_active', 'date_joined', 'is_staff', 'id', 'first_name', 'last_name')

admin.site.unregister(User)
admin.site.register(User, UserAdmin)