// POST /api/return — returns a previously-bought phone matching the
// current field selections (level 4 only). Mirrors returnPhone() in the
// GAS version. A "no match" outcome is a normal 200 response
// ({success:false, ...}), not an HTTP error — it's a legitimate business
// result, exactly like the old app treated it.
const { wrapHandler, assertMethod, sendJson } = require('../lib/http');
const { withTransaction, withStudentLock } = require('../lib/db');
const { getSettings } = require('../lib/settings');
const { validateEmail, readConfig, configToLogString } = require('../lib/validation');
const { round2 } = require('../lib/pricing');
const { disableDiscountCode } = require('../lib/discount');
const { getStoreCredit, setStoreCredit } = require('../lib/credit');
const {
  getPurchasesForEmail,
  findMatchInPurchases,
  markPurchaseReturned,
  computeReturnEnabledFromPurchases,
} = require('../lib/purchases');
const { newLogEntry, logAction } = require('../lib/actionLog');
const { ValidationError } = require('../lib/errors');

module.exports = wrapHandler(async (req, res) => {
  assertMethod(req, 'POST');
  const params = req.body || {};
  const rawEmail = (params.email || '').toString().trim();
  const logEntry = newLogEntry('Return');
  try {
    const result = await withTransaction(async (client) => {
      await withStudentLock(client, rawEmail);

      const settings = await getSettings(client);
      if (settings.level < 4) {
        throw new ValidationError('Return is not available at the current level.');
      }
      const email = validateEmail(params.email, settings);
      logEntry.email = email;
      const config = readConfig(params);
      logEntry.parameters = configToLogString(config);
      const refundType = (params.refundType || '').toString().trim();
      if (refundType !== 'Refund' && refundType !== 'StoreCredit') {
        throw new ValidationError('refundType must be "Refund" or "StoreCredit".');
      }

      const creditBefore = await getStoreCredit(client, email);
      logEntry.creditBefore = creditBefore;

      // One read of this student's purchase history, reused for both the
      // match lookup and (after the in-memory status update below) the
      // post-return Return-button eligibility check — no second read.
      const purchases = await getPurchasesForEmail(client, email);
      const match = findMatchInPurchases(purchases, config);
      if (!match) {
        logEntry.creditAfter = creditBefore;
        logEntry.message = 'No matching purchase found';
        logEntry.result = 'Failed';
        return {
          success: false,
          message: 'Return action failed. The stated configuration does not match a phone you bought.',
          returnEnabled: computeReturnEnabledFromPurchases(purchases, settings),
        };
      }

      await markPurchaseReturned(client, match.purchaseId);
      match.status = 'Returned'; // keep the in-memory copy consistent for the eligibility check below
      if (match.codeGenerated) {
        await disableDiscountCode(client, email, match.codeGenerated);
      }

      const response = {
        success: true,
        message: 'The phone can be returned',
        refundType,
      };

      if (refundType === 'Refund') {
        response.refundMessage = 'Refund will be completed within 5 business days';
        logEntry.creditAfter = creditBefore;
      } else {
        const creditBasisIsBase = settings.bugs.creditBasis === 'base';
        const creditAmount = creditBasisIsBase ? match.basePrice : match.paidPrice;
        const newBalance = round2(creditBefore + creditAmount);
        await setStoreCredit(client, email, newBalance);
        response.creditAdded = creditAmount;
        response.creditBalance = newBalance;
        response.refundMessage = 'Your store credit is now $' + newBalance.toFixed(2);
        logEntry.creditAfter = newBalance;
        logEntry.calculatedPrice = creditAmount;
      }

      response.returnEnabled = computeReturnEnabledFromPurchases(purchases, settings);
      logEntry.result = 'Success';
      return response;
    });
    sendJson(res, 200, result);
  } catch (err) {
    logEntry.message = err && err.message ? err.message : String(err);
    throw err;
  } finally {
    await logAction(logEntry);
  }
});
