"""Turning a submitted payload into something safe to store.

The browser builds its payload from the same choices.py that renders
the form, so in normal use every id here is already valid. This module
exists for the abnormal use: a stale tab running last week's
JavaScript, a hand-rolled request, a bug in the front end.

Two different postures, deliberately:

  unknown ids are dropped, not rejected. If a chip is renamed and
  somebody has a form open from before the change, losing one selection
  is a far better outcome than losing the whole submission they spent
  ten minutes writing.

  the media manifest is rejected outright when it is wrong. A photo
  whose claimed type or size we will not sign is not something to
  quietly drop: the person can see their photos on screen and would
  have no idea one had gone missing.
"""
import re
import unicodedata
from html import unescape

from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags

from . import choices, media

COMMENT_MAX = 2000
NAME_MAX = 200
DESCRIPTION_MAX = 10000
MARKER_NAME_MAX = 120
# What somebody may write about the change they have just made. Matches
# LocationRevision.revision_comment, so the two cannot drift.
REVISION_COMMENT_MAX = 300
MARKER_NOTE_MAX = 500
MAX_MARKERS = 60

# Characters that have no business in a submission: C0 and C1 control
# codes, zero width and directional marks, line and paragraph
# separators, and the byte order mark. Invisible characters are how a
# duplicate location name gets made to look unique, and how text gets
# made to read one way and sort another.
_CONTROL = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f"
    r"\u200b-\u200f\u202a-\u202e\u2028\u2029\ufeff]"
)
# Runs of whitespace that are not newlines. Newlines are kept because
# descriptions are rendered with linebreaks and paragraphing is the
# person's own.
_SPACES = re.compile(r"[^\S\n]+")
_BLANK_RUNS = re.compile(r"\n{3,}")

SECTION_TO_CATEGORY = {
    "aboveWater": "SURFACE",
    "underwater": "UNDERWATER",
}


class SubmissionError(Exception):
    """Something in the payload cannot be stored as sent."""

    def __init__(self, detail, field=""):
        super().__init__(detail)
        self.detail = detail
        self.field = field


# ── Chip groups ──────────────────────────────────────────────────────

# Built in choices.py, which is where the mapping between a payload
# key and the group behind it belongs. The listing page uses the same
# index in the opposite direction, to turn stored ids back into labels.
GROUP_INDEX = choices.PAYLOAD_SECTIONS


def clean_text(value, limit=COMMENT_MAX):
    """Plain text, with any markup removed.

    Nothing submitted is stored as HTML. This is not the defence
    against cross site scripting, which is Django escaping on output
    and applies whether or not anything was cleaned here. It is so that
    what sits in the database is the words the person wrote, in an
    admin list, a CSV export or an email as much as on the page.

    The order matters. Unicode is normalised first, because a fullwidth
    less-than sign normalises into a real one and would otherwise
    become a tag after the stripping had already finished. Entity
    decoding and tag stripping then repeat, because one pass leaves
    "&lt;script&gt;" untouched and turns "<scr<script>ipt>" into a
    working tag.
    """
    text = unicodedata.normalize("NFKC", str(value or ""))

    for _ in range(3):
        before = text
        text = strip_tags(unescape(text))
        if text == before:
            break

    text = _CONTROL.sub("", text)
    text = _SPACES.sub(" ", text)
    text = _BLANK_RUNS.sub("\n\n", text)
    return text.strip()[:limit]


# Kept as the short internal name, since it is used on nearly every
# line of this module.
_text = clean_text


def clean_group_map(section, raw):
    """Filter one payload section down to ids that still exist.

    A group reports either a bare list of ids or
    {"selected": [...], "comments": "..."}, matching whether it has a
    comment box. Both shapes are preserved.
    """
    index = GROUP_INDEX.get(section, {})
    cleaned = {}

    for key, value in (raw or {}).items():
        if key == "comments":
            cleaned["comments"] = _text(value)
            continue

        group = index.get(key)
        if group is None:
            continue
        allowed = choices.valid_ids(group["key"])

        if isinstance(value, dict):
            selected = [i for i in value.get("selected", []) if i in allowed]
            cleaned[key] = {
                "selected": selected,
                "comments": _text(value.get("comments")),
            }
        elif isinstance(value, list):
            cleaned[key] = [i for i in value if i in allowed]

    return cleaned


