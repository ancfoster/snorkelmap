"""The submission endpoint.

One request creates the listing and hands back an upload slot per
photograph. The browser then puts the files into R2 itself and Django
hears about each one from the bucket, not from the browser.

That ordering is deliberate. The listing exists as a draft before a
single byte has been uploaded, so closing the laptop mid-upload leaves
a draft that can be finished or cleaned up, never a half written
listing. The browser is an observer of the publish, not the thing
driving it.
"""
from uuid import UUID

from django import forms
from django.contrib.gis.geos import Point
from django.db import transaction
from django.db.models import Max
from ninja import Router
from ninja.security import django_auth
from ninja.throttling import UserRateThrottle
from turnstile.fields import TurnstileField

from . import (geography, map_data, media_storage, static_map,
               submissions, tasks, w3w)
from contributions import points
from contributions.models import Contribution
from snorkel_visibility import filing
from locations_snorkelled import counts as snorkelled_counts
from locations_snorkelled.models import Snorkelled
from snorkel_reviews.models import LocationRating

from . import editing
from .models import LocationMedia, LocationRevision, SnorkelLocation
from .schemas import (ErrorOut, MediaConfirmOut, RevisionIn, RevisionOut,
                      SubmissionIn, SubmissionOut)

router = Router()

CATEGORY = {
    "aboveWater": LocationMedia.MediaCategory.SURFACE,
    "underwater": LocationMedia.MediaCategory.UNDERWATER,
}


def presign_for(media_row):
    signed = media_storage.presign_upload(media_row.object_key, media_row.mime_type)
    return {
        "clientId": media_row.orignal_media_meta.get("clientId", ""),
        "mediaUuid": media_row.uuid,
        "key": media_row.object_key,
        "method": signed["method"],
        "url": signed["url"],
        "fields": signed.get("fields", {}),
        "headers": signed.get("headers", {}),
    }


