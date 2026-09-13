"""Leaving a rating, changing it, and taking it away.

Two endpoints, both POST only, both returning the reviews block in its
new state. The block is a partial of the listing page and lives with
it, because what it looks like is the listing page's business; what is
in it is this app's, which is what these views and display.py are for.

Nothing here is clever about order. A submission writes the review,
then rebuilds the location's rating from its reviews, then records the
contribution and rebuilds the person's points from their ledger. Those
last two are a separate concern from the first two and are written as
such: a location and a person are different things, and neither
recalculation knows the other exists.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from contributions import points
from contributions.models import Contribution
from locations_snorkelled.models import Snorkelled
from snorkel_locations.models import SnorkelLocation

from . import display, ratings
from .forms import ReviewForm
from .models import LocationRating, Review

# The reviews block. In snorkel_locations because it is part of that
# page, next to the other partials it is drawn from.
BLOCK = "snorkel_locations/_reviews.html"


def _has_snorkelled(user, location):
    return Snorkelled.objects.filter(user=user, location=location).exists()


def _respond(request, location, **extra):
    """The block back, or the page, depending on who asked."""
    if request.headers.get("HX-Request"):
        return render(request, BLOCK, display.reviews_context(
            request, location, fragment=True, **extra))
    return redirect(location.get_absolute_url())


@require_POST
@login_required
def submit(request, location_uuid):
    """Leave a rating, or change the one already left.

    One endpoint for both, because the person is not doing two
    different things: they are saying what they think of the place,
    and whether they have said it before is something the database
    knows and they should not have to.
    """
    location = get_object_or_404(SnorkelLocation, uuid=location_uuid)

    form = ReviewForm(request.POST)
    if not form.is_valid():
        # Back with what they typed still in it. The rating is read
        # from the raw data rather than from cleaned_data, which is
        # exactly what is missing when the rating is what was wrong.
        return _respond(request, location, form=form,
                        chosen=_submitted_rating(request),
                        body=request.POST.get("body", ""))

    rating_row, _ = LocationRating.objects.get_or_create(location=location)
    body = form.cleaned_data["body"]

    review, created = Review.objects.get_or_create(
        rating_for=rating_row, created_by=request.user,
        defaults={"rating": form.cleaned_data["rating"], "body": body},
    )
    # Whether there were words here before this submission. Read from
    # the row get_or_create handed back, which for an existing review
    # is still the stored one at this point, and for a new one is the
    # submission itself, so a new review has nothing to have removed.
    had_body = (not created) and bool(review.body)
    if not created:
        review.rating = form.cleaned_data["rating"]
        review.body = body
        review.save(update_fields=["rating", "body", "updated_at"])

    # The location's rating is now out of date whichever branch ran.
    ratings.recalculate(rating_row)

    # And then, separately, the ledger. A rating is earned once and
    # editing it earns nothing more, which the award is already
    # idempotent about. Words are worth something on top, so they are
    # paid for when they appear and taken back if they are removed.
    #
    # Only what was written now counts towards what they are told they
    # have earned, which is why each award is asked whether it paid
    # rather than assumed to have.
    earned = 0
    _, paid = points.award(request.user, Contribution.Kind.RATING,
                           location=location, review=review)
    if paid:
        earned += Contribution.POINTS[Contribution.Kind.RATING]

    if body:
        _, paid = points.award(request.user, Contribution.Kind.REVIEW,
                               location=location, review=review)
        if paid:
            earned += Contribution.POINTS[Contribution.Kind.REVIEW]
    elif had_body:
        points.withdraw(request.user, Contribution.Kind.REVIEW,
                        location=location, review=review)

    thanks = display.thanks_for(created, bool(body), had_body, earned)

    # Somebody who has an opinion about a place has usually been in the
    # water there, and the count of who has is worth more when it is
    # complete. Asked, not assumed: a review can be written about
    # somewhere you watched from the harbour wall.
    return _respond(
        request, location,
        thanks=thanks,
        prompt_snorkel=not _has_snorkelled(request.user, location),
    )


@require_POST
@login_required
def delete(request, location_uuid):
    """Take a rating back.

    The confirmation happens in the page before anything is posted
    here, which is where a confirmation belongs: this end is asked
    once and does it.
    """
    location = get_object_or_404(SnorkelLocation, uuid=location_uuid)
    rating_row = display.rating_for(location)

    if rating_row:
        Review.objects.filter(rating_for=rating_row,
                              created_by=request.user).delete()
        ratings.recalculate(rating_row)

    # The contribution rows went with the review, because they point at
    # it and the foreign key cascades. Only the total is left to
    # rebuild, and it is rebuilt rather than decremented.
    points.recalculate(request.user)

    return _respond(request, location)


def _submitted_rating(request):
    """Whatever was in the rating field, if it was a number at all."""
    try:
        return int(request.POST.get("rating", ""))
    except (TypeError, ValueError):
        return 0
