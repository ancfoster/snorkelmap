from django.db import models
from django.conf import settings
from django.contrib.gis.db import models
from django.db.models import F, Q

import uuid

#Gegraphy models

class Country(models.Model):
    # code represents ISO country code
    # (e.g. "GB"
    code = models.CharField(max_length=2, unique=True, db_index=True)
    name = models.CharField(max_length=100)

    # The country's segment in a listing's address: /location/france/
    # rather than /location/fr/, because a URL should read as a place.
    # The ISO code stays on the row, it just is not what the public
    # sees.
    slug = models.SlugField(max_length=120)

    class Meta:
        verbose_name_plural = "countries"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Region(models.Model):
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name="regions"
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=300) 

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}, {self.country.code}"


class Locale(models.Model):
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, related_name="locales"
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.region.name})"


# Listing models

class SnorkelLocation(models.Model):
    class Status(models.IntegerChoices):
        DRAFT = 0, "Draft"
        PUBLISHED = 1, "Published"
        HIDDEN = 2, "Hidden"
        ARCHIVED = 3, "Removed"

    uuid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )

    # The browser generates this once when a draft is started and sends
    # it with the publish request. Unique, so a second request carrying
    # the same value returns the location that already exists rather
    # than creating a duplicate. That is what makes a lost connection
    # or an impatient second tap harmless.
    submission_id = models.UUIDField(
        null=True, blank=True, unique=True, editable=False, db_index=True
    )

    slug = models.SlugField(max_length=400, unique=True, db_index=True)

    current_revision = models.OneToOneField(
        "LocationRevision",
        on_delete=models.PROTECT,
        related_name="current_for",
        null=True,       
        blank=True,
    )
    lat_long = models.PointField(geography=True, srid=4326)

    w3w = models.CharField(
        max_length=200, blank=True, default=""
    )

    country = models.ForeignKey(
        Country, on_delete=models.PROTECT,
        related_name="locations", null=True, blank=True,
    )
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT,
        related_name="locations", null=True, blank=True,
    )
    locale = models.ForeignKey(
        Locale, on_delete=models.PROTECT,
        related_name="locations", null=True, blank=True,
    )

    status = models.PositiveSmallIntegerField(
        choices=Status.choices, default=Status.PUBLISHED, db_index=True
    )

    # The reverse geocode failed rather than returned nothing. Those
    # are different: a listing with no country because Mapbox says it
    # is open water is correct, while one with no country because the
    # request timed out is a beach with the wrong address. Only the
    # second sets this, so an admin view can list exactly the ones
    # worth a human look.
    questionable_geocode = models.BooleanField(default=False, db_index=True)

    # A Mapbox raster of where this is, fetched once by Django and kept
    # in our own bucket. Not a LocationMedia row: nobody uploaded it,
    # there is nothing to verify, and it belongs to the location rather
    # than to any revision of its text. Empty until it has been drawn,
    # which generate_map_images will do for anything missed.
    map_image_key = models.CharField(max_length=255, blank=True, default="")

    # How many people have said they have snorkelled here. A cache of
    # the rows in locations_snorkelled, kept for the same reason the
    # rating beside it is: the listing shows this every time it is
    # drawn, and counting rows every time to print one number is work
    # nobody needs done. locations_snorkelled.counts.recount() is what
    # writes it, so it can always be rebuilt from the rows themselves.
    users_snorkelled = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_notes = models.JSONField(null=True, blank=True)
    notices = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["country", "region", "locale"])]

    @property
    def latitude(self):
        return self.lat_long.y

    @property
    def longitude(self):
        return self.lat_long.x

    def __str__(self):
        rev = self.current_revision
        return rev.name if rev else f"Location {self.uuid}"

    def get_absolute_url(self):
        """The canonical address for this listing.

        Its length depends on how much is known about where it is:
        /location/united-kingdom/scottish-borders/st-abbs/st-abbs-harbour/
        for a place with a town, down to /location/ocean/<slug>/ for
        somewhere with no country at all.

        There is a second, permanent address at /location/?uuid=<uuid>
        which redirects here. That one never changes, so it is the one
        to use anywhere a link has to survive a listing being renamed
        or its geography being corrected.
        """
        from django.urls import reverse

        from .geography import path_segments

        segments = path_segments(self)
        names = {2: "detail", 3: "detail_region", 4: "detail_locale"}
        keys = {
            2: ("country", "slug"),
            3: ("country", "region", "slug"),
            4: ("country", "region", "locale", "slug"),
        }
        count = len(segments)
        return reverse(names[count], kwargs=dict(zip(keys[count], segments)))