@router.post(
    "/submissions",
    response={201: SubmissionOut, 200: SubmissionOut, 400: ErrorOut, 403: ErrorOut},
    auth=django_auth,
    throttle=[UserRateThrottle("60/h")],
)
def create_submission(request, payload: SubmissionIn):
    # Idempotency. The submission id is generated once when the draft
    # is started, so a retry after a dropped connection, or a second
    # tap on publish, finds the location that already exists and gets
    # fresh signatures for whatever has not arrived yet.
    existing = SnorkelLocation.objects.filter(
        submission_id=payload.submissionId).first()
    if existing is not None:
        first_revision = existing.revisions.order_by("increment").first()
        if first_revision and first_revision.created_by_id != request.user.id:
            return 403, {"detail": "That submission belongs to someone else."}
        pending = existing.media.filter(status=LocationMedia.Status.PENDING)
        return 200, {
            "locationUuid": existing.uuid,
            "slug": existing.slug,
            "url": existing.get_absolute_url(),
            "status": existing.get_status_display(),
            "uploads": [presign_for(row) for row in pending],
        }

    try:
        cleaned = submissions.clean(payload)
    except submissions.SubmissionError as error:
        return 400, {"detail": error.detail, "field": error.field}

    # Where this is, asked of Mapbox here rather than taken from the
    # browser. It decides which rows the listing attaches to and what
    # its permanent URL will be, so it is not something to accept on
    # trust from the client. Outside the transaction because it is a
    # network call.
    country, region, locale, geocode_failed = geography.resolve(
        cleaned["lat"], cleaned["lng"])

    with transaction.atomic():
        location = SnorkelLocation.objects.create(
            submission_id=payload.submissionId,
            slug=geography.unique_slug(cleaned["name"]),
            lat_long=Point(cleaned["lng"], cleaned["lat"], srid=4326),
            country=country,
            region=region,
            locale=locale,
            questionable_geocode=geocode_failed,
            # Who started it, which never changes however many people
            # edit it afterwards. Who made any given change is on the
            # revision instead.
            created_by=request.user,
            # Live immediately. A listing used to wait for its first
            # photograph to reach the bucket and pass verification,
            # which meant a dropped connection or a rejected photo left
            # somebody's work invisible and them with nothing to do
            # about it. The written submission is the listing; a
            # photograph improves it.
            status=SnorkelLocation.Status.PUBLISHED,
        )

        revision = LocationRevision.objects.create(
            location=location,
            increment=0,
            name=cleaned["name"],
            alternate_names=cleaned["alternate_names"],
            description=cleaned["description"],
            entry_description=cleaned["entry_description"],
            access_type=cleaned["access_type"],
            water_type=cleaned["water_type"],
            difficulty=cleaned["difficulty"],
            environment_types=cleaned["environment_types"],
            marine_life=cleaned["marine_life"],
            hazards=cleaned["hazards"],
            facilities=cleaned["facilities"],
            marker_data=cleaned["marker_data"],
            created_by=request.user,
            revision_comment="Created",
        )

        rows = []
        order = {"aboveWater": 0, "underwater": 0}
        for item in cleaned["media"]:
            media_uuid = media_storage.new_media_uuid()
            rows.append(LocationMedia(
                uuid=media_uuid,
                location=location,
                media_type=LocationMedia.MediaType.IMAGE,
                media_category=CATEGORY[item.section],
                uploaded_by=request.user,
                description=submissions.clean_text(item.description, 500),
                # The key is built here and signed as an exact match, so
                # the name the file had on the person's phone never
                # reaches the bucket.
                object_key=media_storage.build_key(location.uuid, media_uuid, item.mime),
                status=LocationMedia.Status.PENDING,
                mime_type=item.mime,
                width=item.width,
                height=item.height,
                size_bytes=item.bytes,
                captured_at=submissions.clean_captured_at(
                    item.capturedAt, item.capturedAtOffset),
                captured_at_offset=item.capturedAtOffset or "",
                captured_lat_long=(
                    Point(item.longitude, item.latitude, srid=4326)
                    if item.latitude is not None and item.longitude is not None
                    else None
                ),
                sort_order=order[item.section],
                # Kept so that what the browser claimed can be compared
                # with what verification finds in the bucket.
                orignal_media_meta={
                    "clientId": item.clientId,
                    "section": item.section,
                    "claimed": {
                        "mime": item.mime, "bytes": item.bytes,
                        "width": item.width, "height": item.height,
                        "capturedAt": item.capturedAt,
                        "capturedAtOffset": item.capturedAtOffset,
                        "latitude": item.latitude, "longitude": item.longitude,
                    },
                },
            ))
            order[item.section] += 1

        LocationMedia.objects.bulk_create(rows)

        # No featured image is assigned here. It is set by the
        # verification step once a photograph actually exists in the
        # bucket and has passed its checks, so the field never points
        # at a row that may yet be rejected or never arrive.

        location.current_revision = revision
        location.save(update_fields=["current_revision"])

    # Outside the transaction on purpose: a database transaction should
    # never be left open across a call to somebody else's API. If it
    # fails the location is already safely saved without an address.
    words = w3w.words_for(cleaned["lat"], cleaned["lng"])
    if words:
        location.w3w = words
        location.save(update_fields=["w3w"])

    # Somebody who has written up a location has been in the water
    # there, so the button on their own listing should already say so
    # rather than asking them to state the obvious. get_or_create
    # rather than create, because a resubmitted submission id lands
    # here twice and the second one must not raise.
    Snorkelled.objects.get_or_create(user=request.user, location=location)
    snorkelled_counts.recount(location)

    # A location is the largest single contribution anybody makes, so
    # it is recorded in the ledger here, at the point it is accepted.
    # Awarding is idempotent, so the resubmitted case above pays once.
    points.award(request.user, Contribution.Kind.LOCATION_CREATION,
                 location=location)

    # The visibility report the create form offers, if one was filled
    # in. Filed by the same function the listing page's dialog uses, so
    # there is one set of rules about what a report is and one place
    # that recalculates the figures afterwards.
    #
    # Its own failure is not the submission's failure. Somebody who has
    # just written up a location should not be told their location was
    # rejected because the date beside the slider was a fortnight too
    # old; the listing is saved and they can file the report from its
    # page. Nothing is said back about it for the same reason.
    if payload.visibility is not None:
        filing.file_report(request.user, location, {
            "visibility": payload.visibility.value,
            "observed_at": payload.visibility.date,
            "comment": payload.visibility.comment,
        })

    # Everything a listing needs to be findable and complete exists by
    # this point, so a rating row is opened for it now rather than by
    # whoever happens to review it first. A listing with no reviews has
    # a rating of none, which is a different thing from having no row.
    LocationRating.objects.get_or_create(location=location)

    # The picture of where it is, drawn once and stored, rather than
    # asking Mapbox for it again on every view of the listing.
    static_map.generate_for(location)

    # The map's data file lists published locations, and there is now
    # one more. Both of these swallow their own failures: the listing
    # is already saved, and neither a slow third party nor an
    # unreachable bucket may undo that. rebuild_map_data and
    # generate_map_images exist to put either right afterwards.
    map_data.build_and_publish()

    return 201, {
        "locationUuid": location.uuid,
        "slug": location.slug,
        # The canonical path, so the thank you screen can link straight
        # to the listing the person has just made.
        "url": location.get_absolute_url(),
        "status": location.get_status_display(),
        "uploads": [presign_for(row) for row in rows],
    }


