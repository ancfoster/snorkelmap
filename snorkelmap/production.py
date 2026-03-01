from .settings import *

STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3ManifestStaticStorage",
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
