/**
 * SnorkelMap media event relay.
 *
 * R2 raises an event when an object is written. Those events go into a
 * Cloudflare Queue, and this Worker reads the queue and tells Django.
 *
 * It handles names and sizes only. It never reads, decodes, resizes or
 * even fetches an image, and that restraint is the whole design: a
 * Worker gets 128MB of memory, while a 24 megapixel photograph is over
 * 70MB once decoded and comfortably more than that as RGBA. A Worker
 * that opened one would fall over on exactly the photographs people
 * care most about. Everything to do with pixels happens either in the
 * browser before upload or in Cloudflare's own image service on
 * request, and nothing in between needs to look inside the file.
 *
 * Deployment lives in wrangler.toml. The shared secret is set with
 *
 *     wrangler secret put WEBHOOK_SECRET
 *
 * and must match R2_MEDIA_WEBHOOK_SECRET in the matching Django
 * environment. Development and production have their own bucket,
 * queue, Worker and secret, so a test upload can never announce itself
 * to the live site.
 */

const KEY_PREFIX = 'media/';

// The actions that mean "an object now exists". R2 also raises delete
// events, which are not interesting here: Django removes its own row
// when it deletes an object, so an event about that would only ask it
// to verify something it has already dealt with.
const CREATE_ACTIONS = new Set([
  'PutObject',
  'CompleteMultipartUpload',
  'CopyObject',
]);

/**
 * Cloudflare's event shape flattened into the one Django accepts.
 *
 * Normalising here rather than in Django is deliberate. If Cloudflare
 * changes the event format, redeploying a Worker takes seconds and
 * needs no downtime on the site.
 */
function normalise(body) {
  if (!body || typeof body !== 'object') return null;

  const object = body.object || {};
  const key = object.key || body.key;
  const action = body.action || 'PutObject';

  if (!key || typeof key !== 'string') return null;
  if (!CREATE_ACTIONS.has(action)) return null;
  // Anything outside the media prefix belongs to something else in the
  // bucket and is none of this Worker's business.
  if (!key.startsWith(KEY_PREFIX)) return null;

  return { key, size: object.size ?? body.size ?? 0, action };
}

function toHex(buffer) {
  return [...new Uint8Array(buffer)]
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * HMAC-SHA256 over "<timestamp>.<body>".
 *
 * The timestamp is inside the signed material rather than beside it,
 * so a captured request cannot be replayed later: alter the timestamp
 * and the signature stops matching, leave it and Django refuses the
 * request as stale.
 */
async function sign(secret, timestamp, body) {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const signature = await crypto.subtle.sign(
    'HMAC',
    key,
    new TextEncoder().encode(`${timestamp}.${body}`),
  );
  return toHex(signature);
}

async function deliver(events, env) {
  const body = JSON.stringify({ events });
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const signature = await sign(env.WEBHOOK_SECRET, timestamp, body);

  return fetch(env.DJANGO_WEBHOOK_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-SnorkelMap-Signature': `t=${timestamp},v1=${signature}`,
      'User-Agent': 'snorkelmap-media-events',
    },
    body,
  });
}

export default {
  /**
   * One batch of queue messages.
   *
   * The whole batch is delivered in a single signed request, so twenty
   * photographs uploaded together cost Django one request rather than
   * twenty. Delivery is at least once and may arrive out of order,
   * which Django's handler is written to tolerate.
   */
  async queue(batch, env) {
    const events = batch.messages
      .map((message) => normalise(message.body))
      .filter(Boolean);

    // Nothing here that Django needs to hear about. Acknowledging
    // rather than retrying stops an ignorable event circling the queue
    // until it reaches the dead letter queue.
    if (events.length === 0) {
      batch.ackAll();
      return;
    }

    let response;
    try {
      response = await deliver(events, env);
    } catch (error) {
      console.error('media relay: delivery threw', error);
      batch.retryAll({ delaySeconds: 30 });
      return;
    }

    if (response.ok) {
      batch.ackAll();
      return;
    }

    // A rejected signature or a malformed body will be rejected again
    // no matter how many times it is sent, so those are dropped with a
    // loud log rather than retried until the dead letter queue. Only a
    // server side failure is worth coming back for.
    if (response.status >= 400 && response.status < 500) {
      console.error(
        `media relay: Django refused the batch with ${response.status}`,
        await response.text().catch(() => ''),
      );
      batch.ackAll();
      return;
    }

    console.warn(`media relay: Django returned ${response.status}, retrying`);
    batch.retryAll({ delaySeconds: 30 });
  },

  /**
   * A plain GET for uptime checks. No secrets, no state, and it says
   * nothing about the queue.
   */
  async fetch() {
    return new Response('snorkelmap media relay', {
      headers: { 'Content-Type': 'text/plain' },
    });
  },
};