def clean_facilities(raw):
    """Facilities carry the flat chip groups plus the getting there block."""
    raw = raw or {}
    cleaned = clean_group_map("facilities", raw)

    getting_there = raw.get("gettingThere") or {}
    parking = getting_there.get("parking") or {}
    transport = getting_there.get("transport") or {}

    parking_ids = {t[0] for t in choices.PARKING_TYPES}
    transport_ids = {t[0] for t in choices.TRANSPORT_TYPES}
    availability = {a[0] for a in choices.PARKING_AVAILABILITY}

    cleaned["gettingThere"] = {
        "comments": _text(getting_there.get("comments")),
        "parking": {
            "available": (parking.get("available")
                          if parking.get("available") in availability else None),
            "selected": [i for i in parking.get("selected", []) if i in parking_ids],
            "comments": _text(parking.get("comments")),
        },
        "transport": {
            "selected": [i for i in transport.get("selected", []) if i in transport_ids],
            "description": _text(transport.get("description")),
        },
    }
    cleaned["other"] = _text(raw.get("other"))
    return cleaned


def clean_list(values, allowed):
    return [v for v in (values or []) if v in allowed]


def clean_markers(raw):
    """Rebuild the marker collection from scratch.

    The map hands over a GeoJSON FeatureCollection, and it is the one
    part of the payload that was previously stored exactly as sent.
    Nothing here is copied across: every feature is reconstructed from
    values that have been checked, so an unknown marker id, a
    coordinate that is not a number, or anything extra someone added to
    the properties does not survive. The note is free text the person
    wrote, so it is cleaned like any other.
    """
    valid_ids = {marker[0]
                 for group in choices.MARKER_LIBRARY
                 for marker in group["markers"]}
    features = []

    for feature in ((raw or {}).get("features") or [])[:MAX_MARKERS]:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties") or {}
        marker_id = properties.get("markerId")
        if marker_id not in valid_ids:
            continue

        coordinates = (feature.get("geometry") or {}).get("coordinates")
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 2:
            continue
        try:
            lng, lat = float(coordinates[0]), float(coordinates[1])
        except (TypeError, ValueError):
            continue
        if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
            continue

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "markerId": marker_id,
                "name": clean_text(properties.get("name"), MARKER_NAME_MAX),
                "note": clean_text(properties.get("note"), MARKER_NOTE_MAX),
            },
        })

    return {"type": "FeatureCollection", "features": features}


# ── Media manifest ───────────────────────────────────────────────────

def clean_captured_at(value, offset):
    """EXIF wall clock plus its offset, if the camera recorded one.

    With no offset there is nothing to work from, so the time is read
    as UTC and flagged as such by the empty offset stored beside it.
    Guessing the photographer's timezone from the pin would be worse
    than admitting we do not know.
    """
    if not value:
        return None
    text = str(value)
    if offset and len(str(offset)) in (5, 6):
        text = f"{text}{offset}"
    else:
        text = f"{text}+00:00"
    try:
        return parse_datetime(text)
    except (ValueError, TypeError):
        return None


def clean_media(items):
    """Check every photograph against the same rules the browser used."""
    limits = media.media_rules()["limits"]
    counts = {"aboveWater": 0, "underwater": 0}
    cleaned = []

    for item in items or []:
        if item.section not in SECTION_TO_CATEGORY:
            raise SubmissionError(f"Unknown media section {item.section}", "media")
        if not media.is_accepted(item.mime):
            raise SubmissionError(
                f"{item.mime} is not a format we can accept.", "media")

        shortest = min(item.width, item.height)
        longest = max(item.width, item.height)
        if shortest < limits["min_dimension"]:
            raise SubmissionError(
                f"A photo is {item.width} by {item.height} pixels, under the "
                f"{limits['min_dimension']} pixel minimum.", "media")
        if longest > limits["max_dimension"]:
            raise SubmissionError("A photo is larger than we can process.", "media")
        if (item.width * item.height) / 1_000_000 > limits["max_megapixels"]:
            raise SubmissionError("A photo is larger than we can process.", "media")
        if not (limits["min_bytes"] <= item.bytes <= limits["max_bytes"]):
            raise SubmissionError("A photo is outside the accepted file size.", "media")

        counts[item.section] += 1
        if counts[item.section] > limits["max_files_per_section"]:
            raise SubmissionError(
                f"Up to {limits['max_files_per_section']} photos can be added "
                f"to each section.", "media")

        cleaned.append(item)

    if not counts["aboveWater"]:
        raise SubmissionError(
            "At least one photo of the above water surroundings is needed "
            "to publish.", "media")

    return cleaned


