from django.urls import path

from . import views

urlpatterns = [

    path("create/", views.create, name="create"),
    path("publish/", views.publish, name="publish"),

    # Display a listing

    path(
        "location/<str:country>/<slug:region>/<slug:locale>/<slug:slug>/",
        views.location_detail,
        name="detail",
    ),
]