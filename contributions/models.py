"""A ledger of the things people do that earn them points.

One row per earning event rather than a number kept on the account.
The number is kept as well, on the user, but it is a cache: this table
is what it is calculated from, so it can be rebuilt, explained, and
reversed when whatever earned it is taken away.

What earned a row is recorded by pointing at the thing itself. The
columns are nullable because a location has no review and a review has
no revision, and only one of them is filled on any given row. That is
what makes the constraints below possible: they are what stops the
same contribution being paid for twice, and they are enforced by the
database rather than by whoever remembered to check first.

Nothing in here counts, awards or revokes anything. points.py does
that, and the apps that own these contributions call it. A location
and a person are two different concerns and this app is deliberately
the only place they meet.
"""
from django.conf import settings
from django.db import models


class Contribution(models.Model):
    """One thing one person did, and what it was worth at the time."""

    class Kind(models.TextChoices):
        LOCATION_CREATION = "location-creation", "Location created"
        LOCATION_EDIT = "location-edit", "Location edited"
        RATING = "rating", "Rating left"
        REVIEW = "review", "Review left"
        VISIBILITY_REPORT = "visibility-report", "Visibility report filed"

    # What each kind is worth. Read once, when the row is written, and
    # copied onto it: changing a figure here changes what the next
    # contribution earns and leaves everything already earned alone.
    POINTS = {
        Kind.LOCATION_CREATION: 100,
        Kind.LOCATION_EDIT: 10,
        Kind.RATING: 5,
        Kind.REVIEW: 10,
        Kind.VISIBILITY_REPORT: 5,
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contributions",
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    # The value at the time it was earned, not looked up when it is
    # read. Without this, raising what a review is worth would quietly
    # re-price every review ever left.
    points = models.PositiveSmallIntegerField()

    # Which location this was about. Filled on every row, including the
    # ones that point at a review or a revision as well, because "what
    # has been contributed here" is a question worth being able to ask
    # of a location.
    location = models.ForeignKey(
        "snorkel_locations.SnorkelLocation",
        on_delete=models.CASCADE,
        related_name="contributions",
        null=True, blank=True,
    )
    # Set on a rating or a review row. CASCADE, because a deleted
    # review takes its points with it.
    review = models.ForeignKey(
        "snorkel_reviews.Review",
        on_delete=models.CASCADE,
        related_name="contributions",
        null=True, blank=True,
    )
    # Set on an edit row. Edits are paid per revision rather than per
    # location, which is what lets somebody who improves a listing
    # three times be paid three times while still being paid only once
    # for any one of them.
    revision = models.ForeignKey(
        "snorkel_locations.LocationRevision",
        on_delete=models.CASCADE,
        related_name="contributions",
        null=True, blank=True,
    )
    # Set on a visibility row. Reports are paid per report rather than
    # per location, because somebody who snorkels the same bay every
    # Saturday is telling us something new each time. CASCADE, so a
    # deleted report takes its points with it.
    visibility_report = models.ForeignKey(
        "snorkel_visibility.VisibilityReport",
        on_delete=models.CASCADE,
        related_name="contributions",
        null=True, blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "contribution"
        verbose_name_plural = "contributions"
        ordering = ["-created_at"]
        constraints = [
            # Adding a location pays once, however many times the
            # request is retried or replayed.
            models.UniqueConstraint(
                fields=["user", "location"],
                condition=models.Q(kind="location-creation"),
                name="unique_contribution_per_location_created",
            ),
            # A rating and a review are two rows against the same
            # review, so the kind is part of the key. Editing a review
            # cannot earn anything a second time.
            models.UniqueConstraint(
                fields=["user", "review", "kind"],
                condition=models.Q(review__isnull=False),
                name="unique_contribution_per_review",
            ),
            # One payment per revision, so repeated edits are paid and
            # a replayed one is not.
            models.UniqueConstraint(
                fields=["user", "revision"],
                condition=models.Q(kind="location-edit"),
                name="unique_contribution_per_revision",
            ),
            # And one per visibility report, which the report table
            # already limits to one per person per day.
            models.UniqueConstraint(
                fields=["user", "visibility_report"],
                condition=models.Q(kind="visibility-report"),
                name="unique_contribution_per_visibility_report",
            ),
        ]
        indexes = [
            # The total is a sum over one person's rows, and the
            # profile page will want them newest first.
            models.Index(fields=["user", "-created_at"],
                         name="contribution_user_recent_idx"),
            models.Index(fields=["location"],
                         name="contribution_location_idx"),
        ]

    def __str__(self):
        return f"{self.user}: {self.get_kind_display()} (+{self.points})"
