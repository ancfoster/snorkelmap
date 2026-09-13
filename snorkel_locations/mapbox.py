"""Reverse geocoding, server side.

The create form also asks Mapbox where the pin is, but that answer is
for the person looking at the screen. It is not used for anything that
gets stored.

This lookup is. The country, region and locale it returns decide which
rows a listing is attached to and what its permanent URL is, so the
answer has to come from Mapbox to us directly. Anything that travelled
through the browser is a claim, and a claim is not a good basis for an
address that other people will link to.

The parsing is deliberately separate from the request, so the shape of
a Mapbox response can be tested without the network.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.mapbox.com/geocoding/v5/mapbox.places"

# Matches the types the create form asks for, so what a person sees
# while dropping the pin and what gets stored come from the same view
# of the world.
TYPES = "country,region,place"

TIMEOUT = 4
ATTEMPTS = 2


def _feature_of(features, place_type):
    for feature in features:
        if place_type in (feature.get("place_type") or []):
            return feature
    return None


def extract(features):
    """Pull the three levels out of a Mapbox v5 reverse geocode.

    Returns names plus the ISO country code, which is what the Country
    row is keyed on. Missing levels come back empty, which is normal:
    open water has no country, and plenty of coastline has no place
    near enough to name.
    """
    features = features or []
    country = _feature_of(features, "country")
    region = _feature_of(features, "region")
    place = _feature_of(features, "place")

    code = ""
    if country:
        # On a country feature short_code is the ISO alpha-2, lower
        # case. On a region it is a subdivision code such as GB-SCB,
        # which is why only the country feature is read for it.
        code = str((country.get("properties") or {}).get("short_code") or "")
        code = code.split("-")[0].upper()[:2]

    return {
        "country": (country or {}).get("text", "") or "",
        "country_code": code,
        "region": (region or {}).get("text", "") or "",
        "locale": (place or {}).get("text", "") or "",
    }


def reverse_geocode(lat, lng):
    """Ask Mapbox what is at a point. Returns {} if it cannot say.

    An empty result is not the same as open water, and the caller has
    to treat it as "not known yet" rather than "nowhere". A listing
    that lands with no geography because of a timeout gets the ocean
    URL, which is wrong for a beach, so the failure is logged loudly
    enough to be found and corrected.
    """
    token = getattr(settings, "MAPBOX_TOKEN", "")
    if not token:
        logger.error("MAPBOX_TOKEN is not set: no geography will be resolved")
        return {}

    url = f"{ENDPOINT}/{lng},{lat}.json"
    params = {"types": TYPES, "access_token": token, "language": "en"}

    import requests
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
            if response.status_code != 200:
                logger.warning("Mapbox reverse geocode returned %s for %s,%s",
                               response.status_code, lat, lng)
                continue
            return extract((response.json() or {}).get("features"))
        except Exception:
            logger.warning("Mapbox reverse geocode failed for %s,%s (attempt %s)",
                           lat, lng, attempt, exc_info=True)

    logger.error("Could not resolve geography for %s,%s", lat, lng)
    return {}
