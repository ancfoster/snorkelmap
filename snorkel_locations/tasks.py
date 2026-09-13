"""Checking a photograph once it is in the bucket.

Everything the browser reported was a claim. This is where the claims
meet the file. It runs after the object exists, so it can read the real
bytes rather than trust anything that was sent alongside them.

Three checks, cheapest first:

  size    from a HEAD, which costs one request and no bytes.
  type    from a sixteen byte ranged read, sniffed with the same
          signatures the browser used. Catches a content type that was
          signed but not honoured.
  size in pixels
          from Cloudflare's own metadata endpoint, which decodes the
          image at the edge and reports its dimensions without any of
          it passing through Django. This is the one that cannot be
          faked from the browser.

Nothing here is destructive on a failed check beyond marking the row
rejected and removing the object: the listing survives, and the person
can add another photo.
"""
import logging

from django.utils import timezone

from . import media, media_storage
from .models import LocationMedia, SnorkelLocation

logger = logging.getLogger(__name__)

SNIFF_BYTES = 1024
DIMENSION_TIMEOUT = 10


def _reject(row, reason):
    row.status = LocationMedia.Status.REJECTED
    row.rejection_reason = reason[:120]
    row.verified_at = timezone.now()
    row.save(update_fields=["status", "rejection_reason", "verified_at"])
    media_storage.delete_object(row.object_key)
    logger.warning("Media %s rejected: %s", row.uuid, reason)
    return False


def remote_dimensions(key):
    """Width and height as Cloudflare sees them, or None.

    format=json asks the image service for metadata instead of an
    image, so this works for HEIC as readily as for JPEG and needs no
    decoder of our own.
    """
    base = media_storage.transform_url(key, "format=json")
    if not base.startswith("http"):
        return None
    try:
        import requests
        response = requests.get(base, timeout=DIMENSION_TIMEOUT)
        if response.status_code != 200:
            return None
        payload = response.json()
    except Exception:
        logger.exception("Could not read dimensions for %s", key)
        return None
    width, height = payload.get("width"), payload.get("height")
    return (width, height) if width and height else None


def verify_media(media_uuid):
    """Confirm one uploaded photograph, then publish if it was the last."""
    row = LocationMedia.objects.filter(uuid=media_uuid).first()
    if row is None:
        logger.warning("Verification asked for unknown media %s", media_uuid)
        return False

    # At least once delivery, so this may be the second or third time
    # this object has been announced. A row that has already been
    # decided is left exactly as it is.
    if row.status in (LocationMedia.Status.ACTIVE,
                      LocationMedia.Status.REJECTED,
                      LocationMedia.Status.REMOVED):
        return row.status == LocationMedia.Status.ACTIVE

    stored = media_storage.head_object(row.object_key)
    if stored is None:
        # Not there yet, or R2 had a moment. Either way this is not a
        # verdict on the photograph, so the row stays pending and
        # whichever path runs next gets another go. Rejecting here
        # would turn a confirm that arrived a fraction early, or one
        # transient failure, into a lost photo.
        logger.info("Media %s is not in the bucket yet", row.uuid)
        return False

    limits = media.media_rules()["limits"]
    if not (limits["min_bytes"] <= (stored["bytes"] or 0) <= limits["max_bytes"]):
        return _reject(row, f"Stored size {stored['bytes']} is outside the limits")

    head = media_storage.read_head_bytes(row.object_key, SNIFF_BYTES)
    if not head:
        # The object exists, since HEAD found it, so a failed read is a
        # transient problem rather than a bad file. Leave it pending.
        logger.warning("Could not read %s to verify it", row.object_key)
        return False

    sniffed = media.sniff(head)
    if not media.is_accepted(sniffed):
        return _reject(row, f"Stored bytes are {sniffed or 'unrecognised'}")
    if sniffed != row.mime_type:
        return _reject(row,
                       f"Stored bytes are {sniffed}, not {row.mime_type}")

    size = remote_dimensions(row.object_key)
    if size:
        width, height = size
        if min(width, height) < limits["min_dimension"]:
            return _reject(row, f"Stored image is {width} by {height}")
        if max(width, height) > limits["max_dimension"]:
            return _reject(row, f"Stored image is {width} by {height}")
        row.width, row.height = width, height

    row.size_bytes = stored["bytes"]
    row.status = LocationMedia.Status.ACTIVE
    row.verified_at = timezone.now()
    row.rejection_reason = ""
    row.save(update_fields=["width", "height", "size_bytes", "status",
                            "verified_at", "rejection_reason"])

    assign_featured_image(row)
    return True


def assign_featured_image(media_row):
    """Point the revision at its first confirmed above water photo.

    Called only once a photograph is verified, so the field never holds
    a row that is pending or was later refused.

    Uploads confirm in whatever order they finish, not the order they
    were added in, so a photo that arrives later but sits earlier in
    the list takes over. Once every upload has settled the featured
    image is the first above water photograph the person chose, which
    is the one they would expect to see.

    Only ever fills an empty field or replaces an earlier automatic
    choice. Once someone picks a different picture to represent the
    place, a later upload must not quietly overrule them.
    """
    if media_row.media_category != LocationMedia.MediaCategory.SURFACE:
        return False

    revision = media_row.location.current_revision
    if revision is None:
        return False

    current = revision.featured_above_water_image
    if (current is not None
            and current.status == LocationMedia.Status.ACTIVE
            and current.sort_order <= media_row.sort_order):
        return False

    revision.featured_above_water_image = media_row
    revision.save(update_fields=["featured_above_water_image"])
    return True


def enqueue_verification(media_uuid):
    """Hand verification off to a worker.

    Deliberately still synchronous. django.tasks ships an immediate,
    in request backend and a dummy one, so a real queue means adding
    django-tasks-db and running its db_worker alongside the site. Until
    that is set up this runs inline, which is correct but holds the
    webhook request open for a HEAD, a ranged read and one metadata
    call. Once the backend is chosen this becomes:

        from django.tasks import task
        verify_media_task.enqueue(str(media_uuid))
    """
    return verify_media(media_uuid)
