"""Request and response shapes for the submission endpoint.

The free form sections (environment types, marine life, hazards,
facilities, markers) stay as plain dicts here rather than being given a
schema class each. Their structure is already described once, in
choices.py, and every id inside them is checked against that on the way
in. Restating the same structure in a second place would only create
somewhere for the two to disagree.
"""
from typing import Any, Optional
from uuid import UUID

from ninja import Schema


class CoordinatesIn(Schema):
    lat: float
    lng: float


class MediaIn(Schema):
    """One photograph the browser is holding and wants a slot for."""
    clientId: str
    section: str                      # aboveWater or underwater
    mime: str
    bytes: int
    width: int
    height: int
    description: str = ""

    # Read from EXIF in the browser. Taken on trust: a determined
    # person can edit their own photo's metadata, and the cost of that
    # is a wrong capture date on their own listing.
    capturedAt: Optional[str] = None
    capturedAtOffset: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class VisibilityIn(Schema):
    value: float
    date: str
    comment: str = ""


class SubmissionIn(Schema):
    submissionId: UUID
    name: str
    coordinates: CoordinatesIn

    alternateNames: list[str] = []
    description: str = ""
    entryPointDescription: str = ""
    accessType: list[str] = []
    waterType: list[str] = []
    difficulty: int = 1

    # No locationMeta. The create form runs its own Mapbox lookup to
    # show the person where the pin landed, but the geography that gets
    # stored is resolved server side from the coordinates. Anything the
    # browser says about where this is would be a claim, and the URL it
    # decides is permanent.
    environmentTypes: dict[str, Any] = {}
    marineLife: dict[str, Any] = {}
    hazards: dict[str, Any] = {}
    facilities: dict[str, Any] = {}
    locationMarkerData: dict[str, Any] = {}

    visibility: Optional[VisibilityIn] = None
    media: list[MediaIn] = []


class RevisionIn(Schema):
    """One person's edit of a listing that already exists.

    Deliberately not SubmissionIn with fields removed. What can be
    edited is a shorter list than what can be submitted: where a
    listing is cannot be changed here, photographs are handled on their
    own, and a visibility report is a thing somebody files rather than
    a property of the listing. Saying that in the schema is what stops
    any of them arriving by accident.
    """
    name: str
    alternateNames: list[str] = []
    description: str = ""
    entryPointDescription: str = ""
    accessType: list[str] = []
    waterType: list[str] = []
    difficulty: int = 1

    environmentTypes: dict[str, Any] = {}
    marineLife: dict[str, Any] = {}
    hazards: dict[str, Any] = {}
    facilities: dict[str, Any] = {}
    locationMarkerData: dict[str, Any] = {}

    # What they say they changed and why. Optional, and shown beside
    # the revision in the listing's history.
    revisionComment: str = ""

    # The Turnstile token. Carried in the payload because this form is
    # posted by script rather than by the browser, so nothing else would
    # bring it along.
    turnstileToken: str = ""


class RevisionOut(Schema):
    locationUuid: UUID
    increment: int
    url: str
    # What this edit earned, so the thank you can say so. Zero when the
    # ledger had already paid for this revision, which happens when a
    # request is replayed.
    points: int = 0


class UploadOut(Schema):
    """One signed slot. Either fields (POST) or headers (PUT) is filled."""
    clientId: str
    mediaUuid: UUID
    key: str
    method: str
    url: str
    fields: dict[str, str] = {}
    headers: dict[str, str] = {}


class SubmissionOut(Schema):
    locationUuid: UUID
    slug: str
    url: str
    status: str
    uploads: list[UploadOut]


class MediaConfirmOut(Schema):
    """What became of one photograph, once the server had looked at it."""
    mediaUuid: UUID
    status: str
    verified: bool
    rejectionReason: str = ""
    published: bool
    url: str


class ErrorOut(Schema):
    detail: str
    field: str = ""
