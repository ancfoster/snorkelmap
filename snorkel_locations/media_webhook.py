"""Where the bucket tells Django a photograph has arrived.

R2 raises an event on upload, a Cloudflare Queue holds it, and a very
small Worker reads the queue and posts here. The Worker never touches
the image itself, only its name and size, which is what keeps it clear
of the 128MB memory ceiling a Worker has: a 24 megapixel photo is over
70MB decoded, so a Worker that opened one would fall over.

The Worker normalises Cloudflare's event shape into the payload below,
so this endpoint has one format to deal with and the awkwardness stays
in the one place that is easy to redeploy.

Delivery is at least once and out of order, so the handler is written
to be safe to run twice on the same object.
"""
import hashlib
import hmac
import logging
import time

from django.conf import settings
from ninja import Router, Schema

from .models import LocationMedia
from .tasks import enqueue_verification

logger = logging.getLogger(__name__)
router = Router()

SIGNATURE_HEADER = "HTTP_X_SNORKELMAP_SIGNATURE"
MAX_SKEW_SECONDS = 300
MAX_EVENTS = 100


class MediaEvent(Schema):
    key: str
    size: int = 0
    action: str = "PutObject"


class MediaEventBatch(Schema):
    events: list[MediaEvent]


def parse_signature(raw):
    """Read a `t=<unix>,v1=<hex>` header into its parts."""
    parts = {}
    for chunk in (raw or "").split(","):
        name, _, value = chunk.strip().partition("=")
        if name and value:
            parts[name] = value
    return parts.get("t"), parts.get("v1")


def signature_is_valid(request):
    """Constant time check of the shared secret over timestamp and body.

    The timestamp is inside the signed material, so an intercepted
    request cannot be replayed later: change the timestamp and the
    signature no longer matches, keep it and the age check refuses it.
    """
    secret = getattr(settings, "R2_MEDIA_WEBHOOK_SECRET", "")
    if not secret:
        logger.error("Media webhook called with no secret configured")
        return False

    timestamp, provided = parse_signature(request.META.get(SIGNATURE_HEADER))
    if not timestamp or not provided:
        return False
    try:
        age = abs(time.time() - int(timestamp))
    except ValueError:
        return False
    if age > MAX_SKEW_SECONDS:
        return False

    signed = f"{timestamp}.".encode() + request.body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


@router.post("/events", auth=None)
def media_events(request, payload: MediaEventBatch):
    if not signature_is_valid(request):
        # Deliberately uninformative. Anything more tells whoever is
        # probing which part of the signature they got wrong.
        return 403, {"detail": "Bad signature"}

    accepted = 0
    for event in payload.events[:MAX_EVENTS]:
        row = LocationMedia.objects.filter(object_key=event.key).first()
        if row is None:
            # An object with no row behind it. Most likely a leftover
            # from a submission that was never completed, so it is
            # logged and left alone rather than deleted on a guess.
            logger.warning("Media event for unknown key %s", event.key)
            continue
        enqueue_verification(row.uuid)
        accepted += 1

    # 200 as soon as the events have been taken on, so the queue can
    # let them go. Anything that fails afterwards is our problem to
    # retry, not something to make Cloudflare redeliver.
    return {"received": len(payload.events), "accepted": accepted}
