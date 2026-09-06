/**
 * Main Web App Handler - expects ?role=teacher. A visitor only gets the
 * Teacher Dashboard if they're both asking for it AND on the "Teachers"
 * sheet allowlist (see isAuthorizedTeacher()); anyone else - including a
 * student who simply appends ?role=teacher to the URL - transparently gets
 * the ordinary Student Portal instead, with no error message hinting that
 * a teacher mode exists to try to bypass.
 */
function doGet(e) {
  var role = (e.parameter && e.parameter.role) ? e.parameter.role.toLowerCase() : 'student';

  if (role === 'teacher' && isAuthorizedTeacher()) {
    return HtmlService.createTemplateFromFile('Teacher')
      .evaluate()
      .setTitle('Teacher Dashboard')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
  }

  return HtmlService.createTemplateFromFile('Student')
    .evaluate()
    .setTitle('Student Portal')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/**
 * Returns active user email if available
 */
function getActiveUserEmail() {
  return Session.getActiveUser().getEmail();
}

var STUDENT_EMAIL_DOMAIN = '@post.jce.ac.il';
var FIXED_TABLE_HEADERS = ["Model", "Storage", "Color", "Network", "Accessory"];
var RESPONSES_HEADER = ["Timestamp", "StudentEmail", "QuestionID", "SubmittedData", "IsCorrect", "Score", "MissingCount", "BugsFound", "TestsRun"];
var TEACHERS_SHEET_NAME = 'Teachers';

/**
 * The teacher allowlist: every email in column A (any header text; row 1
 * is always skipped) of the "Teachers" sheet, lower-cased and trimmed.
 * This sheet is never read from, or exposed to, any client-facing
 * function - only from server-side authorization checks like
 * isAuthorizedTeacher() - so listing multiple teachers/TAs here carries no
 * more exposure than the Questions or Responses sheets already do: a
 * student never gets spreadsheet access through the web app itself
 * (it runs as the script owner, not as the visiting user), only through
 * the Sheet's own Drive sharing settings, which is a separate concern.
 */
function getTeacherAllowlist_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(TEACHERS_SHEET_NAME);
  if (!sheet) return [];

  var data = sheet.getDataRange().getValues();
  var emails = [];
  for (var i = 1; i < data.length; i++) {
    var val = data[i][0];
    if (val !== '' && val !== null && val !== undefined) {
      emails.push(val.toString().trim().toLowerCase());
    }
  }
  return emails;
}

function isAuthorizedTeacher() {
  var activeEmail = Session.getActiveUser().getEmail();
  if (!activeEmail) return false;
  return getTeacherAllowlist_().indexOf(activeEmail.toString().trim().toLowerCase()) !== -1;
}

/**
 * Gate for every teacher-only server action (session control, or anything
 * that would hand back other students' raw data or the answer key).
 * Throws rather than returning a boolean so a caller who reaches this
 * without authorization - which should never happen through the app's own
 * UI, only via someone calling the function directly - gets a clear,
 * visible rejection instead of the action silently doing nothing.
 */
function requireTeacher() {
  if (!isAuthorizedTeacher()) {
    throw new Error('You are not authorized to perform this action.');
  }
}

function isValidStudentEmail(email) {
  return typeof email === 'string' && email.trim().toLowerCase().endsWith(STUDENT_EMAIL_DOMAIN);
}

/**
 * Reads questions from the "Questions" sheet, WITH every answer-bearing
 * field included (AcceptableAnswers, BugsDefinition, TestcaseCost). This is
 * the full data every scoring/validation/digestion function needs - but it
 * must NEVER be returned directly to a client. A trailing underscore is not
 * just a naming convention here: Apps Script's google.script.run bridge
 * refuses to expose any top-level function whose name ends in "_" to
 * client-side code at all, so this is a real, platform-enforced boundary,
 * not just obscurity. The public getQuestions() below wraps this and
 * strips every answer-bearing field before returning to a client - see its
 * own comment for why that split exists.
 *
 * Column structure (SRS 4.1):
 * A:QuestionID | B:QuestionText | C:AcceptableAnswers | D:TimeLimitSec
 * E:MinAnswersRequired | F:MaxAnswersAllowed | G:QuestionType | H:BaseScore
 * I:Image (optional) - see getQuestionImage().
 * "Testcase Cost" and "Bugs Definition" (both TABLE_PRICED only - SRS
 * 5.2.5) are looked up by header text rather than a fixed letter, so they
 * can live anywhere in the sheet - see findColumnIndexByHeader().
 *
 * Deliberately does NOT resolve column I's image - that requires a live
 * Drive fetch (see getDriveImageDataUri()) which is too slow to pay on
 * every call. This function is called very often: once per client poll
 * tick (via the public getQuestions() below), and internally by nearly
 * every other function here (submitAnswers, runPriceTest, leaderboards,
 * digestion, etc.) - paying a Drive round-trip on each of those was the
 * actual cause of "Run Test" taking 4-5 seconds, and of "Run All Tests"
 * timing out with spurious errors (each call held the shared script lock
 * for that whole slow duration, so concurrent calls queued up behind it).
 * Clients fetch a question's image separately, once, only when that
 * question becomes active - see getQuestionImage().
 */
function getQuestionsInternal_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Questions");
  if (!sheet) return [];

  var data = sheet.getDataRange().getValues();
  if (data.length <= 1) return [];

  var testcaseCostCol = findColumnIndexByHeader(data[0], 'Testcase Cost');
  var bugsDefinitionCol = findColumnIndexByHeader(data[0], 'Bugs Definition');

  var questions = [];
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    if (row[0] !== "" && row[0] !== null) {
      questions.push({
        id: row[0],
        text: row[1],
        acceptableAnswers: (row[2] !== "" && row[2] !== null) ? row[2].toString() : "",
        timeLimitSec: parseInt(row[3] || 60, 10),
        minAnswers: parseInt(row[4] || 1, 10),
        maxAnswers: parseInt(row[5] || 1, 10),
        type: row[6] ? row[6].toString().toUpperCase().trim() : "TEXT",
        baseScore: parseInt(row[7] || 100, 10),
        testcaseCost: (testcaseCostCol >= 0) ? (parseInt(row[testcaseCostCol], 10) || 0) : 0,
        // TABLE_PRICED only - see getBugsConfig(). Kept as a raw string here
        // (like acceptableAnswers) and validated/parsed only where actually
        // used, so a blank cell on a non-TABLE_PRICED question is a non-issue.
        bugsDefinition: (bugsDefinitionCol >= 0 && row[bugsDefinitionCol] !== "" && row[bugsDefinitionCol] !== null) ? row[bugsDefinitionCol].toString() : ""
      });
    }
  }
  return questions;
}

