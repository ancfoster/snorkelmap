/* ═══════════════════════════════════════════════════════════════════
   SnorkelMap — edit.js

   Editing a listing that already exists.

   Two objects, and the whole file is organised around them. ORIGINAL is
   the listing exactly as the server rendered it, frozen; WORKING is what
   the person is proposing. Nothing ever writes to ORIGINAL, so "has
   anything changed" and "put it back as it was" are both answerable at
   any moment without asking the server again.

   The map is not ours. marker_map.js does the markers, the drawer and
   the note overlay, and reads MAPBOX_TOKEN, MARKER_ICON_BASE and
   state.coordinates out of the surrounding scope: on the create page
   create.js provides those, and here this file does. Its live feature
   collection is window.locationMarkerMapData, and it calls
   window.smScheduleDraftSave on every change, which is how the cancel
   button knows to come alive.
   ═══════════════════════════════════════════════════════════════════ */

function readJSONScript(id, fallback) {
  const el = document.getElementById(id);
  if (!el) return fallback;
  try { return JSON.parse(el.textContent); }
  catch (error) { return fallback; }
}

// marker_map.js reads all three of these by name.
const MAPBOX_TOKEN     = readJSONScript('mapbox-token', null);
const MARKER_ICON_BASE = readJSONScript('marker-icon-base', '/static/images/sm-map-icons/');
const state = { coordinates: readJSONScript('edit-coordinates', null) };

const ORIGINAL = deepFreeze(readJSONScript('edit-original', {}));
const WORKING  = clone(ORIGINAL);

const SUMMARY_MAX = 300;

// A JSON round trip rather than structuredClone, and not as a matter
// of taste: marker_map.js hangs a refreshIcon function off every
// feature it draws, and structuredClone throws on a function. This
// drops them, which is exactly what is wanted, since what goes to the
// server is JSON anyway.
function clone(value) {
  return value === undefined ? value : JSON.parse(JSON.stringify(value));
}

function deepFreeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

