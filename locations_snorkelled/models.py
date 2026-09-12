"""Locations a person has actually been in the water at.

The same shape as a favourite, and deliberately so: who, which
location, and when they said so. What it means is different, though.
A favourite is somewhere you want to go; this is somewhere you have
been, which is what makes it worth anything to the rest of the
community.

One row per person per location, so the question it answers is "have
you snorkelled here", not "how many times". If a log of individual
trips is wanted later, with a date, conditions and what was seen, that
is a different model with a different shape rather than this one with
its constraint removed: a log entry is a thing in its own right, and
this is a flag.
"""
from django.conf import settings
from django.db import models


class Snorkelled(models.Model):
    """One person, one location, marked as snorkelled.

    `Snorkelled` rather than `SnorkelledAt`: the model is the fact, and
    the "at" is already carried by the location field. It also reads
    properly through its relations, which is where the name is actually
    used: `user.snorkelled.all()` and `location.snorkelled_by.all()`.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="snorkelled",
    )
    location = models.ForeignKey(
        "snorkel_locations.SnorkelLocation",
        on_delete=models.CASCADE,
        related_name="snorkelled_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "snorkelled location"
        verbose_name_plural = "snorkelled locations"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "location"],
                name="unique_snorkelled_per_user_location",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"],
                         name="snorkelled_user_recent_idx"),
            # The count of people who have been somewhere is a per
            # location read, so it gets its own index.
            models.Index(fields=["location"],
                         name="snorkelled_location_idx"),
        ]

    def __str__(self):
        return f"{self.user} snorkelled {self.location}"