/**
 * The client-facing question list - called by both Student.html and
 * Teacher.html on every poll. Strips every field that would hand a student
 * the answer key: AcceptableAnswers (the exact accepted values/rows/price
 * table) and BugsDefinition (the exact bug signatures), for EVERY
 * question, not just the active one - a client that only ever needs the
 * currently active question's prompt otherwise has no reason to receive
 * every other question's answers up front. TestcaseCost is dropped too,
 * since nothing client-side reads it.
 *
 * TABLE_PRICED still needs to let the student pick from the price table's
 * known values in its graded dropdown table (see Student.html's
 * getDropdownOptions()) - so instead of the real {value: price} lookup, a
 * priceTableOptions field is sent with just the value NAMES, per header,
 * carrying none of the actual prices.
 */
function getQuestions() {
  var questions = getQuestionsInternal_();
  return questions.map(function (q) {
    var safeQuestion = {
      id: q.id,
      text: q.text,
      timeLimitSec: q.timeLimitSec,
      minAnswers: q.minAnswers,
      maxAnswers: q.maxAnswers,
      type: q.type,
      baseScore: q.baseScore
    };

    if (q.type === 'TABLE_PRICED') {
      var priceTable = getPriceTableConfig(q.acceptableAnswers);
      var options = {};
      FIXED_TABLE_HEADERS.forEach(function (h) {
        options[h] = Object.keys(priceTable[h] || {});
      });
      safeQuestion.priceTableOptions = options;
    }

    return safeQuestion;
  });
}

/**
 * Finds a column's 0-based index in a header row by its text (case/
 * whitespace-insensitive), or -1 if not present. Lets a column like
 * "Testcase Cost" be added anywhere in the Questions sheet without needing
 * to hardcode its letter.
 */
function findColumnIndexByHeader(headerRow, headerName) {
  for (var i = 0; i < headerRow.length; i++) {
    if (headerRow[i] && headerRow[i].toString().trim().toLowerCase() === headerName.toLowerCase()) {
      return i;
    }
  }
  return -1;
}

/**
 * Resolves one question's image on demand, by its position in getQuestions()'s
 * array (0-based, skipping blank-ID rows the same way that function does).
 * Called by clients only when that question becomes the active one - not on
 * every poll tick, and not for every question up front - to keep the
 * (comparatively slow) Drive fetch off the hot path. See getQuestions().
 *
 * The Image column is looked up by header text ("Image"), falling back to
 * column I only if no such header exists - a hardcoded column I broke once
 * a later column (e.g. "Testcase Cost") was inserted before it, shifting
 * every column after it to the right.
 */
function getQuestionImage(qIndex) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Questions");
  if (!sheet) return '';

  var range = sheet.getDataRange();
  var values = range.getValues();
  var formulas = range.getFormulas();
  if (values.length === 0) return '';

  var imageCol = findColumnIndexByHeader(values[0], 'Image');
  if (imageCol < 0) imageCol = 8; // fall back to column I for sheets with no "Image" header

  var count = -1;
  for (var i = 1; i < values.length; i++) {
    if (values[i][0] !== "" && values[i][0] !== null) {
      count++;
      if (count === qIndex) {
        return extractImageUrl(values[i][imageCol], formulas[i][imageCol]);
      }
    }
  }
  return '';
}

/**
 * Resolves the image to show for a question from Questions column I.
 * Accepts, in order of preference: a Google Drive file ID or share link
 * (bare ID, a `/file/d/ID/...` link, or a `...?id=ID` link) - found either
 * as the cell's plain text, inside an `=IMAGE("...")` formula, or from
 * Sheets' native "Insert image in cell" if that was itself inserted by URL.
 * A Drive reference is read server-side via DriveApp (as the script owner,
 * so the file does NOT need to be publicly shared) and returned as an
 * embedded `data:` URI - no external hosting, no hotlink/referrer issues.
 * Falls back to returning a plain external http(s) URL as-is if the cell
 * doesn't reference a Drive file. Returns "" if nothing usable is found.
 */
function extractImageUrl(cellValue, cellFormula) {
  var candidate = '';

  if (cellFormula) {
    var match = cellFormula.match(/=image\(\s*"([^"]+)"/i);
    if (match) candidate = match[1];
  }

  if (!candidate && cellValue && typeof cellValue === 'object' && typeof cellValue.getUrl === 'function') {
    candidate = cellValue.getUrl() || '';
  }

  if (!candidate && cellValue) {
    candidate = cellValue.toString().trim();
  }

  if (!candidate) return '';

  var driveFileId = extractDriveFileId(candidate);
  if (driveFileId) {
    // A Drive reference must resolve to an embedded data URI or nothing -
    // never fall back to the raw Drive URL, since that's the same
    // hotlink-blocked link this whole approach exists to avoid.
    return getDriveImageDataUri(driveFileId);
  }

  return candidate.indexOf('http') === 0 ? candidate : '';
}

function extractDriveFileId(str) {
  var match = str.match(/\/file\/d\/([a-zA-Z0-9_-]{10,})/);
  if (match) return match[1];

  match = str.match(/[?&]id=([a-zA-Z0-9_-]{10,})/);
  if (match) return match[1];

  if (/^[a-zA-Z0-9_-]{20,}$/.test(str.trim())) return str.trim();

  return null;
}

