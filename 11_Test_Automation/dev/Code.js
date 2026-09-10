/**
 * Phone Configurator Simulator — server code.
 *
 * Two ways in:
 *  1. UI (student.html / teacher.html) via google.script.run, calling the
 *     top-level functions below directly.
 *  2. "Under the UI" HTTP testing via doGet (GET, read-only actions) and
 *     doPost (POST, action=... in the query string, form body, or a JSON
 *     body) — both funnel into the SAME functions, so behavior is identical
 *     either way. See handleApiAction_ for the full action list.
 *
 * Deployment: Execute as "Me", Access "Anyone" (fully anonymous) — students
 * never sign in to Google; identity is a self-reported email parameter.
 * Because of that, Session.getActiveUser() cannot reliably identify anyone
 * (Apps Script blanks it out under anonymous access), so the teacher page is
 * instead protected by a shared password (see TEACHER_PASSWORD_KEY below).
 * Change the default password from teacher.html the first time you use it.
 */

// ===== Product data =====
var PRICE_TABLE = {
  Model: { 'Pixel 9': 900, 'Pixel 9 Pro': 1050, 'Pixel 9 Pro XL': 1430 },
  Storage: { '128GB': 0, '256GB': 56, '512GB': 98, '1TB': 164 },
  Color: { 'Black': 0, 'Red': 100, 'Silver': 80, 'Blue': 60 },
  Network: { '5G': 115, '4G': 0 },
  Accessory: { 'None': 0, 'Case': 45, 'Charger': 32, 'Earbuds': 215 }
};
var PARAMETERS = ['Model', 'Storage', 'Color', 'Network', 'Accessory'];
var DISCOUNT_RATE = 0.15;
var DISCOUNT_CODE_LENGTH = 7;
var EMAIL_PREFIX_LENGTH = 5;
var PAD_CHAR = 'Z';

// ===== Sheet names =====
var SHEET_PURCHASES = 'Purchases';
var SHEET_CODES = 'DiscountCodes';
var SHEET_CREDIT = 'StoreCredit';
var SHEET_LOG = 'ActionLog';

// ===== Settings =====
var SETTINGS_KEY = 'SETTINGS';
var DEFAULT_SETTINGS = {
  level: 1,
  requiredEmailDomain: '',
  studentResetEnabled: false,
  bugs: {
    discountCodeMode: 'normal',           // 'normal' | 'acceptAny' | 'acceptNone'
    allowBuyWithPartialConfig: false,
    returnStaysAvailableWhenEmpty: false,
    creditBasis: 'paid',                  // 'paid' (correct) | 'base' (bug)
    allowDiscountCodeReuse: false          // false (correct: single-use, invalidated on return) | true (bug)
  }
};

// ===== Teacher auth =====
var TEACHER_PASSWORD_KEY = 'TEACHER_PASSWORD';
var DEFAULT_TEACHER_PASSWORD = 'teacher123';

// ===================================================================
// Web app entry points
// ===================================================================

