"""Object storage for the map's data file.

A third bucket, separate from static files and from photographs, for
the same reason those two are separate from each other: a different
lifecycle and a different access pattern. This one holds a single small
file that is rewritten whenever a location is published and read by
every visitor who opens the map.

The file is written under a content addressed name and served with an
immutable cache header, because a browser's cache cannot be purged.
Cloudflare's can, with an API call, but every visitor who already has
the file keeps it until its max-age runs out, so a fixed name with a
long cache life would leave people looking at a stale map for however
long that was. A new name for new contents sidesteps the problem
entirely: the URL is rendered into the page by Django, so the next page
load points at the new file and the old one is simply never asked for
again.
"""
import boto3
from botocore.config import Config
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

KEY_PREFIX = "map"

# A year, which is the longest value the spec gives meaning to, plus
# immutable so a browser does not even revalidate on a reload.
CACHE_CONTROL = "public, max-age=31536000, immutable"

CONTENT_TYPE = "application/geo+json"


def _client():
    """An S3 client for the geo bucket, and only the geo bucket.

    Credentials are read explicitly with no fallback to the static or
    media pairs, for the reason set out in media_storage: signing is
    local arithmetic with no permission check, so the wrong token
    produces a client that works perfectly right up until every request
    is refused, and nothing in the logs says why.
    """
    access_key = getattr(settings, "R2_GEO_ACCESS_KEY", "")
    secret_key = getattr(settings, "R2_GEO_SECRET_KEY", "")
    if not access_key or not secret_key:
        raise ImproperlyConfigured(
            "R2_GEO_ACCESS_KEY and R2_GEO_SECRET_KEY must both be set. "
            "They are deliberately separate from the static and media "
            "credentials: this token is scoped to the geo bucket alone."
        )
    endpoint = getattr(settings, "R2_ENDPOINT_URL", "")
    if not endpoint:
        raise ImproperlyConfigured("R2_ENDPOINT_URL is not set.")
    bucket = getattr(settings, "R2_GEO_BUCKET", "")
    if not bucket:
        raise ImproperlyConfigured("R2_GEO_BUCKET is not set.")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def build_key(digest):
    """map/locations-<digest>.geojson"""
    return f"{KEY_PREFIX}/locations-{digest}.geojson"


def put_data_file(key, body):
    """Upload the data file. Raises rather than reporting failure quietly."""
    client = _client()
    client.put_object(
        Bucket=settings.R2_GEO_BUCKET,
        Key=key,
        Body=body,
        ContentType=CONTENT_TYPE,
        CacheControl=CACHE_CONTROL,
    )
    return key


def public_url(key):
    """The address the browser fetches, behind the bucket's own domain."""
    base = (getattr(settings, "R2_GEO_PUBLIC_BASE", "") or "").rstrip("/")
    if not base or not key:
        return ""
    return f"{base}/{key}"


def list_data_files():
    """Every data file in the bucket, current and superseded."""
    client = _client()
    keys = []
    token = None
    while True:
        kwargs = {"Bucket": settings.R2_GEO_BUCKET, "Prefix": f"{KEY_PREFIX}/"}
        if token:
            kwargs["ContinuationToken"] = token
        page = client.list_objects_v2(**kwargs)
        keys.extend(item["Key"] for item in page.get("Contents", []))
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken")
    return keys


def delete_object(key):
    client = _client()
    client.delete_object(Bucket=settings.R2_GEO_BUCKET, Key=key)
