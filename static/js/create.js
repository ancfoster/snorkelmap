// create - the flow for adding a new listing

// config - values handed over from the template
function readJSONScript(id, fallback) {
  const el = document.getElementById(id);
  if (!el) return fallback;
  try { return JSON.parse(el.textContent); }
  catch (e) { console.warn(`Could not parse #${id}`, e); return fallback; }
}

const MAPBOX_TOKEN      = readJSONScript('mapbox-token', null);
const MARKER_ICON_BASE  = readJSONScript('marker-icon-base', '/static/images/sm-map-icons/');
const STEP_TOTAL        = readJSONScript('step-total', 8);
const VIS_MAX_AGE_DAYS  = readJSONScript('visibility-max-age-days', 180);

if (!MAPBOX_TOKEN) {
  console.error('Mapbox token missing: check mapbox_token is in the view context');
}

const ZOOM_THRESHOLD     = 15.6;
const ZOOM_MAX           = 18.5;
const ZOOM_MIN           = 4;
const ZOOM_THRESHOLD_PCT = ((ZOOM_THRESHOLD - ZOOM_MIN) / (ZOOM_MAX - ZOOM_MIN)) * 100;

const MAP_STYLES = {
  terrain:   'mapbox://styles/mapbox/outdoors-v12',
  satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
};

// indexeddb - stores the file itself, not a data url
const DB_NAME     = 'SnorkelMapDB';
const DB_VERSION  = 2;
const PHOTO_STORE = 'photos';

// localstorage keys
const DRAFT_KEY = 'snorkelmap_draft';

// screens - the ones either side of the numbered steps
const STEP_RESUME   = -1;
const STEP_INTRO    = 0;
const STEP_MEDIA    = 3;
const STEP_LOCMAP   = 8;
const STEP_PUBLISH  = 9;
const STEP_THANKYOU = 10;

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

const SESSION_TOKEN = generateUUID();  // mapbox search box session
let   SUBMISSION_ID = generateUUID();  // ties this draft's photos to this submission

function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

// state - read from the page django rendered
let SET_KEYS = [];     // chip groups
let TEXT_KEYS = [];    // text and value fields
const GROUPS = new Map();   // group behaviour by state key

const state = {
  currentStep: STEP_INTRO,
  maxStepReached: STEP_INTRO,
  coordinates: null,
  locationMeta: { country: '', region: '', town: '' },
  locationConfirmed: false,
  alternateNames: [],
  parkingAvailable: '',
  aboveWaterPhotos: [],
  underwaterPhotos: [],
};

function initStateFromDOM() {
  SET_KEYS = [...new Set(
    [...document.querySelectorAll('[data-state-key]')].map(el => el.dataset.stateKey)
  )];
  SET_KEYS.forEach(key => { state[key] = new Set(); });

  TEXT_KEYS = [...new Set(
    [...document.querySelectorAll('[data-field]')].map(el => el.dataset.field)
  )];
  document.querySelectorAll('[data-field]').forEach(el => {
    const key = el.dataset.field;
    if (key in state) return;
    state[key] = el.dataset.fieldType === 'int' ? parseInt(el.value, 10) || 1 : '';
  });
  // difficulty - driven by chips, so it has no data-field
  if (!TEXT_KEYS.includes('parkingAvailable')) TEXT_KEYS.push('parkingAvailable');

  document.querySelectorAll('[data-group-key]').forEach(el => {
    const key = el.dataset.groupKey;
    GROUPS.set(key, {
      key,
      element: el,
      noneId: el.dataset.noneOption === 'true' ? 'none' : null,
      singleSelect: el.dataset.singleSelect === 'true',
      payloadGroup: el.dataset.payloadGroup || null,
      payloadKey: el.dataset.payloadKey || null,
    });
  });
}

function groupFor(stateKey) { return GROUPS.get(stateKey) || null; }

let map = null;
let mapInitialised = false;
let searchDebounceTimer = null;
let mapStyleCurrent = 'terrain';

// init - wire everything up
document.addEventListener('DOMContentLoaded', () => {
  // login - the whole flow is behind a gate
  if (!document.getElementById('step-0')) return;

  document.documentElement.style.setProperty('--zoom-threshold-pct', `${ZOOM_THRESHOLD_PCT}%`);
  initStateFromDOM();
  renderAllDonuts();
  bindIntroStep();
  bindChips();
  bindTextFields();
  bindDifficultySlider();
  bindVisibilityReport();
  bindAltNameModal();
  bindParking();
  bindStepButtons();
  bindStepNavigation();
  bindModal();
  initFileUploads();
  bindPublish();
  bindHistory();
  bindResumeScreen();
  bindUnloadGuards();

  const draft = readDraft();
  if (draft && draft.name) {
    showResumeScreen(draft);
  } else {
    clearDraft();
    goToStep(STEP_INTRO, { replace: true });
  }
});

// progress rings - the donuts on each step
function renderAllDonuts() {
  for (let i = 1; i <= STEP_TOTAL; i++) {
    const el = document.getElementById(`donut-step-${i}`);
    if (el) el.innerHTML = makeDonuts(i);
  }
}

function makeDonuts(stepNum) {
  const progress = (stepNum / STEP_TOTAL) * 100;
  return `
    <svg class="step-donut" viewBox="0 0 36 36" aria-label="Step ${stepNum} of ${STEP_TOTAL}">
      <circle class="step-donut__bg"   cx="18" cy="18" r="15.9155" fill="none" stroke-width="3"/>
      <circle class="step-donut__ring" cx="18" cy="18" r="15.9155" fill="none" stroke-width="3"
        stroke-dasharray="${progress.toFixed(2)} 100"
        transform="rotate(-90 18 18)"/>
      <text class="step-donut__text" x="18" y="20.5" text-anchor="middle">${stepNum}/${STEP_TOTAL}</text>
    </svg>`;
}

// navigation - moving between steps and browser history
function stepElementId(n) {
  if (n === STEP_RESUME)   return 'step-resume';
  if (n === STEP_PUBLISH)  return 'step-publish';
  if (n === STEP_THANKYOU) return 'step-thankyou';
  return `step-${n}`;
}

function goToStep(n, opts = {}) {
  document.querySelectorAll('.create-step').forEach(el => el.classList.remove('create-step--active'));
  const target = document.getElementById(stepElementId(n));
  if (target) { target.classList.add('create-step--active'); window.scrollTo(0, 0); }
  state.currentStep = n;
  if (n > state.maxStepReached && n <= STEP_LOCMAP) state.maxStepReached = n;

  if (n === 1) {
    if (!mapInitialised) { initMap(); mapInitialised = true; }
    else if (map) setTimeout(() => map.resize(), 100);
  }

  if (n === STEP_LOCMAP && state.coordinates && typeof initAnnotationMap === 'function') {
    initAnnotationMap();
  }

  if (!opts.fromHistory) pushStepHistory(n, opts.replace === true);
  if (!opts.skipDraftSave) scheduleDraftSave();
}