function doGet(e) {
  e = e || {};
  var p = e.parameter || {};

  if (p.action) {
    return jsonResponse_(handleApiAction_(p, 'GET'));
  }

  if (p.role === 'teacher') {
    return HtmlService.createHtmlOutputFromFile('teacher')
      .setTitle('Phone Simulator — Teacher')
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
  }

  var tmpl = HtmlService.createTemplateFromFile('student');
  tmpl.optionsJson = JSON.stringify(getProductOptions());
  tmpl.uiConfigJson = JSON.stringify(getUiConfig());
  tmpl.priceTableJson = JSON.stringify(PRICE_TABLE);
  return tmpl.evaluate()
    .setTitle('Phone Configurator Simulator')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function doPost(e) {
  e = e || {};
  var params = {};
  if (e.parameter) {
    for (var k in e.parameter) params[k] = e.parameter[k];
  }
  if (e.postData && e.postData.contents) {
    var ct = e.postData.type || '';
    if (ct.indexOf('json') !== -1) {
      try {
        var body = JSON.parse(e.postData.contents);
        for (var k2 in body) params[k2] = body[k2];
      } catch (err) {
        return jsonResponse_({ ok: false, error: 'Invalid JSON body' });
      }
    }
  }
  return jsonResponse_(handleApiAction_(params, 'POST'));
}

/**
 * "Under the UI" JSON API. All actions below mirror a UI action 1:1.
 *
 * Read-only (GET or POST):
 *   ?action=getUiConfig
 *   ?action=calculate&email=...&model=...&storage=...&color=...&network=...&accessory=...&discountCode=...
 *   ?action=getStudentStatus&email=...
 *   ?action=teacherGetSettings&password=...
 *
 * Mutating (POST only):
 *   action=buy            {email, model, storage, color, network, accessory, discountCode}
 *   action=return          {email, model, storage, color, network, accessory, refundType: "Refund"|"StoreCredit"}
 *   action=resetStudent    {email}
 *   action=teacherUpdateSettings  {password, settings: {...}}
 *   action=teacherResetAll {password}
 */
function handleApiAction_(params, method) {
  var action = params.action;
  try {
    switch (action) {
      case 'getUiConfig':
        return { ok: true, data: getUiConfig() };
      case 'calculate':
        return { ok: true, data: calculatePrice(params) };
      case 'getStudentStatus':
        return { ok: true, data: getStudentStatus(params) };
      case 'buy':
        requireMethod_(method, 'POST');
        return { ok: true, data: buyPhone(params) };
      case 'return':
        requireMethod_(method, 'POST');
        return { ok: true, data: returnPhone(params) };
      case 'resetStudent':
        requireMethod_(method, 'POST');
        return { ok: true, data: resetStudentData(params) };
      case 'teacherGetSettings':
        return { ok: true, data: teacherGetSettings(params.password) };
      case 'teacherUpdateSettings':
        requireMethod_(method, 'POST');
        return { ok: true, data: teacherUpdateSettings(params.password, params.settings) };
      case 'teacherResetAll':
        requireMethod_(method, 'POST');
        return { ok: true, data: teacherResetAll(params.password) };
      default:
        return { ok: false, error: 'Unknown or missing action: ' + action };
    }
  } catch (err) {
    return { ok: false, error: (err && err.message) ? err.message : String(err) };
  }
}

function requireMethod_(method, expected) {
  if (method !== expected) {
    throw new Error('This action requires an HTTP ' + expected + ' request.');
  }
}

function jsonResponse_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// ===================================================================
// Public (student-facing) functions
// ===================================================================

/**
 * Safe-to-expose UI configuration. Deliberately excludes the induced-bugs
 * flags (§6.8 of the requirements doc) EXCEPT allowBuyWithPartialConfig,
 * which the client must know about to render the Buy button's enabled
 * state correctly (§6.3) — every other bug only ever shows up through the
 * *outcome* of an action (discount accepted/rejected, credit amount,
 * return message), which is what makes them testable rather than just
 * readable.
 */
function getUiConfig() {
  ensureSheets_();
  var s = getSettings_();
  return {
    level: s.level,
    studentResetEnabled: s.studentResetEnabled,
    requiredEmailDomain: s.requiredEmailDomain,
    allowBuyWithPartialConfig: s.bugs.allowBuyWithPartialConfig
  };
}

function getProductOptions() {
  var out = {};
  PARAMETERS.forEach(function (p) { out[p] = Object.keys(PRICE_TABLE[p]); });
  return out;
}

/**
 * The component price table — safe to expose: it's the same data the
 * exercise itself hands students up front (§2 of the requirements doc),
 * and Buy always independently recomputes the price server-side from this
 * same table regardless of what the client displays, so exposing it here
 * doesn't weaken purchase integrity. Used by the client to compute the
 * base price instantly, without a round trip, whenever no discount code
 * or store credit is involved (§6.2) — see the performance note there.
 */
function getPriceTable() {
  return PRICE_TABLE;
}

/**
 * Preview price for the current selection. Never mutates purchase/credit
 * data (only appends one row to the action log — see logAction_). No lock
 * is taken: this never does a read-modify-write on Purchases/Credit.
 *
 * The client normally computes the base-price case itself, instantly,
 * using the same PRICE_TABLE (§3, §6.2 of the requirements doc) and only
 * calls this when server data is actually needed (a discount code, or
 * Level 4 credit) — but it also fires this in the background, unawaited,
 * purely so the action still gets logged even when it already rendered
 * the price locally. Either way, this function is the single source of
 * truth for what gets written to the log.
 *
 * params: {email, model, storage, color, network, accessory, discountCode}
 */
function calculatePrice(params) {
  params = params || {};
  ensureSheets_();
  var logEntry = newLogEntry_('CalculatePrice');
  try {
    var settings = getSettings_();
    var email = validateEmail_(params.email, settings);
    logEntry.email = email;
    var config = readConfig_(params);
    logEntry.parameters = configToLogString_(config);
    logEntry.discountCode = (params.discountCode || '').toString().trim();

    var basePrice = computeBasePrice_(config);
    var discount = evaluateDiscount_(email, params.discountCode, settings);
    var paidPrice = round2_(discount.valid ? basePrice * (1 - DISCOUNT_RATE) : basePrice);

    var result = {
      email: email,
      config: config,
      basePrice: basePrice,
      discountCode: discount,
      paidPrice: paidPrice
    };
    logEntry.calculatedPrice = paidPrice;

    if (settings.level >= 4) {
      var creditBalance = getStoreCredit_(email);
      var creditApplied = round2_(Math.min(creditBalance, paidPrice));
      var requestedPayment = round2_(Math.max(0, paidPrice - creditApplied));
      result.creditBalance = creditBalance;
      result.creditApplied = creditApplied;
      result.requestedPayment = requestedPayment;
      logEntry.creditBefore = creditBalance;
      logEntry.creditAfter = creditBalance;
      logEntry.calculatedPrice = requestedPayment;
    }
    logEntry.result = 'Success';
    return result;
  } catch (err) {
    logEntry.message = err && err.message ? err.message : String(err);
    throw err;
  } finally {
    logAction_(logEntry);
  }
}

/** Returns Return-button eligibility and current credit for an email, without any other action. */
function getStudentStatus(params) {
  params = params || {};
  ensureSheets_();
  var settings = getSettings_();
  var email = validateEmail_(params.email, settings);
  return {
    email: email,
    returnEnabled: computeReturnEnabled_(email, settings),
    creditBalance: settings.level >= 4 ? getStoreCredit_(email) : 0
  };
}

/**
 * Buy the current configuration. Records a purchase, generates a discount
 * code (Level 2+), and applies/updates store credit (Level 4).
 * params: {email, model, storage, color, network, accessory, discountCode}
 */
function buyPhone(params) {
  params = params || {};
  ensureSheets_();
  var logEntry = newLogEntry_('Buy');
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var settings = getSettings_();
    var email = validateEmail_(params.email, settings);
    logEntry.email = email;
    var config = readConfig_(params);
    logEntry.parameters = configToLogString_(config);
    logEntry.discountCode = (params.discountCode || '').toString().trim();

    var allSelected = PARAMETERS.every(function (p) { return !!config[p]; });
    if (!allSelected && !settings.bugs.allowBuyWithPartialConfig) {
      throw new Error('All 5 parameters must be selected before buying.');
    }

    var basePrice = computeBasePrice_(config);
    var discount = evaluateDiscount_(email, params.discountCode, settings);
    var paidPrice = round2_(discount.valid ? basePrice * (1 - DISCOUNT_RATE) : basePrice);

    var creditBalanceBefore = getStoreCredit_(email);
    logEntry.creditBefore = creditBalanceBefore;
    var creditApplied = 0;
    var requestedPayment = paidPrice;
    if (settings.level >= 4) {
      creditApplied = round2_(Math.min(creditBalanceBefore, paidPrice));
      requestedPayment = round2_(Math.max(0, paidPrice - creditApplied));
    }

    // One read of this student's purchase history covers both the sequence
    // number (for the discount code) and, after appending, Return-button
    // eligibility — no need for the separate re-reads a naive implementation
    // would do (important once the class has generated thousands of rows).
    var purchases = getPurchasesForEmail_(email);
    var seq = purchases.length + 1;
    var purchaseId = Utilities.getUuid();
    // No new code for a purchase that itself used a valid discount code —
    // handing out a fresh code every time one was just spent is equivalent
    // to letting the same code be applied repeatedly.
    var generatedCode = '';
    if (settings.level >= 2 && !discount.valid) {
      generatedCode = generateDiscountCode_(email, seq);
    }

    appendPurchaseRow_({
      purchaseId: purchaseId, email: email, seq: seq, config: config,
      basePrice: basePrice, discountCodeUsed: discount.valid ? discount.entered : '',
      paidPrice: paidPrice, creditApplied: creditApplied, requestedPayment: requestedPayment,
      codeGenerated: generatedCode, status: 'Bought'
    });

    if (generatedCode) {
      appendDiscountCodeRow_(generatedCode, email, purchaseId);
    }
    if (discount.valid) {
      markCodeRedeemed_(email, discount.entered);
    }

    var creditBalanceAfter = creditBalanceBefore;
    if (settings.level >= 4 && creditApplied > 0) {
      creditBalanceAfter = round2_(creditBalanceBefore - creditApplied);
      setStoreCredit_(email, creditBalanceAfter);
    }
    logEntry.creditAfter = creditBalanceAfter;
    logEntry.calculatedPrice = settings.level >= 4 ? requestedPayment : paidPrice;
    logEntry.result = 'Success';

    return {
      email: email,
      config: config,
      basePrice: basePrice,
      discountCode: discount,
      paidPrice: paidPrice,
      creditApplied: creditApplied,
      requestedPayment: requestedPayment,
      creditBalance: settings.level >= 4 ? creditBalanceAfter : undefined,
      generatedCode: generatedCode || null,
      // We just recorded an active purchase, so Return is trivially eligible
      // at Level 4 — no extra read needed to confirm it.
      returnEnabled: settings.level >= 4
    };
  } catch (err) {
    logEntry.message = err && err.message ? err.message : String(err);
    throw err;
  } finally {
    lock.releaseLock();
    logAction_(logEntry);
  }
}

