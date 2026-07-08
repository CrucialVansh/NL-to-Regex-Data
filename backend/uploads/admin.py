from django.contrib import admin

# Register your models here.

from .models import UploadedFile, Job

admin.site.register(UploadedFile)
admin.site.register(Job)