function getDriveImageDataUri(fileId) {
  try {
    var blob = DriveApp.getFileById(fileId).getBlob();
    var contentType = blob.getContentType() || 'image/png';
    var base64 = Utilities.base64Encode(blob.getBytes());
    return 'data:' + contentType + ';base64,' + base64;
  } catch (err) {
    Logger.log('getDriveImageDataUri failed for fileId=' + fileId + ': ' + err.message);
    return '';
  }
}

/**
 * Sets the active question index and computes end time based on duration.
 * Also records `originalEndTime`, a snapshot that "Add 1 Min" never touches
 * (see addTime()) - scoring's time bonus is computed against this original
 * deadline, not the possibly-extended one, so extending time helps students
 * avoid a Fail but never inflates their score beyond what the original
 * window would have allowed.
 *
 * For a TABLE_PRICED question, this also validates its "Bugs Definition"
 * (see getBugsConfig()) before launching - a misconfigured question throws
 * here and is never started, rather than going live and failing later once
 * students are already interacting with it.
 */
function setActiveQuestion(qIndex, durationSeconds) {
  requireTeacher();
  var question = getQuestionsInternal_()[qIndex];
  if (!question) {
    throw new Error('Invalid question index.');
  }
  if (question.type === 'TABLE_PRICED') {
    getBugsConfig(question); // throws if missing/invalid - question must not start
  }

  var props = PropertiesService.getScriptProperties();
  var now = Date.now();
  var endTime = now + (parseInt(durationSeconds, 10) * 1000);

  props.setProperty('currentQIndex', qIndex.toString());
  props.setProperty('status', 'ACTIVE');
  props.setProperty('endTime', endTime.toString());
  props.setProperty('originalEndTime', endTime.toString());

  return {
    status: 'ACTIVE',
    currentQIndex: qIndex,
    endTime: endTime
  };
}

/**
 * Advances to the next sequential question (by array index) and launches it
 * automatically using that question's own TimeLimitSec.
 */
function launchNextQuestion() {
  requireTeacher();
  var props = PropertiesService.getScriptProperties();
  var currentQIndex = parseInt(props.getProperty('currentQIndex') || '-1', 10);
  var questions = getQuestionsInternal_();
  var nextIndex = currentQIndex + 1;

  if (nextIndex < 0 || nextIndex >= questions.length) {
    throw new Error('No next question available.');
  }

  return setActiveQuestion(nextIndex, questions[nextIndex].timeLimitSec);
}

/**
 * Manually stops the current active question
 */
function stopQuestion() {
  requireTeacher();
  var props = PropertiesService.getScriptProperties();
  props.setProperty('status', 'WAITING');
  props.setProperty('endTime', '0');

  return { status: 'WAITING' };
}

/**
 * Extends the current active question's countdown by the given number of
 * seconds (teacher "Add 1 Min" control). Deliberately only touches `endTime`
 * (the accept-cutoff / countdown-display deadline), never `originalEndTime`
 * (the deadline scoring's time bonus is computed against) - see
 * setActiveQuestion().
 */
function addTime(seconds) {
  requireTeacher();
  var props = PropertiesService.getScriptProperties();
  var status = props.getProperty('status') || 'WAITING';
  if (status !== 'ACTIVE') {
    throw new Error('No active question to extend.');
  }

  var endTime = parseInt(props.getProperty('endTime') || '0', 10);
  var newEndTime = endTime + (parseInt(seconds, 10) * 1000);
  props.setProperty('endTime', newEndTime.toString());

  return { status: 'ACTIVE', endTime: newEndTime };
}

/**
 * Returns the active session state for student & teacher polling
 */
function getSessionState() {
  var props = PropertiesService.getScriptProperties();
  var status = props.getProperty('status') || 'WAITING';
  var currentQIndex = parseInt(props.getProperty('currentQIndex') || '-1', 10);
  var endTime = parseInt(props.getProperty('endTime') || '0', 10);

  if (status === 'ACTIVE' && Date.now() >= endTime) {
    status = 'WAITING';
    props.setProperty('status', 'WAITING');
  }

  return {
    status: status,
    currentQIndex: currentQIndex,
    endTime: endTime
  };
}

/**
 * Counts unique student submissions for the current active question
 */
function getStudentResponseCount() {
  var props = PropertiesService.getScriptProperties();
  var currentQIndex = parseInt(props.getProperty('currentQIndex') || '-1', 10);
  if (currentQIndex < 0) return 0;

  var questions = getQuestionsInternal_();
  if (!questions[currentQIndex]) return 0;
  var currentQId = questions[currentQIndex].id;

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var respSheet = ss.getSheetByName("Responses");
  if (!respSheet) return 0;

  var data = respSheet.getDataRange().getValues();
  var count = 0;
  for (var i = 1; i < data.length; i++) {
    if (data[i][2] == currentQId) {
      count++;
    }
  }
  return count;
}

function normalizeToken(s) {
  return s.toString().trim().toLowerCase();
}

/**
 * True if str is valid JSON. Used to tell a real graded submission
 * (JSON-encoded payload) apart from a TABLE_PRICED price-test log row
 * (plain "Model|Storage|...|Price" text) sharing the same Responses sheet.
 */
