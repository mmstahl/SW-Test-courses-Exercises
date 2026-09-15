// GET/PUT /api/teacher/settings — every call independently re-verifies the
// session cookie (requireTeacher), never trusting that teacher.html was
// reachable. Mirrors teacherGetSettings()/teacherUpdateSettings().
const { wrapHandler, sendJson } = require('../../lib/http');
const { getPool } = require('../../lib/db');
const { requireTeacher } = require('../../lib/auth');
const { getSettings, saveSettings, mergeSettings, validateSettings } = require('../../lib/settings');

module.exports = wrapHandler(async (req, res) => {
  requireTeacher(req);
  const pool = getPool();

  if (req.method === 'GET') {
    const settings = await getSettings(pool);
    sendJson(res, 200, settings);
    return;
  }

  if (req.method === 'PUT') {
    const current = await getSettings(pool);
    const merged = mergeSettings(current, req.body || {});
    validateSettings(merged);
    await saveSettings(pool, merged);
    sendJson(res, 200, merged);
    return;
  }

  const err = new Error('This endpoint requires an HTTP GET or PUT request.');
  err.statusCode = 405;
  throw err;
});
