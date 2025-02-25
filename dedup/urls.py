"""
URLs for the deduplication app.
"""

from django.urls import path
from . import views

app_name = "dedup"

urlpatterns = [
    # Start page with list of collections to dedup, this view is not protected by login
    path("", views.index, name="index"),

    # Collection page with list of records to dedup, main dedup view
    path("col/<slug:col_name>", views.collection, name="collection"),

    # API used by the frontend to get the records to dedup
    path("col/<slug:col_name>/locrecids", views.get_local_record_ids, name="get_local_record_ids"),

    # API used by the frontend to get the data of the local record to dedup
    path("col/<slug:col_name>/locrec/<str:rec_id>", views.local_rec, name="local_rec"),

    # API used by the frontend to save dedup results int the training data
    path("training/add", views.add_to_training_data, name="add_to_training_data"),

    # Views to manage login and logout. The login view does not require
    # authentication to be accessed
    path("login/", views.login_view, name="login_view"),
    path("logout/", views.logout_view, name="logout_view")

    # path("dnbrec/<str:rec_id>", views.get_dnb_rec, name="get_dnb_rec"),
]