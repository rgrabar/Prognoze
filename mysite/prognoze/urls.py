from django.urls import path

from . import views

urlpatterns = [
    path("", views.op, name="prognoza"),
]