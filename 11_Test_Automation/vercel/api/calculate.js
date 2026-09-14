// GET /api/calculate — read-only price/discount/credit preview. Never
// mutates Purchases/DiscountCodes/StoreCredit; still writes one ActionLog
// row (success or failure). Mirrors calculatePrice() in the GAS version.
const { wrapHandler, assertMethod, sendJson } = require('../lib/http');
const { getPool } = require('../lib/db');
const { getSettings } = require('../lib/settings');
const { validateEmail, readConfig, configToLogString } = require('../lib/validation');
const { computeBasePrice, round2 } = require('../lib/pricing');
const { evaluateDiscount } = require('../lib/discount');
const { getStoreCredit } = require('../lib/credit');
const { DISCOUNT_RATE } = require('../lib/priceTable');
const { newLogEntry, logAction } = require('../lib/actionLog');

module.exports = wrapHandler(async (req, res) => {
  assertMethod(req, 'GET');
  const params = req.query || {};
  const pool = getPool();
  const logEntry = newLogEntry('CalculatePrice');
  try {
    const settings = await getSettings(pool);
    const email = validateEmail(params.email, settings);
    logEntry.email = email;
    const config = readConfig(params);
    logEntry.parameters = configToLogString(config);
    logEntry.discountCode = (params.discountCode || '').toString().trim();

    const basePrice = computeBasePrice(config);
    const discount = await evaluateDiscount(pool, email, params.discountCode, settings);
    const paidPrice = round2(discount.valid ? basePrice * (1 - DISCOUNT_RATE) : basePrice);

    const result = { email, config, basePrice, discountCode: discount, paidPrice };
    logEntry.calculatedPrice = paidPrice;

    if (settings.level >= 4) {
      const creditBalance = await getStoreCredit(pool, email);
      const creditApplied = round2(Math.min(creditBalance, paidPrice));
      const requestedPayment = round2(Math.max(0, paidPrice - creditApplied));
      result.creditBalance = creditBalance;
      result.creditApplied = creditApplied;
      result.requestedPayment = requestedPayment;
      logEntry.creditBefore = creditBalance;
      logEntry.creditAfter = creditBalance;
      logEntry.calculatedPrice = requestedPayment;
    }
    logEntry.result = 'Success';
    sendJson(res, 200, result);
  } catch (err) {
    logEntry.message = err && err.message ? err.message : String(err);
    throw err;
  } finally {
    await logAction(logEntry);
  }
});
