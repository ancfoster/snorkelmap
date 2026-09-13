"""Everything the reviews block needs, prepared in Python.

Built here rather than in the listing view because it is this app's
data, and used by both: the listing page asks for it when the page is
drawn, and the endpoints in views.py ask for it again when the block
is swapped. One builder means the block cannot look different
depending on which of the two produced it.

What it does not do is decide what any of it looks like. The listing
page owns that, the same way it owns the rest of itself.
"""
from .models import MAX_RATING, LocationRating, Review


def stars(value):
    """Five booleans: which stars in a row are filled.

    Rounded to the nearest whole star, because a row of five either
    has a star in it or does not. The unrounded figure is printed
    beside it, so nothing is lost by this.
    """
    filled = int(round(value or 0))
    return [position <= filled for position in range(1, MAX_RATING + 1)]


def thanks_for(created, has_body, had_body, earned):
    """What to say once something has just been saved.

    Four things decide the sentence. Whether this is the first time
    they have said anything about the place, whether there are words
    with the rating now, whether there were words with it before, and
    what the ledger actually paid.

    The middle two are what separate adding a review to a rating that
    was already left from changing one that was already there. Telling
    somebody they have updated a review they have only just written is
    the sort of small wrongness that makes a site feel careless.

    The points are only mentioned when some were actually earned.
    Changing a rating that was already left earns nothing, and a line
    reading "you have earned 0 points" is worse than no line at all.
    """
    if created:
        what = "leaving a rating and review" if has_body else "leaving your rating"
    elif has_body and not had_body:
        what = "updating your rating and leaving a review"
    elif has_body:
        what = "updating your rating and review"
    else:
        # Covers both leaving a bare rating alone and taking the words
        # away from one, since either way what is left is the rating.
        what = "updating your rating"

    if not earned:
        return f"Thank you for {what}."
    return (f"Thank you for {what}, you have earned "
            f"{earned} point{'' if earned == 1 else 's'}.")


def _person(review):
    """One review, ready to print."""
    username = review.created_by.get_username()
    return {
        "id": review.id,
        "username": username,
        # The circle beside a review carries a letter rather than a
        # photograph, because there are no photographs of people on
        # this site and inventing one would be the first step towards
        # there being some. Their own letter, not an upper cased one:
        # snorkeller93 is written in lower case and the circle should
        # not be the one place on the site that disagrees.
        "initial": username[:1],
        "rating": review.rating,
        "stars": stars(review.rating),
        "body": review.body,
        "created_at": review.created_at,
    }


def rating_for(location):
    """The location's rating row, or None if it has never had one.

    Read with a filter rather than through the relation, so that a
    location created before ratings existed reads as no rating instead
    of raising.
    """
    return LocationRating.objects.filter(location=location).first()


def reviews_context(request, location, *, thanks="", prompt_snorkel=False,
                    form=None, fragment=False, chosen=None, body=None):
    """The reviews block, in whichever of its three states applies.

    thanks and prompt_snorkel are only ever set by the endpoints, which
    is what makes the block returned after a submission different from
    the one drawn with the page.
    """
    rating = rating_for(location)
    user = request.user

    mine = None
    if user.is_authenticated:
        mine = Review.objects.filter(
            rating_for=rating, created_by=user).first() if rating else None

    # Everybody else's reviews, newest first. The person's own is left
    # out because it is already on the page, in the panel where they
    # can change it; showing it twice would invite them to wonder which
    # one is real.
    others = []
    if rating:
        rows = rating.reviews.select_related("created_by")
        if mine:
            rows = rows.exclude(pk=mine.pk)
        others = [_person(review) for review in rows]

    revision = location.current_revision
    return {
        "location": location,
        # Named here as well as on the page, because the block is also
        # returned on its own, where the rest of the listing's context
        # does not exist.
        "location_name": revision.name if revision else "this location",
        "average_rating": rating.average_rating if rating else None,
        "average_stars": stars(rating.average_rating if rating else 0),
        "number_of_ratings": rating.number_of_reviews if rating else 0,
        "users_snorkelled": location.users_snorkelled,
        "reviews": others,

        # The panel. my_review set means the third state, an
        # authenticated user without one means the second, and nobody
        # signed in means the first.
        "my_review": mine,
        # What the star input should show, and what should be in the
        # box. Whatever was just submitted if there is any, so a
        # rejected submission comes back with the words still in it,
        # and otherwise whatever is stored.
        "chosen": chosen if chosen is not None else (mine.rating if mine else 0),
        "body": body if body is not None else (mine.body if mine else ""),
        # Highest first, because the stars are laid out in reverse and
        # turned back round with CSS. That is what lets a checked star
        # light the ones below it without any script running.
        "star_values": list(range(MAX_RATING, 0, -1)),
        "review_form": form,

        # Said once, after something has just been submitted.
        "thanks": thanks,
        "prompt_snorkel": prompt_snorkel,

        # Set when this is being returned on its own rather than drawn
        # as part of the page, which is when the rating at the top of
        # the page has to be sent along with it.
        "fragment": fragment,
    }
