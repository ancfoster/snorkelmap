
(function () {

  function readJson(id) {
    let node = document.getElementById(id);
    if (!node) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (error) {
      console.warn('Could not read ' + id, error);
      return null;
    }
  }

  let photos = readJson('listing-photos') || [];
  let markers = readJson('listing-markers') || [];
  // Where the marker icons are served from. Supplied by Django
  // because it differs between development and production.
  let markerIconBase = readJson('marker-icon-base') || '/static/images/sm-map-icons/';

  let photosModal = document.getElementById('photos-modal');
  let detailModal = document.getElementById('photo-detail-modal');
  let mapModal = document.getElementById('lmap-modal');

  let shareModal = document.getElementById('share-modal');


  let heldScroll = 0;

  function lock() {
    heldScroll = window.scrollY;
    document.body.style.overflow = 'hidden';
  }

  function unlock() {
    document.body.style.overflow = '';
    window.scrollTo(0, heldScroll);
  }

  function open(modal) {
    if (!modal) return;
    lock();
    modal.hidden = false;
  }

  function close(modal) {
    if (!modal) return;
    modal.hidden = true;
    if (allClosed()) unlock();
  }

  function allClosed() {
    return [photosModal, detailModal, mapModal, shareModal].every(function (modal) {
      return !modal || modal.hidden;
    });
  }

  // photographs - gallery grid and the single photo view

  function photoAt(section, index) {
    let found = photos.filter(function (photo) {
      return photo.section === section;
    });
    return found[index] || null;
  }

  function showDetail(photo) {
    if (!photo || !detailModal) return;
    detailModal.querySelector('#photo-detail-img').src = photo.full;
    detailModal.querySelector('#photo-detail-img').alt = photo.description || '';
    detailModal.querySelector('#photo-detail-title').textContent =
      photo.description || '';
    detailModal.querySelector('#photo-detail-date').textContent =
      photo.taken ? 'Taken ' + photo.taken : '';
    open(detailModal);
  }

  document.querySelectorAll('[data-open-photos]').forEach(function (button) {
    button.addEventListener('click', function () { open(photosModal); });
  });

  if (photosModal) {
    photosModal.querySelectorAll('.photos-modal__thumb').forEach(function (thumb) {
      thumb.addEventListener('click', function () {
        showDetail(photoAt(thumb.dataset.photoSection,
                           parseInt(thumb.dataset.photoIndex, 10)));
      });
    });
  }

  let closePhotos = document.getElementById('photos-modal-close');
  if (closePhotos) {
    closePhotos.addEventListener('click', function () { close(photosModal); });
  }

  let detailBack = document.getElementById('photo-detail-back');
  if (detailBack) {
    // back - return to the grid rather than closing everything
    detailBack.addEventListener('click', function () { close(detailModal); });
  }

  let detailClose = document.getElementById('photo-detail-close');
  if (detailClose) {
    detailClose.addEventListener('click', function () {
      close(detailModal);
      close(photosModal);
    });
  }

  let heroMain = document.querySelector('.listing__hero-main .listing__hero-img');
  if (heroMain && photosModal) {
    heroMain.style.cursor = 'zoom-in';
    heroMain.addEventListener('click', function () { open(photosModal); });
  }

  // map - builds the mapbox map inside the location modal

  let STYLES = {
    satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
    terrain: 'mapbox://styles/mapbox/outdoors-v12',
  };

  let map = null;

  function drawMarkers() {
    markers.forEach(function (marker) {
      if (marker.longitude === null || marker.latitude === null) return;

      let element = document.createElement('div');
      element.className = 'lmap-marker';
      if (marker.icon) {
        let image = document.createElement('img');
        image.src = markerIconBase + marker.id + '.png';
        image.alt = '';
        element.appendChild(image);
      }
      element.style.cursor = marker.note ? 'pointer' : 'default';

      new mapboxgl.Marker({ element: element, anchor: 'bottom' })
        .setLngLat([marker.longitude, marker.latitude])
        .addTo(map);

      element.addEventListener('click', function () {
        showMarkerNote(marker.name, marker.note);
      });
    });
  }

  function showMarkerNote(name, note) {
    let popup = document.getElementById('lmap-comment-popup');
    if (!popup) return;
    document.getElementById('lmap-comment-title').textContent = name || '';
    document.getElementById('lmap-comment-text').textContent = note || '';
    // marker card - skip the note line when there is no note
    popup.querySelector('.lmap-comment-popup__card').classList.toggle(
      'lmap-comment-popup__card--name-only', !note);
    popup.classList.remove('hidden');
  }

  function buildMap() {
    if (map || !mapModal || typeof mapboxgl === 'undefined') return;

    mapboxgl.accessToken = mapModal.dataset.token;
    map = new mapboxgl.Map({
      container: 'lmap-map',
      style: STYLES.satellite,
      center: [parseFloat(mapModal.dataset.longitude),
               parseFloat(mapModal.dataset.latitude)],
      zoom: 15,
    });
    map.addControl(new mapboxgl.NavigationControl(), 'bottom-right');
    map.on('load', drawMarkers);
  }

  document.querySelectorAll('[data-open-map]').forEach(function (button) {
    button.addEventListener('click', function () {
      open(mapModal);
      buildMap();
      // resize - the map was hidden so make it measure again
      if (map) window.setTimeout(function () { map.resize(); }, 50);
    });
  });

  let mapClose = document.getElementById('lmap-close');
  if (mapClose) {
    mapClose.addEventListener('click', function () { close(mapModal); });
  }

  let noteClose = document.getElementById('lmap-comment-close');
  if (noteClose) {
    noteClose.addEventListener('click', function () {
      document.getElementById('lmap-comment-popup').classList.add('hidden');
    });
  }

  if (mapModal) {
    mapModal.querySelectorAll('.lmap-modal__style-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        if (!map) return;
        mapModal.querySelectorAll('.lmap-modal__style-btn').forEach(function (other) {
          other.classList.toggle('lmap-modal__style-btn--active', other === button);
        });
        map.setStyle(STYLES[button.dataset.style] || STYLES.satellite);
        // style change - markers are dom elements so they survive it
      });
    });
  }


  // share - modal is the desktop fallback

  let shareButton = document.getElementById('share-button');

  function shareUrl() {
    return (shareButton && shareButton.dataset.shareUrl) || window.location.href;
  }

  function shareTitle() {
    return (shareButton && shareButton.dataset.shareTitle) || document.title;
  }

  // share choice - width decides, not just whether the api exists
  function hasNativeShare() {
    return typeof navigator.share === 'function'
      && window.matchMedia('(max-width: 900px)').matches;
  }

  function openShare() {
    if (hasNativeShare()) {
      navigator.share({ title: shareTitle(), url: shareUrl() })
        .catch(function (error) {
          // share dismissed - a cancelled share is not a failure
          if (error && error.name === 'AbortError') return;
          showShareModal();
        });
      return;
    }
    showShareModal();
  }

  function showShareModal() {
    if (!shareModal) return;

    let url = shareUrl();
    let title = shareTitle();
    let encodedUrl = encodeURIComponent(url);

    let facebook = document.getElementById('share-facebook');
    if (facebook) {
      facebook.href = 'https://www.facebook.com/sharer/sharer.php?u=' + encodedUrl;
    }
    let whatsapp = document.getElementById('share-whatsapp');
    if (whatsapp) {
      whatsapp.href = 'https://wa.me/?text='
        + encodeURIComponent(title + ' ' + url);
    }
    let email = document.getElementById('share-email');
    if (email) {
      email.href = 'mailto:?subject=' + encodeURIComponent(title)
        + '&body=' + encodeURIComponent(title + '\n\n' + url);
    }

    open(shareModal);
  }

  if (shareButton) {
    shareButton.addEventListener('click', openShare);
  }

  if (shareModal) {
    shareModal.querySelectorAll('[data-close-share]').forEach(function (element) {
      element.addEventListener('click', function () { close(shareModal); });
    });
  }

  let copyButton = document.getElementById('share-copy');
  if (copyButton) {
    copyButton.addEventListener('click', function () {
      let field = document.getElementById('share-url');

      function said(word) {
        copyButton.textContent = word;
        copyButton.classList.add('share-modal__copy--done');
        window.setTimeout(function () {
          copyButton.textContent = 'Copy';
          copyButton.classList.remove('share-modal__copy--done');
        }, 2000);
      }

      // clipboard - select the text when copying is refused
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(shareUrl()).then(function () {
          said('Copied');
        }).catch(function () {
          if (field) field.select();
          said('Press ' + (navigator.platform.indexOf('Mac') === 0 ? '\u2318' : 'Ctrl') + '-C');
        });
      } else {
        if (field) field.select();
        said('Press ' + (navigator.platform.indexOf('Mac') === 0 ? '\u2318' : 'Ctrl') + '-C');
      }
    });
  }

  let printButton = document.getElementById('share-print');
  if (printButton) {
    printButton.addEventListener('click', function () {

      close(shareModal);
      window.setTimeout(function () { window.print(); }, 100);
    });
  }

  // escape - closes the topmost thing that is open

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    let popup = document.getElementById('lmap-comment-popup');
    if (popup && !popup.classList.contains('hidden')) {
      popup.classList.add('hidden');
    } else if (shareModal && !shareModal.hidden) {
      close(shareModal);
    } else if (detailModal && !detailModal.hidden) {
      close(detailModal);
    } else if (mapModal && !mapModal.hidden) {
      close(mapModal);
    } else if (photosModal && !photosModal.hidden) {
      close(photosModal);
    }
  });
}());