function isJsonParseable(str) {
  try {
    JSON.parse(str);
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Validates NUMERIC / TEXT answers (SRS 5.2.1 & 5.2.2).
 * Pass condition: all inputs valid, no duplicates, count within [min, max].
 */
function validateSimpleAnswers(question, payload) {
  if (!Array.isArray(payload)) return { isCorrect: false, missingCount: 0 };

  var count = payload.length;
  if (count < question.minAnswers || count > question.maxAnswers) {
    return { isCorrect: false, missingCount: 0 };
  }

  var normalized = [];
  for (var i = 0; i < payload.length; i++) {
    var raw = (payload[i] === null || payload[i] === undefined) ? '' : payload[i].toString().trim();

    if (question.type === 'TEXT' && raw.length > 256) {
      return { isCorrect: false, missingCount: 0 };
    }
    if (question.type === 'NUMERIC' && !/^\d+(\.\d+)?$/.test(raw)) {
      return { isCorrect: false, missingCount: 0 };
    }
    if (raw === '') {
      return { isCorrect: false, missingCount: 0 };
    }

    normalized.push(normalizeToken(raw));
  }

  // No duplicates allowed
  var seen = {};
  for (var j = 0; j < normalized.length; j++) {
    if (seen[normalized[j]]) return { isCorrect: false, missingCount: 0 };
    seen[normalized[j]] = true;
  }

  var acceptable = (question.acceptableAnswers || '')
    .split(';')
    .map(function (s) { return s.trim().toLowerCase(); })
    .filter(function (s) { return s.length > 0; });
  var acceptableSet = {};
  acceptable.forEach(function (a) { acceptableSet[a] = true; });

  var isCorrect = normalized.every(function (a) { return acceptableSet[a] === true; });

  return { isCorrect: isCorrect, missingCount: 0 };
}

/**
 * Validates TABLE answers (SRS 5.2.3).
 * AcceptableAnswers is a JSON object mapping each fixed header to the array
 * of required values for that column. MissingCount = required values never
 * covered by any submitted row. A submitted cell value that is not in that
 * column's valid list is also a fail. Pass condition: MissingCount === 0
 * AND every submitted cell value is a valid value for its column.
 */
function validateTableAnswers(question, payload) {
  var required = {};
  try {
    required = JSON.parse(question.acceptableAnswers || '{}');
  } catch (err) {
    required = {};
  }

  var requiredSets = {};
  FIXED_TABLE_HEADERS.forEach(function (h) {
    var requiredValues = Array.isArray(required[h]) ? required[h] : [];
    var set = {};
    requiredValues.forEach(function (val) { set[normalizeToken(val)] = true; });
    requiredSets[h] = set;
  });

  var submittedByHeader = {};
  FIXED_TABLE_HEADERS.forEach(function (h) { submittedByHeader[h] = {}; });

  var hasInvalidValue = false;

  if (Array.isArray(payload)) {
    payload.forEach(function (row) {
      if (!row) return;
      FIXED_TABLE_HEADERS.forEach(function (h) {
        var val = row[h];
        if (val !== undefined && val !== null && val.toString().trim() !== '') {
          var normalizedVal = normalizeToken(val);
          submittedByHeader[h][normalizedVal] = true;
          if (!requiredSets[h][normalizedVal]) {
            hasInvalidValue = true;
          }
        }
      });
    });
  }

  var missingCount = 0;
  FIXED_TABLE_HEADERS.forEach(function (h) {
    Object.keys(requiredSets[h]).forEach(function (normalizedVal) {
      if (!submittedByHeader[h][normalizedVal]) {
        missingCount++;
      }
    });
  });

  return { isCorrect: (missingCount === 0 && !hasInvalidValue), missingCount: missingCount };
}

function comboKey(row) {
  return FIXED_TABLE_HEADERS.map(function (h) {
    var val = (row && row[h] !== undefined && row[h] !== null) ? row[h] : '';
    return normalizeToken(val);
  }).join('|');
}

/**
 * Scores a combinatorial-test-suite answer table: TABLE_SCORED (e.g. Q4), or
 * the graded 3-row answer table embedded in a TABLE_PRICED question (e.g.
 * Q5). The valid row combinations are read either directly as a JSON array
 * (TABLE_SCORED's AcceptableAnswers format) or from a nested `validCombos`
 * array (TABLE_PRICED's AcceptableAnswers format, which also carries the
 * price-lookup table used by that question's ungraded price-calculator
 * table). A row is only counted correct the first time a given valid
 * combination appears in the submission - a later row repeating an
 * already-counted combination is a duplicate and fails. Each incorrect/
 * duplicate row, and each valid combination never covered by any submitted
 * row, costs 10 points off BaseScore. This only determines the
 * pre-time-bonus points, per-row correctness, and tier; submitAnswers()
 * applies the tier-specific time bonus and final score.
 *
 * Tiers scale proportionally to BaseScore, preserving Q4's original 61/130
 * ratio at any BaseScore: points below ~47% of BaseScore -> FAIL (score 0);
 * up to BaseScore -> PARTIAL (orange, score = points + half the seconds
 * remaining); at or above BaseScore -> PASS (score = BaseScore + seconds
 * remaining). For Q4 (BaseScore 130) this reproduces the original 61/130
 * thresholds exactly.
 */
function scoreCombinatorialTable(question, payload) {
  var validCombos = [];
  try {
    var parsed = JSON.parse(question.acceptableAnswers || '[]');
    if (Array.isArray(parsed)) {
      validCombos = parsed;
    } else if (parsed && Array.isArray(parsed.validCombos)) {
      validCombos = parsed.validCombos;
    }
  } catch (err) {
    validCombos = [];
  }

  var validSet = {};
  validCombos.forEach(function (combo) { validSet[comboKey(combo)] = true; });

  var seenValidCombos = {};
  var rowResults = [];
  var incorrectCount = 0;

  if (Array.isArray(payload)) {
    payload.forEach(function (row) {
      var key = comboKey(row);
      var isValidCombo = validSet[key] === true;
      var isDuplicate = isValidCombo && seenValidCombos[key] === true;
      var isRowValid = isValidCombo && !isDuplicate;

      if (isValidCombo) seenValidCombos[key] = true;

      rowResults.push(isRowValid);
      if (!isRowValid) incorrectCount++;
    });
  }

  var missingCount = 0;
  validCombos.forEach(function (combo) {
    if (!seenValidCombos[comboKey(combo)]) missingCount++;
  });

  var points = question.baseScore - (10 * (incorrectCount + missingCount));

  var failThreshold = Math.ceil(question.baseScore * 61 / 130);
  var passThreshold = question.baseScore;

  var tier;
  if (points < failThreshold) {
    tier = 'FAIL';
  } else if (points < passThreshold) {
    tier = 'PARTIAL';
  } else {
    tier = 'PASS';
  }

  return { points: points, incorrectCount: incorrectCount, missingCount: missingCount, rowResults: rowResults, tier: tier };
}

function cellEq(row, h, expected) {
  var val = (row && row[h] !== undefined && row[h] !== null) ? row[h].toString().trim() : '';
  return normalizeToken(val) === normalizeToken(expected);
}

/**
 * A TABLE_PRICED question's bug list: an array of
 * { conditions: {Header: value, ...}, effect: {...} }, read from that
 * question's "Bugs Definition" column (found by header text, case-
 * insensitively, via findColumnIndexByHeader() - see getQuestions()). A row
 * matches a bug when ALL of its conditions match (cellEq); bugs are checked
 * in array order, first match wins.
 *
 * effect.type is one of:
 *   "flat"   - the price is always effect.value, ignoring the price table.
 *   "string" - the price cell shows the literal text effect.value.
 *   "null"   - no price is shown for this row at all.
 *   "delta"  - the price is the normally-computed price plus effect.value
 *              (which may be negative) - or, if the normal computation
 *              itself errors (e.g. a blank/unmatched cell), that error is
 *              returned as-is rather than trying to add to it.
 *
 * Throws if the column is missing/blank or isn't a valid JSON array - a
 * TABLE_PRICED question with no bugs must say so explicitly with `[]`,
 * rather than a blank cell silently meaning the same thing. This is also
 * what setActiveQuestion() checks before launching the question at all, so
 * a misconfigured question fails loudly (with this same message) instead
 * of launching in a broken state.
 */
function getBugsConfig(question) {
  var raw = (question.bugsDefinition || '').toString().trim();
  if (raw === '') {
    throw new Error('Question ' + question.id + ' has no "Bugs Definition" set in the Questions sheet (use [] for a question with no bugs).');
  }

  var parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error('Question ' + question.id + '\'s "Bugs Definition" is not valid JSON: ' + err.message);
  }

  if (!Array.isArray(parsed)) {
    throw new Error('Question ' + question.id + '\'s "Bugs Definition" must be a JSON array (use [] for no bugs).');
  }

  return parsed;
}

// Loose match: only the headers a bug's `conditions` actually names are
// checked; any header it omits is ignored regardless of that row's value.
// Used for the ungraded price-calculator table (computeRowPrice()), where
// students always type/pick a concrete value for every field - there's no
// "Any" concept there, so a bug like "Storage = 1TB" must trigger no matter
// what the other 4 concrete fields happen to be.
function rowMatchesBugConditionsLoose(row, conditions) {
  return Object.keys(conditions || {}).every(function (h) { return cellEq(row, h, conditions[h]); });
}

// Strict match: ALL 5 FIXED_TABLE_HEADERS must match, and a header a bug's
// `conditions` omits is treated as requiring the literal value "Any" - not
// as a wildcard. Used for the graded bug-report table (scoreBugReports()),
// where the student explicitly picks "Any" from a dropdown for a field
// they judge irrelevant to a bug; picking a concrete value instead (even
// one that happens to be technically compatible) means they didn't
// correctly identify the bug's actual trigger, and must not count as a
// match just because the unrelated fields were never checked.
function rowMatchesBugConditionsStrict(row, conditions) {
  return FIXED_TABLE_HEADERS.every(function (h) {
    var expected = (conditions && conditions[h] !== undefined) ? conditions[h] : 'Any';
    return cellEq(row, h, expected);
  });
}

function findMatchingBugIndex(bugs, row, strict) {
  for (var i = 0; i < bugs.length; i++) {
    var isMatch = strict
      ? rowMatchesBugConditionsStrict(row, bugs[i].conditions)
      : rowMatchesBugConditionsLoose(row, bugs[i].conditions);
    if (isMatch) return i;
  }
  return -1;
}

/**
 * Computes the price of a single test row for the ungraded price-calculator
 * table of a TABLE_PRICED question (e.g. Q5, Q6). AcceptableAnswers is
 * normally a JSON object with a `priceTable` field mapping each fixed
 * header to a {value: price} lookup - but a flat {header: {value: price}}
 * object with no `priceTable` wrapper is also accepted and treated as the
 * price table directly, for compatibility with sheets configured before
 * that wrapper was introduced (see getPriceTableConfig()).
 *
 * The question's bugs (see getBugsConfig()) are checked first, in order; if
 * none apply, the price is the sum of each column's looked-up value, and a
 * blank or unmatched cell makes the whole row an error.
 *
 * Returns a Number (the price), a String (an "Error: ..." message, or any
 * other literal text a bug's effect specifies, to show instead of a
 * price), or null (show/log nothing for this row).
 */
function getPriceTableConfig(acceptableAnswers) {
  try {
    var parsed = JSON.parse(acceptableAnswers || '{}');
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return (parsed.priceTable && typeof parsed.priceTable === 'object') ? parsed.priceTable : parsed;
  } catch (err) {
    return {};
  }
}

function computeBasePrice(question, row) {
  var priceTable = getPriceTableConfig(question.acceptableAnswers);
  var total = 0;
  for (var i = 0; i < FIXED_TABLE_HEADERS.length; i++) {
    var h = FIXED_TABLE_HEADERS[i];
    var val = (row && row[h] !== undefined && row[h] !== null) ? row[h].toString().trim() : '';
    if (val === '') return 'Error: Invalid configuration';

    var columnPrices = priceTable[h] || {};
    var matchKey = Object.keys(columnPrices).find(function (k) { return normalizeToken(k) === normalizeToken(val); });
    if (matchKey === undefined) return 'Error: Invalid configuration';

    total += Number(columnPrices[matchKey]) || 0;
  }
  return total;
}

function applyBugEffect(effect, question, row) {
  if (effect.type === 'flat') return Number(effect.value);
  if (effect.type === 'string') return effect.value.toString();
  if (effect.type === 'null') return null;
  if (effect.type === 'delta') {
    var base = computeBasePrice(question, row);
    return (typeof base === 'number') ? (base + Number(effect.value)) : base;
  }
  return computeBasePrice(question, row);
}

function computeRowPrice(question, row) {
  var bugs = getBugsConfig(question);
  var matchedIndex = findMatchingBugIndex(bugs, row, false); // loose - see rowMatchesBugConditionsLoose()
  if (matchedIndex !== -1) {
    return applyBugEffect(bugs[matchedIndex].effect || {}, question, row);
  }
  return computeBasePrice(question, row);
}

// Human-readable description of a bug's effect, for buildCorrectAnswerText().
function describeBugEffect(effect) {
  if (effect.type === 'flat') return 'price is set to ' + effect.value;
  if (effect.type === 'string') return 'price shows "' + effect.value + '"';
  if (effect.type === 'null') return 'no price is shown';
  if (effect.type === 'delta') {
    var n = Number(effect.value);
    return 'price is the correctly calculated price ' + (n >= 0 ? '+ ' + n : '- ' + Math.abs(n));
  }
  return '(unknown effect)';
}

/**
 * Scores the fixed 3-row "bug report" answer table of a TABLE_PRICED
 * question (e.g. Q5, Q6). AcceptableAnswers' `validCombos` array is not
 * used here (that was the old Q4-style model) - instead each row is
 * checked against that question's own bugs (see getBugsConfig()). A row
 * only counts the first time a given bug is reported in the submission; a
 * row repeating an already-claimed bug, or matching no bug at all, earns 0
 * (no penalty - submissions are one-shot, no retries). Each correctly and
 * uniquely reported bug earns BaseScore + secondsRemaining. From that raw
 * total, `question.testcaseCost * testsRun` is then deducted (SRS 5.2.5 -
 * each "Run Test" during the exploration phase costs points, floored at 0)
 * to get the final score. Tier (FAIL/PARTIAL/PASS) reflects bugsFound
 * alone, not the cost deduction, so it still communicates correctness.
 */
function scoreBugReports(question, payload, secondsRemaining, testsRun) {
  secondsRemaining = secondsRemaining || 0;
  testsRun = testsRun || 0;

  var bugs = getBugsConfig(question);
  var claimed = bugs.map(function () { return false; });
  var rowResults = [];
  var rowScores = [];
  var bugsFound = 0;

  if (Array.isArray(payload)) {
    payload.forEach(function (row) {
      var matchedBugIndex = findMatchingBugIndex(bugs, row, true); // strict - see rowMatchesBugConditionsStrict()

      var isRowCorrect = false;
      var rowScore = 0;

      if (matchedBugIndex !== -1 && !claimed[matchedBugIndex]) {
        claimed[matchedBugIndex] = true;
        isRowCorrect = true;
        rowScore = question.baseScore + secondsRemaining;
        bugsFound++;
      }

      rowResults.push(isRowCorrect);
      rowScores.push(rowScore);
    });
  }

  var rawScore = rowScores.reduce(function (a, b) { return a + b; }, 0);
  var testCost = (question.testcaseCost || 0) * testsRun;
  var totalScore = Math.max(0, rawScore - testCost);

  var tier;
  if (bugsFound >= bugs.length) {
    tier = 'PASS';
  } else if (bugsFound > 0) {
    tier = 'PARTIAL';
  } else {
    tier = 'FAIL';
  }

  return { score: totalScore, rowResults: rowResults, bugsFound: bugsFound, testsRun: testsRun, tier: tier };
}

/**
 * Computes the price of a single test row for a TABLE_PRICED question's
 * price-calculator table (SRS 5.x, Q5). Unlike submitAnswers(), this is not
 * graded and is not logged anywhere - it's a pure, repeatable computation so
 * students can explore the pricing engine freely. How many times a student
 * calls this (individually or via "Run All Tests") is tracked client-side
 * and reported once, as a count, alongside their final graded submission -
 * see submitAnswers()'s testsRun parameter and SRS 5.2.5.
 */
function runPriceTest(email, qId, row, expectedPrice) {
  if (!isValidStudentEmail(email)) {
    throw new Error('You must enter your Azrieli email address!');
  }

  var questions = getQuestionsInternal_();
  var question = questions.find(function (q) { return q.id == qId; });
  if (!question) {
    throw new Error('Unknown question.');
  }

  var price = computeRowPrice(question, row);
  var priceSegment = (price === null || price === undefined) ? '' : price.toString();
  var isMatch = normalizeToken(priceSegment) === normalizeToken(expectedPrice || '');

  return { price: price, isMatch: isMatch };
}

function getResponsesSheet(ss) {
  var respSheet = ss.getSheetByName("Responses");
  if (!respSheet) {
    respSheet = ss.insertSheet("Responses");
    respSheet.appendRow(RESPONSES_HEADER);
  }
  return respSheet;
}

/**
 * Submits student responses and performs answer validation & scoring.
 * Enforces: Azrieli email domain, one submission per student per question,
 * and safe concurrent writes via LockService (SRS 5.4).
 *
 * `testsRun` is only meaningful for TABLE_PRICED (SRS 5.2.5): the number of
 * "Run Test" calls (individual clicks, or rows processed by "Run All
 * Tests") the student made against the price calculator before submitting,
 * as counted client-side. It's recorded on this graded row (TestsRun
 * column) and used to reduce the score by BaseScore's Testcase Cost per
 * test - see scoreBugReports(). Ignored for all other question types.
 */
function submitAnswers(email, qId, payload, testsRun) {
  if (!isValidStudentEmail(email)) {
    throw new Error('You must enter your Azrieli email address!');
  }
  var normalizedEmail = email.toString().trim().toLowerCase();

  var lock = LockService.getScriptLock();
  lock.waitLock(10000);

  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var respSheet = getResponsesSheet(ss);

    var data = respSheet.getDataRange().getValues();
    for (var i = 1; i < data.length; i++) {
      if (data[i][1] === normalizedEmail && data[i][2] == qId && isJsonParseable(data[i][3])) {
        throw new Error('You have already submitted an answer for this question.');
      }
    }

    var questions = getQuestionsInternal_();
    var question = questions.find(function (q) { return q.id == qId; });
    if (!question) {
      throw new Error('Unknown question.');
    }

    var props = PropertiesService.getScriptProperties();
    // Scored against the ORIGINAL deadline, not any "Add 1 Min" extension -
    // extending time should give students more room to answer without
    // inflating what a correct answer is worth (see setActiveQuestion()).
    var originalEndTime = parseInt(props.getProperty('originalEndTime') || props.getProperty('endTime') || '0', 10);
    var secondsRemaining = Math.max(0, Math.floor((originalEndTime - Date.now()) / 1000));

    var isOverallCorrect, score, missingCount, response;
    var bugsFoundForRow = 0, testsRunForRow = 0;

    if (question.type === 'TABLE_SCORED') {
      var scored = scoreCombinatorialTable(question, payload);
      if (scored.tier === 'FAIL') {
        score = 0;
      } else if (scored.tier === 'PARTIAL') {
        score = scored.points + Math.floor(secondsRemaining / 2);
      } else {
        score = question.baseScore + secondsRemaining;
      }
      isOverallCorrect = (scored.tier === 'PASS');
      missingCount = scored.missingCount;
      response = { isOverallCorrect: isOverallCorrect, score: score, tier: scored.tier, rowResults: scored.rowResults };
    } else if (question.type === 'TABLE_PRICED') {
      var bugScore = scoreBugReports(question, payload, secondsRemaining, testsRun);
      isOverallCorrect = (bugScore.tier === 'PASS');
      score = bugScore.score;
      missingCount = 0; // superseded by the explicit BugsFound column below
      bugsFoundForRow = bugScore.bugsFound;
      testsRunForRow = bugScore.testsRun;
      response = { isOverallCorrect: isOverallCorrect, score: score, tier: bugScore.tier, rowResults: bugScore.rowResults };
    } else {
      var result = (question.type === 'TABLE')
        ? validateTableAnswers(question, payload)
        : validateSimpleAnswers(question, payload);
      isOverallCorrect = result.isCorrect;
      score = isOverallCorrect ? (question.baseScore + secondsRemaining) : 0;
      missingCount = result.missingCount;
      response = { isOverallCorrect: isOverallCorrect, score: score };
    }

    var payloadString = JSON.stringify(payload);
    respSheet.appendRow([new Date(), normalizedEmail, qId, payloadString, isOverallCorrect, score, missingCount, bugsFoundForRow, testsRunForRow]);

    return response;
  } finally {
    lock.releaseLock();
  }
}

