// visibility - dialogs and slider readout for the visibility section

(function () {

  var held = 0;
  var locked = false;

  // scale - metre marks and their labels, matching display.py
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
    // unlock - only give the page back when no dialog is left open
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

  // hint - live readout under the slider
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
        // delete target - swap the report id into the form action
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
    // escape - close the topmost dialog first
    var confirm = document.getElementById('vis-delete-modal');
    if (confirm && !confirm.hidden) { close('vis-delete-modal'); return; }
    close('vis-submit-modal');
    close('vis-reports-modal');
  });

  document.addEventListener('input', function (event) {
    if (event.target.id === 'vis-slider') hint();
  });

  // after swap - close dialogs unless the form came back rejected
  document.body.addEventListener('htmx:afterSwap', function (event) {
    if (!event.target || event.target.id !== 'visibility') return;
    var form = document.getElementById('vis-submit-modal');
    if (form && !form.hidden) { locked = false; lock(); hint(); return; }
    closeAll();
  });

  hint();
}());
