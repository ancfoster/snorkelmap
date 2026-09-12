"""Turning a location into the handful of fields a card shows.

Shared by the pane down the side of the map, the card that opens when a
pin is clicked, and the first paint of the map page. One place, because
three copies of "which photograph, and what if there isn't one" is how
they end up disagreeing.

Nothing here queries. It is handed rows that were fetched with their
geography and photograph already selected, so a pane of twenty costs
one query rather than sixty.
"""
from django.conf import settings

from . import media_storage

# What the card image is asked for. The edge produces it from the
# stored original on first request and caches it after that.
THUMBNAIL_OPTIONS = "width=600,format=auto"

OPEN_WATER = "Open water"


def thumbnail_for(revision):
    """The card's photograph, or the stand-in.

    A location can be published and still have no usable image: the
    photograph that published it can be removed later, and an older
    listing may never have had one. Both land here, and both get the
    same picture rather than a broken image.
    """
    image = getattr(revision, "featured_above_water_image", None)
    key = getattr(image, "object_key", "") if image is not None else ""
    if not key:
        return settings.NO_IMAGE_URL
    return media_storage.transform_url(key, THUMBNAIL_OPTIONS)


def place_line(location):
    """Where it is, in the two most specific names available.

    A town and its region when both are known, otherwise the region and
    its country, otherwise just the country. Somewhere offshore has
    none of them and says so.
    """
    locale = location.locale.name if location.locale_id else ""
    region = location.region.name if location.region_id else ""
    country = location.country.name if location.country_id else ""

    if locale and region:
        return f"{locale}, {region}"
    if region and country:
        return f"{region}, {country}"
    return country or OPEN_WATER


def card_for(location):
    """Everything one card needs, and nothing else."""
    revision = location.current_revision
    return {
        "uuid": str(location.uuid),
        "name": revision.name if revision else location.slug,
        "place": place_line(location),
        "thumbnail": thumbnail_for(revision),
        "url": location.get_absolute_url(),
    }


def cards_for(locations):
    return [card_for(location) for location in locations]
