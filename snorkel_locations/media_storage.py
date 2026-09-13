"""Object storage for submitted photographs.

The browser never sends image bytes to Django. It asks for an upload
slot, receives a signature that is only good for one exact object, and
puts the file into R2 itself. Django stays out of the data path
entirely, which is what keeps a request holding a dozen 8MB photos from
tying up a worker process.

What the signature pins:

  the key          the object name is part of what is signed, so the
                   browser cannot choose it. A file arrives as
                   media/<location uuid>/<media uuid>.<ext> whatever it
                   was called on the person's phone.
  the content type derived from the sniffed bytes, not from the name or
                   from what the browser claimed the type was.
  the size         a presigned POST carries a content-length-range
                   condition, so an oversized body is refused by R2
                   rather than accepted and cleaned up afterwards.

The size condition is the reason for preferring POST over PUT. If R2
turns out not to accept POST object uploads on this account, set
R2_MEDIA_UPLOAD_METHOD to "put": everything else is unchanged and the
size is then caught by the verification step instead, which reads the
stored object's real length back before the media row goes active.
"""
import uuid

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .media import MAX_FILE_BYTES, MIN_FILE_BYTES, extension_for

KEY_PREFIX = "media"


def _client():
    """An S3 client for the media bucket, and only the media bucket.

    The credentials are read explicitly, with no fallback to the pair
    the static files bucket uses. A fallback would be convenient and
    dangerous: a token scoped to the static bucket produces a client
    that signs uploads perfectly well, because signing is local
    arithmetic with no permission check, and then every upload is
    refused by R2 and every verification reports the object as simply
    not there. Nothing in the logs would say why.

    Missing credentials therefore raise here rather than producing a
    client that looks fine and silently cannot reach anything.
    """
    access_key = getattr(settings, "R2_MEDIA_ACCESS_KEY", "")
    secret_key = getattr(settings, "R2_MEDIA_SECRET_KEY", "")
    if not access_key or not secret_key:
        raise ImproperlyConfigured(
            "R2_MEDIA_ACCESS_KEY and R2_MEDIA_SECRET_KEY must both be set. "
            "They are deliberately separate from the static files "
            "credentials: this token signs uploads, so it is scoped to "
            "the media bucket alone."
        )
    if not settings.R2_ENDPOINT_URL:
        raise ImproperlyConfigured("R2_ENDPOINT_URL is not set.")

    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def build_key(location_uuid, media_uuid, mime):
    """The object name, decided here and nowhere else."""
    return (f"{KEY_PREFIX}/{location_uuid}/{media_uuid}"
            f".{extension_for(mime)}")


def new_media_uuid():
    return uuid.uuid4()


def presign_upload(key, mime, max_bytes=None):
    """An upload slot for exactly one object.

    Returns a dict the browser can act on without knowing which method
    was signed:

        {"method": "post", "url": ..., "fields": {...}}
        {"method": "put",  "url": ..., "headers": {...}}
    """
    max_bytes = max_bytes or MAX_FILE_BYTES
    client = _client()
    expires = getattr(settings, "R2_MEDIA_UPLOAD_EXPIRY", 900)

    if getattr(settings, "R2_MEDIA_UPLOAD_METHOD", "post") == "put":
        url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.R2_MEDIA_BUCKET,
                "Key": key,
                "ContentType": mime,
            },
            ExpiresIn=expires,
        )
        return {"method": "put", "url": url, "headers": {"Content-Type": mime}}

    signed = client.generate_presigned_post(
        Bucket=settings.R2_MEDIA_BUCKET,
        Key=key,
        Fields={"Content-Type": mime},
        Conditions=[
            {"Content-Type": mime},
            ["content-length-range", MIN_FILE_BYTES, max_bytes],
        ],
        ExpiresIn=expires,
    )
    return {"method": "post", "url": signed["url"], "fields": signed["fields"]}


def head_object(key):
    """Size and type of a stored object, or None if it is not there.

    The client is built outside the try, so a configuration problem
    raises instead of being reported as a missing object. The broad
    except is there to absorb "not found" and transient R2 errors, not
    to hide a bad setup.
    """
    client = _client()
    try:
        response = client.head_object(
            Bucket=settings.R2_MEDIA_BUCKET, Key=key)
    except Exception:
        return None
    return {
        "bytes": response.get("ContentLength"),
        "mime": response.get("ContentType"),
    }


def read_head_bytes(key, length=1024):
    """The opening bytes of a stored object.

    Used by the verification step to sniff what actually landed, rather
    than trusting the content type the browser asked to have signed. A
    ranged read, so the cost is the same whether the object is 200KB or
    20MB.
    """
    client = _client()
    try:
        response = client.get_object(
            Bucket=settings.R2_MEDIA_BUCKET, Key=key,
            Range=f"bytes=0-{length - 1}")
    except Exception:
        return None
    return response["Body"].read()


def delete_object(key):
    client = _client()
    try:
        client.delete_object(Bucket=settings.R2_MEDIA_BUCKET, Key=key)
        return True
    except Exception:
        return False


def public_url(key):
    """Where the object is served from, through the custom domain."""
    base = getattr(settings, "R2_MEDIA_PUBLIC_BASE", "") or ""
    return f"{base.rstrip('/')}/{key}" if base else key


def transform_url(key, options="width=800,format=auto"):
    """A Cloudflare Image Transformations URL for a stored original.

    No variants are pre-generated and nothing is written to a second
    bucket: the original is the only copy, and every size the site asks
    for is produced at the edge on first request and then cached.
    """
    base = (getattr(settings, "R2_MEDIA_PUBLIC_BASE", "") or "").rstrip("/")
    return f"{base}/cdn-cgi/image/{options}/{key}"