function same(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

// ── What is on the page ─────────────────────────────────────────────

const GROUPS = new Map();   // state key → how that group behaves

function readGroups() {
  document.querySelectorAll('[data-group-key]').forEach(el => {
    GROUPS.set(el.dataset.groupKey, {
      key: el.dataset.groupKey,
      element: el,
      noneId: el.dataset.noneOption === 'true' ? 'none' : null,
      singleSelect: el.dataset.singleSelect === 'true',
      payloadGroup: el.dataset.payloadGroup || null,
      payloadKey: el.dataset.payloadKey || null,
    });
  });
}

function listFor(key) {
  if (!Array.isArray(WORKING[key])) WORKING[key] = [];
  return WORKING[key];
}

// ── Putting the listing into the form ───────────────────────────────

function fillForm() {
  document.querySelectorAll('[data-field]').forEach(el => {
    const key = el.dataset.field;
    if (!(key in WORKING)) return;
    el.value = WORKING[key];
  });

  document.querySelectorAll('.chip[data-state-key]').forEach(chip => {
    const chosen = listFor(chip.dataset.stateKey);
    chip.classList.toggle('chip--active', chosen.includes(chip.dataset.id));
  });

  document.querySelectorAll('[data-parking-available]').forEach(chip => {
    chip.classList.toggle('chip--active',
      chip.dataset.parkingAvailable === WORKING.parkingAvailable);
  });

  renderAltNames();
  refreshSummaryCounter();
  refreshMarkerCount();
}

// ── Chips ───────────────────────────────────────────────────────────

function bindChips() {
  document.addEventListener('click', event => {
    const chip = event.target.closest('.chip[data-state-key]');
    if (chip) { toggleChip(chip); return; }

    const parking = event.target.closest('[data-parking-available]');
    if (parking) { chooseParking(parking); }
  });
}

function toggleChip(chip) {
  const key = chip.dataset.stateKey;
  const id = chip.dataset.id;
  const group = GROUPS.get(key) || {};
  let chosen = listFor(key);

  const isNone = id === group.noneId;

  if (isNone || group.singleSelect) {
    chosen = chosen.includes(id) ? [] : [id];
  } else if (chosen.includes(id)) {
    chosen = chosen.filter(other => other !== id);
  } else {
    // Water type: picking from the other group replaces the answer
    // rather than being refused, so a wrong first tap is never a dead
    // end. Same behaviour as the create form.
    if (chip.dataset.waterGroup) {
      const active = document.querySelector('#chips-waterType .chip--active');
      if (active && active.dataset.waterGroup !== chip.dataset.waterGroup) {
        chosen = [];
      }
    }
    chosen = chosen.filter(other => other !== group.noneId).concat(id);
  }

  WORKING[key] = chosen;
  document.querySelectorAll(`.chip[data-state-key="${key}"]`).forEach(el => {
    el.classList.toggle('chip--active', chosen.includes(el.dataset.id));
  });
  refreshSaveState();
}

function chooseParking(chip) {
  const id = chip.dataset.parkingAvailable;
  WORKING.parkingAvailable = WORKING.parkingAvailable === id ? '' : id;
  document.querySelectorAll('[data-parking-available]').forEach(el => {
    el.classList.toggle('chip--active',
      el.dataset.parkingAvailable === WORKING.parkingAvailable);
  });
  refreshSaveState();
}

// ── Text, numbers and the counter ───────────────────────────────────

function bindFields() {
  document.addEventListener('input', event => {
    const el = event.target.closest('[data-field]');
    if (!el) return;
    WORKING[el.dataset.field] = el.dataset.fieldType === 'int'
      ? parseInt(el.value, 10) || 1
      : el.value;
    if (el.dataset.field === 'revisionComment') refreshSummaryCounter();
    refreshSaveState();
  });
}

function refreshSummaryCounter() {
  const box = document.getElementById('edit-summary');
  const counter = document.getElementById('summary-counter');
  if (!box || !counter) return;
  counter.textContent = `${box.value.length}/${SUMMARY_MAX}`;
  counter.classList.toggle('edit-form__counter--over', box.value.length > SUMMARY_MAX);
}

// ── Alternate names ─────────────────────────────────────────────────

function renderAltNames() {
  const list = document.getElementById('edit-alt-names');
  if (!list) return;
  list.replaceChildren();

  (WORKING.alternateNames || []).forEach((name, index) => {
    const tag = document.createElement('span');
    tag.className = 'alt-names__tag';

    // textContent rather than innerHTML: this is somebody else's text
    // and it is going back into the page.
    const label = document.createElement('span');
    label.textContent = name;

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'alt-names__remove';
    remove.setAttribute('aria-label', `Remove ${name}`);
    remove.textContent = '×';
    remove.addEventListener('click', () => {
      WORKING.alternateNames.splice(index, 1);
      renderAltNames();
      refreshSaveState();
    });

    tag.append(label, remove);
    list.append(tag);
  });
}

function bindAltNames() {
  const input = document.getElementById('edit-alt-name-input');
  const add = document.getElementById('edit-alt-name-add');
  if (!input || !add) return;

  function commit() {
    const name = input.value.trim();
    if (!name) return;
    if (!Array.isArray(WORKING.alternateNames)) WORKING.alternateNames = [];
    if (!WORKING.alternateNames.includes(name)) WORKING.alternateNames.push(name);
    input.value = '';
    renderAltNames();
    refreshSaveState();
  }

  add.addEventListener('click', commit);
  input.addEventListener('keydown', event => {
    // Otherwise the form submits, which is not what adding a name means.
    if (event.key === 'Enter') { event.preventDefault(); commit(); }
  });
}

// ── Sections ────────────────────────────────────────────────────────

function bindSections() {
  document.querySelectorAll('.edit-section__toggle').forEach(toggle => {
    toggle.addEventListener('click', () => {
      const body = document.getElementById(toggle.getAttribute('aria-controls'));
      if (!body) return;
      const open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', open ? 'false' : 'true');
      body.hidden = open;
      toggle.closest('.edit-section').classList.toggle('edit-section--open', !open);
    });
  });
}

// ── The map ─────────────────────────────────────────────────────────

let markersTouched = false;
// Putting the markers back is done by adding each one again, and
// marker_map.js reports every one of those as a change. It is not one,
// so it is not counted as one.
let restoringMarkers = false;

// marker_map.js calls this on every change it makes: a marker added,
// moved, deleted, or its note edited. It is the only signal needed.
window.smScheduleDraftSave = function () {
  if (!restoringMarkers) markersTouched = true;
  WORKING.markerData = clone(window.locationMarkerMapData);
  refreshMarkerButtons();
  refreshMarkerCount();
  refreshSaveState();
};

function markerFeatures(data) {
  return (data && Array.isArray(data.features)) ? data.features : [];
}

function refreshMarkerCount() {
  const count = document.getElementById('marker-count');
  const line = document.getElementById('marker-count-line');
  if (!count) return;
  const total = markerFeatures(WORKING.markerData).length;
  count.textContent = String(total);
  if (line) {
    line.lastChild.textContent =
      total === 1 ? ' marker on the map at the moment'
                  : ' markers on the map at the moment';
  }
}

function markersDiffer() {
  return !same(markerFeatures(WORKING.markerData),
               markerFeatures(ORIGINAL.markerData));
}

function refreshMarkerButtons() {
  const cancel = document.getElementById('marker-cancel');
  if (!cancel) return;
  // Live from the first change onwards, and stays live across the modal
  // being closed and opened again: what it undoes is everything back to
  // how the page loaded, not back to how this visit to the map started.
  cancel.disabled = !markersDiffer();
}

function openMarkerModal() {
  const modal = document.getElementById('marker-modal');
  if (!modal) return;
  modal.hidden = false;
  document.body.style.overflow = 'hidden';

  if (typeof initAnnotationMap === 'function') {
    // The container has only just been given a size, so the map is
    // built after the browser has laid it out rather than into a box
    // that is still zero by zero.
    requestAnimationFrame(() => {
      initAnnotationMap();
      if (!markersTouched) restoreMarkers(WORKING.markerData);
      if (typeof locationMarkerMap !== 'undefined' && locationMarkerMap) {
        locationMarkerMap.resize();
      }
    });
  }
  refreshMarkerButtons();
}

function closeMarkerModal() {
  const modal = document.getElementById('marker-modal');
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  document.body.style.overflow = '';
}

function restoreMarkers(data) {
  restoringMarkers = true;
  // The markers on the map are plain elements that marker_map.js made,
  // so taking them out of the page takes them off the map. The feature
  // collection is then emptied and rebuilt through marker_map.js's own
  // restore path, which is what wires each new marker up again.
  document.querySelectorAll('#sm-annotate-map-cont__map .map-marker')
    .forEach(el => el.remove());
  if (window.locationMarkerMapData) {
    window.locationMarkerMapData.features.length = 0;
  }
  window.smPendingMarkerFeatures = clone(markerFeatures(data));
  try {
    if (typeof restorePendingMarkers === 'function') restorePendingMarkers();
  } finally {
    restoringMarkers = false;
  }
  WORKING.markerData = clone(data);
}

function cancelMarkerChanges() {
  restoreMarkers(ORIGINAL.markerData);
  markersTouched = false;
  refreshMarkerButtons();
  refreshMarkerCount();
  refreshSaveState();
}

function bindMarkerModal() {
  const open = document.getElementById('open-marker-map');
  const close = document.getElementById('marker-close');
  const cancel = document.getElementById('marker-cancel');

  if (open) open.addEventListener('click', openMarkerModal);
  if (close) close.addEventListener('click', closeMarkerModal);
  if (cancel) cancel.addEventListener('click', cancelMarkerChanges);

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const modal = document.getElementById('marker-modal');
    // The note overlay is on top of the map and closes first.
    const note = document.querySelector('.note-overlay');
    if (note && !note.classList.contains('hidden')) return;
    if (modal && !modal.hidden) closeMarkerModal();
  });
}