/**
 * Fetches existing submission for a student on a specific question
 */
function getStudentSubmission(email, qId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var respSheet = ss.getSheetByName("Responses");
  if (!respSheet) return null;
  var normalizedEmail = email.toString().trim().toLowerCase();

  var data = respSheet.getDataRange().getValues();
  for (var i = data.length - 1; i >= 1; i--) {
    if (data[i][1] === normalizedEmail && data[i][2] == qId && isJsonParseable(data[i][3])) {
      var submittedAnswers = JSON.parse(data[i][3]);
      var result = {
        submittedAnswers: submittedAnswers,
        isOverallCorrect: data[i][4],
        score: data[i][5]
      };

      var questions = getQuestionsInternal_();
      var question = questions.find(function (q) { return q.id == qId; });
      if (question && question.type === 'TABLE_SCORED') {
        var scored = scoreCombinatorialTable(question, submittedAnswers);
        result.tier = scored.tier;
        result.rowResults = scored.rowResults;
      } else if (question && question.type === 'TABLE_PRICED') {
        var bugScore = scoreBugReports(question, submittedAnswers, 0);
        result.tier = bugScore.tier;
        result.rowResults = bugScore.rowResults;
      }

      return result;
    }
  }
  return null;
}

function getAllResponses() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Responses");
  if (!sheet) return [];

  var data = sheet.getDataRange().getValues();
  var out = [];
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    if (row[1] === "" || row[1] === null) continue;

    var submittedData;
    try {
      submittedData = JSON.parse(row[3]);
    } catch (e) {
      submittedData = row[3];
    }

    out.push({
      timestamp: row[0],
      email: row[1],
      qId: row[2],
      submittedData: submittedData,
      isCorrect: (row[4] === true || row[4] === 'TRUE'),
      score: Number(row[5]) || 0,
      missingCount: Number(row[6]) || 0,
      bugsFound: Number(row[7]) || 0,
      testsRun: Number(row[8]) || 0
    });
  }
  return out;
}

