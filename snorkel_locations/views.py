import json

from django.contrib.auth.decorators import login_required
from django.contrib.gis.geos import Point
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.html import strip_tags
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .models import (
    Country,
    Region,
    Locale,
    SnorkelLocation,
    LocationRevision,
)

# GET request, serve creation UI
@login_required          # users who are note logged in are redirected to login url
def create(request):
    return render(request, "snorkel_locations/create.html")

#  Helpers — cleaning

def _clean_text(value, max_length=None):
    """Strip HTML tags and surrounding whitespace from a free-text field."""
    if not isinstance(value, str):
        return ""
    cleaned = strip_tags(value).strip()
    return cleaned[:max_length] if max_length else cleaned


def _as_list(value):
    return value if isinstance(value, list) else []


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_submission(payload):
    """
    Validate JSON submission
    """
    errors = {}
    name = _clean_text(payload.get("name"), max_length=200)
    if not name:
        errors["name"] = "A location name is required."

    lat = _as_float(payload.get("lat"))
    lng = _as_float(payload.get("lng"))
    if lat is None or lng is None:
        errors["coordinates"] = "Invalid coordinates"
    elif not (-90 <= lat <= 90 and -180 <= lng <= 180):
        errors["coordinates"] = "Coordinates out of range"

    overall = _clean_text(payload.get("overall_description"))
    surface = _clean_text(payload.get("surface_description"))
    underwater = _clean_text(payload.get("underwater_description"))
    if not (overall or surface or underwater):
        errors["description"] = "A description of the site is required"

    difficulty = _as_int(payload.get("difficulty"),
                         default=LocationRevision.Difficulty.EASY)
    if difficulty not in LocationRevision.Difficulty.values:
        errors["difficulty"] = "Invalid difficulty value"

    cleaned = {
        "name": name,
        "lat": lat,
        "lng": lng,
        "alternate_names": [_clean_text(n, 200) for n in
                            _as_list(payload.get("alternate_names")) if _clean_text(n)],
        "description": overall,
        "entry_description": surface,
        "access_type": _as_list(payload.get("access_type")),
        "water_type": _as_list(payload.get("water_type")),
        "difficulty": difficulty,
        "environment_types": _as_dict(payload.get("environment_types")),
        "marine_life": _as_dict(payload.get("marine_life")),
        "hazards": _as_dict(payload.get("hazards")),
        "facilities": _as_dict(payload.get("facilities")),
        "marker_data": _as_dict(payload.get("marker_data")),
        "country_code": _clean_text(payload.get("country_code"), 2).upper(),
        "country_name": _clean_text(payload.get("country_name"), 100),
        "region_name": _clean_text(payload.get("region_name"), 120),
        "locale_name": _clean_text(payload.get("locale_name"), 120),
    }
    return cleaned, errors


#  Helpers — geography

def resolve_geography(cleaned):
    country = region = locale = None

    if cleaned["country_code"]:
        country, _ = Country.objects.get_or_create(
            code=cleaned["country_code"],
            defaults={"name": cleaned["country_name"] or cleaned["country_code"]},
        )

    if country and cleaned["region_name"]:
        region, _ = Region.objects.get_or_create(
            country=country,
            name=cleaned["region_name"],
            defaults={"slug": slugify(cleaned["region_name"])},
        )

    if region and cleaned["locale_name"]:
        locale, _ = Locale.objects.get_or_create(
            region=region,
            name=cleaned["locale_name"],
            defaults={"slug": slugify(cleaned["locale_name"])},
        )

    return country, region, locale


def unique_slug(name):
    """Ensure slug is unique"""
    base = slugify(name)[:200] or "location"
    slug, n = base, 2
    while SnorkelLocation.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug

#  POST — publish

@login_required
@require_POST
def publish(request):
    """
    Receive the assembled location JSON, validate and create the SnorkelLocation with its first revision (increment 0).

    On success the new slug is returned so the client 
    """
    # convert json to python dict
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"errors": {"payload": "incorrecy JSON."}}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"errors": {"payload": "error with json object"}}, status=400)

    #validate submission
    cleaned, errors = validate_submission(payload)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    # create location
    try:
        with transaction.atomic():
            country, region, locale = resolve_geography(cleaned)
            location = SnorkelLocation.objects.create(
                point=Point(cleaned["lng"], cleaned["lat"], srid=4326),
                slug=unique_slug(cleaned["name"]),
                country=country,
                region=region,
                locale=locale,
                status=SnorkelLocation.Status.PUBLISHED,
            )
            revision = LocationRevision.objects.create(
                location=location,
                increment=0,
                name=cleaned["name"],
                alternate_names=cleaned["alternate_names"],
                overall_description=cleaned["overall_description"],
                surface_description=cleaned["surface_description"],
                underwater_description=cleaned["underwater_description"],
                access_type=cleaned["access_type"],
                water_type=cleaned["water_type"],
                difficulty=cleaned["difficulty"],
                environment_types=cleaned["environment_types"],
                marine_life=cleaned["marine_life"],
                hazards=cleaned["hazards"],
                facilities=cleaned["facilities"],
                marker_data=cleaned["marker_data"],
                created_by=request.user,
                revision_comment="Initial creation",
                diff={},                      # revision 0 has no predecessor
            )

            location.current_revision = revision
            location.save(update_fields=["current_revision"])

    except IntegrityError:
        return JsonResponse(
            {"errors": {"database": "Could not save the location, please retry."}},
            status=409,
        )

    # return slug to user
    return JsonResponse(
        {"slug": location.slug, "url": f"/location/{location.slug}/"},
        status=201,
    )