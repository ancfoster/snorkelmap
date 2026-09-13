"""Awarding, withdrawing and totalling contribution points.

The same shape as snorkel_reviews.ratings: a cached number beside the
thing it describes, and one function that rebuilds it from the rows it
was calculated from. The number on the user is never adjusted up or
down by a delta, because a delta that is missed once is wrong forever;
it is recalculated from the ledger, which cannot drift.

Whoever accepts the contribution calls these. Nothing here is wired to
a signal or to a model's save(), so the order things happen in is
visible at the place where they happen.
"""
from django.db.models import Sum

from .models import Contribution


def recalculate(user):
    """Rebuild one person's points total from their ledger rows.

    Takes the person whose total has changed, not everybody. Called
    after any award or withdrawal, and safe to call at any other time:
    it reads the rows and writes the total, and that is all it does.
    """
    total = user.contributions.aggregate(total=Sum("points"))["total"] or 0

    user.community_points = total
    user.save(update_fields=["community_points"])
    return total


def award(user, kind, *, location=None, review=None, revision=None):
    """Record a contribution, and bring the person's total up to date.

    Returns the row, whether it was written now or was already there.
    Repeating an award is harmless: the unique constraints mean the
    second attempt finds the first one rather than paying twice, which
    is what makes this safe to call from a path that can be retried.
    """
    contribution, _ = Contribution.objects.get_or_create(
        user=user,
        kind=kind,
        location=location,
        review=review,
        revision=revision,
        defaults={"points": Contribution.POINTS[kind]},
    )
    recalculate(user)
    return contribution


def withdraw(user, kind, *, location=None, review=None, revision=None):
    """Take back a contribution that no longer exists.

    For the cases where the thing itself survives and the contribution
    does not, which at the moment means a review whose text has been
    removed, leaving a bare rating. A deleted review needs nothing from
    here: the foreign key cascades and only the total has to be
    rebuilt.
    """
    Contribution.objects.filter(
        user=user, kind=kind, location=location, review=review,
        revision=revision,
    ).delete()
    recalculate(user)