# ── The whole payload ────────────────────────────────────────────────

def clean(payload):
    """Everything that goes onto the revision, validated and trimmed."""
    name = _text(payload.name, NAME_MAX)
    if not name:
        raise SubmissionError("A name is needed.", "name")

    lat = payload.coordinates.lat
    lng = payload.coordinates.lng
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise SubmissionError("Those coordinates are not on Earth.", "coordinates")

    access_ids = {a[0] for a in choices.ACCESS_TYPES}
    water_ids = set()
    for group in choices.WATER_TYPE_GROUPS:
        water_ids.update(chip["id"] for chip in group["chips"])

    difficulty = payload.difficulty if payload.difficulty in (1, 2, 3, 4) else 1

    return {
        "name": name,
        "lat": lat,
        "lng": lng,
        "alternate_names": [_text(n, NAME_MAX) for n in payload.alternateNames][:10],
        "description": _text(payload.description, DESCRIPTION_MAX),
        "entry_description": _text(payload.entryPointDescription, DESCRIPTION_MAX),
        "access_type": clean_list(payload.accessType, access_ids),
        "water_type": clean_list(payload.waterType, water_ids),
        "difficulty": difficulty,
        "environment_types": clean_group_map("environmentTypes", payload.environmentTypes),
        "marine_life": clean_group_map("marineLife", payload.marineLife),
        "hazards": clean_group_map("hazards", payload.hazards),
        "facilities": clean_facilities(payload.facilities),
        "marker_data": clean_markers(payload.locationMarkerData),
        "media": clean_media(payload.media),
    }


def clean_revision(payload):
    """Everything that goes onto a revision of a listing that exists.

    The same cleaners as clean(), over a shorter list. What is missing
    is missing on purpose: coordinates, because where a listing is is
    not edited here; media, because photographs are their own thing and
    an edit only chooses which of them is featured; and the visibility
    report, which is filed against a listing rather than being part of
    one.

    A revision still needs a name, for the same reason a submission
    does: everything else on the page can be empty and the listing is
    still a listing, but a listing with no name is not one.
    """
    name = _text(payload.name, NAME_MAX)
    if not name:
        raise SubmissionError("A name is needed.", "name")

    access_ids = {a[0] for a in choices.ACCESS_TYPES}
    water_ids = set()
    for group in choices.WATER_TYPE_GROUPS:
        water_ids.update(chip["id"] for chip in group["chips"])

    difficulty = payload.difficulty if payload.difficulty in (1, 2, 3, 4) else 1

    return {
        "name": name,
        "alternate_names": [n for n in
                            (_text(n, NAME_MAX) for n in payload.alternateNames)
                            if n][:10],
        "description": _text(payload.description, DESCRIPTION_MAX),
        "entry_description": _text(payload.entryPointDescription, DESCRIPTION_MAX),
        "access_type": clean_list(payload.accessType, access_ids),
        "water_type": clean_list(payload.waterType, water_ids),
        "difficulty": difficulty,
        "environment_types": clean_group_map("environmentTypes",
                                             payload.environmentTypes),
        "marine_life": clean_group_map("marineLife", payload.marineLife),
        "hazards": clean_group_map("hazards", payload.hazards),
        "facilities": clean_facilities(payload.facilities),
        "marker_data": clean_markers(payload.locationMarkerData),
        "revision_comment": _text(payload.revisionComment,
                                  REVISION_COMMENT_MAX),
    }
