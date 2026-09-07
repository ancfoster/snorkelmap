from .settings import *

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent

ALLOWED_HOSTS = ['snorkelmap.local', 'localhost', '127.0.0.1']

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

TURNSTILE_SECRET = '1x0000000000000000000000000000000AA'  #Cloudflare test key
TURNSTILE_SITEKEY = '1x00000000000000000000AA'  # Cloudflare test key

# GeoDjango  C libraries (Homebrew Apple Silicon)
GDAL_LIBRARY_PATH = "/opt/homebrew/lib/libgdal.dylib"
GEOS_LIBRARY_PATH = "/opt/homebrew/lib/libgeos_c.dylib"

INSTALLED_APPS.append('django_extensions')

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    }
}

STATICFILES_DIRS = [
    BASE_DIR / "static",
]