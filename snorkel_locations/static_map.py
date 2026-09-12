"""A picture of where a location is, drawn once and kept.

Mapbox will render a raster map of any point on request, and the
listing page could simply point an <img> at that URL. It should not.
That URL carries an access token, so publishing it on a public page
hands the token to anybody who reads the source, and every view of
every listing becomes a billable Mapbox request. Fetching it once here,
storing the result, and serving it from our own bucket costs one
request per location for the life of the location.

It lives in the geo bucket, under listing-maps/, beside the map's data
file: both are pictures of where things are rather than anything
anybody uploaded, and keeping them out of the media bucket means the
Worker that watches for new photographs never sees them.

It is served exactly as Mapbox rendered it, with no image service in
front. That makes the constants below the only thing deciding how big
the file a visitor downloads is, so they are worth reading before
changing.

The framing matches the static prototype exactly: outdoors-v12, zoom
14, no bearing or pitch, 800x450. The only addition is @2x, which is
the same picture at twice the pixels for a retina screen; it changes
what is in frame not at all, and dropping it is one character.

Nothing here is allowed to fail loudly. A listing with no map picture
is a listing missing a picture, not a broken one, and generate_map_images
exists to fill in whatever did not work the first time.
"""
import logging

from django.conf import settings

from . import geo_storage

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.mapbox.com/styles/v1"

# As the prototype had it.
STYLE = "mapbox/outdoors-v12"
ZOOM = 14
BEARING = 0
PITCH = 0
WIDTH = 800
HEIGHT = 450
RETINA = True

TIMEOUT = 10

# A plausible floor and ceiling for a 800x450 PNG from Mapbox. Anything
# outside it is not a map: an error page, a truncated response, or an
# empty body served with a 200.
MIN_BYTES = 5_000
MAX_BYTES = 5_000_000


def build_url(lat, lng, token):
    """The Mapbox Static Images request for a point.

    Note the order: Mapbox takes longitude first, and getting that the
    wrong way round produces a perfectly valid map of somewhere else,
    which is the kind of mistake that survives a casual look.
    """
    size = f"{WIDTH}x{HEIGHT}" + ("@2x" if RETINA else "")
    return (f"{ENDPOINT}/{STYLE}/static/"
            f"{lng},{lat},{ZOOM},{BEARING},{PITCH}/{size}"
            f"?access_token={token}")


def fetch(lat, lng):
    """The rendered map as bytes, or b"" if it could not be had.

    Uses the server token rather than the public one. The public token
    is meant to be restricted to the site's own URLs, and a request
    made from Django carries no referring page, so a restricted token
    would fail here and only here.
    """
    token = getattr(settings, "MAPBOX_SERVER_TOKEN", "")
    if not token:
        logger.error(
            "MAPBOX_SERVER_TOKEN is not set, so no location maps can be "
            "drawn. It is separate from MAPBOX_TOKEN because that one is "
            "restricted by URL and a request from the server has no URL.")
        return b""

    try:
        import requests
        response = requests.get(build_url(lat, lng, token), timeout=TIMEOUT)
    except Exception:
        logger.exception("Mapbox static map request failed for %s,%s", lat, lng)
        return b""

    if response.status_code != 200:
        logger.warning("Mapbox static map returned %s for %s,%s",
                       response.status_code, lat, lng)
        return b""

    body = response.content or b""
    if not (MIN_BYTES <= len(body) <= MAX_BYTES):
        logger.warning("Mapbox static map for %s,%s was %s bytes, which is "
                       "not a map", lat, lng, len(body))
        return b""
    if not body.startswith(b"\x89PNG\r\n\x1a\n"):
        logger.warning("Mapbox static map for %s,%s was not a PNG", lat, lng)
        return b""
    return body


def generate_for(location, force=False):
    """Draw, store and record a location's map. Returns the key, or "".

    Already has one and force is off: nothing happens and no request is
    made, which is what makes the backfill command safe to run as often
    as you like.
    """
    if location.map_image_key and not force:
        return location.map_image_key

    point = location.lat_long
    if point is None:
        return ""

    body = fetch(point.y, point.x)
    if not body:
        return ""

    key = geo_storage.build_listing_map_key(location.uuid)
    try:
        geo_storage.put_listing_map(key, body)
    except Exception:
        logger.exception("Could not store the map for location %s",
                         location.uuid)
        return ""

    location.map_image_key = key
    location.save(update_fields=["map_image_key"])
    return key


def image_url(location):
    """The stored map, served straight from the bucket. "" if none.

    No image service in front of it: what Mapbox rendered is what the
    browser gets. The size of that file is therefore decided entirely
    by WIDTH, HEIGHT and RETINA above, since nothing downstream will
    resize or re-encode it.
    """
    key = getattr(location, "map_image_key", "")
    if not key:
        return ""
    base = (getattr(settings, "R2_GEO_PUBLIC_BASE", "") or "").rstrip("/")
    if not base:
        return ""
    return f"{base}/{key}"