function pushStepHistory(n, replace) {
  const url  = n === STEP_RESUME ? '#resume'
             : n === STEP_PUBLISH ? '#publishing'
             : n === STEP_THANKYOU ? '#done'
             : `#step-${n}`;
  const data = { smStep: n };
  try {
    if (replace) history.replaceState(data, '', url);
    else         history.pushState(data, '', url);
  } catch (e) { /* history blocked, navigation still works */ }
}

// publishing - absorb back rather than unwinding the form
let navigationLocked = false;
let publishInFlight  = false;

function bindHistory() {
  window.addEventListener('popstate', e => {
    if (navigationLocked) {
      pushStepHistory(state.currentStep, false);
      return;
    }
    const n = e.state && typeof e.state.smStep === 'number' ? e.state.smStep : STEP_INTRO;
    goToStep(n, { fromHistory: true });
  });
}

function bindUnloadGuards() {
  window.addEventListener('beforeunload', e => {
    // leaving - a submission is already under way
    if (publishInFlight) {
      e.preventDefault();
      e.returnValue = '';
      return '';
    }
    flushDraftSave();
  });
  window.addEventListener('pagehide', () => { if (!publishInFlight) flushDraftSave(); });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && !publishInFlight) flushDraftSave();
  });
}

function bindStepNavigation() {
  document.addEventListener('click', e => {
    const el = e.target.closest('[data-goto]');
    if (!el) return;
    e.preventDefault();
    const target = parseInt(el.dataset.goto, 10);
    if (target > state.currentStep && !validateStep(state.currentStep)) return;
    goToStep(target);
  });
}

function bindStepButtons() {
  const next = { 'step2-continue': STEP_MEDIA, 'step3-continue': 4, 'step4-continue': 5, 'step5-continue': 6 };
  Object.keys(next).forEach(id => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.addEventListener('click', () => {
      if (!validateStep(state.currentStep)) return;
      goToStep(next[id]);
    });
  });
}

// draft - saved from step two once the location has a name
let draftSaveTimer = null;

function scheduleDraftSave() {
  clearTimeout(draftSaveTimer);
  draftSaveTimer = setTimeout(saveDraft, 400);
}
window.smScheduleDraftSave = scheduleDraftSave;

function flushDraftSave() {
  clearTimeout(draftSaveTimer);
  syncStep2Fields();
  saveDraft();
}

function draftIsSaveable() {
  return state.currentStep >= 2
      && state.currentStep <= STEP_LOCMAP
      && String(state.name || '').trim().length > 0;
}

function saveDraft() {
  if (!draftIsSaveable()) return;
  const payload = {
    version: 3,
    submissionId: SUBMISSION_ID,
    savedAt: new Date().toISOString(),
    currentStep: state.currentStep,
    maxStepReached: state.maxStepReached,
    coordinates: state.coordinates,
    locationMeta: state.locationMeta,
    locationConfirmed: state.locationConfirmed,
    alternateNames: state.alternateNames,
    sets: {},
    text: {},
    photos: {
      aboveWater: state.aboveWaterPhotos.map(p => ({ id: p.id, description: p.description })),
      underwater: state.underwaterPhotos.map(p => ({ id: p.id, description: p.description })),
    },
    markers: window.locationMarkerMapData
      ? JSON.parse(JSON.stringify(window.locationMarkerMapData))
      : { type: 'FeatureCollection', features: [] },
  };
  SET_KEYS.forEach(k => { payload.sets[k] = [...state[k]]; });
  TEXT_KEYS.forEach(k => { payload.text[k] = state[k]; });

  try { localStorage.setItem(DRAFT_KEY, JSON.stringify(payload)); }
  catch (e) { console.warn('Could not save draft to localStorage:', e); }
}

function readDraft() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const d = JSON.parse(raw);
    if (!d || !d.text) return null;
    d.name = d.text.name || '';
    return d;
  } catch (e) { console.warn('Could not read draft:', e); return null; }
}

function clearDraft() {
  try { localStorage.removeItem(DRAFT_KEY); } catch (e) { /* ignore */ }
}

async function discardDraft(draft) {
  clearDraft();
  if (draft && draft.submissionId) {
    try { await deletePhotosForSubmission(draft.submissionId); }
    catch (e) { console.warn('Could not clear draft photos:', e); }
  }
}

// resume - offer to pick a saved draft back up
let pendingDraft = null;

function showResumeScreen(draft) {
  pendingDraft = draft;
  const nameEl = document.getElementById('resume-location-name');
  if (nameEl) nameEl.textContent = draft.name;
  goToStep(STEP_RESUME, { replace: true, skipDraftSave: true });
}

function bindResumeScreen() {
  const resumeBtn = document.getElementById('resume-continue-btn');
  const freshBtn  = document.getElementById('resume-fresh-btn');
  if (!resumeBtn || !freshBtn) return;

  resumeBtn.addEventListener('click', () => {
    if (!pendingDraft) { goToStep(STEP_INTRO); return; }
    applyDraft(pendingDraft);
  });
  freshBtn.addEventListener('click', async () => {
    const draft = pendingDraft;
    pendingDraft = null;
    await discardDraft(draft);
    goToStep(STEP_INTRO, { replace: true });
  });
}

async function applyDraft(draft) {
  SUBMISSION_ID = draft.submissionId || SUBMISSION_ID;

  state.coordinates       = draft.coordinates || null;
  state.locationMeta      = draft.locationMeta || { country: '', region: '', town: '' };
  state.locationConfirmed = !!draft.locationConfirmed;
  state.alternateNames    = Array.isArray(draft.alternateNames) ? draft.alternateNames.slice() : [];
  state.maxStepReached    = draft.maxStepReached || 2;

  SET_KEYS.forEach(k => { state[k] = new Set(draft.sets?.[k] || []); });
  TEXT_KEYS.forEach(k => {
    if (draft.text && k in draft.text) state[k] = draft.text[k];
  });

  if (draft.markers && Array.isArray(draft.markers.features)) {
    window.smPendingMarkerFeatures = draft.markers.features;
  }

  try {
    const db     = await openPhotoDB();
    const stored = await getPhotosForSubmission(db, SUBMISSION_ID);
    const byId   = {};
    stored.forEach(rec => { byId[rec.id] = rec; });
    const restore = refs => (refs || [])
      .filter(ref => byId[ref.id] && byId[ref.id].file)
      .map(ref => {
        const rec = byId[ref.id];
        return {
          id: rec.id,
          file: rec.file,
          name: rec.name,
          mime: rec.mime,
          extension: rec.extension,
          bytes: rec.bytes,
          width: rec.width,
          height: rec.height,
          previewable: rec.previewable,
          capturedAt: rec.capturedAt || null,
          capturedAtOffset: rec.capturedAtOffset || null,
          latitude: typeof rec.latitude === 'number' ? rec.latitude : null,
          longitude: typeof rec.longitude === 'number' ? rec.longitude : null,
          description: ref.description || '',
        };
      });
    state.aboveWaterPhotos = restore(draft.photos?.aboveWater);
    state.underwaterPhotos = restore(draft.photos?.underwater);
  } catch (e) {
    console.warn('Could not restore draft photos:', e);
  }

  repopulateFormFromState();
  pendingDraft = null;

  const resumeTo = Math.min(Math.max(draft.currentStep || 2, 2), STEP_LOCMAP);
  // seed - so back walks the form rather than leaving the page
  pushStepHistory(1, true);
  for (let i = 2; i < resumeTo; i++) pushStepHistory(i, false);
  goToStep(resumeTo);
}