@router.post(
    "/media/{media_uuid}/confirm",
    response={200: MediaConfirmOut, 403: ErrorOut, 404: ErrorOut},
    auth=django_auth,
    throttle=[UserRateThrottle("600/h")],
)
def confirm_media(request, media_uuid: UUID):
    """The browser reporting that one upload finished.

    This exists so a listing goes live while the person is still on the
    publishing screen, rather than a few seconds later when the bucket
    gets round to mentioning it.

    The browser is only saying "look now". It is not trusted for
    anything: verification reads the object out of R2 and checks it
    there, exactly as it does when the Worker asks. A client that
    confirms an upload it never made simply finds nothing, and the row
    stays pending.

    The bucket notification remains the authority for the case this
    cannot cover, which is the browser dying mid-publish. Both paths
    run the same function and it is safe to run twice, so them racing
    each other does not matter.
    """
    row = (LocationMedia.objects
           .select_related("location")
           .filter(uuid=media_uuid)
           .first())
    if row is None:
        return 404, {"detail": "No such upload."}
    if row.uploaded_by_id != request.user.id:
        return 403, {"detail": "That upload belongs to someone else."}

    verified = tasks.verify_media(row.uuid)

    row.refresh_from_db()
    location = row.location
    location.refresh_from_db()

    return 200, {
        "mediaUuid": row.uuid,
        "status": row.get_status_display(),
        "verified": bool(verified),
        "rejectionReason": row.rejection_reason,
        "published": location.status == SnorkelLocation.Status.PUBLISHED,
        "url": location.get_absolute_url(),
    }


# ── Editing a listing that already exists ────────────────────────────

