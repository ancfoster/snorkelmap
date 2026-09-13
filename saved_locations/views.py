"""Saving a location, and unsaving it.

One endpoint that does both, because the button is one button and the
person thinks of it as one thing. Which way it goes is decided by what
is already in the table rather than by anything the browser sends, so a
double tap, a stale page or a back button cannot get the two out of
step.

POST only. The obvious way to write this is a link and a GET, and it
works right up until a browser prefetches the page, a crawler follows
the link, or somebody's mail client previews it, at which point people
find locations saved that they never saved. A form and a CSRF token
cost one more line and none of that happens.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from snorkel_locations.models import SnorkelLocation

from .models import SavedLocation


def button_context(request, location):
    """What the fragment needs to draw itself."""
    return {
        "location": location,
        "saved": SavedLocation.objects.filter(
            user=request.user, location=location).exists(),
    }


@require_POST
@login_required
def toggle(request, location_uuid):
    """Save the location, or unsave it, and hand back the button."""
    location = get_object_or_404(SnorkelLocation, uuid=location_uuid)

    existing = SavedLocation.objects.filter(
        user=request.user, location=location)
    if existing.exists():
        existing.delete()
    else:
        # Two taps arriving at once would otherwise raise on the unique
        # constraint. get_or_create turns that into a no-op.
        SavedLocation.objects.get_or_create(
            user=request.user, location=location)

    if request.headers.get("HX-Request"):
        return render(request, "saved_locations/_button.html",
                      button_context(request, location))
    return redirect(location.get_absolute_url())