/**
 * Return a previously-bought phone matching the current field selections.
 * params: {email, model, storage, color, network, accessory, refundType}
 */
function returnPhone(params) {
  params = params || {};
  ensureSheets_();
  var logEntry = newLogEntry_('Return');
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var settings = getSettings_();
    if (settings.level < 4) {
      throw new Error('Return is not available at the current level.');
    }
    var email = validateEmail_(params.email, settings);
    logEntry.email = email;
    var config = readConfig_(params);
    logEntry.parameters = configToLogString_(config);
    var refundType = (params.refundType || '').toString().trim();
    if (refundType !== 'Refund' && refundType !== 'StoreCredit') {
      throw new Error('refundType must be "Refund" or "StoreCredit".');
    }

    var creditBefore = getStoreCredit_(email);
    logEntry.creditBefore = creditBefore;

    // Single read of this student's purchase history, reused for both the
    // match lookup and (after a local, in-memory status update — no second
    // read) the post-return Return-button eligibility check.
    var purchases = getPurchasesForEmail_(email);
    var match = findMatchInPurchases_(purchases, config);
    if (!match) {
      logEntry.creditAfter = creditBefore;
      logEntry.message = 'No matching purchase found';
      logEntry.result = 'Failed';
      return {
        success: false,
        message: 'Return action failed. The stated configuration does not match a phone you bought.',
        returnEnabled: computeReturnEnabledFromPurchases_(purchases, settings)
      };
    }

    markPurchaseReturned_(match.rowIndex);
    match.row.Status = 'Returned'; // keep the in-memory copy consistent for the eligibility check below
    if (match.codeGenerated) {
      disableDiscountCode_(email, match.codeGenerated);
    }

    var response = {
      success: true,
      message: 'The phone can be returned',
      refundType: refundType
    };

    if (refundType === 'Refund') {
      response.refundMessage = 'Refund will be completed within 5 business days';
      logEntry.creditAfter = creditBefore;
    } else {
      var creditBasisIsBase = settings.bugs.creditBasis === 'base';
      var creditAmount = creditBasisIsBase ? match.basePrice : match.paidPrice;
      var newBalance = round2_(creditBefore + creditAmount);
      setStoreCredit_(email, newBalance);
      response.creditAdded = creditAmount;
      response.creditBalance = newBalance;
      response.refundMessage = 'Your store credit is now $' + newBalance.toFixed(2);
      logEntry.creditAfter = newBalance;
      logEntry.calculatedPrice = creditAmount;
    }

    response.returnEnabled = computeReturnEnabledFromPurchases_(purchases, settings);
    logEntry.result = 'Success';
    return response;
  } catch (err) {
    logEntry.message = err && err.message ? err.message : String(err);
    throw err;
  } finally {
    lock.releaseLock();
    logAction_(logEntry);
  }
}