# Which fields are worth recording as having changed. Kept as names
# rather than values: the revision itself holds what the values became,
# and the previous revision holds what they were, so a list of what
# moved is all that is needed to read the history back.
def _client_ip(request):
    """The address the request came from, for Turnstile to bind to.

    The first entry of X-Forwarded-For when there is one, since this
    runs behind Cloudflare; REMOTE_ADDR otherwise.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


TRACKED = ("name", "alternate_names", "description", "entry_description",
           "access_type", "water_type", "difficulty", "environment_types",
           "marine_life", "hazards", "facilities", "marker_data")


def changed_fields(previous, cleaned):
    """Which of the tracked fields this edit actually moved."""
    if previous is None:
        return sorted(TRACKED)
    return sorted(name for name in TRACKED
                  if getattr(previous, name, None) != cleaned[name])


@router.post(
    "/{location_uuid}/revisions",
    response={201: RevisionOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
    auth=django_auth,
    throttle=[UserRateThrottle("60/h")],
)
def create_revision(request, location_uuid: UUID, payload: RevisionIn):
    """One person's edit of somebody else's listing.

    A revision is written rather than the listing being changed in
    place, so every version of every listing is kept and the history
    page has something to read. The listing then points at the new
    revision, which is the only thing that makes it the current one.

    What is not touched: where the listing is, its slug, its
    photographs, and who created it. A rename changes the name shown
    everywhere but leaves the address alone, because an address that
    moved every time somebody corrected a spelling would break every
    link to it.
    """
    location = (SnorkelLocation.objects
                .select_related("current_revision")
                .filter(uuid=location_uuid)
                .first())
    if location is None or location.status != SnorkelLocation.Status.PUBLISHED:
        return 404, {"detail": "No listing matches that address."}

    if location.is_locked and not editing.may_edit_locked(request.user):
        return 403, {"detail": "This listing has been locked and cannot be "
                               "edited at the moment."}

    # The same challenge, the same keys and the same verification the
    # login and signup forms use. Checked before anything is cleaned or
    # written, so a failed challenge costs nothing.
    try:
        TurnstileField(remote_ip=_client_ip(request)).clean(
            payload.turnstileToken)
    except forms.ValidationError as error:
        return 400, {"detail": " ".join(error.messages), "field": "turnstile"}

    try:
        cleaned = submissions.clean_revision(payload)
    except submissions.SubmissionError as error:
        return 400, {"detail": error.detail, "field": error.field}

    previous = location.current_revision

    with transaction.atomic():
        # The row is locked for the length of this block so that two
        # people saving at the same moment cannot both work out the
        # same next increment and collide on the unique constraint.
        held = SnorkelLocation.objects.select_for_update().get(pk=location.pk)
        highest = (LocationRevision.objects
                   .filter(location=held)
                   .aggregate(highest=Max("increment"))["highest"])

        revision = LocationRevision.objects.create(
            location=held,
            increment=(highest or 0) + 1,
            created_by=request.user,
            revision_comment=cleaned["revision_comment"],
            diff={"changed": changed_fields(previous, cleaned)},
            # Carried forward. Which photographs a listing leads with is
            # changed in its own section, not by editing the words.
            featured_above_water_image=(
                previous.featured_above_water_image if previous else None),
            featured_underwater_image=(
                previous.featured_underwater_image if previous else None),
            name=cleaned["name"],
            alternate_names=cleaned["alternate_names"],
            description=cleaned["description"],
            entry_description=cleaned["entry_description"],
            access_type=cleaned["access_type"],
            water_type=cleaned["water_type"],
            difficulty=cleaned["difficulty"],
            environment_types=cleaned["environment_types"],
            marine_life=cleaned["marine_life"],
            hazards=cleaned["hazards"],
            facilities=cleaned["facilities"],
            marker_data=cleaned["marker_data"],
        )

        held.current_revision = revision
        held.save(update_fields=["current_revision"])

    # Outside the transaction, and separately from it: the ledger is
    # about the person, the listing is about the place, and neither
    # recalculation knows the other exists. Keyed on the revision, so
    # editing the same listing again next week is paid again and a
    # replayed request is not.
    _, paid = points.award(request.user, Contribution.Kind.LOCATION_EDIT,
                           location=location, revision=revision)

    # The map's data file carries each listing's name, so a rename has
    # to reach it. Swallows its own failures, as everywhere else.
    map_data.build_and_publish()

    location.refresh_from_db()
    return 201, {
        "locationUuid": location.uuid,
        "increment": revision.increment,
        "url": location.get_absolute_url(),
        "points": (Contribution.POINTS[Contribution.Kind.LOCATION_EDIT]
                   if paid else 0),
    }
