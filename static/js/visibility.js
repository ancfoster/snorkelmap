/* ═══════════════════════════════════════════════════════════════════
   SnorkelMap — visibility.js

   The three dialogs in the visibility section, and the running figure
   under the slider.

   Everything it touches is inside #visibility, which htmx replaces
   whole on every exchange. So nothing is bound to an element: the
   listeners are on the document and find what was clicked when it is
   clicked, the way listing.js handles the review dialog, because a
   listener bound at load would be pointing at markup that is no longer
   in the page after the first submission.

   The delete dialog is one dialog for every row rather than one per
   row. Which report it is about is carried on the button that opened
   it and written into the form's action then, because a list that
   grows every time somebody goes snorkelling should not put a dialog
   into the page for each of its rows.
   ═══════════════════════════════════════════════════════════════════ */

(function () {

  var held = 0;
  var locked = false;

  /* The scale, kept in step with display.py. The figure under the
     slider has to say the same word the bar will say about it once it
     has been filed, or moving the slider to five metres and being told
     something else afterwards reads as the site disagreeing with
     itself. */
  var POINTS = [0, 2, 5, 8, 12];
  var LABELS = ['Very Poor', 'Poor', 'Average', 'Very Good', 'Excellent'];

  function category(metres) {
    var nearest = 0;
    for (var index = 1; index < POINTS.length; index++) {
      if (Math.abs(POINTS[index] - metres) < Math.abs(POINTS[nearest] - metres)) {
        nearest = index;
      }
    }
    return LABELS[nearest];
  }

  function lock() {
    if (locked) return;
    held = window.scrollY;
    document.body.style.overflow = 'hidden';
    locked = true;
  }

  function unlock() {
    if (!locked) return;
    document.body.style.overflow = '';
    locked = false;
    window.scrollTo(0, held);
  }

  function open(id) {
    var box = document.getElementById(id);
    if (!box || !box.hidden) return;
    lock();
    box.hidden = false;
    var first = box.querySelector('[data-close-vis], [data-close-vis-delete]');
    if (first && first.focus) first.focus();
  }

  function close(id) {
    var box = document.getElementById(id);
    if (!box || box.hidden) return;
    box.hidden = true;
    /* Only give the page back once nothing is open. The delete dialog
       can be opened from in front of nothing, but the reports dialog
       and the report form both lock, and closing one should not
       unlock the page while the other is still up. */
    if (!anyOpen()) unlock();
  }

  function anyOpen() {
    return ['vis-submit-modal', 'vis-reports-modal', 'vis-delete-modal']
      .some(function (id) {
        var box = document.getElementById(id);
        return box && !box.hidden;
      });
  }

  function closeAll() {
    ['vis-submit-modal', 'vis-reports-modal', 'vis-delete-modal']
      .forEach(function (id) {
        var box = document.getElementById(id);
        if (box) box.hidden = true;
      });
    unlock();
  }

  /* The figure under the slider, in the words the bar uses. */
  function hint() {
    var slider = document.getElementById('vis-slider');
    var line = document.getElementById('vis-hint');
    if (!slider || !line) return;
    var metres = parseFloat(slider.value);
    if (isNaN(metres)) { line.textContent = ''; return; }
    var printed = metres >= 12 ? '12 metres or more' : metres + ' metres';
    line.textContent = 'Reporting ' + printed
      + ', which reads as ' + category(metres) + '.';
  }

  document.addEventListener('click', function (event) {
    if (event.target.closest('[data-open-vis-submit]')) {
      event.preventDefault();
      open('vis-submit-modal');
      hint();
      return;
    }

    if (event.target.closest('[data-open-vis-reports]')) {
      event.preventDefault();
      open('vis-reports-modal');
      return;
    }

    var remove = event.target.closest('[data-delete-report]');
    if (remove) {
      event.preventDefault();
      var form = document.getElementById('vis-delete-form');
      if (form) {
        /* The address is built from the template the server drew with
           a nought in it, so the id is substituted rather than the URL
           being assembled here out of string pieces. */
        var action = form.dataset.actionTemplate
          .replace(/0\/$/, remove.dataset.deleteReport + '/');
        form.setAttribute('action', action);
        form.setAttribute('hx-post', action);
        if (window.htmx) window.htmx.process(form);
      }
      var when = document.getElementById('vis-delete-date');
      if (when) {
        when.textContent = remove.dataset.deleteDate
          ? ' from ' + remove.dataset.deleteDate
          : '';
      }
      open('vis-delete-modal');
      return;
    }

    if (event.target.closest('[data-close-vis-delete]')) {
      event.preventDefault();
      close('vis-delete-modal');
      return;
    }

    if (event.target.closest('[data-close-vis]')) {
      event.preventDefault();
      close('vis-submit-modal');
      close('vis-reports-modal');
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    /* The topmost one first: the delete dialog can sit over the
       others, and escape should take away what is in front. */
    var confirm = document.getElementById('vis-delete-modal');
    if (confirm && !confirm.hidden) { close('vis-delete-modal'); return; }
    close('vis-submit-modal');
    close('vis-reports-modal');
  });

  document.addEventListener('input', function (event) {
    if (event.target.id === 'vis-slider') hint();
  });

  /* The block that replaces this one arrives with its dialogs closed,
     so the scroll lock has to be given back by hand. A rejected form
     is the exception: the server sends it back open, and this leaves
     it that way. */
  document.body.addEventListener('htmx:afterSwap', function (event) {
    if (!event.target || event.target.id !== 'visibility') return;
    var form = document.getElementById('vis-submit-modal');
    if (form && !form.hidden) { locked = false; lock(); hint(); return; }
    closeAll();
  });

  hint();
}());