/** Clears only the calling student's own data. Requires studentResetEnabled. */
function resetStudentData(params) {
  params = params || {};
  ensureSheets_();
  var logEntry = newLogEntry_('Reset');
  var settings = getSettings_();
  if (!settings.studentResetEnabled) {
    logEntry.message = 'Student reset is currently disabled by the teacher.';
    logAction_(logEntry);
    throw new Error('Student reset is currently disabled by the teacher.');
  }
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var email = validateEmail_(params.email, settings);
    logEntry.email = email;
    logEntry.creditBefore = getStoreCredit_(email);
    logEntry.creditAfter = 0;
    deleteRowsByEmail_(SHEET_PURCHASES, email);
    deleteRowsByEmail_(SHEET_CODES, email);
    deleteRowsByEmail_(SHEET_CREDIT, email);
    logEntry.result = 'Success';
    return { success: true, email: email };
  } catch (err) {
    logEntry.message = err && err.message ? err.message : String(err);
    throw err;
  } finally {
    lock.releaseLock();
    logAction_(logEntry);
  }
}

// ===================================================================
// Teacher functions (password-protected — see file header)
// ===================================================================

function teacherGetSettings(password) {
  requireTeacherPassword_(password);
  ensureSheets_();
  return getSettings_();
}

function teacherUpdateSettings(password, newSettings) {
  requireTeacherPassword_(password);
  if (typeof newSettings === 'string') {
    newSettings = JSON.parse(newSettings);
  }
  var merged = mergeSettings_(getSettings_(), newSettings || {});
  validateSettings_(merged);
  saveSettings_(merged);
  return merged;
}

