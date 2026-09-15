// explore sample - picks which locations the pane lists
(function (global) {
  'use strict';

  var CELLS_ACROSS_LANDSCAPE = 3;
  var CELLS_DOWN_LANDSCAPE = 2;

  // scale - longitude narrows towards the poles, so correct for it
  function distanceSq(aLng, aLat, bLng, bLat, cosLat) {
    var dx = (aLng - bLng) * cosLat;
    var dy = aLat - bLat;
    return dx * dx + dy * dy;
  }

  // antimeridian - mapbox reports west greater than east, so shift
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

  // largest remainder - share the places out across the grid cells
  function allocate(counts, budget) {
    var cells = counts.length;
    var share = new Array(cells);
    var i;

    for (i = 0; i < cells; i++) share[i] = 0;

    // more cells than places - only with a very small limit
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

  // sample - takes items and bounds, returns what the pane shows
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
    // exported for the test suite
    _allocate: allocate,
    _normalise: normalise,
    _inside: inside,
  };
}(typeof window !== 'undefined' ? window : globalThis));
