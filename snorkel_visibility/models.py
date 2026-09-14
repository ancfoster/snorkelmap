"""How far people could see, on the days they were in the water.

Two tables, the same shape as the reviews app: a row per location
carrying the figures the listing page reads, and a row per report
carrying what one person actually saw. The first is a cache of the
second and is rebuilt from it in visibility.py, never adjusted by a
delta, because a delta that is missed once is wrong forever.

Unlike a rating, a person may file as many reports as they like about
one location, so long as each is for a different day. That is what the
constraint below says, and it is said in the database rather than in
the form: two tabs, a replayed request or a double press all arrive as
two writes, and only the database sees both.
"""
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class VisibilityLocation(models.Model):
    snorkel_location = models.OneToOneField(
        "snorkel_locations.SnorkelLocation",
        on_delete=models.CASCADE,
        related_name="visibility",
    )
    number_of_reports = models.PositiveIntegerField(default=0)
    average_visibility = models.FloatField(null=True, blank=True)  # raw mean, unrounded
    # The most recent day anybody reported on, not the moment the row
    # was written. It answers "how fresh is this figure", and the
    # answer is about when somebody was in the water.
    last_report_at = models.DateField(null=True, blank=True)
    ai_comment = models.TextField(blank=True, default="")
    ai_comment_updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Visibility at {self.snorkel_location_id}"


class VisibilityReport(models.Model):
    location = models.ForeignKey(
        VisibilityLocation,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visibility_reports",
    )
    visibility = models.DecimalField(
        max_digits=4, decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
    )
    # The day they were in the water, not the moment. A date rather
    # than a timestamp because that is what is being reported and
    # because "one report per person per day" has to be a unique index,
    # which Postgres will not build over date(timestamptz): that cast
    # reads the session's timezone, so it is not immutable.
    observed_at = models.DateField()
    user_comment = models.TextField(blank=True, default="")
    is_hidden = models.BooleanField(default=False)  # moderation
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-observed_at"]
        constraints = [
            # One person, one location, one day. Somebody who snorkels
            # the same bay every Saturday is filing a new report each
            # time and is paid for each; somebody pressing the button
            # twice is not.
            models.UniqueConstraint(
                fields=["location", "submitted_by", "observed_at"],
                name="unique_visibility_report_per_day",
            ),
        ]
        indexes = [models.Index(fields=["location", "-observed_at"])]

    def __str__(self):
        return f"{self.visibility}m on {self.observed_at}"
