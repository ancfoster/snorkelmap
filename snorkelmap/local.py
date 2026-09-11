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

# Development uploads go to their own bucket. The check is here because
# an .env copied from the server is an easy mistake to make and a
# hard one to notice: the first sign would be test photographs on the
# live site.
from django.core.exceptions import ImproperlyConfigured  # noqa: E402

R2_MEDIA_BUCKET = os.environ.get('R2_MEDIA_BUCKET', 'snorkelmap-media-dev')
if not R2_MEDIA_BUCKET.endswith(('-dev', '-local')):
    raise ImproperlyConfigured(
        f"R2_MEDIA_BUCKET is {R2_MEDIA_BUCKET!r}. Development settings will "
        f"only use a bucket ending in -dev or -local."
    )
