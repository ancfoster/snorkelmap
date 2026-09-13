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

from django.contrib.gis.geos import Point
from django.db import transaction
from ninja import Router
from ninja.security import django_auth
from ninja.throttling import UserRateThrottle

from . import (geography, map_data, media_storage, static_map,
               submissions, tasks, w3w)
from contributions import points
from contributions.models import Contribution
from locations_snorkelled import counts as snorkelled_counts
from locations_snorkelled.models import Snorkelled
from snorkel_reviews.models import LocationRating

from .models import LocationMedia, LocationRevision, SnorkelLocation
from .schemas import ErrorOut, MediaConfirmOut, SubmissionIn, SubmissionOut

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
