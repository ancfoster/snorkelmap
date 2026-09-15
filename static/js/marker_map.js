// marker map - placing and editing markers on a listing

const locationMarkerMapData = { type: 'FeatureCollection', features: [] };
const COMMENT_SUFFIX = '-comment';

// zoom range - close enough for a slipway, wide enough for the bay
const ANNOTATION_ZOOM_START = 17.2;
const ANNOTATION_ZOOM_MIN   = 14;
const ANNOTATION_ZOOM_MAX   = 22;
const ANNOTATION_PAN_METRES = 1000;

const ANNOTATION_STYLES = {
  satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
  terrain:   'mapbox://styles/mapbox/outdoors-v12',
};

let locationMarkerMap  = null;
let annotationMapReady = false;
let annotationHelpShown = false;
let annotationStyle = 'satellite';

// features - create.js reads this when assembling the submission
window.locationMarkerMapData = locationMarkerMapData;

function markerIconSrc(markerId, hasNote) {
  return `${MARKER_ICON_BASE}${markerId}${hasNote ? COMMENT_SUFFIX : ''}.png`;
}

function notifyDraftChanged() {
  if (typeof window.smScheduleDraftSave === 'function') window.smScheduleDraftSave();
}

// lazy init - build the map only when the step is reached
function initAnnotationMap() {
  // intro - explain the step while the tiles load
  showAnnotationHelpOnce();

  if (annotationMapReady) {
    locationMarkerMap?.resize();
    return;
  }
  if (!MAPBOX_TOKEN || typeof mapboxgl === 'undefined' || !state.coordinates) return;
  annotationMapReady = true;

  mapboxgl.accessToken = MAPBOX_TOKEN;
  const centre = new mapboxgl.LngLat(state.coordinates.lng, state.coordinates.lat);

  locationMarkerMap = new mapboxgl.Map({
    container: 'sm-annotate-map-cont__map',
    style: ANNOTATION_STYLES[annotationStyle],
    center: centre,
    zoom: ANNOTATION_ZOOM_START,
    maxZoom: ANNOTATION_ZOOM_MAX,
    minZoom: ANNOTATION_ZOOM_MIN,
    maxBounds: centre.toBounds(ANNOTATION_PAN_METRES),
  });
  locationMarkerMap.addControl(new mapboxgl.NavigationControl(), 'bottom-right');

  initAnnotationStyleToggle();

  // restore - rebuild markers carried over from a saved draft
  restorePendingMarkers();
}

// explanation modal - open and close the help panel
function showAnnotationHelpOnce() {
  if (annotationHelpShown) return;
  annotationHelpShown = true;
  showAnnotationHelp();
}

function showAnnotationHelp() {
  if (typeof window.smShowExample === 'function') window.smShowExample('locationMapHelp');
}

// style toggle - terrain and satellite, markers survive the swap
function initAnnotationStyleToggle() {
  const wrap = document.getElementById('annotate-style-toggle');
  if (!wrap) return;
  wrap.querySelectorAll('.map-style-toggle__btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const next = btn.dataset.style;
      if (!locationMarkerMap || next === annotationStyle) return;
      annotationStyle = next;
      wrap.querySelectorAll('.map-style-toggle__btn').forEach(b => {
        b.classList.toggle('map-style-toggle__btn--active', b === btn);
      });
      locationMarkerMap.setStyle(ANNOTATION_STYLES[next]);
    });
  });
}

// draft restore - put saved markers back on the map
function restorePendingMarkers() {
  const pending = window.smPendingMarkerFeatures;
  if (!Array.isArray(pending) || !pending.length) return;
  window.smPendingMarkerFeatures = null;

  // same array - create.js holds this reference through window
  locationMarkerMapData.features.length = 0;

  pending.forEach(f => {
    const props  = f.properties || {};
    const coords = f.geometry && f.geometry.coordinates;
    addMarker(props.markerId, props.name, {
      lngLat: coords ? { lng: coords[0], lat: coords[1] } : null,
      note: props.note || '',
    });
  });
}

// drawer - bind the marker list and its controls
document.addEventListener('DOMContentLoaded', () => {
  const addMarkerButton = document.querySelector('.sm-annotate-map-toolbar__btn--add-marker');
  const markerDrawer    = document.querySelector('.marker-drawer');
  const markerDrawerList = document.querySelector('.marker-drawer__list');
  if (!addMarkerButton || !markerDrawer || !markerDrawerList) return;

  addMarkerButton.addEventListener('click', () => markerDrawer.classList.toggle('hidden'));

  document.addEventListener('click', e => {
    if (markerDrawer.contains(e.target)) return;
    if (e.target.closest('.sm-annotate-map-toolbar__btn--add-marker')) return;
    markerDrawer.classList.add('hidden');
  });

  markerDrawerList.addEventListener('click', e => {
    const item = e.target.closest('.marker-drawer__item');
    if (!item) return;
    markerDrawer.classList.add('hidden');
    addMarker(item.dataset.markerId, item.dataset.markerName);
  });

  const helpBtn = document.getElementById('annotate-help-btn');
  if (helpBtn) helpBtn.addEventListener('click', showAnnotationHelp);

  bindNoteOverlay();
});

