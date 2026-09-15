(function () {
  'use strict';

  var PARAM_KEY_MAP = { model: 'Model', storage: 'Storage', color: 'Color', network: 'Network', accessory: 'Accessory' };
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  // Bootstrapped from the server on load — replaces the values GAS used to
  // inject via HtmlService templating (tmpl.optionsJson, etc.).
  var OPTIONS = null;
  var UI_CONFIG = null;
  var PRICE_TABLE = null;

  var els = {
    email: document.getElementById('student-email'),
    selects: {
      Model: document.getElementById('model-select'),
      Storage: document.getElementById('storage-select'),
      Color: document.getElementById('color-select'),
      Network: document.getElementById('network-select'),
      Accessory: document.getElementById('accessory-select')
    },
    discountWrap: document.getElementById('discount-field-wrap'),
    discountCode: document.getElementById('discount-code'),
    discountStatus: document.getElementById('discount-status'),
    calcBtn: document.getElementById('calc-price-btn'),
    buyBtn: document.getElementById('buy-btn'),
    priceBreakdown: document.getElementById('price-breakdown'),
    totalPrice: document.getElementById('total-price'),
    phonePriceRow: document.getElementById('phone-price-row'),
    phonePrice: document.getElementById('phone-price'),
    appliedCreditRow: document.getElementById('applied-credit-row'),
    appliedCredit: document.getElementById('applied-credit'),
    requestedPaymentRow: document.getElementById('requested-payment-row'),
    requestedPayment: document.getElementById('requested-payment'),
    generatedCodeRow: document.getElementById('generated-code-row'),
    generatedCode: document.getElementById('generated-code'),
    noCodeRow: document.getElementById('no-code-row'),
    storeCreditWrap: document.getElementById('store-credit-wrap'),
    storeCreditBalance: document.getElementById('store-credit-balance'),
    returnSection: document.getElementById('return-section'),
    returnBtn: document.getElementById('return-btn'),
    returnMessage: document.getElementById('return-message'),
    resetWrap: document.getElementById('reset-wrap'),
    resetBtn: document.getElementById('reset-btn'),
    purchaseHistory: document.getElementById('purchase-history'),
    purchaseHistoryList: document.getElementById('purchase-history-list'),
    errorMessage: document.getElementById('error-message')
  };

  var everFullyConfigured = false;
  // Buy stays disabled until Calculate Price has run for the CURRENT inputs.
  // Any change to a parameter or the discount code invalidates it again —
  // clicking Buy itself does not (so repeated Buy clicks against the same
  // calculated configuration are allowed, e.g. buying several identical
  // phones in a row).
  var priceCalculated = false;

  // ===== API helpers =====

  function apiGet(path, params) {
    var qs = new URLSearchParams();
    Object.keys(params || {}).forEach(function (k) {
      if (params[k] !== undefined && params[k] !== null) qs.set(k, params[k]);
    });
    var url = path + (qs.toString() ? '?' + qs.toString() : '');
    return fetch(url, { method: 'GET' }).then(handleApiResponse);
  }

  function apiPost(path, body) {
    return fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    }).then(handleApiResponse);
  }

  function handleApiResponse(res) {
    return res.json().catch(function () { return {}; }).then(function (data) {
      if (!res.ok) {
        throw new Error(data.error || ('Request failed with status ' + res.status));
      }
      return data;
    });
  }

  // ===== Setup =====

  function populateSelects() {
    Object.keys(els.selects).forEach(function (param) {
      var select = els.selects[param];
      (OPTIONS[param] || []).forEach(function (opt) {
        var o = document.createElement('option');
        o.value = opt;
        o.textContent = opt;
        select.appendChild(o);
      });
    });
  }

  function applyUiConfig() {
    els.discountWrap.hidden = UI_CONFIG.level < 2;
    els.returnSection.hidden = UI_CONFIG.level < 4;
    els.storeCreditWrap.hidden = UI_CONFIG.level < 4;
    els.resetWrap.hidden = !UI_CONFIG.studentResetEnabled;
  }

  function clearError() { els.errorMessage.hidden = true; els.errorMessage.textContent = ''; }
  function showError(err) {
    els.errorMessage.hidden = false;
    els.errorMessage.textContent = err && err.message ? err.message : String(err);
  }

  function getConfig() {
    return {
      model: els.selects.Model.value,
      storage: els.selects.Storage.value,
      color: els.selects.Color.value,
      network: els.selects.Network.value,
      accessory: els.selects.Accessory.value
    };
  }

  function buildParams(extra) {
    var p = getConfig();
    p.email = els.email.value.trim();
    p.discountCode = els.discountCode.value.trim();
    if (extra) Object.keys(extra).forEach(function (k) { p[k] = extra[k]; });
    return p;
  }

  function updateBuyButtonState() {
    var cfg = getConfig();
    var allFilled = Object.keys(cfg).every(function (k) { return !!cfg[k]; });
    if (allFilled) everFullyConfigured = true;
    var configOk = allFilled || (UI_CONFIG.allowBuyWithPartialConfig && everFullyConfigured);
    els.buyBtn.disabled = !(configOk && priceCalculated);
  }

  function invalidateCalculation() {
    priceCalculated = false;
    updateBuyButtonState();
  }

  function computeBasePriceClient(cfg) {
    var total = 0;
    Object.keys(PARAM_KEY_MAP).forEach(function (k) {
      var tableKey = PARAM_KEY_MAP[k];
      var val = cfg[k];
      if (val && PRICE_TABLE[tableKey] && PRICE_TABLE[tableKey].hasOwnProperty(val)) {
        total += PRICE_TABLE[tableKey][val];
      }
    });
    return Math.round(total * 100) / 100;
  }

  // A server round trip is only actually needed when server-side data is
  // involved: a discount code (validity lives in the DiscountCodes table)
  // or store credit (level 4). Otherwise the base price is just a lookup
  // sum over publicly-known PRICE_TABLE values, computed here instantly.
  function needsServerCalculation() {
    var codeEntered = !els.discountWrap.hidden && els.discountCode.value.trim().length > 0;
    return codeEntered || UI_CONFIG.level >= 4;
  }

  function buildCongratsMessage(cfg) {
    var msg = 'Congratulations! You are now the owner of a ' + cfg.Network + ' ' + cfg.Color + ' ' + cfg.Model + ' with ' + cfg.Storage;
    if (cfg.Accessory && cfg.Accessory !== 'None') {
      var article = (cfg.Accessory === 'Case' || cfg.Accessory === 'Charger') ? 'a ' : '';
      msg += ' and ' + article + cfg.Accessory;
    }
    msg += '.';
    return msg;
  }

  function addPurchaseToHistory(config) {
    var li = document.createElement('li');
    li.textContent = buildCongratsMessage(config);
    els.purchaseHistoryList.appendChild(li);
    els.purchaseHistory.hidden = false;
    els.purchaseHistory.scrollTop = els.purchaseHistory.scrollHeight;
  }

  // Briefly clears an element's text, then fills in the new value shortly
  // after — so a value that happens to come back unchanged still visibly
  // updates, giving feedback that the click actually did something.
  var BLINK_DELAY_MS = 150;
  function blinkText(el, text, className) {
    el.textContent = '';
    if (className !== undefined) el.className = '';
    setTimeout(function () {
      el.textContent = text;
      if (className !== undefined) el.className = className;
    }, BLINK_DELAY_MS);
  }

  function renderDiscountStatus(discount) {
    var text = '';
    var cls = '';
    if (discount && discount.entered) {
      if (discount.valid) {
        text = 'Applied (15% off)';
        cls = 'status-valid';
      } else if (discount.message) {
        text = discount.message;
        cls = 'status-unknown';
      }
    }
    blinkText(els.discountStatus, text, cls);
  }

  function renderPriceBreakdown(result) {
    els.priceBreakdown.hidden = false;
    els.generatedCodeRow.hidden = true;
    els.noCodeRow.hidden = true;
    renderDiscountStatus(result.discountCode);

    if (UI_CONFIG.level >= 4) {
      var total = (result.requestedPayment !== undefined ? result.requestedPayment : result.paidPrice);
      blinkText(els.totalPrice, total.toFixed(2));
      els.phonePriceRow.hidden = false;
      blinkText(els.phonePrice, result.paidPrice.toFixed(2));
      els.appliedCreditRow.hidden = false;
      blinkText(els.appliedCredit, (result.creditApplied || 0).toFixed(2));
      els.requestedPaymentRow.hidden = false;
      blinkText(els.requestedPayment, total.toFixed(2));
      if (result.creditBalance !== undefined) {
        els.storeCreditBalance.textContent = Number(result.creditBalance).toFixed(2);
      }
    } else {
      blinkText(els.totalPrice, result.paidPrice.toFixed(2));
      els.phonePriceRow.hidden = true;
      els.appliedCreditRow.hidden = true;
      els.requestedPaymentRow.hidden = true;
    }
  }

  // ===== Event wiring =====

  els.calcBtn.addEventListener('click', function () {
    clearError();
    if (!EMAIL_RE.test(els.email.value.trim())) {
      showError({ message: 'A valid email address is required.' });
      return;
    }
    var params = buildParams();

    if (needsServerCalculation()) {
      apiGet('/api/calculate', params)
        .then(function (result) {
          renderPriceBreakdown(result);
          priceCalculated = true;
          updateBuyButtonState();
        })
        .catch(showError);
    } else {
      // Instant, client-side — see needsServerCalculation() above.
      var basePrice = computeBasePriceClient(getConfig());
      renderPriceBreakdown({ paidPrice: basePrice, discountCode: { entered: '', valid: false, message: null } });
      priceCalculated = true;
      updateBuyButtonState();
      // Fire-and-forget: same calculation, run server-side purely so this
      // action still gets logged (ActionLog), without making the student
      // wait for it. Its result is intentionally ignored.
      apiGet('/api/calculate', params).catch(function () {});
    }
  });

  els.buyBtn.addEventListener('click', function () {
    clearError();
    apiPost('/api/buy', buildParams())
      .then(function (result) {
        renderPriceBreakdown(result);
        if (result.generatedCode) {
          els.generatedCodeRow.hidden = false;
          els.generatedCode.textContent = result.generatedCode;
        } else if (UI_CONFIG.level >= 2) {
          els.noCodeRow.hidden = false;
        }
        if (result.creditBalance !== undefined) {
          els.storeCreditBalance.textContent = Number(result.creditBalance).toFixed(2);
        }
        els.returnBtn.disabled = !result.returnEnabled;
        addPurchaseToHistory(result.config);
      })
      .catch(showError);
  });

  els.returnBtn.addEventListener('click', function () {
    clearError();
    var refundType = document.querySelector('input[name="refund-type"]:checked').value;
    apiPost('/api/return', buildParams({ refundType: refundType }))
      .then(function (result) {
        els.returnMessage.textContent = result.success
          ? (result.message + '. ' + result.refundMessage)
          : result.message;
        els.returnMessage.className = result.success ? 'success' : 'failure';
        if (result.creditBalance !== undefined) {
          els.storeCreditBalance.textContent = Number(result.creditBalance).toFixed(2);
        }
        els.returnBtn.disabled = !result.returnEnabled;
      })
      .catch(showError);
  });

  els.resetBtn.addEventListener('click', function () {
    clearError();
    if (!confirm('Reset all of your own purchase, discount code, and store credit data?')) return;
    apiPost('/api/reset', { email: els.email.value.trim() })
      .then(function () {
        els.priceBreakdown.hidden = true;
        els.generatedCode.textContent = '';
        els.storeCreditBalance.textContent = '0.00';
        els.returnMessage.textContent = '';
        els.returnBtn.disabled = true;
        els.purchaseHistoryList.innerHTML = '';
        els.purchaseHistory.hidden = true;
        everFullyConfigured = false;
        invalidateCalculation();
        alert('Your data has been reset.');
      })
      .catch(showError);
  });

  var statusDebounce = null;
  function refreshStudentStatus() {
    clearTimeout(statusDebounce);
    statusDebounce = setTimeout(function () {
      var email = els.email.value.trim();
      if (!EMAIL_RE.test(email)) return;
      apiGet('/api/student-status', { email: email })
        .then(function (status) {
          els.returnBtn.disabled = !status.returnEnabled;
          if (UI_CONFIG.level >= 4) {
            els.storeCreditBalance.textContent = Number(status.creditBalance).toFixed(2);
          }
        })
        .catch(function () { /* ignore — likely still typing an invalid email */ });
    }, 400);
  }

  Object.keys(els.selects).forEach(function (param) {
    els.selects[param].addEventListener('change', invalidateCalculation);
  });
  els.discountCode.addEventListener('input', invalidateCalculation);
  els.email.addEventListener('input', refreshStudentStatus);

  // ===== Bootstrap =====

  Promise.all([
    apiGet('/api/product-options', {}),
    apiGet('/api/ui-config', {})
  ]).then(function (results) {
    PRICE_TABLE = results[0].priceTable;
    OPTIONS = results[0].options;
    UI_CONFIG = results[1];
    populateSelects();
    applyUiConfig();
    updateBuyButtonState();
  }).catch(showError);
})();
