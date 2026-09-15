from .settings import *

STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "snorkelmap.storage_backends.NonStrictS3ManifestStaticStorage",
        "OPTIONS": {
            "bucket_name": os.environ['R2_BUCKET_NAME'],
            "endpoint_url": os.environ['R2_ENDPOINT_URL'],
            "access_key": os.environ['R2_ACCESS_KEY'],
            "secret_key": os.environ['R2_SECRET_KEY'],
            "region_name": "auto",
            "location": "",
            "file_overwrite": True,
            "default_acl": None,
            "querystring_auth": False,
             "custom_domain": "static.snorkelmap.com", 
            "object_parameters": {
                "CacheControl": "max-age=86400, immutable",
            },
        },
    }
}

# CDN URL for static files
STATIC_URL = "https://static.snorkelmap.com/"
STATIC_ROOT = BASE_DIR / "staticfiles"


from django.core.exceptions import ImproperlyConfigured  # noqa: E402

if not R2_MEDIA_BUCKET:
    raise ImproperlyConfigured("R2_MEDIA_BUCKET is not set.")
if R2_MEDIA_BUCKET.endswith(('-dev', '-local', '-test')):
    raise ImproperlyConfigured(
        f"R2_MEDIA_BUCKET is {R2_MEDIA_BUCKET!r}, which is a development "
        f"bucket. Production will not write to it."
    )
