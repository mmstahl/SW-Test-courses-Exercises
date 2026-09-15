// GET /api/product-options — public, no auth, no DB. New endpoint not in
// the old API contract: static HTML has no server-side templating step to
// inject PRICE_TABLE/option lists the way GAS's HtmlService did, so the
// client bootstraps from this instead of hand-maintaining a duplicate
// (driftable) copy of the price table client-side.
const { wrapHandler, assertMethod, sendJson } = require('../lib/http');
const { PRICE_TABLE, getProductOptions } = require('../lib/priceTable');

module.exports = wrapHandler(async (req, res) => {
  assertMethod(req, 'GET');
  sendJson(res, 200, { priceTable: PRICE_TABLE, options: getProductOptions() });
});