function teacherResetAll(password) {
  requireTeacherPassword_(password);
  ensureSheets_();
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    clearSheetData_(SHEET_PURCHASES);
    clearSheetData_(SHEET_CODES);
    clearSheetData_(SHEET_CREDIT);
    clearSheetData_(SHEET_LOG);
    return { success: true };
  } finally {
    lock.releaseLock();
  }
}

function changeTeacherPassword(oldPassword, newPassword) {
  requireTeacherPassword_(oldPassword);
  newPassword = (newPassword || '').toString();
  if (newPassword.length < 4) {
    throw new Error('New password must be at least 4 characters.');
  }
  PropertiesService.getScriptProperties().setProperty(TEACHER_PASSWORD_KEY, newPassword);
  return { success: true };
}

function requireTeacherPassword_(password) {
  var stored = PropertiesService.getScriptProperties().getProperty(TEACHER_PASSWORD_KEY) || DEFAULT_TEACHER_PASSWORD;
  if (!password || password !== stored) {
    throw new Error('Invalid teacher password.');
  }
}

// ===================================================================
// Settings storage
// ===================================================================

function getSettings_() {
  var raw = PropertiesService.getScriptProperties().getProperty(SETTINGS_KEY);
  var stored = raw ? JSON.parse(raw) : {};
  return mergeSettings_(DEFAULT_SETTINGS, stored);
}

