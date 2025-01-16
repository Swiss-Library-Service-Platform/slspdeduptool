from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("locrecids", views.get_local_record_ids, name="get_local_record_ids"),
    path("nzrec/<str:mms_id>", views.get_nz_rec, name="get_nz_rec"),
    path("locrec/<str:rec_id>", views.local_rec, name="local_rec"),
    path("dnbrec/<str:rec_id>", views.get_dnb_rec, name="get_dnb_rec"),
]