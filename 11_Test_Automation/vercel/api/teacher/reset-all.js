// POST /api/teacher/reset-all — wipes all students' purchases, discount
// codes, credit balances, and the action log. Mirrors teacherResetAll().
const { wrapHandler, assertMethod, sendJson } = require('../../lib/http');
const { withTransaction } = require('../../lib/db');
const { requireTeacher } = require('../../lib/auth');

module.exports = wrapHandler(async (req, res) => {
  assertMethod(req, 'POST');
  requireTeacher(req);
  await withTransaction(async (client) => {
    // A fixed-key global lock, cheap insurance against racing an
    // in-flight student Buy/Return (those take a per-student lock; this
    // takes a separate, unused-elsewhere key so it never deadlocks with
    // them, just serializes against other resets).
    await client.query('SELECT pg_advisory_xact_lock(0)');
    // Listing all four together lets Postgres resolve the
    // purchases -> discount_codes foreign key ordering automatically.
    await client.query('TRUNCATE TABLE purchases, discount_codes, store_credit, action_log');
  });
  sendJson(res, 200, { success: true });
});
