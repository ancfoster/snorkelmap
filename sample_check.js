/* Checks for the pane's sampling.

   This is where the bugs will be. The allocation has rounding in it,
   the grid has an edge on every side, and the whole thing has to give
   the same answer twice for a map that barely moved, or the pane
   flickers as you drag.

   Run with: node sample_check.js
*/
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(
  path.join(__dirname, 'static/js/explore_sample.js'), 'utf8');
(0, eval)(src);
const { sampleViewport, _allocate, _inside, _normalise } = globalThis.SMSample;

const results = [];
function check(label, condition, detail = '') {
  results.push([label, !!condition, detail]);
}

const BOX = { west: -4, south: 54, east: -2, north: 56 };

function grid(count, west, south, spanLng, spanLat, prefix = 'p') {
  // A deterministic spread, so a failure is reproducible.
  const out = [];
  for (let i = 0; i < count; i++) {
    out.push({
      uuid: `${prefix}-${i}`,
      lng: west + ((i * 37) % 100) / 100 * spanLng,
      lat: south + ((i * 53) % 100) / 100 * spanLat,
    });
  }
  return out;
}

// ── Allocation ───────────────────────────────────────────────────────

check('every place is handed out',
  _allocate([50, 20, 10], 20).reduce((a, b) => a + b, 0) === 20,
  JSON.stringify(_allocate([50, 20, 10], 20)));

check('a cell with one location still gets a place',
  _allocate([300, 1], 20)[1] === 1,
  JSON.stringify(_allocate([300, 1], 20)));

check('the busiest cell gets the most',
  (() => { const s = _allocate([300, 1], 20); return s[0] === 19; })(),
  JSON.stringify(_allocate([300, 1], 20)));

check('no cell is given more than it holds',
  _allocate([2, 2, 40], 20).every((n, i) => n <= [2, 2, 40][i]),
  JSON.stringify(_allocate([2, 2, 40], 20)));

check('a cell that cannot take its share passes it on',
  _allocate([1, 1, 1, 40], 20).reduce((a, b) => a + b, 0) === 20,
  JSON.stringify(_allocate([1, 1, 1, 40], 20)));

check('everything fits when the budget exceeds the total',
  JSON.stringify(_allocate([2, 3], 20)) === JSON.stringify([2, 3]),
  JSON.stringify(_allocate([2, 3], 20)));

check('more cells than places hands out exactly the budget',
  _allocate([5, 4, 3, 2, 1], 3).reduce((a, b) => a + b, 0) === 3,
  JSON.stringify(_allocate([5, 4, 3, 2, 1], 3)));

check('more cells than places favours the fullest',
  JSON.stringify(_allocate([5, 4, 3, 2, 1], 3)) === JSON.stringify([1, 1, 1, 0, 0]),
  JSON.stringify(_allocate([5, 4, 3, 2, 1], 3)));

check('the allocation always terminates',
  _allocate([1, 1], 20).reduce((a, b) => a + b, 0) === 2,
  JSON.stringify(_allocate([1, 1], 20)));

// ── Bounds ───────────────────────────────────────────────────────────

check('a point inside is inside',
  _inside({ lng: -3, lat: 55 }, _normalise(BOX)));
check('a point outside is outside',
  !_inside({ lng: 5, lat: 55 }, _normalise(BOX)));
check('the edge counts as inside',
  _inside({ lng: -4, lat: 54 }, _normalise(BOX)));

// Crossing the antimeridian: Mapbox reports west greater than east.
const dateline = { west: 170, south: -10, east: -170, north: 10 };
check('a viewport across the antimeridian is normalised',
  _normalise(dateline).east === 190 && _normalise(dateline).wrapped);
check('a point east of the seam is in view',
  _inside({ lng: 175, lat: 0 }, _normalise(dateline)));
check('a point west of the seam is in view',
  _inside({ lng: -175, lat: 0 }, _normalise(dateline)));
check('a point nowhere near is not in view',
  !_inside({ lng: 0, lat: 0 }, _normalise(dateline)));