/**
 * Top 10 (Current Question) and Top 10 (Overall) leaderboards.
 * Updates live regardless of session ACTIVE/WAITING status (SRS 5.3.2, 5.3.4).
 * Each row also carries bugsFound/testsRun totals (SRS 5.2.5) - these are
 * only ever non-zero for TABLE_PRICED responses, so they naturally read as
 * 0 for students/boards not involving a TABLE_PRICED question.
 */
function getLeaderboards() {
  requireTeacher(); // raw student emails - never expose to a student caller
  var props = PropertiesService.getScriptProperties();
  var currentQIndex = parseInt(props.getProperty('currentQIndex') || '-1', 10);
  var questions = getQuestionsInternal_();
  var currentQId = (currentQIndex >= 0 && questions[currentQIndex]) ? questions[currentQIndex].id : null;

  var responses = getAllResponses();
  var currentQuestionStats = {};
  var overallStats = {};

  function addStats(map, r) {
    if (!map[r.email]) map[r.email] = { email: r.email, score: 0, bugsFound: 0, testsRun: 0 };
    map[r.email].score += r.score;
    map[r.email].bugsFound += r.bugsFound;
    map[r.email].testsRun += r.testsRun;
  }

  responses.forEach(function (r) {
    addStats(overallStats, r);
    if (currentQId !== null && r.qId == currentQId) {
      addStats(currentQuestionStats, r);
    }
  });

  function toSortedTop10(statsMap) {
    return Object.keys(statsMap)
      .map(function (email) { return statsMap[email]; })
      .sort(function (a, b) { return b.score - a.score; })
      .slice(0, 10);
  }

  return {
    currentQuestion: toSortedTop10(currentQuestionStats),
    overall: toSortedTop10(overallStats)
  };
}