function repopulateFormFromState() {
  document.querySelectorAll('[data-field]').forEach(el => {
    const key = el.dataset.field;
    if (!(key in state)) return;
    el.value = state[key] === null || state[key] === undefined ? '' : state[key];
  });

  renderAlternateNames();
  showLocationMetaStep2();

  document.querySelectorAll('.chip[data-state-key]').forEach(btn => {
    const set = state[btn.dataset.stateKey];
    if (!set || typeof set.has !== 'function') return;
    btn.classList.toggle('chip--active', set.has(btn.dataset.id));
  });
  refreshAllGroupLocks();
  syncParkingUI();
  syncVisibilityUI();

  renderPhotoGrid('aboveWater');
  renderPhotoGrid('underwater');

  if (state.locationConfirmed) {
    const btn = document.getElementById('confirm-location-btn');
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Location confirmed';
      btn.classList.add('btn--confirmed');
    }
  }
}

// validation - what each step needs before moving on
function showFieldError(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.style.display = 'block';
}
function clearFieldError(id) {
  const el = document.getElementById(id);
  if (el) { el.textContent = ''; el.style.display = 'none'; }
}

function anySelected(keys) {
  return keys.some(k => state[k] && state[k].size > 0);
}

function keysWithPrefix(prefix) {
  return SET_KEYS.filter(k => k.startsWith(prefix));
}

function syncStep2Fields() {
  ['name', 'description', 'entryPointDescription'].forEach(key => {
    const el = document.querySelector(`[data-field="${key}"]`);
    if (el) state[key] = el.value.trim();
  });
}

function validateStep(step) {
  if (step === 1) {
    if (!state.locationConfirmed) {
      const btn = document.getElementById('confirm-location-btn');
      btn.classList.add('btn--shake');
      setTimeout(() => btn.classList.remove('btn--shake'), 500);
      return false;
    }
    return true;
  }

  if (step === 2) {
    let valid = true;
    ['err-name', 'err-description', 'err-access', 'err-water', 'err-visibility'].forEach(clearFieldError);
    syncStep2Fields();
    if (String(state.name).length < 2)  { showFieldError('err-name',        'Please enter a location name (minimum 2 characters).'); valid = false; }
    if (!state.description)             { showFieldError('err-description', 'Please add a description.');                            valid = false; }
    if (state.accessType.size === 0)    { showFieldError('err-access',      'Please select at least one access type.');              valid = false; }
    if (state.waterType.size === 0)     { showFieldError('err-water',       'Please select a water type.');                          valid = false; }
    if (visibilityIsSet()) {
      const dateError = validateVisibilityDate(state.visibilityDate);
      if (dateError) { showFieldError('err-visibility', dateError); valid = false; }
    }
    return valid;
  }

  if (step === STEP_MEDIA) {
    clearFieldError('err-photos');
    if (state.aboveWaterPhotos.length < 1) {
      showFieldError('err-photos', 'Please add at least one photo of the above water surroundings. This is the only photo needed to publish.');
      return false;
    }
    return true;
  }

  if (step === 4) {
    clearFieldError('err-env');
    if (!anySelected(keysWithPrefix('env'))) {
      showFieldError('err-env', 'Please select at least one environment type.');
      return false;
    }
    return true;
  }

  if (step === 5) {
    clearFieldError('err-marine');
    if (!anySelected(keysWithPrefix('ml'))) {
      showFieldError('err-marine', 'Please select at least one type of marine life.');
      return false;
    }
    return true;
  }

  return true; // optional - steps six, seven and eight
}

// intro - the screen before step one
function bindIntroStep() {
  const checkbox = document.getElementById('intro-checkbox');
  const startBtn = document.getElementById('intro-start');
  if (!checkbox || !startBtn) return;
  checkbox.addEventListener('change', () => { startBtn.disabled = !checkbox.checked; });
  startBtn.addEventListener('click', () => { if (checkbox.checked) goToStep(1); });
}

// step one - find the location on the map
function initMap() {
  if (!MAPBOX_TOKEN || typeof mapboxgl === 'undefined') {
    const container = document.getElementById('mapbox-map');
    if (container) {
      container.innerHTML = '<div class="map-placeholder"><p>Map unavailable — the Mapbox token is missing.</p></div>';
    }
    return;
  }

  mapboxgl.accessToken = MAPBOX_TOKEN;
  const start = state.coordinates ? [state.coordinates.lng, state.coordinates.lat] : [-2.0, 54.5];

  map = new mapboxgl.Map({
    container: 'mapbox-map',
    style: MAP_STYLES.terrain,
    center: start,
    zoom: state.coordinates ? ZOOM_THRESHOLD + 0.4 : 5,
    maxZoom: ZOOM_MAX,
    minZoom: ZOOM_MIN,
    attributionControl: false,
  });
  map.addControl(new mapboxgl.AttributionControl({ compact: true }), 'bottom-left');

  map.on('zoom', () => {
    const z = map.getZoom();
    document.getElementById('zoom-slider').value = z;
    updateCrosshairColour(z);
    document.getElementById('confirm-location-btn').disabled = z < ZOOM_THRESHOLD;
  });
  map.on('move', () => {
    const { lat, lng } = map.getCenter();
    state.coordinates = { lat, lng };
  });

  document.getElementById('zoom-slider').addEventListener('input', e => {
    map.setZoom(parseFloat(e.target.value));
  });
  document.getElementById('confirm-location-btn').addEventListener('click', handleConfirmLocation);
  initMapSearch();
  initFinderStyleToggle();

  const initialZoom = map.getZoom();
  updateCrosshairColour(initialZoom);
  document.getElementById('confirm-location-btn').disabled = initialZoom < ZOOM_THRESHOLD;
}

function initFinderStyleToggle() {
  const wrap = document.getElementById('finder-style-toggle');
  if (!wrap) return;
  wrap.querySelectorAll('.map-style-toggle__btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const next = btn.dataset.style;
      if (!map || next === mapStyleCurrent) return;
      mapStyleCurrent = next;
      wrap.querySelectorAll('.map-style-toggle__btn').forEach(b => {
        b.classList.toggle('map-style-toggle__btn--active', b === btn);
      });
      map.setStyle(MAP_STYLES[next]);
    });
  });
}