// reviews - character counter, delete dialog, update button

(function () {

  var BODY_MAX = 900;
  var held = 0;
  // scroll lock - whether this dialog is the one holding the page
  var locked = false;

  function modal() {
    return document.getElementById('review-delete-modal');
  }

  function openConfirm() {
    var box = modal();
    if (!box) return;
    held = window.scrollY;
    document.body.style.overflow = 'hidden';
    locked = true;
    box.hidden = false;
    var cancel = box.querySelector('[data-close-delete]');
    if (cancel && cancel.focus) cancel.focus();
  }

  function closeConfirm() {
    var box = modal();
    if (locked) {
      document.body.style.overflow = '';
      locked = false;
    }
    if (!box || box.hidden) return;
    box.hidden = true;
    window.scrollTo(0, held);
  }

  document.addEventListener('click', function (event) {
    if (event.target.closest('[data-open-delete]')) {
      event.preventDefault();
      openConfirm();
      return;
    }
    if (event.target.closest('[data-close-delete]')) {
      event.preventDefault();
      closeConfirm();
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    var box = modal();
    if (box && !box.hidden) closeConfirm();
  });

  // after swap - release a lock the replaced dialog left behind
  document.body.addEventListener('htmx:afterSettle', function () {
    if (locked) {
      var box = modal();
      if (!box || box.hidden) {
        document.body.style.overflow = '';
        locked = false;
      }
    }
    refresh();
    count();
  });

  // changed - compare the form with what it was drawn with
  function changed(form) {
    var chosen = form.querySelector('input[name="rating"]:checked');
    var rating = chosen ? chosen.value : '0';
    var body = form.querySelector('#review-body');
    return rating !== (form.dataset.initialRating || '0')
      || (body ? body.value : '') !== (form.dataset.initialBody || '');
  }

  function refresh() {
    var form = document.getElementById('review-form');
    if (!form) return;
    var update = form.querySelector('#review-submit');
    if (!update) return;
    update.disabled = !changed(form);
  }

  function count() {
    var body = document.getElementById('review-body');
    var counter = document.getElementById('review-counter');
    if (!body || !counter) return;
    var left = BODY_MAX - body.value.length;
    counter.textContent = left + ' character' + (left === 1 ? '' : 's') + ' left';
    counter.classList.toggle('reviews__counter--over', left < 0);
  }

  document.addEventListener('input', function (event) {
    if (!event.target.closest('#review-form')) return;
    refresh();
    count();
  });

  document.addEventListener('change', function (event) {
    if (!event.target.closest('#review-form')) return;
    refresh();
  });

  refresh();
  count();
}());