// add marker - place one, or rebuild one from a saved draft
function addMarker(markerId, markerName, opts = {}) {
  if (!locationMarkerMap || !markerId) return;

  const el = document.createElement('div');
  el.className = 'map-marker map-marker--editable';

  const commentBtn = document.createElement('button');
  commentBtn.type = 'button';
  commentBtn.className = 'map-marker__comment';
  commentBtn.setAttribute('aria-label', 'Add or edit comment');
  commentBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><path d="M6.25 13.75H13.75V12.25H6.25V13.75ZM6.25 10.75H17.75V9.25H6.25V10.75ZM6.25 7.75H17.75V6.25H6.25V7.75ZM2.5 21.0385V4.30775C2.5 3.80258 2.675 3.375 3.025 3.025C3.375 2.675 3.80258 2.5 4.30775 2.5H19.6923C20.1974 2.5 20.625 2.675 20.975 3.025C21.325 3.375 21.5 3.80258 21.5 4.30775V15.6923C21.5 16.1974 21.325 16.625 20.975 16.975C20.625 17.325 20.1974 17.5 19.6923 17.5H6.0385L2.5 21.0385ZM5.4 16H19.6923C19.7693 16 19.8398 15.9679 19.9038 15.9038C19.9679 15.8398 20 15.7693 20 15.6923V4.30775C20 4.23075 19.9679 4.16025 19.9038 4.09625C19.8398 4.03208 19.7693 4 19.6923 4H4.30775C4.23075 4 4.16025 4.03208 4.09625 4.09625C4.03208 4.16025 4 4.23075 4 4.30775V17.3848L5.4 16Z" fill="white"/></svg>`;

  const deleteBtn = document.createElement('button');
  deleteBtn.type = 'button';
  deleteBtn.className = 'map-marker__delete';
  deleteBtn.setAttribute('aria-label', 'Delete marker');
  deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><path d="M7.30775 20.5C6.80908 20.5 6.38308 20.3234 6.02975 19.9702C5.67658 19.6169 5.5 19.1909 5.5 18.6923V6H4.5V4.5H9V3.6155H15V4.5H19.5V6H18.5V18.6923C18.5 19.1974 18.325 19.625 17.975 19.975C17.625 20.325 17.1974 20.5 16.6923 20.5H7.30775ZM17 6H7V18.6923C7 18.7821 7.02883 18.8558 7.0865 18.9135C7.14417 18.9712 7.21792 19 7.30775 19H16.6923C16.7693 19 16.8398 18.9679 16.9038 18.9038C16.9679 18.8398 17 18.7693 17 18.6923V6ZM9.404 17H10.9037V8H9.404V17ZM13.0962 17H14.596V8H13.0962V17Z" fill="white"/></svg>`;

  const icon = document.createElement('img');
  icon.className = 'map-marker__icon';
  icon.alt = markerName || '';
  // icon - fall back to the plain one when no comment variant exists
  icon.addEventListener('error', () => {
    const plain = markerIconSrc(markerId, false);
    if (!icon.src.endsWith(plain)) icon.src = plain;
  });

  el.append(commentBtn, deleteBtn, icon);

  const position = opts.lngLat || locationMarkerMap.getCenter();
  const marker = new mapboxgl.Marker({ element: el, draggable: true })
    .setLngLat(position)
    .addTo(locationMarkerMap);

  const feature = {
    type: 'Feature',
    properties: { markerId, name: markerName, note: opts.note || '' },
    geometry: { type: 'Point', coordinates: [position.lng, position.lat] },
  };
  locationMarkerMapData.features.push(feature);

  function refreshIcon() {
    icon.src = markerIconSrc(markerId, feature.properties.note.length > 0);
  }
  feature.refreshIcon = refreshIcon;
  refreshIcon();

  marker.on('drag', () => {
    const { lng, lat } = marker.getLngLat();
    feature.geometry.coordinates = [lng, lat];
  });
  marker.on('dragend', notifyDraftChanged);

  deleteBtn.addEventListener('click', e => {
    e.stopPropagation();
    marker.remove();
    const idx = locationMarkerMapData.features.indexOf(feature);
    if (idx !== -1) locationMarkerMapData.features.splice(idx, 1);
    notifyDraftChanged();
  });

  commentBtn.addEventListener('click', e => {
    e.stopPropagation();
    openNoteOverlay(feature);
  });

  notifyDraftChanged();
}

// note overlay - edit the text attached to a marker
let activeFeature = null;

function bindNoteOverlay() {
  const overlay = document.querySelector('.note-overlay');
  if (!overlay) return;
  const textarea = overlay.querySelector('.note-overlay__textarea');
  const counter  = overlay.querySelector('.note-overlay__counter');
  const confirm  = overlay.querySelector('.note-overlay__btn--confirm');
  const cancel   = overlay.querySelector('.note-overlay__btn--cancel');

  textarea.addEventListener('input', () => {
    counter.textContent = `${textarea.value.length} / 550`;
  });

  confirm.addEventListener('click', () => {
    if (activeFeature) {
      activeFeature.properties.note = textarea.value.trim();
      activeFeature.refreshIcon?.();
      notifyDraftChanged();
    }
    closeNoteOverlay();
  });

  cancel.addEventListener('click', closeNoteOverlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) closeNoteOverlay(); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !overlay.classList.contains('hidden')) closeNoteOverlay();
  });
}

function openNoteOverlay(feature) {
  const overlay = document.querySelector('.note-overlay');
  if (!overlay) return;
  activeFeature = feature;
  overlay.querySelector('.note-overlay__title').textContent = feature.properties.name;
  const textarea = overlay.querySelector('.note-overlay__textarea');
  textarea.value = feature.properties.note;
  overlay.querySelector('.note-overlay__counter').textContent = `${textarea.value.length} / 550`;
  overlay.classList.remove('hidden');
  textarea.focus();
}

function closeNoteOverlay() {
  const overlay = document.querySelector('.note-overlay');
  if (!overlay) return;
  activeFeature = null;
  overlay.classList.add('hidden');
}
