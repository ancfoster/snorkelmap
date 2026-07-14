from django.db import models
from django.conf import settings
from django.contrib.gis.db import models
from django.db.models import F, Q

import uuid

#Gegraphy models

class Country(models.Model):
    # code represents ISO countr code
    # (e.g. "GB"
    code = models.CharField(max_length=2, unique=True, db_index=True)
    name = models.CharField(max_length=100)

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["country", "region", "locale"])]

    @property
    def latitude(self):
        return self.point.y

    @property
    def longitude(self):
        return self.point.x

    def __str__(self):
        rev = self.current_revision
        return rev.name if rev else f"Location {self.uuid}"


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
        choices=Difficulty.choices, default=Difficulty.EASY
    )

    environment_types = models.JSONField(default=dict, blank=True)
    marine_life = models.JSONField(default=dict, blank=True)
    hazards = models.JSONField(default=dict, blank=True)

    facilities = models.JSONField(default=dict, blank=True)

    marker_data = models.JSONField(default=dict, blank=True)

    featured_surface_image = models.ForeignKey(
        "LocationMedia", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    featured_underwater_image = models.ForeignKey(
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
        PENDING = 0, "Pending upload"   # row created, Worker upload not confirmed
        ACTIVE = 1, "Active"
        REMOVED = 2, "Removed"          # soft delete / moderation

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

    class Meta:
        verbose_name_plural = "location media"

    def __str__(self):
