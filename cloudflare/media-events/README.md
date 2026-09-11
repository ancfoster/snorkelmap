# Media event relay

A Worker that reads R2 upload events off a queue and tells Django about
them. It handles object names and sizes only, never image data.

```
browser ──upload──> R2 bucket ──event──> Queue ──> this Worker ──signed POST──> Django
```

Django then verifies the object it already has a row for, and the
listing goes live once its required photograph passes.

## Why a Worker at all

R2 event notifications can only be delivered to a queue. Something has
to take them out of the queue, and the two options are an HTTP pull
consumer or a Worker. A Worker is simpler to operate here because
nothing has to poll.

The one hard constraint is memory: a Worker gets 128MB, and a 24
megapixel photograph is over 70MB decoded. So this Worker never touches
the image. Resizing happens in Cloudflare's image service on request,
and validation happens either in the browser or in Django against a
ranged read of a few bytes.

## Setting it up

Each environment gets its own bucket, queue, Worker and secret. They
are named apart on purpose, so a development upload cannot announce
itself to the live site.

1. **Buckets**

   ```
   wrangler r2 bucket create snorkelmap-media
   wrangler r2 bucket create snorkelmap-media-dev
   ```

   Put a lifecycle rule on the dev bucket to expire objects after 30
   days, so test uploads clean up after themselves.

2. **Queues**

   ```
   wrangler queues create snorkelmap-media-events
   wrangler queues create snorkelmap-media-events-dlq
   ```

   And the `-dev` pair if you are wiring up development.

3. **Event notification**, per bucket, for object creation only:

   ```
   wrangler r2 bucket notification create snorkelmap-media \
     --event-type object-create --queue snorkelmap-media-events \
     --prefix media/
   ```

4. **Secret.** Must match `R2_MEDIA_WEBHOOK_SECRET` in the Django
   environment this Worker posts to.

   ```
   wrangler secret put WEBHOOK_SECRET
   ```

5. **Custom domain** on the bucket, and the same value set as
   `R2_MEDIA_PUBLIC_BASE` in Django. Image Transformations are served
   from this host, so `/cdn-cgi/image/` has to be enabled on the zone.

6. **Deploy**

   ```
   npm run deploy         # production
   npm run deploy:dev     # development, needs a tunnel
   ```

## Development without a tunnel

Cloudflare cannot reach a laptop, so rather than tunnelling, use the
Django side simulator, which builds and signs exactly the request this
Worker sends:

```
python manage.py simulate_media_event media/<location-uuid>/<media-uuid>.jpg
python manage.py simulate_media_event <media-uuid> --verify-only
```

## Checks

```
npm run check
```

Runs the Worker against a fake queue and a fake Django. The check worth
knowing about compares the signature produced here by WebCrypto against
one produced by Python's `hmac`, because if those two ever drift apart
every upload quietly stops being confirmed and nothing else would show
it.

## Signature format

```
X-SnorkelMap-Signature: t=<unix seconds>,v1=<hex hmac sha256>
```

The digest is taken over `<timestamp>.<raw body>`. Django refuses
anything more than five minutes old, so a captured request cannot be
replayed: change the timestamp and the digest no longer matches, keep
it and the age check turns it away.