function updateCrosshairColour(zoom) {
  const c = document.getElementById('map-crosshair');
  if (!c) return;
  c.classList.toggle('crosshair--ok',      zoom >= ZOOM_THRESHOLD);
  c.classList.toggle('crosshair--warning', zoom < ZOOM_THRESHOLD);
}

function handleConfirmLocation() {
  if (map) {
    const { lat, lng } = map.getCenter();
    state.coordinates = { lat, lng };
    reverseGeocode(lng, lat);
  }
  state.locationConfirmed = true;
  const btn = document.getElementById('confirm-location-btn');
  btn.textContent = 'Location confirmed';
  btn.classList.add('btn--confirmed');
  setTimeout(() => goToStep(2), 600);
}

function showLocationMetaStep2() {
  const { country, region, town } = state.locationMeta;
  const parts = [country, region, town].filter(Boolean);
  if (!parts.length) return;
  const el = document.getElementById('location-meta-step2');
  if (!el) return;
  el.textContent = parts.join(' » ');
  el.style.display = 'block';
}

function initMapSearch() {
  const input   = document.getElementById('map-search-input');
  const results = document.getElementById('map-search-results');
  input.addEventListener('input', () => {
    clearTimeout(searchDebounceTimer);
    const q = input.value.trim();
    if (q.length < 2) { results.innerHTML = ''; results.style.display = 'none'; return; }
    searchDebounceTimer = setTimeout(() => searchPlaces(q), 350);
  });
  document.addEventListener('click', e => {
    if (!e.target.closest('.map-wrap__search')) { results.innerHTML = ''; results.style.display = 'none'; }
  });
}

async function searchPlaces(q) {
  const results = document.getElementById('map-search-results');
  results.innerHTML = '<div class="map-search__loading">Searching...</div>';
  results.style.display = 'block';
  try {
    const url = new URL('https://api.mapbox.com/search/searchbox/v1/suggest');
    url.searchParams.set('q', q);
    url.searchParams.set('session_token', SESSION_TOKEN);
    url.searchParams.set('access_token', MAPBOX_TOKEN);
    url.searchParams.set('types', 'country,region,district,place,city,locality,neighborhood');
    url.searchParams.set('language', 'en');
    url.searchParams.set('limit', '6');
    const data = await (await fetch(url.toString())).json();
    if (!data.suggestions?.length) { results.innerHTML = '<div class="map-search__no-results">No places found</div>'; return; }
    results.innerHTML = '';
    data.suggestions.forEach(s => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'map-search__result-item';
      item.innerHTML = `<span class="map-search__result-name"></span><span class="map-search__result-place"></span>`;
      item.querySelector('.map-search__result-name').textContent = s.name;
      item.querySelector('.map-search__result-place').textContent = s.place_formatted || '';
      item.addEventListener('click', () => {
        document.getElementById('map-search-input').value = s.name;
        results.innerHTML = ''; results.style.display = 'none';
        retrievePlace(s.mapbox_id);
      });
      results.appendChild(item);
    });
  } catch { results.innerHTML = '<div class="map-search__no-results">Search unavailable.</div>'; }
}

async function retrievePlace(mapboxId) {
  try {
    const url  = `https://api.mapbox.com/search/searchbox/v1/retrieve/${mapboxId}?session_token=${SESSION_TOKEN}&access_token=${MAPBOX_TOKEN}`;
    const feat = (await (await fetch(url)).json()).features?.[0];
    if (!feat) return;
    const [lng, lat] = feat.geometry.coordinates;
    map.flyTo({ center: [lng, lat], zoom: 12, essential: true });
    state.coordinates = { lat, lng };
    reverseGeocode(lng, lat);
  } catch (e) { console.warn('Place retrieve failed:', e); }
}

