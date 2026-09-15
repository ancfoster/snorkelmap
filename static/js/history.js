// history - opens and closes the revision state dialog

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
      // loading - show the dialog straight away with a loading line
      const body = document.getElementById('state-modal-body');
      if (body) {
        body.replaceChildren();
        const loading = document.createElement('p');
        loading.className = 'state-modal__loading';
        loading.textContent = 'Loading…';
        body.append(loading);
      }
      // heading - empty it while the next revision is fetched
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

  // fetch failed - replace the loading line with a message
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
