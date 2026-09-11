from django.urls import path

from . import views

urlpatterns = [

    path("add-location/", views.create, name="create"),

    # The permanent address. /location/?uuid=<uuid> redirects to
    # whatever the canonical path currently is, so a link saved
    # anywhere keeps working after a rename or a correction to the
    # listing's geography.
    path("location/", views.location_by_uuid, name="detail_by_uuid"),

    # The canonical addresses. One pattern per depth, and since Django
    # matches on segment count there is no ambiguity between them.
    #
    #   /location/gb/scottish-borders/st-abbs/st-abbs-harbour/
    #   /location/gb/scottish-borders/st-abbs-harbour/
    #   /location/gb/st-abbs-harbour/
    #   /location/ocean/mid-atlantic-ridge/
    #
    # Longest first so the more specific pattern is tried first.
    path(
        "location/<slug:country>/<slug:region>/<slug:locale>/<slug:slug>/",
        views.location_detail, name="detail_locale",
    ),
    path(
        "location/<slug:country>/<slug:region>/<slug:slug>/",
        views.location_detail, name="detail_region",
    ),
    path(
        "location/<slug:country>/<slug:slug>/",
        views.location_detail, name="detail",
    ),
]