async function reverseGeocode(lng, lat) {
  try {
    const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${lng},${lat}.json?types=country,region,place&access_token=${MAPBOX_TOKEN}&language=en`;
    const f   = (await (await fetch(url)).json()).features || [];
    // display only - the server resolves the geography it stores
    state.locationMeta.country = f.find(x => x.place_type.includes('country'))?.text || '';
    state.locationMeta.region  = f.find(x => x.place_type.includes('region'))?.text  || '';
    state.locationMeta.town    = f.find(x => x.place_type.includes('place'))?.text   || '';
    showLocationMetaStep2();
    scheduleDraftSave();
  } catch (e) { console.warn('Geocode failed:', e); }
}

// chips - bound to markup django already rendered
function bindChips() {
  document.querySelectorAll('.chip[data-state-key]').forEach(btn => {
    btn.addEventListener('click', () => toggleChip(btn));
  });
  refreshAllGroupLocks();
}

function toggleChip(btn) {
  const key = btn.dataset.stateKey;
  const id  = btn.dataset.id;
  const set = state[key];
  if (!set) return;
  const group = groupFor(key);

  const isNone = id === (group && group.noneId);

  if (isNone || (group && group.singleSelect)) {
    if (set.has(id)) set.delete(id);
    else { set.clear(); set.add(id); }
  } else if (set.has(id)) {
    set.delete(id);
  } else {
    // water type - picking from the other group replaces the answer
    if (btn.dataset.waterGroup) {
      const active = activeWaterGroup();
      if (active && active !== btn.dataset.waterGroup) set.clear();
    }
    if (group && group.noneId) set.delete(group.noneId);
    set.add(id);
  }

  document.querySelectorAll(`.chip[data-state-key="${key}"]`).forEach(el => {
    el.classList.toggle('chip--active', set.has(el.dataset.id));
  });
  if (group && group.noneId) refreshGroupLock(group);
  if (key === 'waterType') refreshWaterTypeLock();
  scheduleDraftSave();
}

function activeWaterGroup() {
  const active = document.querySelector('#chips-waterType .chip--active');
  return active ? active.dataset.waterGroup : null;
}

// dimmed - the inactive group is still clickable
function refreshWaterTypeLock() {
  const active = activeWaterGroup();
  document.querySelectorAll('#chips-waterType .chip').forEach(btn => {
    btn.classList.toggle('chip--muted', active !== null && btn.dataset.waterGroup !== active);
  });
  document.querySelectorAll('#chips-waterType .chip-sub-group').forEach(el => {
    el.classList.toggle('chip-sub-group--muted', active !== null && el.dataset.waterGroup !== active);
  });
}

// none - picking a real option simply clears it
function refreshGroupLock(group) {
  if (!group || !group.noneId) return;
  const noneOn = state[group.key].has(group.noneId);
  document.querySelectorAll(`.chip[data-state-key="${group.key}"]`).forEach(el => {
    if (el.dataset.id === group.noneId) return;
    el.classList.toggle('chip--muted', noneOn);
  });
}

function refreshAllGroupLocks() {
  GROUPS.forEach(group => refreshGroupLock(group));
  refreshWaterTypeLock();
}

// text - fields and difficulty
function bindTextFields() {
  document.querySelectorAll('[data-field]').forEach(el => {
    if (el.id === 'vis-create-slider' || el.dataset.fieldType === 'int') return; // bound separately
    const key = el.dataset.field;
    const evt = el.tagName === 'INPUT' && el.type === 'date' ? 'change' : 'input';
    el.addEventListener(evt, e => {
      state[key] = e.target.value;
      scheduleDraftSave();
    });
  });
}

function bindDifficultySlider() {
  const input = document.querySelector('[data-field="difficulty"]');
  if (!input) return;
  state.difficulty = parseInt(input.value, 10) || 1;
  input.addEventListener('input', e => {
    state.difficulty = parseInt(e.target.value, 10);
    scheduleDraftSave();
  });
}

// visibility report - optional, on step two
function visibilityIsSet() {
  return state.visibilityValue !== '' && state.visibilityValue !== null
      && state.visibilityValue !== undefined;
}

function bindVisibilityReport() {
  const form = document.getElementById('vis-create-form');
  if (!form) return;
  const slider  = document.getElementById('vis-create-slider');
  const date    = document.getElementById('vis-create-date');
  const comment = document.getElementById('vis-create-comment');
  const clear   = document.getElementById('vis-create-clear');

  // slider - browsers restore range values, so set it from state
  slider.value = state.visibilityValue || 0;

  slider.addEventListener('input', e => {
    state.visibilityValue = e.target.value;
    if (!state.visibilityDate) {
      state.visibilityDate = new Date().toISOString().slice(0, 10);
      date.value = state.visibilityDate;
    }
    syncVisibilityUI();
    scheduleDraftSave();
  });

  date.addEventListener('change', () => clearFieldError('err-visibility'));

  clear.addEventListener('click', () => {
    state.visibilityValue = '';
    state.visibilityDate = '';
    state.visibilityComment = '';
    slider.value = 0;
    date.value = '';
    comment.value = '';
    clearFieldError('err-visibility');
    syncVisibilityUI();
    scheduleDraftSave();
  });

  syncVisibilityUI();
}

function syncVisibilityUI() {
  const form = document.getElementById('vis-create-form');
  if (!form) return;
  const set = visibilityIsSet();
  form.classList.toggle('vis-report-form--untouched', !set);
  const hint = document.getElementById('vis-create-hint');
  if (hint) {
    hint.textContent = set
      ? `Reporting roughly ${formatVisibilityMetres(state.visibilityValue)} of visibility`
      : 'Drag the slider to add a report';
  }
}

function formatVisibilityMetres(value) {
  const v = parseFloat(value);
  if (isNaN(v)) return '';
  return v >= 12 ? '12m or more' : `${v}m`;
}

function validateVisibilityDate(dateVal) {
  if (!dateVal) return 'Please add the date you snorkelled here.';
  const date   = new Date(dateVal); date.setHours(0, 0, 0, 0);
  const today  = new Date();        today.setHours(0, 0, 0, 0);
  const oldest = new Date(today.getTime() - VIS_MAX_AGE_DAYS * 24 * 60 * 60 * 1000);
  if (isNaN(date.getTime())) return 'Please add a valid date.';
  if (date > today)          return 'The date cannot be in the future.';
  if (date < oldest)         return `Reports must be for a date within the last ${VIS_MAX_AGE_DAYS} days.`;
  return null;
}

// alternate names - add and remove extra names
function bindAltNameModal() {
  const openBtn = document.getElementById('alt-name-open');
  const modal   = document.getElementById('alt-name-modal');
  if (!openBtn || !modal) return;

  const input    = document.getElementById('alt-name-modal-input');
  const addBtn   = document.getElementById('alt-name-modal-add');
  const closeBtn = document.getElementById('alt-name-modal-close');
  const overlay  = document.getElementById('alt-name-modal-overlay');

  function open() {
    modal.removeAttribute('inert');
    modal.classList.add('sm-modal--visible');
    input.value = '';
    requestAnimationFrame(() => input.focus());
  }
  function close() {
    modal.classList.remove('sm-modal--visible');
    modal.setAttribute('inert', '');
    openBtn.focus();
  }
  function commit() {
    const val = input.value.trim();
    if (!val) { close(); return; }
    if (!state.alternateNames.includes(val)) {
      state.alternateNames.push(val);
      renderAlternateNames();
      scheduleDraftSave();
    }
    close();
  }

  openBtn.addEventListener('click', open);
  addBtn.addEventListener('click', commit);
  closeBtn.addEventListener('click', close);
  overlay.addEventListener('click', close);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter')  { e.preventDefault(); commit(); }
    if (e.key === 'Escape') { e.preventDefault(); close(); }
  });
}

function renderAlternateNames() {
  const list = document.getElementById('alt-names-list');
  if (!list) return;
  list.innerHTML = '';
  state.alternateNames.forEach((name, i) => {
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.textContent = name;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'tag__remove';
    remove.setAttribute('aria-label', `Remove ${name}`);
    remove.innerHTML = '<svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 2l6 6M8 2l-6 6"/></svg>';
    remove.addEventListener('click', () => {
      state.alternateNames.splice(i, 1);
      renderAlternateNames();
      scheduleDraftSave();
    });
    tag.appendChild(remove);
    list.appendChild(tag);
  });
}

// parking - yes reveals the type chips, none hides them
function bindParking() {
  const wrap = document.getElementById('parking-available-chips');
  if (!wrap) return;
  wrap.querySelectorAll('.chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const value = btn.dataset.parkingAvailable;
      state.parkingAvailable = state.parkingAvailable === value ? '' : value;
      if (state.parkingAvailable !== 'yes') state.facParking.clear();
      syncParkingUI();
      scheduleDraftSave();
    });
  });
  syncParkingUI();
}

function syncParkingUI() {
  const availWrap = document.getElementById('parking-available-chips');
  const typeWrap  = document.getElementById('parking-type-chips');
  if (!availWrap || !typeWrap) return;
  availWrap.querySelectorAll('.chip').forEach(btn => {
    btn.classList.toggle('chip--active', btn.dataset.parkingAvailable === state.parkingAvailable);
  });
  typeWrap.style.display = state.parkingAvailable === 'yes' ? '' : 'none';
  typeWrap.querySelectorAll('.chip').forEach(btn => {
    btn.classList.toggle('chip--active', state.facParking.has(btn.dataset.id));
  });
}

// step three - upload media
function initFileUploads() {
  document.querySelectorAll('[data-media-key]').forEach(section => {
    const key  = section.dataset.mediaKey;
    const zone = section.querySelector('.drop-zone');
    const input = section.querySelector('.drop-zone__input');
    if (!zone || !input) return;

    zone.addEventListener('click', e => { if (e.target !== input) input.click(); });
    input.addEventListener('change', () => {
      handleFiles(Array.from(input.files), key);
      setTimeout(() => { input.value = ''; }, 0);
    });
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drop-zone--dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drop-zone--dragover'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('drop-zone--dragover');
      // file type - heic often arrives with an empty type, so do not filter
      handleFiles(Array.from(e.dataTransfer.files), key);
    });
  });
}

function photoListFor(type) {
  return type === 'aboveWater' ? state.aboveWaterPhotos : state.underwaterPhotos;
}

function photoGridFor(type) {
  const section = document.querySelector(`[data-media-key="${type}"]`);
  return section ? section.querySelector('.photo-grid') : null;
}

// manifest entry - what the browser claims about one photo
function mediaManifestEntry(photo, section) {
  return {
    clientId: photo.id,
    section,
    mime: photo.mime,
    bytes: photo.bytes,
    width: photo.width,
    height: photo.height,
    capturedAt: photo.capturedAt,
    capturedAtOffset: photo.capturedAtOffset,
    latitude: photo.latitude,
    longitude: photo.longitude,
    description: photo.description || '',
  };
}

function rejectListFor(type) {
  const section = document.querySelector(`[data-media-key="${type}"]`);
  return section ? section.querySelector('.media-rejects') : null;
}

function showRejects(type, messages) {
  const list = rejectListFor(type);
  if (!list) return;
  list.innerHTML = '';
  messages.forEach(message => {
    const li = document.createElement('li');
    li.className = 'media-rejects__item';
    li.textContent = message;
    list.appendChild(li);
  });
  list.hidden = messages.length === 0;
}

// one at a time - reading exif from a dozen photos at once stalls a phone
async function handleFiles(files, type) {
  if (!files.length) return;
  const limits   = SMMedia.rules().limits;
  const messages = SMMedia.rules().messages;
  const list     = photoListFor(type);
  const rejected = [];

  setDropZoneBusy(type, true);
  try {
    for (const file of files) {
      if (list.length >= limits.max_files_per_section) {
        rejected.push(SMMedia.fill(messages.too_many_files, {
          max: limits.max_files_per_section,
          name: file.name || 'That file',
        }));
        break;
      }

      const result = await SMMedia.validateFile(file);
      if (!result.ok) { rejected.push(result.message); continue; }

      const photo = {
        id: `photo-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        file: result.file,
        name: result.name,
        mime: result.mime,
        extension: result.extension,
        bytes: result.bytes,
        width: result.width,
        height: result.height,
        previewable: result.previewable,
        capturedAt: result.capturedAt,
        capturedAtOffset: result.capturedAtOffset,
        latitude: result.latitude,
        longitude: result.longitude,
        description: '',
      };
      list.push(photo);
      renderPhotoGrid(type);
      clearFieldError('err-photos');

      try { await persistPhoto(photo, type); }
      catch (err) { console.warn('Could not store photo:', err); }
      scheduleDraftSave();
    }
  } finally {
    setDropZoneBusy(type, false);
  }

  showRejects(type, rejected);
}