function mergeSettings_(base, override) {
  var merged = JSON.parse(JSON.stringify(base));
  for (var k in override) {
    if (k === 'bugs' && override.bugs) {
      merged.bugs = Object.assign({}, merged.bugs, override.bugs);
    } else {
      merged[k] = override[k];
    }
  }
  return merged;
}

function saveSettings_(settings) {
  PropertiesService.getScriptProperties().setProperty(SETTINGS_KEY, JSON.stringify(settings));
}

function validateSettings_(settings) {
  settings.level = Number(settings.level);
  if ([1, 2, 3, 4].indexOf(settings.level) === -1) throw new Error('level must be 1-4.');
  if (['normal', 'acceptAny', 'acceptNone'].indexOf(settings.bugs.discountCodeMode) === -1) {
    throw new Error('invalid discountCodeMode');
  }
  if (['paid', 'base'].indexOf(settings.bugs.creditBasis) === -1) {
    throw new Error('invalid creditBasis');
  }
  settings.bugs.allowBuyWithPartialConfig = !!settings.bugs.allowBuyWithPartialConfig;
  settings.bugs.returnStaysAvailableWhenEmpty = !!settings.bugs.returnStaysAvailableWhenEmpty;
  settings.bugs.allowDiscountCodeReuse = !!settings.bugs.allowDiscountCodeReuse;
  settings.studentResetEnabled = !!settings.studentResetEnabled;
  settings.requiredEmailDomain = (settings.requiredEmailDomain || '').toString().trim();
}

// ===================================================================
// Business-logic helpers
// ===================================================================

function readConfig_(params) {
  return {
    Model: normalizeParam_(params.model),
    Storage: normalizeParam_(params.storage),
    Color: normalizeParam_(params.color),
    Network: normalizeParam_(params.network),
    Accessory: normalizeParam_(params.accessory)
  };
}

function normalizeParam_(v) {
  return (v === undefined || v === null) ? '' : String(v).trim();
}

function computeBasePrice_(config) {
  var total = 0;
  PARAMETERS.forEach(function (p) {
    var val = config[p];
    if (val && PRICE_TABLE[p].hasOwnProperty(val)) {
      total += PRICE_TABLE[p][val];
    }
  });
  return round2_(total);
}

function evaluateDiscount_(email, codeRaw, settings) {
  var code = (codeRaw || '').toString().trim();
  if (settings.level < 2 || !code) {
    return { entered: code, valid: false, message: null };
  }
  if (code.length !== DISCOUNT_CODE_LENGTH) {
    return { entered: code, valid: false, message: 'Unknown code' };
  }
  var mode = settings.bugs.discountCodeMode;
  if (mode === 'acceptNone') {
    return { entered: code, valid: false, message: 'Unknown code' };
  }
  if (mode === 'acceptAny') {
    return { entered: code, valid: true, message: null };
  }
  var row = findDiscountCode_(email, code);
  if (!row) {
    return { entered: code, valid: false, message: 'Unknown code' };
  }
  if (settings.bugs.allowDiscountCodeReuse) {
    return { entered: code, valid: true, message: null };
  }
  if (row.status === 'Active') {
    return { entered: code, valid: true, message: null };
  }
  if (row.status === 'Redeemed') {
    return { entered: code, valid: false, message: 'This code was already used' };
  }
  if (row.status === 'Disabled') {
    return { entered: code, valid: false, message: 'Invalid code. The phone that got you this code was returned.' };
  }
  return { entered: code, valid: false, message: 'Unknown code' };
}

function validateEmail_(email, settings) {
  email = (email || '').toString().trim();
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email || !EMAIL_RE.test(email)) {
    throw new Error('A valid email address is required.');
  }
  if (settings.requiredEmailDomain) {
    var domain = settings.requiredEmailDomain.replace(/^@/, '').toLowerCase();
    if (!email.toLowerCase().endsWith('@' + domain)) {
      throw new Error('Email must end with @' + domain);
    }
  }
  return email;
}

