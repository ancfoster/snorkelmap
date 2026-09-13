"""Rebuilding a location's rating from its reviews."""
from django.db.models import Count, Sum


def recalculate(rating):
    """Count a LocationRating's reviews, total their scores, store both.

    The average is the total divided by the count rather than anything
    stored and adjusted, so a row can always be put right without
    knowing what went wrong with it.

    No reviews gives None rather than 0: nought out of five is a
    verdict, no reviews is the absence of one.
    """
    totals = rating.reviews.aggregate(total=Sum("rating"), count=Count("id"))
    count = totals["count"] or 0

    rating.number_of_reviews = count
    rating.average_rating = (totals["total"] / count) if count else None
    rating.save(update_fields=["average_rating", "number_of_reviews",
                               "updated_at"])
    return rating
