// GET /api/student-status — Return-button eligibility + current credit for
// an email, no other action. Not logged (matches getStudentStatus() in the
// GAS version, which never writes to ActionLog).
const { wrapHandler, assertMethod, sendJson } = require('../lib/http');
const { getPool } = require('../lib/db');
const { getSettings } = require('../lib/settings');
const { validateEmail } = require('../lib/validation');
const { getPurchasesForEmail, computeReturnEnabledFromPurchases } = require('../lib/purchases');
const { getStoreCredit } = require('../lib/credit');

module.exports = wrapHandler(async (req, res) => {
  assertMethod(req, 'GET');
  const pool = getPool();
  const settings = await getSettings(pool);
  const email = validateEmail((req.query || {}).email, settings);
  const purchases = await getPurchasesForEmail(pool, email);
  const returnEnabled = computeReturnEnabledFromPurchases(purchases, settings);
  const creditBalance = settings.level >= 4 ? await getStoreCredit(pool, email) : 0;
  sendJson(res, 200, { email, returnEnabled, creditBalance });
});