function generateDiscountCode_(email, seq) {
  var localPart = email.split('@')[0];
  var prefix = localPart.substring(0, EMAIL_PREFIX_LENGTH);
  while (prefix.length < EMAIL_PREFIX_LENGTH) prefix += PAD_CHAR;
  var seqStr = seq < 10 ? ('0' + seq) : String(seq);
  return prefix + seqStr;
}

function computeReturnEnabled_(email, settings) {
  return computeReturnEnabledFromPurchases_(getPurchasesForEmail_(email), settings);
}

/** Same as computeReturnEnabled_, but reuses a purchase list already read this request. */
function computeReturnEnabledFromPurchases_(purchases, settings) {
  if (settings.level < 4) return false;
  if (purchases.length === 0) return false;
  if (settings.bugs.returnStaysAvailableWhenEmpty) return true;
  for (var i = 0; i < purchases.length; i++) {
    if (purchases[i].Status === 'Bought') return true;
  }
  return false;
}

function round2_(x) {
  return Math.round((Number(x) || 0) * 100) / 100;
}

// ===================================================================
// Sheet access
// ===================================================================

function ensureSheets_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ensureSheet_(ss, SHEET_PURCHASES, ['PurchaseID', 'StudentEmail', 'PurchaseSeq', 'Model', 'Storage', 'Color', 'Network', 'Accessory', 'BasePrice', 'DiscountCodeUsed', 'PaidPrice', 'CreditApplied', 'RequestedPayment', 'CodeGenerated', 'Status', 'Timestamp']);
  ensureSheet_(ss, SHEET_CODES, ['Code', 'StudentEmail', 'GeneratedByPurchaseID', 'Status', 'CreatedAt']);
  ensureSheet_(ss, SHEET_CREDIT, ['StudentEmail', 'Balance']);
  ensureSheet_(ss, SHEET_LOG, ['Timestamp', 'StudentEmail', 'Action', 'Parameters', 'DiscountCode', 'CalculatedPrice', 'CreditBefore', 'CreditAfter', 'Result', 'Message']);
}

function ensureSheet_(ss, name, headers) {
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    sheet.appendRow(headers);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function getSheet_(name) {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(name);
}

function readRows_(sheetName) {
  var sheet = getSheet_(sheetName);
  var values = sheet.getDataRange().getValues();
  var headers = values[0];
  var rows = [];
  for (var i = 1; i < values.length; i++) {
    var obj = {};
    for (var j = 0; j < headers.length; j++) obj[headers[j]] = values[i][j];
    obj.__row = i + 1;
    rows.push(obj);
  }
  return rows;
}

function appendPurchaseRow_(data) {
  getSheet_(SHEET_PURCHASES).appendRow([
    data.purchaseId, data.email, data.seq,
    data.config.Model, data.config.Storage, data.config.Color, data.config.Network, data.config.Accessory,
    data.basePrice, data.discountCodeUsed, data.paidPrice, data.creditApplied, data.requestedPayment,
    data.codeGenerated, data.status, new Date()
  ]);
}

function appendDiscountCodeRow_(code, email, purchaseId) {
  getSheet_(SHEET_CODES).appendRow([code, email, purchaseId, 'Active', new Date()]);
}

function findDiscountCode_(email, code) {
  var rows = readRows_(SHEET_CODES);
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].StudentEmail === email && rows[i].Code === code) {
      return { rowIndex: rows[i].__row, status: rows[i].Status };
    }
  }
  return null;
}

function markCodeRedeemed_(email, code) {
  var rows = readRows_(SHEET_CODES);
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].StudentEmail === email && rows[i].Code === code && rows[i].Status === 'Active') {
      getSheet_(SHEET_CODES).getRange(rows[i].__row, 4).setValue('Redeemed');
      return;
    }
  }
}

