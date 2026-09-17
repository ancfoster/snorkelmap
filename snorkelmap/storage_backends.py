"""
Custom storage backends.

S3ManifestStaticStorage (django-storages) mixes in Django's
ManifestFilesMixin, the same hashed-filename machinery as the built-in
ManifestStaticFilesStorage. By default `manifest_strict = True`, so
{% static %} raises ValueError -> HTTP 500 for the whole page whenever
a referenced file was missing at collectstatic time (e.g. a template
points at an image that was never added to the repo).

That's the wrong failure mode for us: a missing thumbnail or example
photo shouldn't take down the page it's on. Setting manifest_strict =
False makes Django log a warning and fall back to the plain, unhashed
URL instead of raising. The browser then requests that URL, gets a 404
from R2, and shows its normal broken-image placeholder - exactly the
degradation we want. See:
https://docs.djangoproject.com/en/stable/ref/contrib/staticfiles/#django.contrib.staticfiles.storage.ManifestStaticFilesStorage.manifest_strict
"""
from storages.backends.s3 import S3ManifestStaticStorage


class LenientS3ManifestStaticStorage(S3ManifestStaticStorage):
    manifest_strict = False