class LocationRevision(models.Model):
    class Difficulty(models.IntegerChoices):
        EASY = 1, "Easy"
        MODERATE = 2, "Moderate"
        DIFFICULT = 3, "Difficult"
        EXTREME = 4, "Extreme"

    location = models.ForeignKey(
        SnorkelLocation, on_delete=models.CASCADE, related_name="revisions"
    )
    # starts at 0, then 1,2,3,4,5 etc
    increment = models.PositiveIntegerField(default=0)
    # e.g Starney Bay
    name = models.CharField(max_length=200)
    # e.g ["Backwash", ...]
    alternate_names = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True, default="")
    entry_description = models.TextField(blank=True, default="")    
    access_type = models.JSONField(default=list, blank=True)  # ["shore","boat"]
    water_type = models.JSONField(default=list, blank=True)   # ["ocean-sea", …]
    difficulty = models.PositiveSmallIntegerField(
        choices=Difficulty.choices, default=Difficulty.EASY    )
    environment_types = models.JSONField(default=dict, blank=True)
    marine_life = models.JSONField(default=dict, blank=True)
    hazards = models.JSONField(default=dict, blank=True)
    facilities = models.JSONField(default=dict, blank=True)
    marker_data = models.JSONField(default=dict, blank=True)
    # The one photograph that represents this location: on the map, in
    # a list of results, and at the top of the listing. Always an above
    # water shot, which is the kind a listing cannot be published
    # without.
    #
    # Set by the verification step rather than at creation, so it never
    # points at a row that is still pending or might yet be rejected. It
    # starts as the first above water photograph the person added, and
    # is meant to be changed afterwards: which picture best represents a
    # place is a judgement for the people who snorkel there, not
    # something to leave to upload order.
    #
    # Null means no photograph has been confirmed yet. A listing in that
    # state is still a draft, so nothing without one reaches the public
    # site.
    featured_above_water_image = models.ForeignKey(
        "LocationMedia", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="location_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revision_comment = models.CharField(  
        max_length=255, blank=True, default="" 
    )
    diff = models.JSONField(default=dict, blank=True)
    class Meta:
        ordering = ["-increment"]
        constraints = [
            models.UniqueConstraint(
                fields=["location", "increment"],
                name="unique_increment_per_location",
            ),
        ]
        indexes = [models.Index(fields=["location", "-increment"])]

    def __str__(self):
        return f"{self.name} r{self.increment}"




class LocationMedia(models.Model):

    class MediaType(models.IntegerChoices):
        IMAGE = 1, "Image"
        VIDEO = 2, "Video"

    class MediaCategory(models.IntegerChoices):
        UNDERWATER = 1, "Underwater"
        SURFACE = 2, "Surface"

    class Status(models.IntegerChoices):
        PENDING = 0, "Pending upload"   # presigned, nothing in the bucket yet
        ACTIVE = 1, "Active"
        REMOVED = 2, "Removed"          # soft delete / moderation
        REJECTED = 3, "Rejected"        # arrived, failed verification
        UPLOADED = 4, "Awaiting checks"  # in the bucket, not yet verified

    uuid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    location = models.ForeignKey(
        SnorkelLocation, on_delete=models.CASCADE, related_name="media"
    )
    media_type = models.PositiveSmallIntegerField(choices=MediaType.choices)

    media_category = models.PositiveSmallIntegerField(choices=MediaCategory.choices)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="uploaded_media",
    )

    description = models.CharField(max_length=500, blank=True, default="")
    object_key = models.CharField(max_length=255, blank=True, default="")
    status = models.PositiveSmallIntegerField(
        choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    orignal_media_meta = models.JSONField(default=dict, blank=True)

    # ── What the file is ────────────────────────────────────────────
    # Written from the sniffed bytes at presign time and confirmed
    # against the stored object during verification, so these are the
    # server's own findings rather than the browser's claims.
    mime_type = models.CharField(max_length=60, blank=True, default="")
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)

    # ── What the camera recorded ────────────────────────────────────
    # Read in the browser and taken on trust. EXIF has no timezone, so
    # captured_at holds the wall clock the camera wrote and
    # captured_at_offset holds the offset when the camera recorded one.
    captured_at = models.DateTimeField(null=True, blank=True)
    captured_at_offset = models.CharField(max_length=6, blank=True, default="")
    captured_lat_long = models.PointField(
        geography=True, srid=4326, null=True, blank=True
    )

    sort_order = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    # Why verification refused it, for support and for the admin.
    rejection_reason = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        verbose_name_plural = "location media"
        ordering = ["media_category", "sort_order", "created_at"]
        indexes = [
            models.Index(fields=["location", "status"],
                         name="locmedia_loc_status_idx"),
        ]

    def __str__(self):
        return f"{self.get_media_type_display()} image for {self.location_id}"

    @property
    def is_visible(self):
        return self.status == self.Status.ACTIVE


class MapData(models.Model):
    """Which map data file is current. One row, always.

    The map page renders this key into the page, so it is the only
    thing that decides which file a visitor fetches. A row rather than
    a setting because it changes when a location is published, not when
    the site is deployed.
    """
    object_key = models.CharField(max_length=200, blank=True, default="")
    size_bytes = models.PositiveIntegerField(default=0)
    built_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "map data"

    def __str__(self):
        return self.object_key or "no map data built yet"

    @classmethod
    def load(cls):
        row, _ = cls.objects.get_or_create(pk=1)
        return row

    def mark_built(self, key, size):
        from django.utils import timezone
        self.object_key = key
        self.size_bytes = size
        self.built_at = timezone.now()
        self.save(update_fields=["object_key", "size_bytes", "built_at"])
