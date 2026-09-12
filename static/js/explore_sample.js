/* ══════════════════════════════════════════════════════════════════════
   CHOOSING WHICH LOCATIONS THE PANE SHOWS

   The browser holds every published location, so working out what is
   on screen is arithmetic rather than a request. What it cannot do is
   show all of them: a pane is twenty cards on a desktop and twelve on
   a phone, and a busy stretch of coast can have hundreds in view.

   Taking the twenty nearest the middle of the screen would be simpler,
   and wrong: pan over a marina and the pane fills with one bay while
   everything else on screen goes unmentioned. So the viewport is cut
   into six cells, and each cell that has anything in it is represented
   in proportion to how much it has, with a floor of one so a single
   location alone in a corner still appears.

   Within a cell the picks are the ones nearest that cell's centre.
   That matters more than it sounds: it makes the result a function of
   where the map is, so nudging it a few pixels returns almost the same
   list. Anything random here would reshuffle the pane on every frame
   of a drag and read as broken.

   No Mapbox and no DOM in this file, so it can be run and checked
   outside a browser.
   ══════════════════════════════════════════════════════════════════ */
(function (global) {
  'use strict';

  var CELLS_ACROSS_LANDSCAPE = 3;
  var CELLS_DOWN_LANDSCAPE = 2;

  /* Longitude degrees get narrower towards the poles, so comparing raw
     degrees would stretch distances east to west near the equator and
     squash them near Scotland. One cosine fixes it well enough for
     ordering, which is all this is for: nothing here needs a real
     distance, only a consistent one. */
  function distanceSq(aLng, aLat, bLng, bLat, cosLat) {
    var dx = (aLng - bLng) * cosLat;
    var dy = aLat - bLat;
    return dx * dx + dy * dy;
  }

  /* Mapbox reports a viewport spanning the antimeridian with its west
     edge greater than its east. Shifting the east edge and everything
     west of the seam into a continuous range makes the rest of the
     arithmetic ordinary. */
  function normalise(bounds) {
    var west = bounds.west;
    var east = bounds.east;
    var wrapped = east < west;
    if (wrapped) east += 360;
    return { west: west, east: east, south: bounds.south,
             north: bounds.north, wrapped: wrapped };
  }

  function unwrapLng(lng, box) {
    if (box.wrapped && lng < box.west) return lng + 360;
    return lng;
  }

  function inside(item, box) {
    var lng = unwrapLng(item.lng, box);
    return lng >= box.west && lng <= box.east
        && item.lat >= box.south && item.lat <= box.north;
  }

  /* Largest remainder, with two corrections that matter in practice.

     Every non-empty cell is given one first, so a cell holding a single
     location is never rounded out of existence. And a cell can be
     allocated more than it holds when the shares are lumpy, so the
     excess is handed back and offered to the cells that still have
     room, repeatedly, until either the budget is spent or nothing can
     take any more. */
  function allocate(counts, budget) {
    var cells = counts.length;
    var share = new Array(cells);
    var i;

    for (i = 0; i < cells; i++) share[i] = 0;

    /* More cells with something in them than places in the pane. Only
       reachable with a very small limit, but it must not hand out more
       than the budget, so the fullest cells win. */
    if (cells > budget) {
      var order = [];
      for (i = 0; i < cells; i++) order.push(i);
      order.sort(function (a, b) { return counts[b] - counts[a] || a - b; });
      for (i = 0; i < budget; i++) share[order[i]] = 1;
      return share;
    }

    for (i = 0; i < cells; i++) share[i] = 1;
    var remaining = budget - cells;
    var total = 0;
    for (i = 0; i < cells; i++) total += counts[i] - 1;

    while (remaining > 0 && total > 0) {
      var spare = [];
      for (i = 0; i < cells; i++) {
        spare.push(Math.max(0, counts[i] - share[i]));
      }
      var pool = 0;
      for (i = 0; i < cells; i++) pool += spare[i];
      if (pool === 0) break;

      var handed = 0;
      var remainders = [];
      for (i = 0; i < cells; i++) {
        if (spare[i] === 0) continue;
        var exact = remaining * spare[i] / pool;
        var whole = Math.min(Math.floor(exact), spare[i]);
        share[i] += whole;
        handed += whole;
        remainders.push({ cell: i, fraction: exact - whole });
      }

      var left = remaining - handed;
      if (left > 0) {
        remainders.sort(function (a, b) {
          return b.fraction - a.fraction || a.cell - b.cell;
        });
        for (i = 0; i < remainders.length && left > 0; i++) {
          var cell = remainders[i].cell;
          if (share[cell] < counts[cell]) { share[cell] += 1; left -= 1; }
        }
      }

      if (left === remaining) break;   // nothing moved, stop rather than spin
      remaining = left;
    }

    return share;
  }

  /* items: [{ uuid, lng, lat, ... }]
     bounds: { west, south, east, north }
     options: { limit, landscape } */
  function sampleViewport(items, bounds, options) {
    options = options || {};
    var limit = Math.max(1, options.limit || 20);
    var landscape = options.landscape !== false;

    var box = normalise(bounds);
    var visible = [];
    var i;
    for (i = 0; i < (items || []).length; i++) {
      if (inside(items[i], box)) visible.push(items[i]);
    }

    var midLat = (box.south + box.north) / 2;
    var midLng = (box.west + box.east) / 2;
    var cosLat = Math.cos(midLat * Math.PI / 180) || 1;

    function byDistanceFromCentre(a, b) {
      return distanceSq(unwrapLng(a.lng, box), a.lat, midLng, midLat, cosLat)
           - distanceSq(unwrapLng(b.lng, box), b.lat, midLng, midLat, cosLat);
    }

    if (visible.length <= limit) {
      return { items: visible.slice().sort(byDistanceFromCentre),
               total: visible.length, truncated: false };
    }

    var across = landscape ? CELLS_ACROSS_LANDSCAPE : CELLS_DOWN_LANDSCAPE;
    var down = landscape ? CELLS_DOWN_LANDSCAPE : CELLS_ACROSS_LANDSCAPE;
    var cellWidth = (box.east - box.west) / across;
    var cellHeight = (box.north - box.south) / down;

    var buckets = {};
    for (i = 0; i < visible.length; i++) {
      var item = visible[i];
      var lng = unwrapLng(item.lng, box);
      var col = cellWidth > 0
        ? Math.min(across - 1, Math.floor((lng - box.west) / cellWidth)) : 0;
      var row = cellHeight > 0
        ? Math.min(down - 1, Math.floor((item.lat - box.south) / cellHeight)) : 0;
      var key = row * across + col;
      if (!buckets[key]) buckets[key] = [];
      buckets[key].push(item);
    }

    var keys = Object.keys(buckets).map(Number).sort(function (a, b) {
      return a - b;
    });
    var counts = keys.map(function (key) { return buckets[key].length; });
    var share = allocate(counts, limit);

    var picked = [];
    for (i = 0; i < keys.length; i++) {
      var take = share[i];
      if (take <= 0) continue;
      var key2 = keys[i];
      var cellCol = key2 % across;
      var cellRow = Math.floor(key2 / across);
      var centreLng = box.west + (cellCol + 0.5) * cellWidth;
      var centreLat = box.south + (cellRow + 0.5) * cellHeight;

      var members = buckets[key2].slice().sort(function (a, b) {
        return distanceSq(unwrapLng(a.lng, box), a.lat, centreLng, centreLat, cosLat)
             - distanceSq(unwrapLng(b.lng, box), b.lat, centreLng, centreLat, cosLat);
      });
      picked = picked.concat(members.slice(0, take));
    }

    picked.sort(byDistanceFromCentre);
    return { items: picked, total: visible.length,
             truncated: picked.length < visible.length };
  }

  global.SMSample = {
    sampleViewport: sampleViewport,
    // Exported for the test suite.
    _allocate: allocate,
    _normalise: normalise,
    _inside: inside,
  };
}(typeof window !== 'undefined' ? window : globalThis));
