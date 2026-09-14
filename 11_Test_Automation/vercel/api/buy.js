// POST /api/buy — records a purchase, generates a discount code (level
// 2+), applies/updates store credit (level 4). Mirrors buyPhone() in the
// GAS version, with GAS's single global LockService lock replaced by a
// per-student Postgres advisory lock held for the whole transaction (see
// lib/db.js withStudentLock).
const { wrapHandler, assertMethod, sendJson } = require('../lib/http');
const { withTransaction, withStudentLock } = require('../lib/db');
const { getSettings } = require('../lib/settings');
const { validateEmail, readConfig, configToLogString } = require('../lib/validation');
const { computeBasePrice, round2 } = require('../lib/pricing');
const { evaluateDiscount, generateDiscountCode, insertDiscountCode, markCodeRedeemed } = require('../lib/discount');
const { getStoreCredit, setStoreCredit } = require('../lib/credit');
const { getPurchasesForEmail, insertPurchase } = require('../lib/purchases');
const { PARAMETERS, DISCOUNT_RATE } = require('../lib/priceTable');
const { newLogEntry, logAction } = require('../lib/actionLog');
const { ValidationError } = require('../lib/errors');

module.exports = wrapHandler(async (req, res) => {
  assertMethod(req, 'POST');
  const params = req.body || {};
  const rawEmail = (params.email || '').toString().trim();
  const logEntry = newLogEntry('Buy');
  try {
    const result = await withTransaction(async (client) => {
      // Locked first (like GAS's global lock acquired before anything
      // else), keyed on the raw self-reported email — even one that turns
      // out invalid, so the transaction still opens/rolls back cleanly.
      await withStudentLock(client, rawEmail);

      const settings = await getSettings(client);
      const email = validateEmail(params.email, settings);
      logEntry.email = email;
      const config = readConfig(params);
      logEntry.parameters = configToLogString(config);
      logEntry.discountCode = (params.discountCode || '').toString().trim();

      const allSelected = PARAMETERS.every((p) => !!config[p]);
      if (!allSelected && !settings.bugs.allowBuyWithPartialConfig) {
        throw new ValidationError('All 5 parameters must be selected before buying.');
      }

      const basePrice = computeBasePrice(config);
      const discount = await evaluateDiscount(client, email, params.discountCode, settings);
      const paidPrice = round2(discount.valid ? basePrice * (1 - DISCOUNT_RATE) : basePrice);

      // Only read StoreCredit when it's actually used (matches the GAS
      // version's own fix for this — see requirements doc's §6.5 note).
      const creditBalanceBefore = settings.level >= 4 ? await getStoreCredit(client, email) : 0;
      logEntry.creditBefore = creditBalanceBefore;
      let creditApplied = 0;
      let requestedPayment = paidPrice;
      if (settings.level >= 4) {
        creditApplied = round2(Math.min(creditBalanceBefore, paidPrice));
        requestedPayment = round2(Math.max(0, paidPrice - creditApplied));
      }

      // One read of this student's purchase history, reused for the
      // sequence number (locked, so race-safe).
      const purchases = await getPurchasesForEmail(client, email);
      const seq = purchases.length + 1;

      // No new code for a purchase that itself used a valid discount code.
      let generatedCode = '';
      if (settings.level >= 2 && !discount.valid) {
        generatedCode = generateDiscountCode(email, seq);
      }

      const purchaseId = await insertPurchase(client, {
        email,
        seq,
        config,
        basePrice,
        discountCodeUsed: discount.valid ? discount.entered : '',
        paidPrice,
        creditApplied,
        requestedPayment,
        codeGenerated: generatedCode,
      });

      if (generatedCode) {
        await insertDiscountCode(client, generatedCode, email, purchaseId);
      }
      if (discount.valid) {
        await markCodeRedeemed(client, email, discount.entered);
      }

      let creditBalanceAfter = creditBalanceBefore;
      if (settings.level >= 4 && creditApplied > 0) {
        creditBalanceAfter = round2(creditBalanceBefore - creditApplied);
        await setStoreCredit(client, email, creditBalanceAfter);
      }
      logEntry.creditAfter = creditBalanceAfter;
      logEntry.calculatedPrice = settings.level >= 4 ? requestedPayment : paidPrice;
      logEntry.result = 'Success';

      return {
        email,
        config,
        basePrice,
        discountCode: discount,
        paidPrice,
        creditApplied,
        requestedPayment,
        creditBalance: settings.level >= 4 ? creditBalanceAfter : undefined,
        generatedCode: generatedCode || null,
        // We just recorded an active purchase, so Return is trivially
        // eligible at level 4 — no extra read needed to confirm it.
        returnEnabled: settings.level >= 4,
      };
    });
    sendJson(res, 200, result);
  } catch (err) {
    logEntry.message = err && err.message ? err.message : String(err);
    throw err;
  } finally {
    await logAction(logEntry);
  }
});
