(function () {
  'use strict';

  var els = {
    logoutBtn: document.getElementById('logout-btn'),
    loadMsg: document.getElementById('load-msg'),
    loginPanel: document.getElementById('login-panel'),
    loginForm: document.getElementById('login-form'),
    loginUsername: document.getElementById('login-username'),
    loginPassword: document.getElementById('login-password'),
    loginMsg: document.getElementById('login-msg'),
    settingsPanel: document.getElementById('settings-panel'),
    dangerZone: document.getElementById('danger-zone'),
    level: document.getElementById('level-select'),
    domain: document.getElementById('domain-input'),
    studentReset: document.getElementById('student-reset-checkbox'),
    partialConfig: document.getElementById('partial-config-checkbox'),
    returnStaysAvailable: document.getElementById('return-stays-available-checkbox'),
    reuseCode: document.getElementById('reuse-code-checkbox'),
    saveBtn: document.getElementById('save-settings-btn'),
    saveMsg: document.getElementById('save-msg'),
    resetAllBtn: document.getElementById('reset-all-btn'),
    resetMsg: document.getElementById('reset-msg')
  };

  function apiGet(path) {
    return fetch(path, { method: 'GET', credentials: 'same-origin' }).then(handleApiResponse);
  }
  function apiPost(path, body) {
    return fetch(path, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    }).then(handleApiResponse);
  }
  function apiPut(path, body) {
    return fetch(path, {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    }).then(handleApiResponse);
  }
  function handleApiResponse(res) {
    return res.json().catch(function () { return {}; }).then(function (data) {
      if (!res.ok) {
        var err = new Error(data.error || ('Request failed with status ' + res.status));
        err.statusCode = res.status;
        throw err;
      }
      return data;
    });
  }

  function showMsg(el, text, isError) {
    el.textContent = text;
    el.className = 'msg ' + (isError ? 'error' : 'success');
  }

  function populateForm(settings) {
    els.level.value = String(settings.level);
    els.domain.value = settings.requiredEmailDomain || '';
    els.studentReset.checked = !!settings.studentResetEnabled;
    document.querySelector('input[name="discount-mode"][value="' + settings.bugs.discountCodeMode + '"]').checked = true;
    els.partialConfig.checked = !!settings.bugs.allowBuyWithPartialConfig;
    els.returnStaysAvailable.checked = !!settings.bugs.returnStaysAvailableWhenEmpty;
    els.reuseCode.checked = !!settings.bugs.allowDiscountCodeReuse;
    document.querySelector('input[name="credit-basis"][value="' + settings.bugs.creditBasis + '"]').checked = true;
  }

  function readForm() {
    return {
      level: Number(els.level.value),
      requiredEmailDomain: els.domain.value.trim(),
      studentResetEnabled: els.studentReset.checked,
      bugs: {
        discountCodeMode: document.querySelector('input[name="discount-mode"]:checked').value,
        allowBuyWithPartialConfig: els.partialConfig.checked,
        returnStaysAvailableWhenEmpty: els.returnStaysAvailable.checked,
        allowDiscountCodeReuse: els.reuseCode.checked,
        creditBasis: document.querySelector('input[name="credit-basis"]:checked').value
      }
    };
  }

  function showLoggedOut() {
    els.logoutBtn.hidden = true;
    els.loginPanel.hidden = false;
    els.settingsPanel.hidden = true;
    els.dangerZone.hidden = true;
  }

  function showLoggedIn(settings) {
    els.logoutBtn.hidden = false;
    els.loginPanel.hidden = true;
    populateForm(settings);
    els.settingsPanel.hidden = false;
    els.dangerZone.hidden = false;
  }

  // Every teacher endpoint independently re-verifies the session cookie
  // server-side (see lib/auth.js's requireTeacher) — this client-side
  // login-gating is UX only, never the real security boundary.
  function loadSettings() {
    els.loadMsg.textContent = '';
    apiGet('/api/teacher/settings')
      .then(function (settings) {
        showLoggedIn(settings);
      })
      .catch(function (err) {
        if (err.statusCode === 401) {
          showLoggedOut();
        } else {
          showMsg(els.loadMsg, err.message || String(err), true);
        }
      });
  }

  // A <form> submit fires both on clicking the (type="submit") login
  // button and on pressing Enter in either field -- one handler covers
  // both, for free, via normal browser form-submission behavior.
  els.loginForm.addEventListener('submit', function (e) {
    e.preventDefault();
    showMsg(els.loginMsg, '', false);
    els.loginMsg.textContent = '';
    apiPost('/api/teacher/login', {
      username: els.loginUsername.value.trim(),
      password: els.loginPassword.value
    })
      .then(function () {
        els.loginPassword.value = '';
        loadSettings();
      })
      .catch(function (err) {
        showMsg(els.loginMsg, err.message || String(err), true);
      });
  });

  els.logoutBtn.addEventListener('click', function () {
    apiPost('/api/teacher/logout').then(function () {
      showLoggedOut();
    });
  });

  els.saveBtn.addEventListener('click', function () {
    apiPut('/api/teacher/settings', readForm())
      .then(function (settings) {
        populateForm(settings);
        showMsg(els.saveMsg, 'Settings saved.', false);
      })
      .catch(function (err) {
        showMsg(els.saveMsg, err.message || String(err), true);
      });
  });

  els.resetAllBtn.addEventListener('click', function () {
    if (!confirm('This will permanently delete ALL students\' purchases, codes, and credit. Continue?')) return;
    var typed = prompt('Type RESET to confirm:');
    if (typed !== 'RESET') {
      showMsg(els.resetMsg, 'Reset cancelled.', true);
      return;
    }
    apiPost('/api/teacher/reset-all')
      .then(function () {
        showMsg(els.resetMsg, 'All simulator data has been reset.', false);
      })
      .catch(function (err) {
        showMsg(els.resetMsg, err.message || String(err), true);
      });
  });

  loadSettings();
})();
