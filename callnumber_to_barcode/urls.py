"""
URLs for the deduplication app.
"""

from django.urls import path
from . import views

app_name = "callnumber_to_barcode"

urlpatterns = [
    # Start page with list of collections to dedup, this view is not protected by login
    path("", views.index, name="index"),
path("test", views.testwrapper, name="testwrapper"),
    path("<slug:col_name>", views.collection, name="collection"),
    path("<slug:col_name>/update/<str:item_id>", views.update, name="update"),
    # Views to manage login and logout. The login view does not require
    # authentication to be accessed
    path("login/", views.login_view, name="login_view"),
    path("logout/", views.logout_view, name="logout_view")
]