function setDropZoneBusy(type, busy) {
  const section = document.querySelector(`[data-media-key="${type}"]`);
  const zone = section && section.querySelector('.drop-zone');
  if (zone) zone.classList.toggle('drop-zone--busy', busy);
}

// object urls - held on the record and revoked with the tile
function previewUrlFor(photo) {
  if (!photo.previewable) return null;
  if (!photo.objectUrl) photo.objectUrl = URL.createObjectURL(photo.file);
  return photo.objectUrl;
}

function releasePreviewUrl(photo) {
  if (photo.objectUrl) {
    URL.revokeObjectURL(photo.objectUrl);
    photo.objectUrl = null;
  }
}

function photoMetaLine(photo) {
  const parts = [`${photo.width} x ${photo.height}`, SMMedia.formatBytes(photo.bytes)];
  if (photo.capturedAt) {
    const date = new Date(photo.capturedAt);
    if (!isNaN(date.getTime())) {
      parts.push(date.toLocaleDateString('en-GB', {
        day: 'numeric', month: 'short', year: 'numeric',
      }));
    }
  }
  return parts.join(' · ');
}

function renderPhotoGrid(type) {
  const grid = photoGridFor(type);
  if (!grid) return;
  grid.innerHTML = '';
  photoListFor(type).forEach(photo => {
    const item = document.createElement('div');
    item.className = 'photo-item';
    item.innerHTML = `
      <div class="photo-item__img-wrap">
        <img class="photo-item__img" alt="Uploaded photo" hidden>
        <div class="photo-item__placeholder" hidden>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="10.5" r="1.5"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 16l-5-5-4 4-2-2-4 4"/></svg>
          <p class="photo-item__placeholder-name"></p>
          <p class="photo-item__placeholder-note"></p>
        </div>
        <button class="photo-item__remove" type="button" aria-label="Remove photo">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M2 2l10 10M12 2L2 12"/></svg>
        </button>
      </div>
      <div class="photo-item__caption">
        <p class="photo-item__meta"></p>
        <label class="photo-item__label">Describe what is in the picture</label>
        <input type="text" class="photo-item__desc" placeholder="e.g. View of the entry point from the beach">
      </div>`;

    const img         = item.querySelector('.photo-item__img');
    const placeholder = item.querySelector('.photo-item__placeholder');
    const url         = previewUrlFor(photo);

    if (url) {
      img.src = url;
      img.hidden = false;
    } else {
      // heic - no decoder here, so the thumbnail waits for cloudflare
      placeholder.querySelector('.photo-item__placeholder-name').textContent = photo.name;
      placeholder.querySelector('.photo-item__placeholder-note').textContent =
        SMMedia.rules().messages.no_preview;
      placeholder.hidden = false;
    }

    item.querySelector('.photo-item__meta').textContent = photoMetaLine(photo);

    const descInput = item.querySelector('.photo-item__desc');
    descInput.value = photo.description || '';
    descInput.addEventListener('input', e => { photo.description = e.target.value; scheduleDraftSave(); });
    item.querySelector('.photo-item__remove').addEventListener('click', () => removePhoto(photo.id, type));
    grid.appendChild(item);
  });
}

async function removePhoto(id, type) {
  const list = photoListFor(type);
  const photo = list.find(p => p.id === id);
  if (photo) releasePreviewUrl(photo);

  if (type === 'aboveWater') state.aboveWaterPhotos = state.aboveWaterPhotos.filter(p => p.id !== id);
  else                       state.underwaterPhotos = state.underwaterPhotos.filter(p => p.id !== id);
  renderPhotoGrid(type);
  try { await deletePhotoFromIndexedDB(id); }
  catch (e) { console.warn('Could not delete stored photo:', e); }
  scheduleDraftSave();
}

