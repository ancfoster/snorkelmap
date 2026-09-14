"""Everything the visibility block needs, prepared in Python.

Built here rather than in the listing view because it is this app's
data, and used by both: the listing page asks for it when the page is
drawn, and the endpoints ask for it again when the block is swapped.
One builder means the block cannot look different depending on which
of the two produced it.

What it does not do is decide what any of it looks like. The listing
page owns that, the same way it owns the rest of itself. What is
decided here is where a figure sits on the scale and what the scale
calls it, which are facts about the scale rather than about the design.
"""
from snorkel_locations.choices import (VISIBILITY_CATEGORY_LABELS,
                                       VISIBILITY_MAX_AGE_DAYS,
                                       VISIBILITY_SCALE_LABELS)

from .models import VisibilityReport

# Where the printed scale labels actually fall. "12m+" is the top of
# the scale rather than a point on it, so anything at or past twelve
# sits at the end.
SCALE_POINTS = [0.0, 2.0, 5.0, 8.0, 12.0]

# What the scale calls each of those points. Read from choices.py so
# the listing page, the create page and this all say the same words.
CATEGORY_LABELS = list(VISIBILITY_CATEGORY_LABELS)

# The gradient the bar is painted with, sampled at the same five
# points. Named here rather than read back out of the CSS because the
# dot beside a figure has to be a single colour, and a single colour
# cannot be taken from a gradient by a stylesheet.
SCALE_COLOURS = ["#cc2200", "#f07b13", "#f5c242", "#a8c940", "#4db340"]

MAX_AGE_DAYS = VISIBILITY_MAX_AGE_DAYS
SCALE_LABELS = list(VISIBILITY_SCALE_LABELS)


def position(metres):
    """Where a figure sits along the bar, as a percentage of its width.

    The printed labels are spaced evenly, so the scale they describe is
    piecewise rather than linear: half way between the 2m and 5m marks
    means 3.5m, not 6m. Working it out any other way would put the dot
    somewhere the person cannot read off the labels underneath it,
    which is the one thing the bar is for.
    """
    if metres is None:
        return None

    value = max(0.0, float(metres))
    last = len(SCALE_POINTS) - 1
    step = 100.0 / last

    if value >= SCALE_POINTS[-1]:
        return 100.0

    for index in range(last):
        low, high = SCALE_POINTS[index], SCALE_POINTS[index + 1]
        if value < high:
            within = (value - low) / (high - low)
            return round((index + within) * step, 2)
    return 100.0


def category(metres):
    """What the scale calls a figure: the nearest labelled point's name.

    Nearest rather than "the band it falls in", because the labels are
    printed above the points rather than between them. Four metres and
    six metres are both nearer the 5m mark than any other, so both read
    as whatever that mark is called, which is what somebody looking at
    the bar would say they were.
    """
    if metres is None:
        return ""

    value = max(0.0, float(metres))
    nearest = min(range(len(SCALE_POINTS)),
                  key=lambda index: abs(SCALE_POINTS[index] - value))
    return CATEGORY_LABELS[nearest]


def colour(metres):
    """The gradient's colour at a figure, for the dot beside it."""
    if metres is None:
        return ""
    value = max(0.0, float(metres))
    nearest = min(range(len(SCALE_POINTS)),
                  key=lambda index: abs(SCALE_POINTS[index] - value))
    return SCALE_COLOURS[nearest]


def metres(value):
    """A figure as it is printed: 4.5, but 6 rather than 6.0."""
    if value is None:
        return ""
    number = round(float(value), 1)
    return int(number) if number == int(number) else number


def thanks_for(earned):
    """What to say once a report has just been filed.

    The points are only mentioned when some were actually earned. A
    line reading "you have earned 0 points" is worse than no line at
    all.
    """
    if not earned:
        return "Thank you for your visibility report."
    return (f"Thank you for your visibility report, you have earned "
            f"{earned} point{'' if earned == 1 else 's'}.")


def _report(report):
    """One report, ready to print."""
    person = report.submitted_by
    username = person.get_username() if person else ""
    return {
        "id": report.id,
        "username": username,
        # The circle beside a report carries a letter rather than a
        # photograph, for the same reason the one beside a review does:
        # there are no photographs of people on this site and inventing
        # one would be the first step towards there being some. Their
        # own letter, not an upper cased one.
        "initial": username[:1],
        "who_known": person is not None,
        "visibility": metres(report.visibility),
        "observed_at": report.observed_at,
        "category": category(report.visibility),
        "colour": colour(report.visibility),
        "comment": report.user_comment,
    }


def visibility_context(request, location, *, row=None, thanks="",
                       fragment=False, form=None, values=None):
    """The visibility block, in whichever of its states applies.

    The states that matter to the template are: whether anybody has
    reported at all, and whether the person reading has reported here
    themselves. Everything else is the same block.
    """
    from . import visibility as recalc

    if row is None:
        row = recalc.row_for(location)

    count = row.number_of_reports if row else 0
    average = row.average_visibility if row and count else None

    user = request.user
    mine = []
    if row and user.is_authenticated:
        mine = [_report(report) for report in
                row.reports.filter(submitted_by=user, is_hidden=False)
                .select_related("submitted_by")]

    # Everybody's, for the dialog. Not fetched unless there is
    # something to fetch: the button that opens it is hidden when there
    # is nothing, so the list behind it would never be looked at.
    everyone = []
    if row and count:
        everyone = [_report(report) for report in
                    row.reports.filter(is_hidden=False)
                    .select_related("submitted_by")]

    revision = location.current_revision
    return {
        "location": location,
        # Named here as well as on the page, because the block is also
        # returned on its own, where the rest of the listing's context
        # does not exist.
        "location_name": revision.name if revision else "this location",

        "has_reports": bool(count),
        "number_of_reports": count,
        "average_visibility": metres(average),
        "average_category": category(average),
        "average_colour": colour(average),
        "average_position": position(average),

        "my_reports": mine,
        "all_reports": everyone,

        # The scale itself, so the bar and the slider are labelled from
        # one place rather than from three templates.
        "scale_labels": SCALE_LABELS,
        "category_labels": CATEGORY_LABELS,
        "max_age_days": MAX_AGE_DAYS,

        # What the submit form should start from. Whatever was just
        # submitted if there is any, so a rejected submission comes
        # back with what they typed still in it.
        "values": values or {},
        "visibility_form": form,

        "thanks": thanks,
        "fragment": fragment,
    }


def reports_for(location):
    """Every visible report about a location, newest day first."""
    return (VisibilityReport.objects
            .filter(location__snorkel_location=location, is_hidden=False)
            .select_related("submitted_by"))
