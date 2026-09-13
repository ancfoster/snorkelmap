"""Marking a location as somewhere you have snorkelled, and unmarking it.

The same shape as saving a location, and deliberately the same shape:
one endpoint, POST only, the direction decided by what is already in
the table rather than by anything the browser sends.

What it means is different, though, and worth saying out loud. Saving
is private and says nothing about the place. This is a claim to have
been in the water there, which is what makes a count of it worth
anything to everybody else, so it wants the same care as any other
contribution.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from snorkel_locations.models import SnorkelLocation

from . import counts
from .models import Snorkelled


def button_context(request, location):
    """What the fragment needs to draw itself."""
    return {
        "location": location,
        "snorkelled": Snorkelled.objects.filter(
            user=request.user, location=location).exists(),
        "snorkelled_count": location.users_snorkelled,
    }


@require_POST
@login_required
def toggle(request, location_uuid):
    """Mark the location as snorkelled, or unmark it."""
    location = get_object_or_404(SnorkelLocation, uuid=location_uuid)

    existing = Snorkelled.objects.filter(user=request.user, location=location)
    if existing.exists():
        existing.delete()
    else:
        Snorkelled.objects.get_or_create(user=request.user, location=location)

    # The stored count is now one out either way, so it is rebuilt from
    # the rows before anything reads it back.
    counts.recount(location)

    if request.headers.get("HX-Request"):
        return render(request, "locations_snorkelled/_button.html",
                      button_context(request, location))
    return redirect(location.get_absolute_url())
