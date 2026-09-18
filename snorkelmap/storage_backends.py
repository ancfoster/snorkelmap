"""
Custom storage backends.

S3ManifestStaticStorage (django-storages) mixes in Django's
ManifestFilesMixin, the same hashed-filename machinery as the built-in
ManifestStaticFilesStorage. By default a {% static %} reference to a
file that was not present at collectstatic time raises ValueError, so
one missing image returns HTTP 500 for the whole page. A missing
example photograph should not take down the page it sits on.

Note on why manifest_strict = False is NOT the fix here, despite the
Django docs suggesting it. Setting it False only skips the first
raise; stored_name() then falls through to hashed_name(), which calls
self.exists() and raises its own ValueError when the file is genuinely
absent. The documented "nonexistent paths will remain unchanged"
behaviour holds only when the file exists in storage but is missing
from the manifest, which is not our case. Worse, on an S3 backend that
exists() is a network HEAD request against R2, so every missing image
would cost a round trip on every page render.

So manifest_strict stays at its default True, making the manifest miss
a cheap dict lookup that raises immediately with no I/O, and we catch
that here and fall back to the plain unhashed path. The browser
requests that URL, R2 returns 404, and the browser shows its normal
broken-image placeholder while the rest of the page renders.

Files that ARE in the manifest are untouched and still get their
hashed, cache-busted URL.
"""
import logging

from storages.backends.s3 import S3ManifestStaticStorage

logger = logging.getLogger(__name__)


class LenientS3ManifestStaticStorage(S3ManifestStaticStorage):
    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            logger.warning(
                "Static file missing from manifest, serving unhashed URL: %s", name
            )
            return name