// ── Has anything changed ────────────────────────────────────────────

// The change summary is about the edit rather than part of it, so
// writing one on its own is not a change to the listing.
function changed() {
  return Object.keys(ORIGINAL).some(key => !same(WORKING[key], ORIGINAL[key]));
}

function refreshSaveState() {
  const save = document.getElementById('edit-save');
  renderChanges();
  if (!save) return;
  save.disabled = !changed();
}

// ── What is about to be published ───────────────────────────────────

// The fields that are one thing each, and what to call them in a
// sentence. Everything else is a chip group, and takes its name from
// the heading above it on the page, so the two cannot disagree.
const FIELD_LABELS = {
  name: 'the location name',
  description: 'the description',
  entryPointDescription: 'the entry point description',
  accessType: 'the access type',
  waterType: 'the water type',
  parkingAvailable: 'whether there is parking',
  facParking: 'the parking options',
  facTransport: 'the public transport options',
  marineLifeComments: 'the notes on marine life',
  hazardsComments: 'the notes on hazards',
  gettingThereComments: 'the notes on getting there',
  facParkingComments: 'the notes on parking',
  facTransportDescription: 'the public transport description',
  facOther: 'the note on other facilities',
};

function groupLabel(key) {
  const group = GROUPS.get(key);
  const heading = group && group.element
    && group.element.querySelector('.form-section__heading');
  return heading ? heading.textContent.trim() : null;
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
}

