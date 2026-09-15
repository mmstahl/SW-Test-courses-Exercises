const { getPool } = require('./db');

function newLogEntry(action) {
  return {
    action,
    email: '',
    parameters: '',
    discountCode: '',
    calculatedPrice: '',
    creditBefore: '',
    creditAfter: '',
    result: 'Error',
    message: '',
  };
}

function blankToNull(v) {
  return v === '' || v === undefined ? null : v;
}

// Appends one row to action_log, using the pool directly (its own
// connection) rather than any transaction the caller may have just
// finished — deliberately so a ROLLBACK on the main action never erases
// the log row that records the failure. Never throws: logging is
// best-effort and must never break the action it's recording (mirrors
// logAction_'s try/catch-and-swallow in the GAS version).
async function logAction(entry) {
  try {
    await getPool().query(
      `INSERT INTO action_log (
         student_email, action, parameters, discount_code,
         calculated_price, credit_before, credit_after, result, message
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)`,
      [
        entry.email,
        entry.action,
        entry.parameters,
        entry.discountCode,
        blankToNull(entry.calculatedPrice),
        blankToNull(entry.creditBefore),
        blankToNull(entry.creditAfter),
        entry.result,
        entry.message,
      ]
    );
  } catch (e) {
    // Swallow — logging must never break the caller.
  }
}

module.exports = { newLogEntry, logAction };
