
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

  // ── Photographs ────────────────────────────────────────────────────

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
    // Back to the grid, not out of the photographs altogether.
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

  // ── The map ────────────────────────────────────────────────────────

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
        image.src = '/static/' + marker.icon;
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
    // Without a note there is nothing to read, so the card shrinks to
    // its title rather than opening with an empty paragraph in it.
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
      // The container had no size while the modal was hidden, so the
      // canvas comes out the wrong shape unless it is told to look
      // again once it is on screen.
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
        // Markers are DOM elements rather than layers, so they survive a
        // style change; layers would not.
      });
    });
  }


  // modal is the desktop sharing fallback

  let shareButton = document.getElementById('share-button');

  function shareUrl() {
    return (shareButton && shareButton.dataset.shareUrl) || window.location.href;
  }

  function shareTitle() {
    return (shareButton && shareButton.dataset.shareTitle) || document.title;
  }

  /* navigator.share exists on desktop Safari too, where a modal is the
     better experience, so the width is part of the decision rather than
     the API alone. */
  function hasNativeShare() {
    return typeof navigator.share === 'function'
      && window.matchMedia('(max-width: 900px)').matches;
  }

  function openShare() {
    if (hasNativeShare()) {
      navigator.share({ title: shareTitle(), url: shareUrl() })
        .catch(function (error) {
          // A person dismissing the drawer rejects the promise, which
          // is not a failure and must not open the modal behind it.
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

      /* The clipboard API needs a secure context and permission, and
         selecting the text is a usable answer when it is refused. */
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

  //  closes the topmost thing that is open 

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


/* ── Reviews ─────────────────────────────────────────────────────────

   Three small jobs, none of which the block needs to work: the rating
   can be chosen, the text written and the whole thing submitted with
   this file absent. What is here is the confirmation before a
   deletion, the update button staying inert until something has
   actually changed, and the character count.

   Everything is delegated from the document and every element is
   looked up when it is wanted, because the whole block is replaced by
   htmx on each exchange and anything held on to here would be pointing
   at markup that is no longer in the page.
   ──────────────────────────────────────────────────────────────────── */

(function () {

  var BODY_MAX = 900;
  var held = 0;
  /* Whether the page is scroll locked because of this dialog, as
     opposed to because one of the photo modals is open. */
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

  /* The block that replaces this one arrives with its dialog already
     closed, so the only thing left over from an open one is the locked
     page. Released only if this is what locked it, so that a swap
     while a photo modal is open does not unlock it underneath. */
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

  /* Whether anything is different from what the form was drawn with.
     Read off the form itself rather than remembered here, so that a
     freshly swapped form compares against its own values and not
     against the ones the last one had. */
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
