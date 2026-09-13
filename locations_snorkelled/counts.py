"""Rebuilding a location's count of people who have snorkelled there.

The same shape as snorkel_reviews.ratings.recalculate: the rows are the
truth, the number on the location is a cache, and this is the one place
that turns one into the other. Takes a single location, because the
count that has changed is the count for the place somebody just marked.

Deliberately not incrementing. A count that goes up by one every time
something happens is wrong the first time something happens twice, or
fails halfway; a count that is recalculated from the rows is wrong
until the next time it is run and right after it.
"""
from .models import Snorkelled


def recount(location):
    """Count the people who have snorkelled here and store it."""
    total = Snorkelled.objects.filter(location=location).count()

    location.users_snorkelled = total
    location.save(update_fields=["users_snorkelled"])
    return total
