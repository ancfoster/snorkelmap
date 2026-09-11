// Checks the Worker without deploying it.
//
// The signature is the part worth testing: it is produced here with
// WebCrypto and checked in Django with hmac, and if the two ever
// disagree every upload silently stops being confirmed. So the digest
// this file produces is compared against one produced by Python.
import worker from './src/index.js';
import { execFileSync } from 'node:child_process';

const results = [];
const check = (label, cond, detail) => results.push({ label, pass: !!cond, detail: detail || '' });

const SECRET = 'test-secret-value';
let sent = null;

globalThis.fetch = async (url, init) => {
  sent = { url, init };
  return new Response('{"received":1,"accepted":1}', { status: 200 });
};

function makeBatch(bodies) {
  let acked = false, retried = null;
  return {
    messages: bodies.map(body => ({ body })),
    ackAll() { acked = true; },
    retryAll(opts) { retried = opts || {}; },
    get acked() { return acked; },
    get retried() { return retried; },
  };
}

const env = {
  WEBHOOK_SECRET: SECRET,
  DJANGO_WEBHOOK_URL: 'https://example.invalid/api/v1/media/events',
};

const putEvent = key => ({
  account: 'acc', bucket: 'snorkelmap-media',
  object: { key, size: 402301, eTag: 'abc' },
  action: 'PutObject', eventTime: '2026-09-10T12:00:00Z',
});

// ── A normal batch ────────────────────────────────────────────────────
let batch = makeBatch([
  putEvent('media/loc-1/photo-1.jpg'),
  putEvent('media/loc-1/photo-2.heic'),
]);
await worker.queue(batch, env);

check('a batch is delivered in one request', sent !== null);
check('the batch is acknowledged', batch.acked);

const body = sent.init.body;
const parsed = JSON.parse(body);
check('both events are carried', parsed.events.length === 2, JSON.stringify(parsed.events));
check('the key survives normalising',
  parsed.events[0].key === 'media/loc-1/photo-1.jpg', parsed.events[0].key);
check('the size is carried', parsed.events[0].size === 402301);

const header = sent.init.headers['X-SnorkelMap-Signature'];
const [, timestamp, signature] = header.match(/^t=(\d+),v1=([0-9a-f]{64})$/) || [];
check('the signature header is well formed', !!signature, header);

// ── The signature agrees with Python ─────────────────────────────────
const fromPython = execFileSync('python3', ['-c', `
import hmac, hashlib, sys
secret, timestamp = sys.argv[1].encode(), sys.argv[2]
body = sys.stdin.buffer.read()
print(hmac.new(secret, f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest())
`, SECRET, timestamp], { input: Buffer.from(body, 'utf8') }).toString().trim();

check('WebCrypto and Python produce the same digest',
  signature === fromPython, `${signature}\n     vs ${fromPython}`);

// ── Events that should be ignored ────────────────────────────────────
sent = null;
batch = makeBatch([
  { object: { key: 'media/loc-1/photo.jpg' }, action: 'DeleteObject' },
  { object: { key: 'static/css/main.css' }, action: 'PutObject' },
  { nonsense: true },
]);
await worker.queue(batch, env);
check('deletes, other prefixes and junk are dropped', sent === null);
check('an empty batch is acknowledged, not retried',
  batch.acked && batch.retried === null);

// ── Failure handling ─────────────────────────────────────────────────
globalThis.fetch = async () => new Response('nope', { status: 503 });
batch = makeBatch([putEvent('media/loc-2/photo.jpg')]);
await worker.queue(batch, env);
check('a 503 is retried', batch.retried !== null && !batch.acked);

globalThis.fetch = async () => new Response('bad signature', { status: 403 });
batch = makeBatch([putEvent('media/loc-2/photo.jpg')]);
await worker.queue(batch, env);
check('a 403 is dropped rather than circling the queue',
  batch.acked && batch.retried === null);

globalThis.fetch = async () => { throw new Error('network down'); };
batch = makeBatch([putEvent('media/loc-2/photo.jpg')]);
await worker.queue(batch, env);
check('a thrown request is retried', batch.retried !== null);

let failed = 0;
results.forEach(r => {
  if (!r.pass) failed++;
  console.info(`${r.pass ? 'PASS' : 'FAIL'}  ${r.label}${r.pass ? '' : '   ->  ' + r.detail}`);
});
console.info(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
