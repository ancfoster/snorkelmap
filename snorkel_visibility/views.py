"""Filing a visibility report from a listing page, and taking one back.

Two endpoints, both POST only, both returning the visibility block in
its new state. The block is a partial of the listing page and lives
with it, because what it looks like is the listing page's business;
what is in it is this app's, which is what these views and display.py
are for.

Writing a report is filing.file_report, not something done here, since
the create form files them too and there is only one set of rules about
what a report is.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from contributions import points
from snorkel_locations.models import SnorkelLocation

from . import display, filing, visibility
from .models import VisibilityReport

# The visibility block. In snorkel_locations because it is part of that
# page, next to the other partials it is drawn from.
BLOCK = "snorkel_locations/_visibility.html"


def _respond(request, location, **extra):
    """The block back, or the page, depending on who asked."""
    if request.headers.get("HX-Request"):
        return render(request, BLOCK, display.visibility_context(
            request, location, fragment=True, **extra))
    return redirect(location.get_absolute_url())


def _submitted(request):
    """What they sent, so a rejected form comes back with it still in."""
    return {
        "visibility": request.POST.get("visibility", ""),
        "observed_at": request.POST.get("observed_at", ""),
        "comment": request.POST.get("comment", ""),
    }


@require_POST
@login_required
def submit(request, location_uuid):
    """File a report about how far you could see on a given day.

    Unlike a rating, this is not one per person per location. Somebody
    who snorkels the same bay every Saturday has something new to say
    each week, and is paid for each of them. What they cannot do is
    report twice about the same day, which the database enforces rather
    than this view: two tabs and a double press both arrive here as two
    requests, and only the database sees both.
    """
    location = get_object_or_404(SnorkelLocation, uuid=location_uuid)

    report, form, earned = filing.file_report(
        request.user, location, request.POST)

    if report is None:
        return _respond(request, location, form=form,
                        values=_submitted(request))

    return _respond(request, location, thanks=display.thanks_for(earned))


@require_POST
@login_required
def delete(request, location_uuid, report_id):
    """Take a report back.

    The confirmation happens in the page before anything is posted
    here, which is where a confirmation belongs: this end is asked once
    and does it.

    Only your own, and the filter says so rather than a check saying
    so, because a filter that matches nothing deletes nothing.
    """
    location = get_object_or_404(SnorkelLocation, uuid=location_uuid)
    row = visibility.row_for(location)

    if row:
        VisibilityReport.objects.filter(
            pk=report_id, location=row, submitted_by=request.user).delete()
        visibility.recalculate(row)

    # The contribution row went with the report, because it points at
    # it and the foreign key cascades. Only the total is left to
    # rebuild, and it is rebuilt rather than decremented.
    points.recalculate(request.user)

    return _respond(request, location)
