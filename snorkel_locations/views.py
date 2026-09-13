import uuid as uuid_lib

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from . import choices, geography, media_storage, static_map
from .choices import create_page_context
from locations_snorkelled.models import Snorkelled
from saved_locations.models import SavedLocation
from snorkel_reviews import display as reviews_display
from .models import LocationMedia, SnorkelLocation


# GET request, serve creation UI
def create(request):
    """Serve the location creation UI.

    Deliberately not @login_required: the template renders a signed-out
    message in place of the form, so the page itself stays reachable and
    linkable. create_page_context() supplies every chip, marker and label
    from choices.py, plus the Mapbox token the map needs.
    """
    return render(request, "snorkel_locations/create.html", create_page_context())


# ── Reading a listing back ───────────────────────────────────────────

def _flat_water_types():
    """Water types come grouped for the form; flatten them for lookup."""
    return [(chip["id"], chip["label"])
            for group in choices.WATER_TYPE_GROUPS
            for chip in group["chips"]]


def _media_for(location, category):
    """Verified photographs only.

    Anything still pending, rejected or removed is left out, so a
    listing never shows a broken image for a file that did not survive
    its checks.
    """
    rows = location.media.filter(
        media_category=category, status=LocationMedia.Status.ACTIVE)
    return [{
        "description": row.description,
        "width": row.width,
        "height": row.height,
        "captured_at": row.captured_at,
        # Sizes are produced at the edge from the stored original, so
        # nothing needs to have been generated in advance.
        "thumbnail": media_storage.transform_url(
            row.object_key, "width=600,format=auto"),
        "full": media_storage.transform_url(
            row.object_key, "width=2000,format=auto"),
    } for row in rows]


def is_saved(user, location):
    return bool(user.is_authenticated) and SavedLocation.objects.filter(
        user=user, location=location).exists()


def has_snorkelled(user, location):
    return bool(user.is_authenticated) and Snorkelled.objects.filter(
        user=user, location=location).exists()


def _marker(feature):
    """One map marker, ready to read.

    The stored feature is GeoJSON, so the useful parts are buried two
    levels down and the coordinates are the wrong way round for a human
    reading them. Flattened here rather than picked apart in the
    template.
    """
    properties = feature.get("properties") or {}
    coordinates = (feature.get("geometry") or {}).get("coordinates") or []
    marker_id = properties.get("markerId", "")
    return {
        "id": marker_id,
        "icon": f"images/sm-map-icons/{marker_id}.png" if marker_id else "",
        "name": properties.get("name") or marker_id,
        "note": properties.get("note", ""),
        "latitude": coordinates[1] if len(coordinates) > 1 else None,
        "longitude": coordinates[0] if coordinates else None,
    }


def listing_context(request, location):
    """Everything the listing template needs, prepared in Python.

    The template stays a plain loop over lists. Turning stored ids back
    into labels is done here rather than with template tags, because
    the mapping belongs to choices.py and this keeps it in one place.

    Takes the request as well as the location, because two things on
    the page are about the person reading it rather than about the
    place: whether they have saved it and whether they have been there.
    """
    revision = location.current_revision
    surface = _media_for(location, LocationMedia.MediaCategory.SURFACE)
    underwater = _media_for(location, LocationMedia.MediaCategory.UNDERWATER)
    facilities = (revision.facilities or {}) if revision else {}
    getting_there = facilities.get("gettingThere") or {}
    parking = getting_there.get("parking") or {}
    transport = getting_there.get("transport") or {}

    context = {
        "location": location,
        "revision": revision,
        # The stored Mapbox raster of where this is, ready for the
        # template to place beside the photographs. Empty string when
        # one has not been drawn yet, so the template can decide.
        "map_image": static_map.image_url(location),
        "access_types": choices.labels_for(
            choices.ACCESS_TYPES, revision.access_type if revision else []),
        "water_types": choices.labels_for(
            _flat_water_types(), revision.water_type if revision else []),
        "difficulty": revision.get_difficulty_display() if revision else "",

        "environment": choices.describe_group_map(
            "environmentTypes", revision.environment_types if revision else {}),
        "marine_life": choices.describe_group_map(
            "marineLife", revision.marine_life if revision else {}),
        "marine_life_comments": (revision.marine_life or {}).get("comments", "")
            if revision else "",
        "hazards": choices.describe_group_map(
            "hazards", revision.hazards if revision else {}),
        "hazards_comments": (revision.hazards or {}).get("comments", "")
            if revision else "",
        "facilities": choices.describe_group_map("facilities", facilities),
        "facilities_other": facilities.get("other", ""),

        "getting_there_comments": getting_there.get("comments", ""),
        "parking_available": dict(choices.PARKING_AVAILABILITY).get(
            parking.get("available"), ""),
        "parking_types": choices.labels_for(
            choices.PARKING_TYPES, parking.get("selected")),
        "parking_comments": parking.get("comments", ""),
        "transport_types": choices.labels_for(
            choices.TRANSPORT_TYPES, transport.get("selected")),
        "transport_description": transport.get("description", ""),

        "surface_photos": surface,
        "underwater_photos": underwater,
        "all_photos_count": len(surface) + len(underwater),
        # The big panel always has something in it. A listing with no
        # above water photograph is a listing waiting for one, not a
        # listing with a hole in its layout, so it gets the same
        # stand-in the map pane and the directory cards use.
        "hero_image": surface[0]["full"] if surface else settings.NO_IMAGE_URL,
        "hero_image_alt": (surface[0]["description"] or revision.name
                           if surface and revision
                           else "No photograph has been added yet"),
        # The same photographs again, flat and serialisable, for the
        # detail modal to read out of a json_script block. Dates are
        # formatted here because the browser has no idea what format
        # this site writes them in.
        "photo_data": [
            {
                "section": section,
                "full": photo["full"],
                "thumbnail": photo["thumbnail"],
                "description": photo["description"],
                "taken": (photo["captured_at"].strftime("%-d %B %Y")
                          if photo["captured_at"] else ""),
            }
            for section, photos in (("surface", surface),
                                    ("underwater", underwater))
            for photo in photos
        ],

        # The modal draws a real map, so it needs the same public token
        # the create page uses.
        "mapbox_token": settings.MAPBOX_TOKEN,

        "markers": [_marker(feature) for feature in
                    ((revision.marker_data or {}).get("features") or []
                     if revision else [])],

        # Whether this person has saved the location and whether they
        # have been there. Two booleans: the apps that store them own
        # the rows, this page owns what the buttons look like.
        "saved": is_saved(request.user, location),
        "snorkelled": has_snorkelled(request.user, location),

        # Drives the wording of the draft notice: the person who added
        # it needs to be told what is missing and what to do, staff
        # just need to know why they can see it.
        "is_owner": (revision is not None
                     and revision.created_by_id is not None),
    }

    # The reviews block is part of this page and drawn from this app's
    # templates, but everything in it belongs to snorkel_reviews, so
    # that app prepares it. The same builder runs again when the block
    # is swapped, which is what keeps the two renderings identical.
    context.update(reviews_display.reviews_context(request, location))
    return context


