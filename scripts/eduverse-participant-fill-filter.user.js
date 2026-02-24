// ==UserScript==
// @name         Eduverse participant: fill search by id and click Filter
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  On app.eduverse.kz/default/participant, if URL has ?id=, fill the search input and click the Filter button (for use inside CRM iframe).
// @match        https://app.eduverse.kz/default/participant*
// @grant        none
// ==/UserScript==

(function() {
  var url = new URL(window.location.href);
  var id = url.searchParams.get('id');
  if (!id) return;

  function run() {
    var form = document.querySelector('form');
    if (!form) return false;
    var input = form.querySelector('input[type=text]');
    if (!input) return false;
    input.value = id;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    var btn = form.querySelector('.fa-filter');
    if (btn) {
      var target = btn.closest('button') || btn.closest('app-button');
      if (target) target.click();
    }
    return true;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      setTimeout(run, 500);
    });
  } else {
    setTimeout(run, 500);
  }
})();
