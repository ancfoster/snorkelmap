/* ═══════════════════════════════════════════════════════════════════
   SnorkelMap — history.js

   Opening and closing the dialog that shows the listing as one revision
   left it.

   Fetching what goes in it is htmx's job: each View State button
   carries its own hx-get and drops the answer into the dialog's body,
   and the heading into the dialog's header out of band. All this does
   is open the dialog when one is pressed, empty both halves so the
   previous revision is not left on screen while the next one is
   fetched, and close it again.
   ═══════════════════════════════════════════════════════════════════ */

(function () {

  let held = 0;

  function modal() {
    return document.getElementById('state-modal');
  }

  function open() {
    const box = modal();
    if (!box || !box.hidden) return;
    held = window.scrollY;
    document.body.style.overflow = 'hidden';
    box.hidden = false;
    const close = box.querySelector('.state-modal__close');
    if (close && close.focus) close.focus();
  }

  function close() {
    const box = modal();
    if (!box || box.hidden) return;
    box.hidden = true;
    document.body.style.overflow = '';
    window.scrollTo(0, held);
  }

  document.addEventListener('click', event => {
    if (event.target.closest('[data-state-increment]')) {
      // Opened here rather than waiting for the fetch, so the dialog is
      // there with something in it from the moment it is asked for.
      const body = document.getElementById('state-modal-body');
      if (body) {
        body.replaceChildren();
        const loading = document.createElement('p');
        loading.className = 'state-modal__loading';
        loading.textContent = 'Loading…';
        body.append(loading);
      }
      // Emptied rather than left as it was: the previous revision's
      // date and author sitting above the next revision's contents
      // would be labelling it wrongly for as long as the fetch takes.
      const heading = document.getElementById('state-modal-heading');
      if (heading) heading.replaceChildren();
      open();
      return;
    }
    if (event.target.closest('[data-close-state]')) {
      event.preventDefault();
      close();
    }
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') close();
  });

  // A fetch that failed leaves the loading line on screen forever
  // otherwise, which reads as a page that has hung.
  document.body.addEventListener('htmx:responseError', () => {
    const heading = document.getElementById('state-modal-heading');
    if (heading) heading.replaceChildren();
    const body = document.getElementById('state-modal-body');
    if (!body) return;
    body.replaceChildren();
    const failed = document.createElement('p');
    failed.className = 'state-modal__missing';
    failed.textContent = 'That version of the listing could not be loaded.';
    body.append(failed);
  });
}());
