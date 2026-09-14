"""Rebuilding a location's visibility figures from its reports.

The same shape as snorkel_reviews.ratings: three cached numbers beside
the thing they describe, and one function that rebuilds all of them
from the rows they were calculated from. Never adjusted by a delta,
because a delta that is missed once is wrong forever.

Whoever writes or removes a report calls this. Nothing here is wired
to a signal or to a model's save(), so the order things happen in is
visible at the place where they happen.
"""
from django.db.models import Avg, Count, Max

from .models import VisibilityLocation


def row_for(location, *, create=False):
    """The visibility row for a snorkel location, if it has one.

    Read with a filter rather than through the relation, so a location
    added before this app existed reads as no reports instead of
    raising. `create` is for the writing paths, which need somewhere to
    put the report they have just been handed.
    """
    if create:
        row, _ = VisibilityLocation.objects.get_or_create(
            snorkel_location=location)
        return row
    return VisibilityLocation.objects.filter(snorkel_location=location).first()


def recalculate(row):
    """Count a location's reports, average them, note the most recent.

    Hidden reports are left out of all three. A report a moderator has
    taken down should not go on quietly holding the average up, and a
    count that includes rows nobody can see is a count that cannot be
    checked against the page.

    No reports gives None rather than 0: nought metres is a report of
    water you cannot see through, and no reports is the absence of one.
    """
    visible = row.reports.filter(is_hidden=False)
    totals = visible.aggregate(mean=Avg("visibility"), count=Count("id"),
                               latest=Max("observed_at"))
    count = totals["count"] or 0

    row.number_of_reports = count
    # Stored unrounded. The listing page decides how many decimal
    # places to print; this is the figure it decides about.
    row.average_visibility = float(totals["mean"]) if count else None
    row.last_report_at = totals["latest"] if count else None
    row.save(update_fields=["number_of_reports", "average_visibility",
                            "last_report_at"])
    return row


def recalculate_for(location):
    """The same, given a snorkel location rather than its row."""
    row = row_for(location)
    return recalculate(row) if row else None