// indexeddb - photo storage for drafts
function openPhotoDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = e => {
      const db = e.target.result;
      // version one - old records held data urls, nothing worth migrating
      if (db.objectStoreNames.contains(PHOTO_STORE)) {
        db.deleteObjectStore(PHOTO_STORE);
      }
      const store = db.createObjectStore(PHOTO_STORE, { keyPath: 'id' });
      store.createIndex('submissionId', 'submissionId', { unique: false });
    };
    request.onsuccess = e => resolve(e.target.result);
    request.onerror   = e => reject(e.target.error);
  });
}

function savePhotoToIndexedDB(db, photo, type) {
  return new Promise((resolve, reject) => {
    const store = db.transaction(PHOTO_STORE, 'readwrite').objectStore(PHOTO_STORE);
    const req = store.put({
      id: photo.id,
      submissionId: SUBMISSION_ID,
      type,
      file: photo.file,
      name: photo.name,
      mime: photo.mime,
      extension: photo.extension,
      bytes: photo.bytes,
      width: photo.width,
      height: photo.height,
      previewable: photo.previewable,
      capturedAt: photo.capturedAt,
      capturedAtOffset: photo.capturedAtOffset,
      latitude: photo.latitude,
      longitude: photo.longitude,
      description: photo.description,
      createdAt: new Date().toISOString(),
    });
    req.onsuccess = () => resolve();
    req.onerror   = e => reject(e.target.error);
  });
}

async function persistPhoto(photo, type) {
  const db = await openPhotoDB();
  return savePhotoToIndexedDB(db, photo, type);
}

function deletePhotoFromIndexedDB(id) {
  return openPhotoDB().then(db => new Promise((resolve, reject) => {
    const req = db.transaction(PHOTO_STORE, 'readwrite').objectStore(PHOTO_STORE).delete(id);
    req.onsuccess = () => resolve();
    req.onerror   = e => reject(e.target.error);
  }));
}

function getPhotosForSubmission(db, submissionId) {
  return new Promise((resolve, reject) => {
    const index = db.transaction(PHOTO_STORE, 'readonly').objectStore(PHOTO_STORE).index('submissionId');
    const req = index.getAll(submissionId);
    req.onsuccess = () => resolve(req.result || []);
    req.onerror   = e => reject(e.target.error);
  });
}

async function deletePhotosForSubmission(submissionId) {
  const db = await openPhotoDB();
  const records = await getPhotosForSubmission(db, submissionId);
  await Promise.all(records.map(r => deletePhotoFromIndexedDB(r.id)));
}

// payload - nesting comes from data-payload-group and data-payload-key
function getStateJSON() {
  const payload = {
    submissionId: SUBMISSION_ID,
    coordinates:  state.coordinates,
    locationMeta: state.locationMeta,
    name:         state.name,
    alternateNames:        state.alternateNames,
    description:           state.description,
    entryPointDescription: state.entryPointDescription,
    accessType: [...state.accessType],
    waterType:  [...state.waterType],
    difficulty: state.difficulty,
    environmentTypes: {},
    marineLife: { comments: state.marineLifeComments || '' },
    hazards:    { comments: state.hazardsComments || '' },
    facilities: {
      gettingThere: {
        comments: state.gettingThereComments || '',
        parking: {
          available: state.parkingAvailable,
          selected:  [...state.facParking],
          comments:  state.facParkingComments || '',
        },
        transport: {
          selected:    [...state.facTransport],
          description: state.facTransportDescription || '',
        },
      },
      other: state.facOther || '',
    },
    visibility: visibilityIsSet()
      ? {
          value:   parseFloat(state.visibilityValue),
          date:    state.visibilityDate,
          comment: state.visibilityComment || '',
        }
      : null,
    // media - the manifest only, the bytes follow on presigned urls
    media: [
      ...state.aboveWaterPhotos.map(p => mediaManifestEntry(p, 'aboveWater')),
      ...state.underwaterPhotos.map(p => mediaManifestEntry(p, 'underwater')),
    ],
    locationMarkerData: window.locationMarkerMapData
      ? JSON.parse(JSON.stringify(window.locationMarkerMapData))
      : { type: 'FeatureCollection', features: [] },
  };

  GROUPS.forEach(group => {
    if (!group.payloadGroup || !group.payloadKey) return;
    const selected = [...(state[group.key] || [])];
    const commentKey = `${group.key}Comments`;
    const target = payload[group.payloadGroup];
    if (!target) return;
    // group shape - with a comment box or a bare list of ids
    target[group.payloadKey] = TEXT_KEYS.includes(commentKey)
      ? { selected, comments: state[commentKey] || '' }
      : selected;
  });

  return payload;
}

// publish - walks the progress list and posts the submission
const PUBLISH_STAGES = ['validate', 'location', 'media', 'finalise'];

function bindPublish() {
  const publishBtn = document.getElementById('publish-btn');
  if (!publishBtn) return;

  publishBtn.addEventListener('click', () => {
    // recheck - earlier steps, before a screen they cannot back out of
    if (!validateStep(2))          { goToStep(2); return; }
    if (!validateStep(STEP_MEDIA)) { goToStep(STEP_MEDIA); return; }
    startPublish();
  });

  const retry = document.getElementById('publish-retry');
  if (retry) retry.addEventListener('click', () => startPublish());

  const back = document.getElementById('publish-back');
  if (back) back.addEventListener('click', () => {
    // after failure - the guards come off
    publishInFlight = false;
    navigationLocked = false;
    goToStep(STEP_LOCMAP);
  });
}

function startPublish() {
  const nameEl = document.getElementById('publish-location-name');
  if (nameEl) nameEl.textContent = state.name || 'your location';

  resetPublishProgress();
  publishInFlight = true;
  navigationLocked = true;
  goToStep(STEP_PUBLISH);
  runPublish();
}

function resetPublishProgress() {
  document.querySelectorAll('.publish-progress__item').forEach(item => {
    item.classList.remove('publish-progress__item--active',
                          'publish-progress__item--done',
                          'publish-progress__item--failed');
    const detail = item.querySelector('.publish-progress__detail');
    if (detail) detail.textContent = '';
  });
  const err = document.getElementById('publish-error');
  if (err) err.hidden = true;
  const status = document.getElementById('publish-status-line');
  if (status) status.hidden = false;
}

function setStage(stage, status, detail) {
  const item = document.querySelector(`.publish-progress__item[data-stage="${stage}"]`);
  if (!item) return;
  item.classList.toggle('publish-progress__item--active', status === 'active');
  item.classList.toggle('publish-progress__item--done',   status === 'done');
  item.classList.toggle('publish-progress__item--failed', status === 'failed');
  const detailEl = item.querySelector('.publish-progress__detail');
  if (detailEl && detail !== undefined) detailEl.textContent = detail;
}

