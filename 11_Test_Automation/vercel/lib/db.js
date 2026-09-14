// Postgres access layer. Uses plain `pg` (node-postgres) rather than
// @vercel/postgres (deprecated — Vercel has moved Postgres provisioning to
// Neon and points people at Neon's own SDKs instead). `pg` works with any
// standard Postgres connection string and gives us ordinary transactions
// and advisory locks with no special-casing.
const { Pool } = require('pg');

let pool;
function getPool() {
  if (!pool) {
    const connectionString = process.env.DATABASE_URL;
    if (!connectionString) {
      throw new Error('DATABASE_URL is not set.');
    }
    pool = new Pool({
      connectionString,
      ssl: connectionString.includes('sslmode=disable')
        ? false
        : { rejectUnauthorized: false },
    });
  }
  return pool;
}

// One-shot query against the pool — for reads that don't need a
// transaction (e.g. GET endpoints with no read-modify-write).
async function query(text, params) {
  return getPool().query(text, params);
}

// Runs `fn(client)` inside a single BEGIN/COMMIT transaction on one
// dedicated connection (required for advisory locks and multi-statement
// atomicity — a pooled one-shot query per statement would not hold the
// lock or the transaction across statements). Rolls back and rethrows on
// any error.
async function withTransaction(fn) {
  const client = await getPool().connect();
  try {
    await client.query('BEGIN');
    const result = await fn(client);
    await client.query('COMMIT');
    return result;
  } catch (err) {
    try {
      await client.query('ROLLBACK');
    } catch (_) {
      // ignore — original error is what matters
    }
    throw err;
  } finally {
    client.release();
  }
}

// Takes a transaction-scoped advisory lock keyed on the student's email —
// replaces GAS's single global LockService lock with a per-student
// equivalent (different students' actions no longer block each other).
// Auto-released on COMMIT/ROLLBACK; must be called after BEGIN, on the
// same client used for the rest of the transaction.
async function withStudentLock(client, email) {
  await client.query('SELECT pg_advisory_xact_lock(hashtext($1))', [email]);
}

module.exports = { getPool, query, withTransaction, withStudentLock };
