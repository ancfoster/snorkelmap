from django.urls import path

from . import explore, views

urlpatterns = [

    path("add-location/", views.create, name="create"),

    # An A-Z of every country with a published listing, then its
    # regions, then the listings themselves.
    path("directory/", views.directory, name="directory"),

    # The map, and the two HTML fragments it asks for as it moves.
    # Both fragments sit here rather than under /api/v1/ because they
    # return markup, not JSON.
    path("explore/", explore.explore, name="explore"),
    path("explore/cards/", explore.explore_cards, name="explore_cards"),
    path("explore/card/<uuid:location_uuid>/", explore.explore_card,
         name="explore_card"),

    # The permanent address. /location/?uuid=<uuid> redirects to
    # whatever the canonical path currently is, so a link saved
    # anywhere keeps working after a rename or a correction to the
    # listing's geography.
    path("location/", views.location_by_uuid, name="detail_by_uuid"),

    # The canonical addresses. One pattern per depth, and since Django
    # matches on segment count there is no ambiguity between them.
    #
    #   /location/united-kingdom/scottish-borders/st-abbs/st-abbs-harbour/
    #   /location/united-kingdom/scottish-borders/st-abbs-harbour/
    #   /location/united-kingdom/st-abbs-harbour/
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