/**
 * Digestion analytics for a given question index (SRS 5.3.3): a bar-chart
 * histogram of submitted numerical answers for NUMERIC/TEXT questions, of
 * MissingCount values for TABLE questions, of FAIL/PARTIAL/PASS tier counts
 * for TABLE_SCORED questions, or of how many of the 3 known bugs each
 * student found (their graded submission's BugsFound column) for
 * TABLE_PRICED questions. Intended to be requested by the Teacher UI only
 * once the question session is closed.
 */
function getQuestionDigestion(qIndex) {
  requireTeacher(); // includes the answer key - never expose to a student caller
  var questions = getQuestionsInternal_();
  var question = questions[qIndex];
  if (!question) return null;

  var responses = getAllResponses().filter(function (r) { return r.qId == question.id; });

  var histogramMap = {};
  var tierOrder = null;
  if (question.type === 'TABLE_SCORED') {
    tierOrder = ['FAIL', 'PARTIAL', 'PASS'];
    tierOrder.forEach(function (t) { histogramMap[t] = 0; });
    responses.forEach(function (r) {
      var tier = scoreCombinatorialTable(question, r.submittedData).tier;
      histogramMap[tier] = (histogramMap[tier] || 0) + 1;
    });
  } else if (question.type === 'TABLE') {
    responses.forEach(function (r) {
      var key = r.missingCount.toString();
      histogramMap[key] = (histogramMap[key] || 0) + 1;
    });
  } else if (question.type === 'TABLE_PRICED') {
    var totalBugs = getBugsConfig(question).length;
    var bugCounts = {};
    for (var b = 0; b <= totalBugs; b++) bugCounts[b] = 0;
    responses.forEach(function (r) {
      // Skip any legacy per-test log rows left over from before this sheet
      // stopped logging individual "Run Test" calls - only a real graded
      // submission (a JSON array payload) counts here.
      if (!Array.isArray(r.submittedData)) return;
      var n = Math.max(0, Math.min(totalBugs, r.bugsFound));
      bugCounts[n] = (bugCounts[n] || 0) + 1;
    });
    tierOrder = [];
    for (var b2 = 0; b2 <= totalBugs; b2++) {
      tierOrder.push(b2 + (b2 === 1 ? ' bug found' : ' bugs found'));
    }
    tierOrder.forEach(function (label, idx) { histogramMap[label] = bugCounts[idx] || 0; });
  } else {
    responses.forEach(function (r) {
      var vals = Array.isArray(r.submittedData) ? r.submittedData : [r.submittedData];
      vals.forEach(function (v) {
        var key = (v === null || v === undefined) ? '' : v.toString();
        if (key === '') return;
        histogramMap[key] = (histogramMap[key] || 0) + 1;
      });
    });
  }

  var histogram = tierOrder
    ? tierOrder.map(function (t) { return { label: t, count: histogramMap[t] }; })
    : Object.keys(histogramMap).map(function (key) {
        return { label: key, count: histogramMap[key] };
      }).sort(function (a, b) {
        var na = parseFloat(a.label), nb = parseFloat(b.label);
        if (!isNaN(na) && !isNaN(nb)) return na - nb;
        return a.label.localeCompare(b.label);
      });

  return {
    qType: question.type,
    histogram: histogram,
    correctAnswer: buildCorrectAnswerText(question)
  };
}

