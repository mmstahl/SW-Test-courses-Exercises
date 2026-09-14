// Teacher auth: bcrypt password hashing + a hand-rolled HMAC-signed session
// cookie (no framework needed for a trivial {username, iat, exp} payload).
//
// Every teacher-only endpoint calls requireTeacher(req) as its first line —
// an independent, per-request re-check, exactly mirroring the GAS version's
// requireTeacher_() being called inside every settings-changing function
// regardless of how the page was reached. teacher.html's own client-side
// redirect-if-not-logged-in is UX only, never the real gate.
const crypto = require('crypto');
const bcrypt = require('bcryptjs');
const { AuthError } = require('./errors');

const SESSION_COOKIE_NAME = 'teacher_session';
const SESSION_MAX_AGE_SECONDS = 12 * 60 * 60; // 12 hours

function getSecret() {
  const secret = process.env.SESSION_SECRET;
  if (!secret) {
    throw new Error('SESSION_SECRET is not set.');
  }
  return secret;
}

function base64url(buf) {
  return buf.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64urlDecode(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/');
  while (str.length % 4) str += '=';
  return Buffer.from(str, 'base64');
}

function sign(payloadB64) {
  return crypto.createHmac('sha256', getSecret()).update(payloadB64).digest('hex');
}

function signSession(username) {
  const payload = {
    username,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + SESSION_MAX_AGE_SECONDS,
  };
  const payloadB64 = base64url(Buffer.from(JSON.stringify(payload)));
  const signature = sign(payloadB64);
  return `${payloadB64}.${signature}`;
}

function verifySession(token) {
  if (!token || typeof token !== 'string') return null;
  const dot = token.lastIndexOf('.');
  if (dot === -1) return null;
  const payloadB64 = token.slice(0, dot);
  const signature = token.slice(dot + 1);
  const expected = sign(payloadB64);

  const sigBuf = Buffer.from(signature, 'hex');
  const expectedBuf = Buffer.from(expected, 'hex');
  if (sigBuf.length !== expectedBuf.length || !crypto.timingSafeEqual(sigBuf, expectedBuf)) {
    return null;
  }

  let payload;
  try {
    payload = JSON.parse(base64urlDecode(payloadB64).toString('utf8'));
  } catch (e) {
    return null;
  }
  if (!payload || typeof payload.exp !== 'number' || payload.exp < Math.floor(Date.now() / 1000)) {
    return null;
  }
  return { username: payload.username };
}

function parseCookies(req) {
  const header = req.headers && req.headers.cookie;
  const out = {};
  if (!header) return out;
  header.split(';').forEach((part) => {
    const eq = part.indexOf('=');
    if (eq === -1) return;
    const key = part.slice(0, eq).trim();
    const value = part.slice(eq + 1).trim();
    if (key) out[key] = decodeURIComponent(value);
  });
  return out;
}

function buildSessionCookie(token) {
  const parts = [
    `${SESSION_COOKIE_NAME}=${encodeURIComponent(token)}`,
    'HttpOnly',
    'Secure',
    'SameSite=Lax',
    'Path=/',
    `Max-Age=${SESSION_MAX_AGE_SECONDS}`,
  ];
  return parts.join('; ');
}

function buildClearCookie() {
  return [`${SESSION_COOKIE_NAME}=`, 'HttpOnly', 'Secure', 'SameSite=Lax', 'Path=/', 'Max-Age=0'].join(
    '; '
  );
}

// Throws AuthError (-> 401) if the request has no valid teacher session.
// Returns the authenticated username otherwise.
function requireTeacher(req) {
  const cookies = parseCookies(req);
  const session = verifySession(cookies[SESSION_COOKIE_NAME]);
  if (!session) {
    throw new AuthError('You are not authorized to perform this action.');
  }
  return session.username;
}

async function verifyPassword(password, hash) {
  return bcrypt.compare(password, hash);
}

module.exports = {
  SESSION_COOKIE_NAME,
  signSession,
  verifySession,
  parseCookies,
  buildSessionCookie,
  buildClearCookie,
  requireTeacher,
  verifyPassword,
};
