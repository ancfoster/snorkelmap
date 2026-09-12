"""Locations a person has saved for later.

A join table and nothing else: who, which location, and when they said
so. There is no ordering to preserve and no note to attach, so the row
carries no state of its own beyond existing.

The unique constraint is what makes it usable. Without it a second tap
on the button creates a second row, and "is this one of mine" stops
being a question with one answer.
"""
from django.conf import settings
from django.db import models


class Favourite(models.Model):
    """One person, one location, saved once.

    Named in the singular because a row is one favourite; the app is
    the plural. `user.favourites.all()` and
    `location.favourited_by.all()` are what anything actually reads.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favourites",
    )
    location = models.ForeignKey(
        "snorkel_locations.SnorkelLocation",
        on_delete=models.CASCADE,
        related_name="favourited_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "favourite"
        verbose_name_plural = "favourites"
        # Newest first, which is the order a "your favourites" page
        # wants without asking for it.
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "location"],
                name="unique_favourite_per_user_location",
            ),
        ]
        indexes = [
            # Covers "this person's favourites, newest first", which is
            # the only read this table has.
            models.Index(fields=["user", "-created_at"],
                         name="favourite_user_recent_idx"),
        ]

    def __str__(self):
        return f"{self.user} favourited {self.location}"