function disableDiscountCode_(email, code) {
  var rows = readRows_(SHEET_CODES);
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].StudentEmail === email && rows[i].Code === code) {
      getSheet_(SHEET_CODES).getRange(rows[i].__row, 4).setValue('Disabled');
      return;
    }
  }
}

/**
 * One read of the Purchases sheet, filtered to a single student. Every
 * caller that needs purchase count, active count, or a config match derives
 * it from this single array instead of re-reading the sheet — important
 * once a class of 30 students has generated thousands of rows across a
 * session (see §performance note in requirements doc, "efficiency" ask).
 */
function getPurchasesForEmail_(email) {
  var rows = readRows_(SHEET_PURCHASES);
  var mine = [];
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].StudentEmail === email) mine.push(rows[i]);
  }
  return mine;
}

/** Pure, in-memory — takes a list already fetched via getPurchasesForEmail_. */
function findMatchInPurchases_(purchases, config) {
  for (var i = 0; i < purchases.length; i++) {
    var r = purchases[i];
    if (r.Status === 'Bought' &&
        String(r.Model) === (config.Model || '') &&
        String(r.Storage) === (config.Storage || '') &&
        String(r.Color) === (config.Color || '') &&
        String(r.Network) === (config.Network || '') &&
        String(r.Accessory) === (config.Accessory || '')) {
      return {
        rowIndex: r.__row,
        basePrice: Number(r.BasePrice),
        paidPrice: Number(r.PaidPrice),
        codeGenerated: r.CodeGenerated,
        row: r
      };
    }
  }
  return null;
}

function markPurchaseReturned_(rowIndex) {
  getSheet_(SHEET_PURCHASES).getRange(rowIndex, 15).setValue('Returned'); // Status column
}

function getStoreCredit_(email) {
  var rows = readRows_(SHEET_CREDIT);
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].StudentEmail === email) return Number(rows[i].Balance) || 0;
  }
  return 0;
}

function setStoreCredit_(email, balance) {
  var sheet = getSheet_(SHEET_CREDIT);
  var rows = readRows_(SHEET_CREDIT);
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].StudentEmail === email) {
      sheet.getRange(rows[i].__row, 2).setValue(balance);
      return;
    }
  }
  sheet.appendRow([email, balance]);
}

function deleteRowsByEmail_(sheetName, email) {
  var sheet = getSheet_(sheetName);
  var rows = readRows_(sheetName);
  var toDelete = [];
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].StudentEmail === email) toDelete.push(rows[i].__row);
  }
  toDelete.sort(function (a, b) { return b - a; });
  for (var j = 0; j < toDelete.length; j++) sheet.deleteRow(toDelete[j]);
}

function clearSheetData_(sheetName) {
  var sheet = getSheet_(sheetName);
  var lastRow = sheet.getLastRow();
  if (lastRow > 1) sheet.deleteRows(2, lastRow - 1);
}

// ===================================================================
// Action logging
// ===================================================================

function newLogEntry_(action) {
  return {
    action: action, email: '', parameters: '', discountCode: '',
    calculatedPrice: '', creditBefore: '', creditAfter: '',
    result: 'Error', message: ''
  };
}

function configToLogString_(config) {
  return [config.Model, config.Storage, config.Color, config.Network, config.Accessory].join('|');
}

/**
 * Appends one row to ActionLog. Deliberately un-locked: an audit log is
 * append-only and doesn't need read-modify-write correctness the way
 * Purchases/StoreCredit do, so it never contends with (or waits behind)
 * the LockService.getScriptLock() that protects those — logging for one
 * student's action never slows down another's Buy/Return. Never throws:
 * a logging failure must not break the student-facing action it's logging.
 */
function logAction_(entry) {
  try {
    getSheet_(SHEET_LOG).appendRow([
      new Date(), entry.email, entry.action, entry.parameters,
      entry.discountCode, entry.calculatedPrice,
      entry.creditBefore, entry.creditAfter,
      entry.result, entry.message
    ]);
  } catch (e) {
    // Swallow — logging is best-effort and must never break the caller.
  }
}
