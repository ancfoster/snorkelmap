"""Placing a listing in the world, and giving it an address.

Two jobs that belong together because they are two views of the same
thing: which country, region and locale a location sits in, and what
that makes its URL.

Geography comes from a Mapbox lookup made here, against the stored
coordinates. Nothing about where a listing is comes from the browser:
the create form runs its own lookup for the person to read on screen,
but that answer decides nothing and is never stored.

It is deliberately forgiving about what comes back. A location in open
water has no country at all, a small country has no regions worth
naming, and a stretch of coast has no town near enough to be useful.
All three are normal, so each level is optional and the URL simply
gets shorter.
"""
from django.utils.text import slugify

from .mapbox import reverse_geocode
from .models import Country, Locale, Region, SnorkelLocation

# Stands in for the country segment when a location has no country,
# which is anything far enough offshore.
OCEAN_SEGMENT = "ocean"

SLUG_MAX = 200



def resolve(lat, lng):
    """Find or create the Country, Region and Locale for a point.

    The lookup happens here, against Mapbox, using the coordinates the
    pin was dropped on. Each level is only reached through the one
    above it, matching the model: a region belongs to a country, a
    locale to a region. So a place name with no country resolves to
    nothing rather than being attached to the wrong country.

    Returns the three rows plus a flag saying the lookup itself failed.
    That flag matters because "Mapbox says this is open water" and
    "Mapbox did not answer" produce an identical result here, and only
    one of them is correct. A caller stores the flag so the handful of
    listings that got the ocean URL by accident can be found and fixed,
    rather than refusing a submission over a timeout.
    """
    place = reverse_geocode(lat, lng)
    # An empty dict is a failure. A successful lookup over open water
    # returns the keys with empty values.
    lookup_failed = not place

    code = str(place.get("country_code") or "").strip().upper()[:2]
    country_name = str(place.get("country") or "").strip()[:100]
    region_name = str(place.get("region") or "").strip()[:120]
    locale_name = str(place.get("locale") or "").strip()[:120]

    country = region = locale = None

    if code:
        country, _ = Country.objects.get_or_create(
            code=code, defaults={"name": country_name or code,
                                 "slug": slugify(country_name or code)})
        # A row created from a code alone is slugged "fr" until the
        # name "France" turns up, so the slug follows the name.
        if country_name and country.name == country.code:
            country.name = country_name
            country.slug = slugify(country_name)
            country.save(update_fields=["name", "slug"])

    if country and region_name:
        region, _ = Region.objects.get_or_create(
            country=country, name=region_name,
            defaults={"slug": slugify(region_name)})

    if region and locale_name:
        locale, _ = Locale.objects.get_or_create(
            region=region, name=locale_name,
            defaults={"slug": slugify(locale_name)})

    return country, region, locale, lookup_failed


def unique_slug(name):
    """A slug for a listing, with a number appended if it is taken.

    Two different bays really can share a name, so the collision is
    handled rather than refused: the second Seal Cove becomes
    seal-cove-2.
    """
    base = slugify(name)[:SLUG_MAX] or "location"
    slug, suffix = base, 2
    while SnorkelLocation.objects.filter(slug=slug).exists():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def path_segments(location):
    """The URL segments for a location, shortest that identifies it.

        country, region and locale   united-kingdom/scottish-borders/st-abbs/<slug>
        country and region           united-kingdom/scottish-borders/<slug>
        country only                 united-kingdom/<slug>
        neither                      ocean/<slug>

    A locale cannot exist without its region, so those four are the
    only shapes there are.
    """
    if location.country_id is None:
        return [OCEAN_SEGMENT, location.slug]

    segments = [location.country.slug]
    if location.region_id is not None:
        segments.append(location.region.slug)
        if location.locale_id is not None:
            segments.append(location.locale.slug)
    segments.append(location.slug)
    return segments


# ── The directory ────────────────────────────────────────────────────

# Listings with no country at all are real: a reef in open water has
# nowhere to sit in an A-Z of countries, so they get their own card at
# the end rather than being dropped.
OCEAN_LABEL = "Open water"


def directory_tree(locations):
    """Group an ordered run of listings into country cards.

    Takes whatever it is given in the order it is given, and groups
    without re-sorting, so the ordering stays the database's job. Each
    card is:

        {"name", "code", "count", "regions", "unplaced",
         "unplaced_label"}

    where "regions" is a list of {"name", "locations"} and "unplaced"
    holds the listings in that country for which no region is known.
    The open water card, if there is one, is always last.

    Only attributes are read, so this can be checked without a database
    and without a Mapbox request.
    """
    countries = []   # the cards, in the order their countries first appear
    seen = {}        # country id -> its card
    regions = {}     # (country id, region id) -> its column
    ocean = {"name": OCEAN_LABEL, "code": "", "count": 0,
             "regions": [], "unplaced": [], "unplaced_label": ""}

    for location in locations:
        revision = location.current_revision
        entry = {"name": revision.name if revision else location.slug,
                 "url": location.get_absolute_url()}

        if location.country_id is None:
            ocean["unplaced"].append(entry)
            ocean["count"] += 1
            continue

        card = seen.get(location.country_id)
        if card is None:
            card = {
                "name": location.country.name,
                "code": location.country.code,
                "count": 0,
                "regions": [],
                # In the country, but the reverse geocode returned no
                # region for it. Listed under the country's own name
                # rather than hidden.
                "unplaced": [],
                "unplaced_label": location.country.name,
            }
            seen[location.country_id] = card
            countries.append(card)
        card["count"] += 1

        if location.region_id is None:
            card["unplaced"].append(entry)
            continue

        key = (location.country_id, location.region_id)
        column = regions.get(key)
        if column is None:
            column = {"name": location.region.name, "locations": []}
            regions[key] = column
            card["regions"].append(column)
        column["locations"].append(entry)

    if ocean["count"]:
        countries.append(ocean)
    return countries
