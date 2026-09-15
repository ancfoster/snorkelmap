"""Small storage subclasses that only exist to set class attributes
django-storages doesn't expose through STORAGES' OPTIONS dict (that
dict is validated as S3 connection settings, not passed through to the
Django manifest mixin underneath it).
"""
from storages.backends.s3 import S3ManifestStaticStorage


class NonStrictS3ManifestStaticStorage(S3ManifestStaticStorage):
    # A CSS/JS file referencing a static asset that doesn't exist (typo,
    # forgotten commit) would otherwise fail the whole collectstatic step
    # and block the deploy. With this off, the reference is left as its
    # plain, unhashed URL instead, which will 404 for real users, so it's
    # a build safety net, not a fix for the missing file.
    manifest_strict = False
