const { wrapHandler, assertMethod, sendJson } = require('../../lib/http');
const { getPool } = require('../../lib/db');
const { verifyPassword, signSession, buildSessionCookie } = require('../../lib/auth');
const { AuthError, ValidationError } = require('../../lib/errors');

module.exports = wrapHandler(async (req, res) => {
  assertMethod(req, 'POST');
  const { username, password } = req.body || {};
  if (!username || !password) {
    throw new ValidationError('username and password are required.');
  }

  const result = await getPool().query(
    'SELECT password_hash FROM teachers WHERE username = $1',
    [username]
  );
  // Same generic message whether the username doesn't exist or the
  // password is wrong — don't reveal which.
  if (result.rows.length === 0 || !(await verifyPassword(password, result.rows[0].password_hash))) {
    throw new AuthError('Invalid username or password.');
  }

  const token = signSession(username);
  res.setHeader('Set-Cookie', buildSessionCookie(token));
  sendJson(res, 200, { success: true, username });
});
