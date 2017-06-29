# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class UnprocessedUploads(models.Model):
    uuid = models.UUIDField()
    filename = models.FilePathField()
    user = User()
