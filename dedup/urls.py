from django.urls import path

from . import views

app_name = "dedup"

urlpatterns = [
    path("", views.index, name="index"),
    path("col/<slug:col_name>", views.collection, name="collection"),
    path("col/<slug:col_name>/locrecids", views.get_local_record_ids, name="get_local_record_ids"),
    path("nzrec/<str:mms_id>", views.get_nz_rec, name="get_nz_rec"),
    path("col/<slug:col_name>/locrec/<str:rec_id>", views.local_rec, name="local_rec"),
    path("training/add", views.add_to_training_data, name="add_to_training_data"),
    path("login/", views.login_view, name="login_view"),
    path("logout/", views.logout_view, name="logout_view")
    # path("dnbrec/<str:rec_id>", views.get_dnb_rec, name="get_dnb_rec"),
]