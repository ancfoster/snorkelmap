"""The map page, and the two fragments it asks for.

Three views, and only the first is a page.

  explore         the map itself, with the data file's address and the
                  first cards rendered in, so there is something to
                  read before any JavaScript runs.
  explore_cards   the pane, refreshed as the map moves. Takes a list of
                  at most twenty ids that the browser chose.
  explore_card    one card, for the popup that opens when a pin is
                  clicked.

Both fragments return HTML rather than JSON. The thumbnail URL is built
by media_storage, the fallback image comes from settings, and the
escaping of a location's name is the template engine's job. Rendering
those in JavaScript would mean a second copy of all three in a second
language, which is the kind of duplication that quietly diverges.

They are outside /api/v1/ for the same reason: an HTML fragment is not
an API response, and putting one through django-ninja means working
around its schema handling for no benefit.

The map is public, so neither fragment can be behind a session. What
protects them instead is that neither can be made expensive. The pane
fetches at most twenty rows by id, the popup one, and a bounded query
is a bounded query however it is called. The cross site check and the
rate limit below are there to stop another site using the endpoints in
a browser and to blunt a crawler, not because the queries are dangerous.
"""
import uuid as uuid_lib

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import cards, geo_storage
from .models import MapData, SnorkelLocation

# The pane never asks for more than this, so neither does the endpoint.
MAX_IDS = 24

# Per IP, per minute. Generous for a person panning a map, tight enough
# that walking the whole collection takes a while.
RATE_LIMIT = 120
RATE_WINDOW = 60


def _is_cross_site(request):
    """True when the browser says this request came from another site.

    Sec-Fetch-Site is set by the browser and cannot be changed by script,
    so it is trustworthy when present. Origin is the older signal and is
    only sent on some requests. Neither appears on a request from curl,
    which is why this stops other websites rather than other people.
    """
    fetch_site = request.headers.get("Sec-Fetch-Site", "")
    if fetch_site and fetch_site not in ("same-origin", "same-site", "none"):
        return True

    origin = request.headers.get("Origin", "")
    if origin:
        host = request.get_host()
        if origin.split("://")[-1].split("/")[0] != host:
            return True
    return False


def _client_ip(request):
    forwarded = request.headers.get("CF-Connecting-IP") or \
        request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _rate_limited(request, bucket):
    """A crude fixed window counter, kept in the cache.

    Deliberately crude. Cloudflare does the real rate limiting in front
    of this; the point of having it here as well is that anything
    reaching the origin directly is not covered by that, and the cost
    of a cache increment is nothing.
    """
    ip = _client_ip(request)
    if not ip:
        return False
    key = f"explore:{bucket}:{ip}"
    try:
        added = cache.add(key, 1, RATE_WINDOW)
        count = 1 if added else cache.incr(key)
    except ValueError:
        # The key expired between add and incr.
        cache.set(key, 1, RATE_WINDOW)
        return False
    return count > RATE_LIMIT


def _guard(request, bucket):
    """The two checks both fragments share. Returns a response or None."""
    if _is_cross_site(request):
        return HttpResponseForbidden("This endpoint serves snorkelmap.com.")
    if _rate_limited(request, bucket):
        response = HttpResponse("Too many requests.", status=429)
        response["Retry-After"] = str(RATE_WINDOW)
        return response
    return None


def parse_ids(raw):
    """The browser's chosen ids, cleaned.

    Anything malformed is dropped rather than refused: the list is a
    hint about what to display, not an instruction worth failing over,
    and one bad entry should not empty the pane. Duplicates are removed
    because the same row twice is a rendering bug, and the whole thing
    is capped so the query stays the size it was designed to be.
    """
    parsed, seen = [], set()
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part or part in seen:
            continue
        try:
            parsed.append(uuid_lib.UUID(part))
        except (ValueError, AttributeError, TypeError):
            continue
        seen.add(part)
        if len(parsed) >= MAX_IDS:
            break
    return parsed


def published(*uuids):
    """Published locations only, with everything a card needs attached."""
    query = (
        SnorkelLocation.objects
        .filter(status=SnorkelLocation.Status.PUBLISHED,
                current_revision__isnull=False)
        .select_related("current_revision",
                        "current_revision__featured_above_water_image",
                        "country", "region", "locale")
    )
    if uuids:
        query = query.filter(uuid__in=uuids)
    return query


def _in_requested_order(rows, wanted):
    """Keep the browser's ordering, which is by distance from the centre.

    The database returns rows in whatever order suits it, and re-sorting
    on the client would mean shipping the distances too. Cheaper to
    reorder here.
    """
    by_uuid = {row.uuid: row for row in rows}
    return [by_uuid[u] for u in wanted if u in by_uuid]


@require_GET
def explore(request):
    """The map page."""
    record = MapData.load()
    recent = published().order_by("-created_at")[:settings.MAP_PANE_LIMIT]

    return render(request, "snorkel_locations/explore.html", {
        "mapbox_token": settings.MAPBOX_TOKEN,
        "map_data_url": geo_storage.public_url(record.object_key),
        "cards": cards.cards_for(recent),
        # Nothing was left out of a list that is simply the newest ones.
        "truncated": False,
        "pane_limit": settings.MAP_PANE_LIMIT,
        "pane_limit_mobile": settings.MAP_PANE_LIMIT_MOBILE,
    })


@require_GET
def explore_cards(request):
    """The pane, for the ids the browser picked."""
    blocked = _guard(request, "cards")
    if blocked is not None:
        return blocked

    wanted = parse_ids(request.GET.get("ids", ""))
    rows = _in_requested_order(published(*wanted), wanted) if wanted else []

    response = render(request, "snorkel_locations/_pane_cards.html", {
        "cards": cards.cards_for(rows),
        # Cosmetic only, so the browser is simply believed: it is the
        # only side that knows how many were in view before sampling.
        "truncated": request.GET.get("more") == "1",
    })
    # Safe to share: the response depends only on the ids in the URL,
    # and every location in it is published.
    response["Cache-Control"] = "public, max-age=300"
    return response


@require_GET
def explore_card(request, location_uuid):
    """One card, for the popup on a pin."""
    blocked = _guard(request, "card")
    if blocked is not None:
        return blocked

    try:
        parsed = uuid_lib.UUID(str(location_uuid))
    except (ValueError, AttributeError, TypeError):
        raise Http404("That is not a location reference.")

    location = published(parsed).first()
    if location is None:
        raise Http404("No published location matches this reference.")

    response = render(request, "snorkel_locations/_map_card.html",
                      {"card": cards.card_for(location)})
    response["Cache-Control"] = "public, max-age=300"
    return response
