"""
URLs for the slspstafftool app.
"""

from django.urls import path
from . import views
from slsptools.views import login_view, logout_view

app_name = "slspstafftool"

urlpatterns = [
    path("", views.index, name="index"),
]