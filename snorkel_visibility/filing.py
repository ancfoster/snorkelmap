"""Writing one visibility report, wherever it came from.

Two places file reports: the dialog on a listing page, and the create
form, which collects one while somebody is adding the location in the
first place. What counts as a valid report is the same in both, and so
is what has to happen afterwards, so it is written once here rather
than twice at either end.

What is not here is anything about how either of them answers. The
listing's endpoint swaps a block, the create endpoint returns a
location; that is their business.
"""
from django.db import IntegrityError, transaction

from contributions import points
from contributions.models import Contribution

from . import visibility
from .forms import VisibilityReportForm
from .models import VisibilityReport


class AlreadyFiled(Exception):
    """This person has already reported on this location for that day."""


def file_report(user, location, data):
    """Validate and write one report, then bring both caches up to date.

    `data` is whatever the form expects: visibility, observed_at and
    comment. Returns (report, form, earned). A report is None when the
    form rejected it, and the form carries why.

    The two recalculations after it are deliberately separate and in
    this order. The location's figures are about the place; the points
    are about the person; neither knows the other exists.
    """
    form = VisibilityReportForm(data)
    if not form.is_valid():
        return None, form, 0

    row = visibility.row_for(location, create=True)

    try:
        with transaction.atomic():
            report = VisibilityReport.objects.create(
                location=row,
                submitted_by=user,
                visibility=form.cleaned_data["visibility"],
                observed_at=form.cleaned_data["observed_at"],
                user_comment=form.cleaned_data["comment"],
            )
    except IntegrityError:
        # The only unique rule on this table is one report per person
        # per day, so this is that and nothing else. Said back as a
        # field error rather than a five hundred, because from where
        # the person is sitting they have made an ordinary mistake.
        form.add_error("observed_at",
                       "You have already filed a report for that date. "
                       "Delete it first if you want to change it.")
        return None, form, 0

    visibility.recalculate(row)

    # Keyed on the report, so filing about a second day is paid again
    # and a replayed request is not.
    _, paid = points.award(user, Contribution.Kind.VISIBILITY_REPORT,
                           location=location, visibility_report=report)
    earned = (Contribution.POINTS[Contribution.Kind.VISIBILITY_REPORT]
              if paid else 0)
    return report, form, earned
