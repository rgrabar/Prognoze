"""URL configuration for mysite project.

https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/prognoze/", permanent=False)),
    path("prognoze/", include("prognoze.urls")),
    path("admin/", admin.site.urls),
]
