// POST /api/reset — clears only the calling student's own data. Requires
// studentResetEnabled. Mirrors resetStudentData() in the GAS version.
const { wrapHandler, assertMethod, sendJson } = require('../lib/http');
const { withTransaction, withStudentLock } = require('../lib/db');
const { getSettings } = require('../lib/settings');
const { validateEmail } = require('../lib/validation');
const { getStoreCredit } = require('../lib/credit');
const { newLogEntry, logAction } = require('../lib/actionLog');
const { ValidationError } = require('../lib/errors');

module.exports = wrapHandler(async (req, res) => {
  assertMethod(req, 'POST');
  const params = req.body || {};
  const rawEmail = (params.email || '').toString().trim();
  const logEntry = newLogEntry('Reset');
  try {
    const result = await withTransaction(async (client) => {
      const settings = await getSettings(client);
      if (!settings.studentResetEnabled) {
        throw new ValidationError('Student reset is currently disabled by the teacher.');
      }
      await withStudentLock(client, rawEmail);
      const email = validateEmail(params.email, settings);
      logEntry.email = email;
      logEntry.creditBefore = await getStoreCredit(client, email);
      logEntry.creditAfter = 0;
      // discount_codes references purchases via a foreign key, so it must
      // be deleted first.
      await client.query('DELETE FROM discount_codes WHERE student_email = $1', [email]);
      await client.query('DELETE FROM purchases WHERE student_email = $1', [email]);
      await client.query('DELETE FROM store_credit WHERE student_email = $1', [email]);
      logEntry.result = 'Success';
      return { success: true, email };
    });
    sendJson(res, 200, result);
  } catch (err) {
    logEntry.message = err && err.message ? err.message : String(err);
    throw err;
  } finally {
    await logAction(logEntry);
  }
});
