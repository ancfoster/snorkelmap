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

The form itself is one long page of collapsible sections rather than
the create page's wizard. Somebody adding a location is being walked
through a thing they have not done before; somebody editing one has
come to change a particular detail and should not have to walk past
seven steps to reach it.

What the browser starts from is `edit_original`, the current revision
flattened into exactly the shape the form works in. edit.js freezes
that and works on a copy, so what was there and what is being proposed
are two separate objects and the difference between them is always
answerable.
"""
import uuid as uuid_lib

from django.shortcuts import render

from turnstile import settings as turnstile_settings

from . import choices, geography, submissions
from .models import SnorkelLocation


# Who may edit a listing that has been locked: the admin and the level
# one moderators, and nobody else. The user model numbers its types
# with the most senior first, so this is everything at MOD_LEVEL_1 or
# above.
#
# The number is written here rather than reached for across into the
# user model at import time. edit_check.py holds the two together, so
# renumbering the types there cannot leave this behind.
LOCK_OVERRIDE_LEVEL = 2      # snorkelusers.User.UserType.MOD_LEVEL_1


def may_edit_locked(user):
    """Whether a lock applies to this person.

    Coerced rather than compared directly, so that an account whose
    type is missing, empty or some leftover string from before the
    field was an integer reads as an ordinary member. Everything here
    fails closed: anything that is not plainly a senior enough number
    is not one.
    """
    if not user.is_authenticated:
        return False
    try:
        return int(user.user_type) <= LOCK_OVERRIDE_LEVEL
    except (AttributeError, TypeError, ValueError):
        return False


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

    context = edit_page_context(location)
    context.update({
        "state": "editing",
        # A moderator editing a locked listing is still told it is
        # locked, since that is why nobody else is doing it.
        "locked_notice": location.is_locked,
        "locked_message": location.locked_message,
    })
    return render(request, "snorkel_locations/edit.html", context)


# ── Reading the history back ─────────────────────────────────────────

# What each stored field is called on the page, and how a change to it
# should be shown. "text" prints both versions in full, because a
# history that summarises the words is not a history of the words.
# "value" is a one line before and after. "chips" shows only what was
# added and what was taken away, which is what somebody reading a
# history actually wants: repeating forty unchanged chips either side
# of one new one hides the change rather than showing it.
SIMPLE_FIELDS = (
    ("name", "Name", "value"),
    ("description", "Description", "text"),
    ("entry_description", "Entry point description", "text"),
)

SECTION_FIELDS = (
    ("environment_types", "environmentTypes", choices.ENVIRONMENT_GROUPS),
    ("marine_life", "marineLife", choices.MARINE_LIFE_GROUPS),
    ("hazards", "hazards", choices.HAZARD_GROUPS),
    ("facilities", "facilities", choices.FACILITY_GROUPS),
)


def _text_change(label, before, after):
    if (before or "") == (after or ""):
        return None
    return {"kind": "text", "label": label,
            "before": before or "", "after": after or ""}


def _value_change(label, before, after):
    if (before or "") == (after or ""):
        return None
    return {"kind": "value", "label": label,
            "before": before or "", "after": after or ""}


def _chip_change(label, before, after, to_label):
    before = list(before or [])
    after = list(after or [])
    added = [to_label(chip) for chip in after if chip not in before]
    removed = [to_label(chip) for chip in before if chip not in after]
    if not added and not removed:
        return None
    return {"kind": "chips", "label": label,
            "added": added, "removed": removed}


def _group_changes(before, after, section, groups):
    """One line per chip group that moved, plus its comment box."""
    changes = []
    before = before or {}
    after = after or {}

    for group in groups:
        was, was_comment = _chips(group, before)
        now, now_comment = _chips(group, after)

        change = _chip_change(
            group["label"], was, now,
            lambda chip, key=group["key"]: choices.label_for(key, chip))
        if change:
            changes.append(change)

        comment = _text_change(f"{group['label']} notes",
                               was_comment, now_comment)
        if comment:
            changes.append(comment)

    return changes


def _getting_there_changes(before, after):
    """Parking and public transport, which sit inside facilities."""
    was = (before or {}).get("gettingThere") or {}
    now = (after or {}).get("gettingThere") or {}
    was_parking = was.get("parking") or {}
    now_parking = now.get("parking") or {}
    was_transport = was.get("transport") or {}
    now_transport = now.get("transport") or {}

    availability = dict(choices.PARKING_AVAILABILITY)
    parking_types = dict(choices.PARKING_TYPES)
    transport_types = dict(choices.TRANSPORT_TYPES)

    candidates = [
        _text_change("Getting there", was.get("comments"), now.get("comments")),
        _value_change("Parking",
                      availability.get(was_parking.get("available"), ""),
                      availability.get(now_parking.get("available"), "")),
        _chip_change("Parking options",
                     was_parking.get("selected"), now_parking.get("selected"),
                     lambda chip: parking_types.get(chip, chip)),
        _text_change("Parking notes",
                     was_parking.get("comments"), now_parking.get("comments")),
        _chip_change("Public transport",
                     was_transport.get("selected"), now_transport.get("selected"),
                     lambda chip: transport_types.get(chip, chip)),
        _text_change("Public transport description",
                     was_transport.get("description"),
                     now_transport.get("description")),
        _text_change("Other facilities",
                     (before or {}).get("other"), (after or {}).get("other")),
    ]
    return [change for change in candidates if change]


def _marker_names(marker_data):
    features = (marker_data or {}).get("features") or []
    return [(feature.get("properties") or {}).get("name")
            or (feature.get("properties") or {}).get("markerId") or "Marker"
            for feature in features]


def revision_changes(before, after):
    """What one revision changed about the one before it.

    Worked out from the two revisions rather than read from the stored
    diff, because the diff was only ever written by the editing
    endpoint: a listing whose first revision predates it would have
    nothing to show. Two rows are always available; a summary of them
    may not be.
    """
    if before is None:
        return []

    changes = []

    for field, label, kind in SIMPLE_FIELDS:
        change = (_text_change if kind == "text" else _value_change)(
            label, getattr(before, field, ""), getattr(after, field, ""))
        if change:
            changes.append(change)

    alternates = _chip_change(
        "Alternate names",
        before.alternate_names, after.alternate_names, lambda name: name)
    if alternates:
        changes.append(alternates)

    access = dict(choices.ACCESS_TYPES)
    changes += [change for change in (
        _chip_change("Access type", before.access_type, after.access_type,
                     lambda chip: access.get(chip, chip)),
        _chip_change("Water type", before.water_type, after.water_type,
                     lambda chip: choices.labels_for(
                         [(c["id"], c["label"])
                          for group in choices.WATER_TYPE_GROUPS
                          for c in group["chips"]], [chip])[0]),
        _value_change("Difficulty",
                      before.get_difficulty_display(),
                      after.get_difficulty_display()),
    ) if change]

    for field, section, groups in SECTION_FIELDS:
        changes += _group_changes(getattr(before, field, None),
                                  getattr(after, field, None),
                                  section, groups)

    # The two section wide comment boxes, which are not part of any
    # group.
    for field, label in (("marine_life", "Marine life notes"),
                         ("hazards", "Hazard notes")):
        change = _text_change(
            label,
            (getattr(before, field, None) or {}).get("comments"),
            (getattr(after, field, None) or {}).get("comments"))
        if change:
            changes.append(change)

    changes += _getting_there_changes(before.facilities, after.facilities)

    markers = _chip_change("Map markers",
                           _marker_names(before.marker_data),
                           _marker_names(after.marker_data),
                           lambda name: name)
    if markers:
        changes.append(markers)
    elif (before.marker_data or {}) != (after.marker_data or {}):
        # Same markers, moved or annotated. Worth saying, without
        # printing a pair of coordinates at somebody.
        changes.append({"kind": "value", "label": "Map markers",
                        "before": "", "after": "Moved or annotated"})

    return changes


def revision_head(revision, created, current_increment):
    """What kind of event a revision was, when it was, and who did it.

    The top of a timeline entry, and the top of the dialog that opens
    one. Both draw it from _revision_head.html, so both are given it
    from here rather than each view deciding separately what to call a
    revision made by an account that has since been deleted.
    """
    return {
        "increment": revision.increment,
        "created": created,
        "at": revision.created_at,
        # A deleted account leaves its revisions behind, which is the
        # point of SET_NULL. Named here so the template does not have
        # to decide what to call nobody.
        "who": (revision.created_by.get_username()
                if revision.created_by else "a deleted account"),
        "who_known": revision.created_by is not None,
        "is_current": revision.increment == current_increment,
    }


def history(request):
    """Every change made to a listing, and by whom.

    Oldest first, so it reads forwards: the listing is created, and then
    each thing that happened to it is added underneath. Each entry
    carries what that revision changed about the one before it, and a
    button that opens the listing as it stood at that moment.
    """
    location, asked = _requested(request)
    if location is None:
        return render(request, "snorkel_locations/history.html", {
            "location": None, "revision": None, "asked": asked,
            "events": [],
        })

    revisions = list(location.revisions.select_related("created_by")
                     .order_by("increment"))

    current_increment = (location.current_revision.increment
                         if location.current_revision else None)

    events = []
    previous = None
    for revision in revisions:
        event = revision_head(
            revision,
            created=revision.increment == 0 or previous is None,
            current_increment=current_increment)
        event.update({
            "comment": revision.revision_comment,
            "changes": revision_changes(previous, revision),
            "name": revision.name,
        })
        events.append(event)
        previous = revision

    return render(request, "snorkel_locations/history.html", {
        "location": location,
        "revision": location.current_revision,
        "asked": asked,
        "events": events,
        "current_increment": current_increment,
    })


def revision_snapshot(revision):
    """The listing as one revision left it, ready to draw.

    The same keys listing_context produces, so the same partials draw
    it. Only the parts that belong to the revision: no photographs, no
    rating, no reviews, no visibility, nothing about who has snorkelled
    there. Those are all about the listing now, not about how it was
    written then, and putting them in a historical view would be
    inventing a past that did not happen.
    """
    facilities = revision.facilities or {}
    getting_there = facilities.get("gettingThere") or {}
    parking = getting_there.get("parking") or {}
    transport = getting_there.get("transport") or {}

    return {
        "revision": revision,
        "access_types": choices.labels_for(choices.ACCESS_TYPES,
                                           revision.access_type),
        "water_types": choices.labels_for(choices.flat_water_types(),
                                          revision.water_type),
        "difficulty": revision.get_difficulty_display(),

        "environment": choices.describe_group_map(
            "environmentTypes", revision.environment_types),
        "marine_life": choices.describe_group_map(
            "marineLife", revision.marine_life),
        "marine_life_comments": (revision.marine_life or {}).get("comments", ""),
        "hazards": choices.describe_group_map("hazards", revision.hazards),
        "hazards_comments": (revision.hazards or {}).get("comments", ""),
        "facilities": choices.describe_group_map("facilities", facilities),
        "facilities_other": facilities.get("other", ""),

        "getting_there_comments": getting_there.get("comments", ""),
        "parking_available": dict(choices.PARKING_AVAILABILITY).get(
            parking.get("available"), ""),
        "parking_types": choices.labels_for(choices.PARKING_TYPES,
                                            parking.get("selected")),
        "parking_comments": parking.get("comments", ""),
        "transport_types": choices.labels_for(choices.TRANSPORT_TYPES,
                                              transport.get("selected")),
        "transport_description": transport.get("description", ""),

        "markers": [geography.marker_for(feature) for feature in
                    ((revision.marker_data or {}).get("features") or [])],
    }


def revision_state(request):
    """One revision, as a fragment for the history page's dialog.

    Fetched when it is asked for rather than rendered with the page. A
    listing with thirty revisions would otherwise carry thirty copies
    of a listing page, all but one of them never looked at.
    """
    location, _ = _requested(request)
    if location is None:
        return render(request, "snorkel_locations/_revision_state.html",
                      {"revision": None})

    try:
        increment = int(request.GET.get("increment", ""))
    except (TypeError, ValueError):
        increment = None

    revision = location.revisions.filter(increment=increment).first()
    if revision is None:
        return render(request, "snorkel_locations/_revision_state.html",
                      {"revision": None})

    context = revision_snapshot(revision)
    context["location"] = location
    # The dialog's own header, swapped out of band by the same
    # response. Without a previous revision to hand, increment zero is
    # what makes this the creation, which is what it means anyway.
    context["head"] = revision_head(
        revision,
        created=revision.increment == 0,
        current_increment=(location.current_revision.increment
                           if location.current_revision else None))
    return render(request, "snorkel_locations/_revision_state.html", context)


# ── The current revision, in the shape the form works in ─────────────

# The four chip sections, and the revision field each is stored on.
CHIP_SECTIONS = (
    ("environmentTypes", "environment_types", choices.ENVIRONMENT_GROUPS),
    ("marineLife", "marine_life", choices.MARINE_LIFE_GROUPS),
    ("hazards", "hazards", choices.HAZARD_GROUPS),
    ("facilities", "facilities", choices.FACILITY_GROUPS),
)


def _chips(group, stored):
    """One group's selections and comment, whichever way it was stored.

    A group with a comment box is stored as {"selected", "comments"};
    one without is stored as a bare list. Both shapes are in the
    database already, so both are read here rather than one being
    assumed and the other quietly coming back empty.
    """
    raw = (stored or {}).get(group["payload_key"])
    if isinstance(raw, dict):
        return list(raw.get("selected") or []), raw.get("comments", "") or ""
    if isinstance(raw, list):
        return list(raw), ""
    return [], ""


def form_state(revision):
    """Everything on a revision, flat, as the form and its script use it.

    Keyed exactly as the create form keys its own working state, so one
    script could serve both if that is ever wanted, and so the payload
    this produces is the payload the endpoint already understands.
    """
    if revision is None:
        return {}

    facilities = revision.facilities or {}
    getting_there = facilities.get("gettingThere") or {}
    parking = getting_there.get("parking") or {}
    transport = getting_there.get("transport") or {}

    state = {
        "name": revision.name or "",
        "alternateNames": list(revision.alternate_names or []),
        "description": revision.description or "",
        "entryPointDescription": revision.entry_description or "",
        "accessType": list(revision.access_type or []),
        "waterType": list(revision.water_type or []),
        "difficulty": revision.difficulty or 1,

        # The two section wide comment boxes, which sit beside the
        # groups rather than inside any one of them.
        "marineLifeComments": (revision.marine_life or {}).get("comments", ""),
        "hazardsComments": (revision.hazards or {}).get("comments", ""),

        "gettingThereComments": getting_there.get("comments", "") or "",
        "parkingAvailable": parking.get("available") or "",
        "facParking": list(parking.get("selected") or []),
        "facParkingComments": parking.get("comments", "") or "",
        "facTransport": list(transport.get("selected") or []),
        "facTransportDescription": transport.get("description", "") or "",
        "facOther": facilities.get("other", "") or "",

        "markerData": revision.marker_data or {"type": "FeatureCollection",
                                               "features": []},
    }

    for _, field, groups in CHIP_SECTIONS:
        stored = getattr(revision, field, None) or {}
        for group in groups:
            selected, comments = _chips(group, stored)
            state[group["key"]] = selected
            # A group with a box always gets a slot, empty or not. A
            # group without one gets a slot only if something is
            # stored against it anyway, so an edit cannot quietly drop
            # a comment written before the box was taken away.
            if group["comments"] or comments:
                state[f"{group['key']}Comments"] = comments

    return state


def edit_page_context(location):
    """The chip library, plus this listing's answers to it."""
    revision = location.current_revision
    context = choices.create_page_context()
    context.update({
        "location": location,
        "revision": revision,
        "edit_original": form_state(revision),
        # Where the listing is. Not editable here, but the marker map
        # has to open somewhere, and that somewhere is the pin.
        "coordinates": {"lat": location.latitude, "lng": location.longitude},
        "revision_comment_max": submissions.REVISION_COMMENT_MAX,
        # The challenge, read from the same place the login and signup
        # forms read it, so one setting covers all three.
        "turnstile_enabled": turnstile_settings.ENABLE,
        "turnstile_sitekey": turnstile_settings.SITEKEY,
        "turnstile_api_url": turnstile_settings.JS_API_URL,
    })
    return context