/**
 * Human-readable "answer key" text for a question, shown only on the
 * Teacher UI's digestion panel (i.e. only once the question is closed) -
 * students never see this. Format depends on QuestionType.
 */
function buildCorrectAnswerText(question) {
  if (question.type === 'NUMERIC' || question.type === 'TEXT') {
    var vals = (question.acceptableAnswers || '')
      .split(';')
      .map(function (s) { return s.trim(); })
      .filter(function (s) { return s.length > 0; });
    return vals.length ? vals.join(', ') : '(none defined)';
  }

  if (question.type === 'TABLE') {
    var required = {};
    try { required = JSON.parse(question.acceptableAnswers || '{}'); } catch (err) { required = {}; }
    return FIXED_TABLE_HEADERS.map(function (h) {
      var vals = Array.isArray(required[h]) ? required[h] : [];
      return h + ': ' + (vals.length ? vals.join(', ') : '-');
    }).join(' | ');
  }

  if (question.type === 'TABLE_SCORED') {
    var validCombos = [];
    try {
      var parsed = JSON.parse(question.acceptableAnswers || '[]');
      validCombos = Array.isArray(parsed) ? parsed : (Array.isArray(parsed.validCombos) ? parsed.validCombos : []);
    } catch (err) {
      validCombos = [];
    }
    return validCombos.map(function (c) {
      return FIXED_TABLE_HEADERS.map(function (h) { return (c && c[h]) || ''; }).join(', ');
    }).join(' | ');
  }

  if (question.type === 'TABLE_PRICED') {
    var bugs = getBugsConfig(question);
    return bugs.map(function (bug, idx) {
      var condText = Object.keys(bug.conditions || {}).map(function (h) {
        return h + ' = ' + bug.conditions[h];
      }).join(' AND ');
      return 'Bug ' + (idx + 1) + ': ' + condText + ' (all other fields = Any) -> ' + describeBugEffect(bug.effect || {});
    }).join(' | ');
  }

  return '';
}

/**
 * Resets session state and deletes all student responses for a new class session
 */
function resetSessionForNewClass() {
  requireTeacher();
  var props = PropertiesService.getScriptProperties();
  props.setProperty('currentQIndex', '-1');
  props.setProperty('status', 'WAITING');
  props.setProperty('endTime', '0');
  props.setProperty('originalEndTime', '0');

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Responses");

  if (sheet) {
    var lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      sheet.deleteRows(2, lastRow - 1);
    }
    sheet.getRange(1, 1, 1, RESPONSES_HEADER.length).setValues([RESPONSES_HEADER]);
  } else {
    sheet = ss.insertSheet("Responses");
    sheet.appendRow(RESPONSES_HEADER);
  }

  return "Class session and student responses have been reset!";
}
