// GET /api/ui-config — public, no auth. Deliberately excludes every bug
// flag except allowBuyWithPartialConfig, which the client needs to render
// the Buy button's enabled state correctly (requirements §6.3, §6.8's
// implementation note). Mirrors getUiConfig() in the GAS version exactly.
const { wrapHandler, assertMethod, sendJson } = require('../lib/http');
const { getPool } = require('../lib/db');
const { getSettings } = require('../lib/settings');

module.exports = wrapHandler(async (req, res) => {
  assertMethod(req, 'GET');
  const settings = await getSettings(getPool());
  sendJson(res, 200, {
    level: settings.level,
    studentResetEnabled: settings.studentResetEnabled,
    requiredEmailDomain: settings.requiredEmailDomain,
    allowBuyWithPartialConfig: settings.bugs.allowBuyWithPartialConfig,
  });
});