// ── Sampling ─────────────────────────────────────────────────────────

const many = grid(200, -4, 54, 2, 2);

let r = sampleViewport(many, BOX, { limit: 20 });
check('the limit is respected', r.items.length === 20, String(r.items.length));
check('the total counts everything in view', r.total === 200, String(r.total));
check('truncation is reported', r.truncated === true);
check('no location appears twice',
  new Set(r.items.map(i => i.uuid)).size === r.items.length);

const mobile = sampleViewport(many, BOX, { limit: 12, landscape: false });
check('a phone gets twelve', mobile.items.length === 12, String(mobile.items.length));

const few = grid(8, -4, 54, 2, 2);
r = sampleViewport(few, BOX, { limit: 20 });
check('fewer than the limit are all returned', r.items.length === 8);
check('and nothing is reported as left out', r.truncated === false);

r = sampleViewport(grid(20, -4, 54, 2, 2), BOX, { limit: 20 });
check('exactly the limit is not truncated',
  r.items.length === 20 && r.truncated === false);

r = sampleViewport([], BOX, { limit: 20 });
check('an empty map returns nothing',
  r.items.length === 0 && r.total === 0 && r.truncated === false);

// Everything crammed into one corner: the cells with nothing in them
// must not consume places.
const corner = grid(60, -3.95, 55.9, 0.04, 0.04, 'corner');
r = sampleViewport(corner, BOX, { limit: 20 });
check('locations all in one corner still fill the pane',
  r.items.length === 20, String(r.items.length));
check('and they all come from that corner',
  r.items.every(i => i.lng < -3.8 && i.lat > 55.8));

// One lone location far from a dense cluster. It must survive.
const lopsided = grid(300, -3.9, 54.1, 0.05, 0.05, 'dense')
  .concat([{ uuid: 'lonely', lng: -2.05, lat: 55.95 }]);
r = sampleViewport(lopsided, BOX, { limit: 20 });
check('a lone location in an empty cell is not drowned out',
  r.items.some(i => i.uuid === 'lonely'),
  r.items.map(i => i.uuid).join(','));

// ── Stability ────────────────────────────────────────────────────────
//
// The pane redraws on every moveend. If a tiny pan reshuffles it, the
// list flickers while the map is being dragged.

const nudged = { west: BOX.west + 0.0001, south: BOX.south + 0.0001,
                 east: BOX.east + 0.0001, north: BOX.north + 0.0001 };
const before = sampleViewport(many, BOX, { limit: 20 }).items.map(i => i.uuid);
const after = sampleViewport(many, nudged, { limit: 20 }).items.map(i => i.uuid);
const kept = after.filter(u => before.includes(u)).length;
check('a tiny pan keeps almost the same list', kept >= 18,
  `${kept}/20 kept`);

const twice = sampleViewport(many, BOX, { limit: 20 }).items.map(i => i.uuid);
check('the same viewport gives the same answer',
  JSON.stringify(before) === JSON.stringify(twice));

check('the input array is not reordered',
  many[0].uuid === 'p-0' && many[199].uuid === 'p-199');

// ── Ordering ─────────────────────────────────────────────────────────

r = sampleViewport(many, BOX, { limit: 20 });
const midLng = (BOX.west + BOX.east) / 2;
const midLat = (BOX.south + BOX.north) / 2;
const cos = Math.cos(midLat * Math.PI / 180);
const distances = r.items.map(i =>
  Math.pow((i.lng - midLng) * cos, 2) + Math.pow(i.lat - midLat, 2));
check('the list runs outwards from the middle of the screen',
  distances.every((d, i) => i === 0 || d >= distances[i - 1]),
  JSON.stringify(distances.map(d => d.toFixed(4))));

let failed = 0;
for (const [label, passed, detail] of results) {
  if (!passed) failed++;
  console.log(`${passed ? 'PASS' : 'FAIL'}  ${label}` +
              (passed ? '' : '   ->  ' + detail));
}
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
