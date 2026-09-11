"""A three word address for a set of coordinates.

Best effort, always. The address is a convenience for people meeting at
a spot with no useful postcode, which describes most of the coastline.
A listing without one is complete; a publish that fails because a third
party API was slow is not acceptable.

So every failure here returns an empty string and the caller carries
on. The timeout is short for the same reason: the person is watching a
progress screen, and no three word address is worth making them wait
for.

This is the piece most obviously suited to a background task. It is
inline for now because the site has no worker process yet, and the
shape of the call does not change when it moves: the same function gets
called from a task instead of from the endpoint.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.what3words.com/v3/convert-to-3wa"
TIMEOUT = 3
MAX_LENGTH = 200


def words_for(lat, lng, language="en"):
    """Return "filled.count.soap" for a point, or "" if unavailable."""
    api_key = getattr(settings, "W3W_API_KEY", "")
    if not api_key:
        return ""

    try:
        import requests
        response = requests.get(
            ENDPOINT,
            params={
                "coordinates": f"{lat},{lng}",
                "key": api_key,
                "language": language,
            },
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            logger.warning("what3words returned %s for %s,%s",
                           response.status_code, lat, lng)
            return ""
        words = (response.json() or {}).get("words") or ""
    except Exception:
        # Timeout, DNS, a rate limit, malformed JSON. All the same
        # outcome from here: no address, publish continues.
        logger.exception("what3words lookup failed for %s,%s", lat, lng)
        return ""

    return str(words)[:MAX_LENGTH]