function publishFailed(message) {
  publishInFlight = false;          // unload - no longer warranted
  const err = document.getElementById('publish-error');
  const txt = document.getElementById('publish-error-text');
  const status = document.getElementById('publish-status-line');
  if (txt) txt.textContent = message;
  if (err) err.hidden = false;
  if (status) status.hidden = true;
}

const SUBMISSION_ENDPOINT = '/api/v1/locations/submissions';
const CONFIRM_ENDPOINT = uuid => `/api/v1/locations/media/${uuid}/confirm`;
const UPLOAD_ATTEMPTS = 3;
// retry - only on answers that can differ a second time
const RETRYABLE_STATUSES = new Set([408, 429, 500, 502, 503, 504, 507]);

// submission - sent once, the id makes a retry safe
let publishedUrl = null;

async function runPublish() {
  const payload = getStateJSON();
  publishedUrl = null;

  try {
    setStage('validate', 'active');
    const photos = allPhotos();
    setStage('validate', 'done', `${photos.length} photo${photos.length === 1 ? '' : 's'} ready`);

    setStage('location', 'active');
    const response = await fetch(SUBMISSION_ENDPOINT, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const problem = await response.json().catch(() => ({}));
      throw new PublishError(problem.detail
        || 'The listing could not be saved. Nothing has been lost.');
    }

    const result = await response.json();
    publishedUrl = result.url || null;
    setStage('location', 'done', 'Saved');

    // photos
    const uploads = result.uploads || [];
    let outcome = null;
    let refused = 0;

    if (!uploads.length) {
      setStage('media', 'done', 'No photos to upload');
    } else {
      let done = 0;
      setStage('media', 'active', `0 of ${uploads.length}`);
      for (const slot of uploads) {
        const photo = photos.find(p => p.id === slot.clientId);
        if (!photo) continue;

        await uploadPhoto(slot, photo);
        done += 1;
        setStage('media', 'active', `${done} of ${uploads.length}`);

        // verify - tell the server to look now rather than waiting
        const checked = await confirmUpload(slot);
        if (checked) {
          outcome = checked;
          if (!checked.verified) refused += 1;
        }
      }
      setStage('media', 'done',
        refused ? `${done} uploaded, ${refused} could not be used`
                : `${done} uploaded`);
    }

    setStage('finalise', 'active');
    // published - the server looked at the photograph, the browser did not
    setStage('finalise', 'done',
      outcome && outcome.published ? 'Published' : 'Checks running');

    finishPublish((outcome && outcome.url) || result.url);
  } catch (e) {
    console.error('Publish failed:', e);

    // created - nothing to resubmit, so send them to the listing
    if (publishedUrl) {
      setStage('media', 'failed');
      finishPublish(publishedUrl, e instanceof PublishError ? e.message : '');
      return;
    }

    publishFailed(e instanceof PublishError ? e.message
      : 'Something went wrong while publishing. Your entry has not been lost.');
  }
}

class PublishError extends Error {}

// verify one - the server reads the object back out of the bucket
async function confirmUpload(slot) {
  try {
    const response = await fetch(CONFIRM_ENDPOINT(slot.mediaUuid), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrfToken() },
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (e) {
    console.warn('Could not confirm upload', e);
    return null;
  }
}

function allPhotos() {
  return [...state.aboveWaterPhotos, ...state.underwaterPhotos];
}

// upload - one file into r2, straight from the browser
async function uploadPhoto(slot, photo) {
  let lastError = null;

  for (let attempt = 1; attempt <= UPLOAD_ATTEMPTS; attempt++) {
    try {
      let response;
      if (slot.method === 'put') {
        response = await fetch(slot.url, {
          method: 'PUT',
          headers: slot.headers || {},
          body: photo.file,
        });
      } else {
        const form = new FormData();
        Object.entries(slot.fields || {}).forEach(([k, v]) => form.append(k, v));
        form.append('file', photo.file, `${slot.mediaUuid}`);
        response = await fetch(slot.url, { method: 'POST', body: form });
      }
      if (response.ok) return;
      // transient - a refused signature will be refused again
      if (!RETRYABLE_STATUSES.has(response.status)) {
        throw new PublishError(
          `${photo.name} was refused by the photo store (${response.status}).`);
      }
      lastError = new Error(`upload failed with ${response.status}`);
    } catch (e) {
      if (e instanceof PublishError) throw e;
      lastError = e;
    }
    await new Promise(r => setTimeout(r, 400 * attempt));
  }

  throw new PublishError(`${photo.name} did not finish uploading.`);
}

function finishPublish(listingUrl, problem) {
  publishInFlight = false;   // saved, so leaving is safe
  clearDraft();              // the draft has served its purpose

  const nameDisplay = document.getElementById('thankyou-location-name');
  if (nameDisplay) nameDisplay.textContent = state.name || 'Your Location';

  // path - as the server built it, hide the button if missing
  const viewBtn = document.getElementById('view-location-btn');
  if (viewBtn) {
    if (listingUrl) {
      viewBtn.href = listingUrl;
      viewBtn.hidden = false;
    } else {
      viewBtn.hidden = true;
    }
  }

  // missing photo - the location is saved, say so plainly
  const notice = document.getElementById('thankyou-notice');
  const noticeText = document.getElementById('thankyou-notice-text');
  if (notice && noticeText) {
    if (problem) {
      noticeText.textContent = problem
        + ' Your location is saved and you can add the photo to it at any time.';
      notice.hidden = false;
    } else {
      notice.hidden = true;
    }
  }

  // locked - the form behind this is not worth returning to
  goToStep(STEP_THANKYOU);
}

// modal - content comes from the examples partial
function bindModal() {
  const overlay = document.getElementById('modal-overlay');
  const close   = document.getElementById('modal-close');
  if (overlay) overlay.addEventListener('click', hideModal);
  if (close)   close.addEventListener('click', hideModal);

  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    const alt = document.getElementById('alt-name-modal');
    if (alt && alt.classList.contains('sm-modal--visible')) return;
    hideModal();
  });

  document.querySelectorAll('[data-example]').forEach(btn => {
    if (btn.closest('#example-content')) return;   // the content blocks themselves
    btn.addEventListener('click', () => showExample(btn.dataset.example));
  });
}

function showExample(key) {
  const block = document.querySelector(`#example-content .sm-example[data-example="${key}"]`);
  if (!block) { console.warn(`No example block for "${key}" in the examples partial`); return; }
  showModal(block.dataset.title || 'Example', block.innerHTML);
}
window.smShowExample = showExample;

function showModal(title, bodyHTML) {
  const modal = document.getElementById('example-modal');
  if (!modal) return;
  modal.removeAttribute('inert');
  modal.classList.add('sm-modal--visible');
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = bodyHTML;
  requestAnimationFrame(() => document.getElementById('modal-close').focus());
}
window.smShowModal = showModal;

function hideModal() {
  const modal = document.getElementById('example-modal');
  if (!modal) return;
  modal.classList.remove('sm-modal--visible');
  modal.setAttribute('inert', '');
}
