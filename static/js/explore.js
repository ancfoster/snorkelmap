// explore - the map page, its pins, sheet and side pane
(function () {
  'use strict';

  var root = document.getElementById('explore-map');
  if (!root) return;

  var DATA_URL = root.dataset.mapDataUrl || '';
  var CARDS_URL = root.dataset.cardsUrl;
  var CARD_URL = root.dataset.cardUrl;        // with a zeroed uuid to swap
  var LIMIT = parseInt(root.dataset.limit, 10) || 20;
  var LIMIT_MOBILE = parseInt(root.dataset.limitMobile, 10) || 12;

  var PHONE = 900;            // matches the css breakpoint
  var SETTLE_MS = 250;        // how long the map must be still
  var CLUSTER_ZOOM_MAX = 13;  // above this every pin stands alone

  var listEl = document.getElementById('explore-list');
  var sidebarEl = document.getElementById('explore-sidebar');

  var points = [];            // uuid, lng and lat for the sampler
  var lastRequest = '';       // so an unchanged viewport asks twice for nothing
  var inFlight = null;
  var settleTimer = null;

  // sheet - the bottom drawer on a phone

  var STATES = ['peek', 'half', 'full'];
  var state = 0;
  var handle = document.getElementById('explore-sheet-handle');

  function applyState() {
    if (!sidebarEl) return;
    STATES.forEach(function (name) {
      sidebarEl.classList.toggle('explore-sidebar--' + name, STATES[state] === name);
    });
    if (handle) handle.setAttribute('aria-expanded', state > 0 ? 'true' : 'false');
  }

  function wireSheet() {
    if (!handle || !sidebarEl) return;
    applyState();

    handle.addEventListener('click', function () {
      state = state >= STATES.length - 1 ? 0 : state + 1;
      applyState();
    });

    var startY = null;
    handle.addEventListener('touchstart', function (event) {
      startY = event.touches[0].clientY;
    }, { passive: true });

    handle.addEventListener('touchend', function (event) {
      if (startY === null) return;
      var moved = startY - event.changedTouches[0].clientY;
      startY = null;
      if (Math.abs(moved) < 24) return;      // a tap, handled by click
      event.preventDefault();
      state = moved > 0 ? Math.min(state + 1, STATES.length - 1)
                        : Math.max(state - 1, 0);
      applyState();
    });

    // resize - a wide window should not leave the sheet half open
    window.addEventListener('resize', function () {
      if (!isPhone() && state !== 0) { state = 0; applyState(); }
    });
  }

  // order - the sheet is wired first so it works if mapbox fails
  wireSheet();

  if (typeof mapboxgl === 'undefined') {
    console.warn('Mapbox did not load; the map is unavailable.');
    return;
  }

  mapboxgl.accessToken = root.dataset.token;

  var map = new mapboxgl.Map({
    container: 'explore-map',
    style: 'mapbox://styles/mapbox/outdoors-v12',
    center: [-3.5, 54.5],
    zoom: 5,
  });
  map.addControl(new mapboxgl.NavigationControl(), 'bottom-right');

  // pin colour - read from the stylesheet rather than written twice
  function accent() {
    return getComputedStyle(document.documentElement)
      .getPropertyValue('--sm-primary-accent').trim() || '#0096CD';
  }

  function isPhone() {
    return window.matchMedia('(max-width: ' + PHONE + 'px)').matches;
  }

  // data file - the locations the map draws

  map.on('load', function () {
    if (!DATA_URL) {
      console.warn('No map data file has been built yet.');
      return;
    }

    // fetched here - the pane needs the coordinates as well as the map
    fetch(DATA_URL)
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.json();
      })
      .then(addLocations)
      .catch(function (error) {
        // failure - the rendered list stays, only the pins are lost
        console.error('Could not load the map data file', error);
      });
  });

  function addLocations(collection) {
    points = (collection.features || []).map(function (feature) {
      return {
        uuid: feature.properties.uuid,
        name: feature.properties.name,
        lng: feature.geometry.coordinates[0],
        lat: feature.geometry.coordinates[1],
      };
    });

    map.addSource('locations', {
      type: 'geojson',
      data: collection,
      cluster: true,
      clusterMaxZoom: CLUSTER_ZOOM_MAX,
      clusterRadius: 50,
      // promote id - lets feature state be set by a location's uuid
      promoteId: 'uuid',
    });

    var colour = accent();

    map.addLayer({
      id: 'clusters', type: 'circle', source: 'locations',
      filter: ['has', 'point_count'],
      paint: {
        'circle-color': colour,
        'circle-opacity': 0.9,
        'circle-stroke-width': 3,
        'circle-stroke-color': '#ffffff',
        // cluster size - grows in steps so the sizes stay distinguishable
        'circle-radius': ['step', ['get', 'point_count'], 16, 10, 22, 50, 30],
      },
    });

    map.addLayer({
      id: 'cluster-count', type: 'symbol', source: 'locations',
      filter: ['has', 'point_count'],
      layout: {
        'text-field': ['get', 'point_count_abbreviated'],
        'text-font': ['DIN Offc Pro Medium', 'Arial Unicode MS Bold'],
        'text-size': 13,
      },
      paint: { 'text-color': '#ffffff' },
    });

    map.addLayer({
      id: 'pins', type: 'circle', source: 'locations',
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-color': colour,
        'circle-radius': ['case', ['boolean', ['feature-state', 'active'], false], 11, 8],
        'circle-stroke-width': 2.5,
        'circle-stroke-color': '#ffffff',
      },
    });

    map.on('click', 'clusters', zoomIntoCluster);
    map.on('click', 'pins', openCard);
    ['clusters', 'pins'].forEach(function (layer) {
      map.on('mouseenter', layer, function () {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', layer, function () {
        map.getCanvas().style.cursor = '';
      });
    });

    map.on('moveend', scheduleRefresh);
    refreshPane();
  }

  // pane - the list beside the map

  function scheduleRefresh() {
    // settle - a wheel zoom fires moveend repeatedly, so wait
    window.clearTimeout(settleTimer);
    settleTimer = window.setTimeout(refreshPane, SETTLE_MS);
  }

  function refreshPane() {
    if (!points.length || !listEl) return;

    var bounds = map.getBounds();
    var result = window.SMSample.sampleViewport(points, {
      west: bounds.getWest(), south: bounds.getSouth(),
      east: bounds.getEast(), north: bounds.getNorth(),
    }, {
      limit: isPhone() ? LIMIT_MOBILE : LIMIT,
      landscape: root.clientWidth >= root.clientHeight,
    });

    var query = 'ids=' + result.items.map(function (item) {
      return item.uuid;
    }).join(',') + (result.truncated ? '&more=1' : '');

    if (query === lastRequest) return;
    lastRequest = query;

    if (inFlight) inFlight.abort();
    var controller = new AbortController();
    inFlight = controller;

    fetch(CARDS_URL + '?' + query, {
      signal: controller.signal,
      headers: { 'X-Requested-With': 'fetch' },
    }).then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.text();
    }).then(function (html) {
      listEl.innerHTML = html;
      if (window.htmx) window.htmx.process(listEl);
      wirePaneRows();
      listEl.scrollTop = 0;
    }).catch(function (error) {
      if (error.name === 'AbortError') return;
      // pane failure - reported and left alone, the map still works
      console.warn('Could not refresh the list', error);
      lastRequest = '';
    }).finally(function () {
      if (inFlight === controller) inFlight = null;
    });
  }

  // hover - lifts the matching pin when one is actually drawn
  function wirePaneRows() {
    listEl.querySelectorAll('.explore-list-item').forEach(function (row) {
      var id = row.dataset.uuid;
      row.addEventListener('mouseenter', function () { setActive(id, true); });
      row.addEventListener('mouseleave', function () { setActive(id, false); });
    });
  }

  function setActive(uuid, on) {
    // clustered - nothing to lift, so do nothing
    if (!map.getSource('locations') || map.getZoom() <= CLUSTER_ZOOM_MAX) return;
    map.setFeatureState({ source: 'locations', id: uuid }, { active: on });
  }

  // clicking the map - open the card for a pin

  function zoomIntoCluster(event) {
    var feature = event.features[0];
    map.getSource('locations').getClusterExpansionZoom(
      feature.properties.cluster_id,
      function (error, zoom) {
        if (error) return;
        map.easeTo({ center: feature.geometry.coordinates, zoom: zoom });
      });
  }

  var openPopup = null;

  function openCard(event) {
    var feature = event.features[0];
    var uuid = feature.properties.uuid;
    var coordinates = feature.geometry.coordinates.slice();

    // world copies - open the card on the pin that was clicked
    while (Math.abs(event.lngLat.lng - coordinates[0]) > 180) {
      coordinates[0] += event.lngLat.lng > coordinates[0] ? 360 : -360;
    }

    if (openPopup) openPopup.remove();
    var popup = new mapboxgl.Popup({
      className: 'explore-popup', closeButton: true,
      offset: 16, maxWidth: 'none',
    }).setLngLat(coordinates)
      .setHTML('<p class="explore-card__loading">Loading</p>')
      .addTo(map);
    openPopup = popup;

    fetch(CARD_URL.replace('00000000-0000-0000-0000-000000000000', uuid), {
      headers: { 'X-Requested-With': 'fetch' },
    }).then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.text();
    }).then(function (html) {
      if (openPopup !== popup) return;   // another pin was clicked meanwhile
      popup.setHTML(html);
    }).catch(function () {
      if (openPopup !== popup) return;
      popup.setHTML('<p class="explore-card__loading">That card could not be loaded.</p>');
    });
  }
}());
