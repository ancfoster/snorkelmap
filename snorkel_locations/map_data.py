"""The map's data file: every published location, in one small file.

The browser holds the whole thing. That is the design, not a shortcut:
with every coordinate already in the page, panning and zooming needs no
request at all, the clustering is Mapbox's own, and working out which
locations are in view is arithmetic rather than a round trip. It stops
being the right design somewhere around five or ten thousand locations,
at which point this becomes vector tiles and the browser stops holding
everything. Until then it is both faster and less to defend, because
there is no per-viewport query for anyone to abuse.

So the file carries only what is needed to place a pin and decide which
pins are on screen: an id, a name, and a position. Roughly seventy
bytes a location. Everything a card shows, the photograph above all,
is fetched separately for the twenty that are actually displayed.

Rebuilt in full every time, never patched. A file assembled by applying
changes to a previous one is a file that drifts, and the whole query
takes milliseconds.
"""
import hashlib
import json
import logging

from . import geo_storage
from .models import MapData, SnorkelLocation

logger = logging.getLogger(__name__)


def feature_collection():
    """Every published location as GeoJSON.

    Coordinates are rounded to five decimal places, a little over a
    metre, which is finer than any pin dropped on a phone screen and
    saves a third of the file.
    """
    rows = (
        SnorkelLocation.objects
        .filter(status=SnorkelLocation.Status.PUBLISHED,
                current_revision__isnull=False)
        .select_related("current_revision")
        .order_by("id")
    )

    features = []
    for location in rows:
        point = location.lat_long
        if point is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(point.x, 5), round(point.y, 5)],
            },
            "properties": {
                "uuid": str(location.uuid),
                "name": location.current_revision.name,
            },
        })

    return {"type": "FeatureCollection", "features": features}


def serialise(collection):
    """Compact JSON as bytes, plus the digest its filename is built from.

    separators matter here: the default ", " and ": " add about eight
    bytes a location for nothing.
    """
    body = json.dumps(collection, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return body, hashlib.sha256(body).hexdigest()[:12]


def build_and_publish(force=False):
    """Rebuild the file and upload it if its contents changed.

    Returns the key now in use, or "" if the upload failed. A failure
    is deliberately not raised: this is called when a location is
    published, and a location going live must not depend on a bucket
    being reachable. The previous file keeps being served, which is
    stale rather than broken, and the next publication or a run of
    rebuild_map_data fixes it.

    The log line is therefore the only sign, and is worth watching.
    """
    record = MapData.load()
    body, digest = serialise(feature_collection())
    key = geo_storage.build_key(digest)

    if key == record.object_key and not force:
        return key

    try:
        geo_storage.put_data_file(key, body)
    except Exception:
        logger.exception(
            "Map data upload failed; still serving %s",
            record.object_key or "nothing")
        return ""

    record.mark_built(key, len(body))
    logger.info("Map data rebuilt: %s (%s bytes)", key, len(body))
    return key
