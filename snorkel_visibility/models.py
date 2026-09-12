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
    last_report_at = models.DateTimeField(null=True, blank=True)
    ai_comment = models.TextField(blank=True, default="")
    ai_comment_updated_at = models.DateTimeField(null=True, blank=True)


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
    observed_at = models.DateTimeField()  # when they were in the water
    user_comment = models.TextField(blank=True, default="")
    is_hidden = models.BooleanField(default=False)  # moderation
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-observed_at"]
        indexes = [models.Index(fields=["location", "-observed_at"])]