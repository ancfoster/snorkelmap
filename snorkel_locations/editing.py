"""Editing a listing somebody else wrote.

The page is reached at /edit/?uuid=<uuid>, the same shape as the
permanent listing address at /location/?uuid=<uuid>, and for the same
reason: a listing's path changes when it is renamed or its geography is
corrected, and an edit link should not go stale because somebody fixed
a spelling.

There are five ways this page can be arrived at and each gets a
different page rather than a redirect, because four of them are things
the person needs told rather than things to be moved past. What decides
between them is `state`, worked out here and read by the template.

Nothing is edited from here yet. The form arrives next; this is the
page it will sit in, and the gate in front of it.
"""
import uuid as uuid_lib

from django.shortcuts import get_object_or_404, render

from .models import SnorkelLocation


# Who may edit a listing that has been locked. The user model numbers
# its types with the most senior first, so this is the admin and the
# level one moderators and nobody else.
#
# Compared as strings because `user_type` is a CharField whose choices
# are integers, so what comes back is "1" or "2" rather than 1 or 2.
# Worth straightening out in the user model at some point; until then
# this is what the stored values actually look like.
LOCK_OVERRIDE_TYPES = {"1", "2"}


def may_edit_locked(user):
    """Whether a lock applies to this person."""
    return (user.is_authenticated
            and str(getattr(user, "user_type", "")) in LOCK_OVERRIDE_TYPES)


def _requested(request):
    """The listing named in the query string, if there is a real one.

    Returns (location, asked). `asked` says whether a uuid was given at
    all, which is what separates "you have not said which listing" from
    "there is no listing with that uuid".
    """
    raw = (request.GET.get("uuid") or "").strip()
    if not raw:
        return None, False

    try:
        parsed = uuid_lib.UUID(raw)
    except (TypeError, ValueError):
        return None, True

    return SnorkelLocation.objects.filter(uuid=parsed).select_related(
        "current_revision", "country", "region", "locale",
    ).first(), True


def edit(request):
    """The editing page, in whichever of its states applies."""
    location, asked = _requested(request)

    if not request.user.is_authenticated:
        # Somebody who followed an edit link from a listing is told
        # what to do about it and sent back afterwards. Somebody who
        # arrived at /edit/ on its own is told what editing here means
        # in the first place.
        if location is not None:
            return render(request, "snorkel_locations/edit.html", {
                "state": "signed-out-listing",
                "location": location,
                "revision": location.current_revision,
            })
        return render(request, "snorkel_locations/edit.html",
                      {"state": "signed-out-general"})

    if not asked:
        return render(request, "snorkel_locations/edit.html",
                      {"state": "no-uuid"})

    if location is None:
        return render(request, "snorkel_locations/edit.html",
                      {"state": "not-found"})

    if location.is_locked and not may_edit_locked(request.user):
        return render(request, "snorkel_locations/edit.html", {
            "state": "locked",
            "location": location,
            "revision": location.current_revision,
            "locked_message": location.locked_message,
        })

    return render(request, "snorkel_locations/edit.html", {
        "state": "editing",
        "location": location,
        "revision": location.current_revision,
        # A moderator editing a locked listing is still told it is
        # locked, since that is why nobody else is doing it.
        "locked_notice": location.is_locked,
        "locked_message": location.locked_message,
    })


def history(request):
    """Every change made to a listing, and by whom.

    A stub for the moment: the revisions are being written, and this is
    where they will be read. It exists now so that the link on the
    listing goes somewhere real rather than nowhere.
    """
    location, asked = _requested(request)
    return render(request, "snorkel_locations/history.html", {
        "location": location,
        "revision": location.current_revision if location else None,
        "asked": asked,
    })
