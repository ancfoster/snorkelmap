# The media pipeline: setup and operation

How a photograph gets from somebody's phone to a published listing,
what has to be configured for that to work, and how to exercise the
whole thing on a laptop.

```
browser  ──1── POST /api/v1/locations/submissions      (listing + manifest)
         ──2── PUT/POST direct to R2                   (the actual files)
R2       ──3── event ──> Queue ──> Worker
Worker   ──4── signed POST /api/v1/media/events
Django   ──5── verifies the stored object, publishes the listing
```

Step 1 needs a session. Step 2 needs a signature that only step 1 hands
out. Steps 3 to 5 need no browser at all, which is why closing the tab
mid-upload cannot strand a listing.

---

## 1. Environment variables

Both environments need these. Nothing has a usable default, and the
code degrades quietly rather than crashing when one is missing, so
check them rather than assuming.

| Variable | What it is |
|---|---|
| `R2_ENDPOINT_URL` | `https://<account id>.r2.cloudflarestorage.com` |
| `R2_ACCESS_KEY` / `R2_SECRET_KEY` | R2 API token, already used for static files |
| `R2_MEDIA_ACCESS_KEY` / `R2_MEDIA_SECRET_KEY` | Optional. A token scoped to the media bucket alone. Falls back to the pair above |
| `R2_MEDIA_BUCKET` | `snorkelmap-media` or `snorkelmap-media-dev` |
| `R2_MEDIA_PUBLIC_BASE` | `https://media.snorkelmap.com`, the custom domain on the bucket |
| `R2_MEDIA_WEBHOOK_SECRET` | Long random string. Must match the Worker's `WEBHOOK_SECRET` |
| `W3W_API_KEY` | Optional. Without it, three word addresses are simply not looked up |
| `R2_MEDIA_UPLOAD_EXPIRY` | Optional, seconds. Default 900 |
| `R2_MEDIA_UPLOAD_METHOD` | Optional, `post` or `put`. Default `post` |

Generate the secret with something like:

```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`local.py` refuses to start unless `R2_MEDIA_BUCKET` ends in `-dev` or
`-local`, and `production.py` refuses if it does. That guard exists
because copying a `.env` from the server is easy to do and the first
sign of it would be test photographs on the live site.

---

## 2. R2 buckets

```
wrangler r2 bucket create snorkelmap-media
wrangler r2 bucket create snorkelmap-media-dev
```

**Lifecycle rule on the dev bucket.** Expire objects after 30 days so
test uploads clean up after themselves.

**Custom domain.** Attach one to each bucket (`media.snorkelmap.com`
and `media-dev.snorkelmap.com`) and set it as `R2_MEDIA_PUBLIC_BASE`.
Image Transformations are served from the same host, so the zone needs
`/cdn-cgi/image/` enabled. The site never links to the
`r2.cloudflarestorage.com` endpoint.

**CORS.** This one is not optional and it is the thing most likely to
be missed, because everything works right up until the first upload and
then fails in the browser with an opaque network error. The browser
uploads straight to R2 from your origin, so R2 has to allow it:

```json
[
  {
    "AllowedOrigins": [
      "https://snorkelmap.com",
      "https://www.snorkelmap.com"
    ],
    "AllowedMethods": ["PUT", "POST"],
    "AllowedHeaders": ["content-type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

For the dev bucket use the local origins instead:

```json
["http://snorkelmap.local:8000", "http://127.0.0.1:8000", "http://localhost:8000"]
```

**API token.** R2 object read and write, scoped to the media bucket if
you are using the separate `R2_MEDIA_*` credentials. Object read alone
is not enough: the code deletes objects that fail verification.

---

## 3. Queues and the event notification

```
wrangler queues create snorkelmap-media-events
wrangler queues create snorkelmap-media-events-dlq
wrangler queues create snorkelmap-media-events-dev
wrangler queues create snorkelmap-media-events-dev-dlq
```

Then tell each bucket to raise events into its queue, for object
creation only and only under the `media/` prefix:

```
wrangler r2 bucket notification create snorkelmap-media \
  --event-type object-create \
  --queue snorkelmap-media-events \
  --prefix media/

wrangler r2 bucket notification create snorkelmap-media-dev \
  --event-type object-create \
  --queue snorkelmap-media-events-dev \
  --prefix media/
```

---

## 4. The Worker

Lives in `cloudflare/media-events/`.

```
cd cloudflare/media-events
npm run check                      # 12 checks, no deployment needed
wrangler secret put WEBHOOK_SECRET # same value as R2_MEDIA_WEBHOOK_SECRET
npm run deploy                     # production
```

`npm run check` is worth running before every deploy. It compares the
signature the Worker produces with WebCrypto against one produced by
Python's `hmac` over the same bytes. If those two ever disagree, every
upload silently stops being confirmed and nothing else in the system
would show it.

Confirm it is consuming: `wrangler tail snorkelmap-media-events`, then
upload a photo through the site.

### The dev Worker

Cloudflare cannot reach a laptop, so the dev Worker needs a tunnel:

```
cloudflared tunnel --url http://127.0.0.1:8000
```

Put the resulting hostname into `[env.dev.vars] DJANGO_WEBHOOK_URL` in
`wrangler.toml`, then:

```
wrangler secret put WEBHOOK_SECRET --env dev
npm run deploy:dev
```

If you would rather not run a tunnel, skip the dev Worker entirely and
use the simulator in the next section. It produces the identical signed
request.

---

## 5. Testing locally

### Without any Cloudflare setup at all

Every client side check runs with no bucket, no keys and no network:
format sniffing, the 800 pixel minimum, size limits, capture date, GPS,
and the HEIC placeholder. So the form is fully testable before any of
the above exists.

```
python manage.py migrate
python manage.py runserver
```

Sign in, go to `/add-location/`, and try the awkward files: a GIF, an
SVG, something small, a `.txt` renamed to `.jpg`, and a HEIC straight
off an iPhone. Each should be refused by name, or accepted with its
real dimensions shown on the tile.

Publishing will fail at the upload step, which is expected without a
bucket. The listing is still created as a draft.

### With the dev bucket

Set the `R2_MEDIA_*` variables, apply the CORS rule, and publish. The
files should appear in the bucket under
`media/<location uuid>/<media uuid>.<ext>`, and the location sits at
`DRAFT` because nothing has confirmed the upload yet.

Then stand in for Cloudflare:

```
# The full path: signed HTTP request through the real endpoint
python manage.py simulate_media_event media/<location-uuid>/<media-uuid>.jpg

# The quick path: run the checks directly, no HTTP
python manage.py simulate_media_event <media-uuid> --verify-only
```

Either one should report the media as Active, and the location should
flip to Published. If it reports Rejected, the reason is printed and
also stored on the row.

### The automated checks

```
python manage.py makemigrations snorkel_locations --check --dry-run
cd cloudflare/media-events && npm run check
```

The browser and node suites for the create flow live outside the repo
at present. Ask if you want them committed.

---

## 6. Things that are deliberately unfinished

**Verification runs inline.** `enqueue_verification()` in `tasks.py`
calls straight through rather than queueing, so the webhook request
stays open for a HEAD, a ranged read and one metadata call. Fine at
this scale, and it becomes a one line change once a task backend is
chosen. `django.tasks` ships only an immediate and a dummy backend, so
a real queue means adding `django-tasks-db` and running its `db_worker`
alongside the site.

**No cleanup of abandoned uploads.** If the Worker is down when a file
lands, its row stays `PENDING` and the object stays in the bucket
unverified. A periodic sweep deleting objects for rows that have been
`PENDING` for more than a few hours would close that. See the security
note below for why it matters.

**Presigned POST is unconfirmed against R2.** POST is preferred because
it carries a `content-length-range` condition the bucket enforces. If
R2 declines POST object uploads on this account, set
`R2_MEDIA_UPLOAD_METHOD=put`; the browser handles both and the size is
then caught during verification instead.

**The old `publish` view** in `views.py` is unrouted dead code and
should be deleted before submission, so there is only one path into
creating a location.