// Added, removed, or both. Phrased without counts, because "changed the
// access type" is what somebody wants to read and "added 1 option to
// the access type" is not.
function describeList(label, before, after) {
  const added = after.some(value => !before.includes(value));
  const removed = before.some(value => !after.includes(value));
  if (added && !removed) return `Added to ${label}`;
  if (removed && !added) return `Removed from ${label}`;
  return `Changed ${label}`;
}

function describeMarkers(before, after) {
  const was = markerFeatures(before).length;
  const now = markerFeatures(after).length;
  if (now > was) return `Added ${plural(now - was, 'map marker')}`;
  if (now < was) return `Removed ${plural(was - now, 'map marker')}`;
  return 'Moved or annotated the map markers';
}

function describeAlternateNames(before, after) {
  const added = after.filter(name => !before.includes(name)).length;
  const removed = before.filter(name => !after.includes(name)).length;
  if (added && !removed) return `Added ${plural(added, 'alternate name')}`;
  if (removed && !added) return `Removed ${plural(removed, 'alternate name')}`;
  return 'Changed the alternate names';
}

function difficultyLabel(value) {
  const labels = [...document.querySelectorAll('.difficulty-slider__label')];
  const label = labels[Number(value) - 1];
  return label ? label.textContent.trim() : String(value);
}

function describe(key) {
  const before = ORIGINAL[key];
  const after = WORKING[key];

  if (key === 'revisionComment') return null;   // about the edit, not the listing
  if (key === 'markerData') return describeMarkers(before, after);
  if (key === 'alternateNames') {
    return describeAlternateNames(before || [], after || []);
  }
  if (key === 'difficulty') {
    return `Changed the difficulty to ${difficultyLabel(after)}`;
  }

  // A chip group's comment box, named after the group it sits under.
  if (key.endsWith('Comments') && !(key in FIELD_LABELS)) {
    const label = groupLabel(key.slice(0, -'Comments'.length));
    return label ? `Updated the notes on ${label}` : null;
  }

  const label = FIELD_LABELS[key] || groupLabel(key);
  if (!label) return null;

  return Array.isArray(before) || Array.isArray(after)
    ? describeList(label, before || [], after || [])
    : `Updated ${label}`;
}

function changeList() {
  const keys = new Set([...Object.keys(ORIGINAL), ...Object.keys(WORKING)]);
  const lines = [];
  keys.forEach(key => {
    if (same(WORKING[key], ORIGINAL[key])) return;
    const line = describe(key);
    if (line && !lines.includes(line)) lines.push(line);
  });
  return lines;
}

function renderChanges() {
  const list = document.getElementById('change-list');
  const empty = document.getElementById('change-list-empty');
  if (!list) return;

  const lines = changeList();
  list.replaceChildren();
  lines.forEach(line => {
    const item = document.createElement('li');
    item.className = 'change-list__item';
    item.textContent = line;
    list.append(item);
  });
  if (empty) empty.hidden = lines.length > 0;
}

// ── Saving ──────────────────────────────────────────────────────────

function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) return meta.content;
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function buildPayload() {
  const payload = {
    name: WORKING.name || '',
    alternateNames: WORKING.alternateNames || [],
    description: WORKING.description || '',
    entryPointDescription: WORKING.entryPointDescription || '',
    accessType: WORKING.accessType || [],
    waterType: WORKING.waterType || [],
    difficulty: WORKING.difficulty || 1,
    environmentTypes: {},
    marineLife: { comments: WORKING.marineLifeComments || '' },
    hazards: { comments: WORKING.hazardsComments || '' },
    facilities: {
      gettingThere: {
        comments: WORKING.gettingThereComments || '',
        parking: {
          available: WORKING.parkingAvailable || null,
          selected: WORKING.facParking || [],
          comments: WORKING.facParkingComments || '',
        },
        transport: {
          selected: WORKING.facTransport || [],
          description: WORKING.facTransportDescription || '',
        },
      },
      other: WORKING.facOther || '',
    },
    locationMarkerData: WORKING.markerData
      || { type: 'FeatureCollection', features: [] },
    revisionComment: WORKING.revisionComment || '',
  };

  GROUPS.forEach(group => {
    if (!group.payloadGroup || !group.payloadKey) return;
    const target = payload[group.payloadGroup];
    if (!target) return;
    const selected = WORKING[group.key] || [];
    const commentKey = `${group.key}Comments`;
    // A group with a comment box reports { selected, comments }; one
    // without is the list of ids on its own. Whether it has one is
    // decided by whether a box for it exists, which is how the create
    // form decides it too.
    target[group.payloadKey] = (commentKey in WORKING)
      ? { selected, comments: WORKING[commentKey] || '' }
      : selected;
  });

  return payload;
}

