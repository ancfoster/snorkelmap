# The map

The explore page at `/explore/` draws every published location from a
single file, and fetches the cards beside it in batches of twenty.

## How it fits together

    R2 (geo bucket)                     Django
    map/locations-<hash>.geojson        MapData row holds the key
          |                                   |
          | browser fetches once              | rendered into the page
          v                                   v
    Mapbox clusters it  ---- pan/zoom ---> explore_sample.js picks 20
                                                |
                                                | ids
                                                v
                                          /explore/cards/  -> HTML

The data file carries an id, a name and a position, and nothing else.
Everything a card shows comes from `/explore/cards/`, so the file stays
small enough for the browser to hold all of it. That is what makes
panning and zooming free: no request is made for pins at any point.

This stops being the right shape somewhere around five to ten thousand
locations, at which point the file becomes vector tiles served from
PostGIS with `ST_AsMVT` and the browser stops holding everything.
Nothing else about the page has to change when that day comes.

## Why the filename has a hash in it

A browser's cache cannot be purged. Cloudflare's can, with an API call,
but anyone who already downloaded the file keeps their copy until its
`max-age` runs out. So the file is written under a name derived from
its contents and served `public, max-age=31536000, immutable`: that
exact URL can never mean anything different, so it is safe to cache
forever, and new contents simply get a new name. Django renders the
current name into the page, so the next page load finds the new file
with nothing to purge and no TTL to wait out.

## What is in the bucket

    map/locations-<hash>.geojson     every published location, one file
    listing-maps/<uuid>.png          one Mapbox raster per listing

Two folders because they are different kinds of file. The data file is
named after its contents, so it is served immutable and cached forever;
a listing map is named after its location, so the same URL can be
redrawn and it is served with a week's cache instead. `--prune` on
rebuild_map_data only ever looks inside `map/`.

The listing maps are served exactly as Mapbox rendered them, straight
from the bucket, with no image service in front. Mapbox only renders
PNG, so the size of the file a visitor downloads is decided entirely by
the constants in static_map.py: WIDTH, HEIGHT and RETINA.

## Setting up the bucket

One bucket per environment, as with media.

    production    geo          behind geo.snorkelmap.com
    development   geo-dev      behind geo-dev.snorkelmap.com

Both are on the same R2 account as the media buckets, so
`R2_ENDPOINT_URL` is already correct and only these change:

    R2_GEO_BUCKET=geo-dev
    R2_GEO_ACCESS_KEY=...
    R2_GEO_SECRET_KEY=...
    R2_GEO_PUBLIC_BASE=https://geo-dev.snorkelmap.com

The token is scoped to this bucket alone. There is no fallback to the
static or media credentials, deliberately: signing is local arithmetic
with no permission check, so the wrong token produces a client that
works right up until every request is refused, and nothing in the log
says why.

### CORS

The browser fetches the data file from `geo.snorkelmap.com`, which is a
different origin from the site. Without a CORS policy on the bucket the
file will load perfectly in the address bar and fail silently in the
page. Set on the bucket:

    [
      {
        "AllowedOrigins": ["https://snorkelmap.com", "https://www.snorkelmap.com"],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedHeaders": ["*"],
        "MaxAgeSeconds": 3600
      }
    ]

Development needs its own, listing the local origin, `https://` included
if the local server has a certificate.

## Rebuilding

The file is rebuilt when a location is published, from
`tasks.publish_if_ready()`, so a contributor sees their own pin as soon
as their photograph passes verification. It is always rebuilt in full
from a fresh query, never patched, because a file assembled by applying
changes to an older one drifts.

That rebuild swallows its own failures. It runs after the listing is
already live, and a bucket being unreachable must not undo that. The
previous file keeps being served, which is stale rather than broken,
and it says so in the log:

    Map data upload failed; still serving map/locations-<hash>.geojson

Which is the only sign, so it is worth alerting on. To fix it:

    manage.py rebuild_map_data            rebuild if the contents changed
    manage.py rebuild_map_data --force    upload regardless
    manage.py rebuild_map_data --prune    delete superseded files

Run it once on a fresh install, or the map has no file to fetch.

Hiding or removing a location does not rebuild anything yet. When that
is added it goes in the same place.

## The two fragments

`/explore/cards/?ids=...` returns the pane, and
`/explore/card/<uuid>/` returns the card that opens over a pin. Both
return HTML rather than JSON, so the thumbnail URL, the fallback image
and the escaping of a location's name all stay in Python rather than
being written a second time in JavaScript. Both sit outside `/api/v1/`
for the same reason: an HTML fragment is not an API response.

The map is public, so neither can be behind a session. What protects
them is that neither can be made expensive: the pane fetches at most
twenty rows by id and the popup one, and there is nothing in either
request an attacker can vary to increase the cost. On top of that:

- requests the browser reports as cross site are refused, which stops
  another website using these in a page. It does nothing against curl,
  which sends no such header;
- a fixed window rate limit per IP, 120 a minute. Note that with no
  `CACHES` configured Django uses a per-process local memory cache, so
  the limit is really per worker until a shared cache is set up.
  Cloudflare does the real rate limiting in front of this;
- `Cache-Control: public, max-age=300`, so repeats are absorbed at the
  edge rather than reaching Django at all.

## Choosing the twenty

`static/js/explore_sample.js`, checked by `sample_check.js`.

Taking the twenty nearest the middle of the screen would be simpler and
worse: pan over a busy bay and the pane fills with it while everything
else on screen goes unmentioned. Instead the viewport is cut into six
cells, three across and two down in landscape and the other way round
in portrait. Empty cells are ignored. The rest are given a share of the
twenty in proportion to how much they hold, by largest remainder, with
a floor of one so a lone location in a corner still appears, and any
share a cell cannot fill is handed back to the cells that can.

Within a cell the picks are the ones nearest that cell's centre, which
makes the whole thing a function of where the map is. That matters:
the pane redraws on every `moveend`, so anything random here would
reshuffle the list on every frame of a drag. A nudge of a few pixels
keeps at least eighteen of the twenty.

Twelve rather than twenty on a phone, to spend less of someone's mobile
data on photographs they have to scroll to see.
