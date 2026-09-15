const { wrapHandler, assertMethod, sendJson } = require('../../lib/http');
const { buildClearCookie } = require('../../lib/auth');

module.exports = wrapHandler(async (req, res) => {
  assertMethod(req, 'POST');
  res.setHeader('Set-Cookie', buildClearCookie());
  sendJson(res, 200, { success: true });
});
