"""Reviews of a location, and the rating they add up to.

Two models, and the split is the usual one: the reviews people write,
and a running total kept beside the location so that a listing or a map
card can show a rating without counting every review each time it is
drawn.

Nothing here maintains that total. Whatever ends up accepting a review
writes it.
"""
from django.conf import settings
from django.core.validators import MaxLengthValidator, MaxValueValidator, \
    MinValueValidator
from django.db import models

# What one person may write. Enforced by the validator here and again
# wherever a review is submitted, the same way a listing's description
# is: the model says what the limit is, and the submission path is
# where text arrives and is cleaned.
BODY_MAX = 900

MIN_RATING = 1
MAX_RATING = 5


class LocationRating(models.Model):
    """What a location's reviews add up to. One row per location.

    Named for what it holds rather than "LocationReview", which reads
    as one review of a location, which is the other model. The
    visibility app names its equivalent pair VisibilityLocation and
    VisibilityReport, so LocationRating and Review is a break from
    that; say the word and they can match instead.
    """

    location = models.OneToOneField(
        "snorkel_locations.SnorkelLocation",
        on_delete=models.CASCADE,
        related_name="rating",
    )
    # Unrounded, so that rounding is the template's decision rather
    # than something baked into the stored value. Null rather than zero
    # when there are no reviews: nought out of five is a verdict, and
    # no reviews is the absence of one.
    average_rating = models.FloatField(null=True, blank=True)
    number_of_reviews = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "location rating"
        verbose_name_plural = "location ratings"

    def __str__(self):
        if not self.number_of_reviews:
            return f"{self.location}: not rated yet"
        return f"{self.location}: {self.average_rating:.1f} from {self.number_of_reviews}"


class Review(models.Model):
    """One person's review of one location.

    The body is optional: a rating on its own is worth having, and
    asking for words alongside it is how you get fewer ratings.
    """

    rating_for = models.ForeignKey(
        LocationRating,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    # A foreign key rather than a bare uuid: the uuid is reachable
    # through it as review.created_by.user_uuid, and the relation is
    # what makes "this person's reviews" a query rather than a join
    # written by hand. CASCADE, so deleting an account takes its
    # reviews with it.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_RATING), MaxValueValidator(MAX_RATING)],
    )
    body = models.TextField(
        blank=True, default="",
        validators=[MaxLengthValidator(BODY_MAX)],
        help_text=f"Optional. Plain text, up to {BODY_MAX} characters.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "review"
        verbose_name_plural = "reviews"
        ordering = ["-created_at"]
        constraints = [
            # One review per person per location. Without it an average
            # is whatever the most determined person wants it to be,
            # and "42 reviews" can be four people.
            models.UniqueConstraint(
                fields=["rating_for", "created_by"],
                name="unique_review_per_user_location",
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=MIN_RATING,
                                   rating__lte=MAX_RATING),
                name="review_rating_within_range",
            ),
        ]
        indexes = [
            models.Index(fields=["rating_for", "-created_at"],
                         name="review_recent_idx"),
        ]

    def __str__(self):
        return f"{self.created_by} rated {self.rating_for.location} {self.rating}"