def may_view(request, location):
    """Who is allowed to see a listing that is not published.

    A draft is a listing whose photograph has not been confirmed yet.
    The person who submitted it can see it, because the most likely
    reason it is still a draft is that their upload did not finish, and
    the listing page is where they go to add the photo again. Staff can
    see it so a stuck upload can be looked at. To everyone else it does
    not exist.
    """
    if location.status == SnorkelLocation.Status.PUBLISHED:
        return True
    if not request.user.is_authenticated:
        return False
    if request.user.is_staff:
        return True
    revision = location.current_revision
    return revision is not None and revision.created_by_id == request.user.id


def _visible_location(request, slug):
    location = get_object_or_404(
        SnorkelLocation.objects.select_related(
            "current_revision",
            "current_revision__created_by",
            "country", "region", "locale",
        ),
        slug=slug,
    )
    if not may_view(request, location):
        raise Http404("No published location matches this address.")
    return location


def location_detail(request, country, slug, region=None, locale=None):
    """One listing, at any of its path lengths.

    The slug alone identifies the listing, so the geography segments
    are not used to find it. They are compared against the canonical
    path instead: a request that arrives with the old region after a
    correction, or with segments in the wrong order, is redirected to
    the right address rather than quietly serving the same page at two
    URLs.
    """
    location = _visible_location(request, slug)

    canonical = location.get_absolute_url()
    if request.path != canonical:
        # A 302 while the URL scheme is still settling. Worth making
        # this permanent once it has stopped changing, since browsers
        # and search engines cache a 301 for a very long time.
        return redirect(canonical)

    return render(request, "snorkel_locations/view.html", listing_context(request, location))


def location_by_uuid(request):
    """The permanent address: /location/?uuid=<uuid>

    A listing's canonical path can change, because a name can be edited
    and a wrongly guessed region can be corrected. Its uuid cannot. So
    this is the address to use anywhere a link needs to keep working.
    """
    raw = request.GET.get("uuid", "")
    try:
        parsed = uuid_lib.UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        raise Http404("That is not a location reference.")

    location = get_object_or_404(
        SnorkelLocation.objects.select_related(
            "current_revision", "country", "region", "locale"),
        uuid=parsed,
    )
    if not may_view(request, location):
        raise Http404("No published location matches this reference.")

    return redirect(location.get_absolute_url())


# ── The directory ──────────────────────────────────────────

def directory(request):
    """An A-Z of every country that has a published listing.

    One query, then grouping in Python. That is cheaper than a query
    per country and it keeps the template to three plain loops.

    The ordering is done by the database, so the countries come out A-Z
    and the regions and listings within them follow suit. The grouping
    itself lives in geography.directory_tree(), which only reads
    attributes and so can be checked without a database.
    """
    rows = (
        SnorkelLocation.objects
        .filter(status=SnorkelLocation.Status.PUBLISHED,
                current_revision__isnull=False)
        .select_related("country", "region", "locale", "current_revision")
        .order_by("country__name", "region__name", "current_revision__name")
    )
    countries = geography.directory_tree(rows)

    return render(request, "snorkel_locations/directory.html", {
        "countries": countries,
        "country_count": sum(1 for card in countries if card["code"]),
        "location_count": sum(card["count"] for card in countries),
    })