function showError(message) {
  const box = document.getElementById('edit-error');
  if (!box) return;
  box.textContent = message;
  box.hidden = !message;
}

// The token Turnstile writes into its own hidden input. Sent with the
// payload because this form is posted by script rather than by the
// browser, so nothing else would carry it.
function turnstileToken() {
  const input = document.querySelector('#edit-form input[name="cf-turnstile-response"]');
  return input ? input.value : '';
}

function resetTurnstile() {
  if (window.turnstile && typeof window.turnstile.reset === 'function') {
    try { window.turnstile.reset('#edit-turnstile'); } catch (error) { /* gone */ }
  }
}

function showThankYou(body) {
  // Nothing on the page is about editing any more, so none of it stays.
  // Removed rather than hidden: the map is a fixed overlay and the form
  // still holds a page's worth of controls that nobody should be able
  // to tab into behind the thank you.
  ['edit-form', 'marker-modal'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.remove();
  });
  document.querySelectorAll('.edit__intro, .edit__header, .edit__staff-notice')
    .forEach(el => el.remove());

  const thanks = document.getElementById('edit-thankyou');
  if (thanks) thanks.hidden = false;

  const points = Number(body && body.points) || 0;
  if (points) {
    const box = document.getElementById('edit-thankyou-points');
    const value = document.getElementById('edit-thankyou-points-value');
    if (value) value.textContent = `+${points} Points`;
    if (box) box.hidden = false;
  }

  document.body.style.overflow = '';
  window.scrollTo(0, 0);
}

function bindSave() {
  const form = document.getElementById('edit-form');
  if (!form) return;

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const save = document.getElementById('edit-save');
    const uuid = form.dataset.locationUuid;
    if (!uuid || !save || save.disabled) return;

    if (!(WORKING.name || '').trim()) {
      showError('A name is needed.');
      return;
    }

    // Only asked for when the challenge is actually on the page: with
    // it switched off in settings there is nothing to complete.
    const challenge = document.getElementById('edit-turnstile');
    if (challenge && !turnstileToken()) {
      showError('Please complete the check below, then publish again.');
      resetTurnstile();
      return;
    }

    showError('');
    save.disabled = true;
    save.textContent = 'Publishing...';

    const restore = () => {
      save.disabled = false;
      save.textContent = 'Publish changes';
      // A token is good for one submission, so a failed attempt needs a
      // fresh one before the next.
      resetTurnstile();
    };

    try {
      const payload = buildPayload();
      payload.turnstileToken = turnstileToken();

      const response = await fetch(`/api/v1/locations/${uuid}/revisions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
        },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      });

      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        showError(body.detail || 'That could not be published. Please try again.');
        restore();
        return;
      }

      // Saved. The guard comes down before anything else, because from
      // here on there is nothing unsaved to guard.
      leaving = true;
      showThankYou(body);
    } catch (error) {
      showError('That could not be published. Please check your connection and try again.');
      restore();
    }
  });
}

// Set once the edit has been published, or while navigating away on
// purpose. Checked by the guard below, which is why it exists at all:
// the guard is an addEventListener, so clearing window.onbeforeunload
// does nothing to it, which is how publishing ended up asking whether
// the person meant to leave.
let leaving = false;

function bindLeaveGuard() {
  window.addEventListener('beforeunload', event => {
    if (leaving || !changed()) return;
    event.preventDefault();
    event.returnValue = '';
  });
}

// ── Start ───────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('edit-form')) return;
  readGroups();
  fillForm();
  bindSections();
  bindChips();
  bindFields();
  bindAltNames();
  bindMarkerModal();
  bindSave();
  bindLeaveGuard();
  refreshSaveState();
});
