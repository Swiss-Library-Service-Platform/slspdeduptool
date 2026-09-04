"""
URLs for the slspstafftool app.
"""

from django.urls import path
from . import views
from slsptools.views import login_view, logout_view

app_name = "slspstafftool"

urlpatterns = [
    path("", views.index, name="index"),
    path("close_library", views.close_library, name="close_library"),
    path('manage_slsp_alma_accounts', views.manage_slsp_alma_accounts, name='manage_slsp_alma_accounts'),
]