#!/usr/bin/env node
// Creates or updates a teacher account. Idempotent (ON CONFLICT DO UPDATE),
// so it doubles as a password-reset tool. No public self-registration
// endpoint exists — this is the only way to create/change a teacher login.
//
// Usage: node db/seed-teacher.js <username> <password>
const { loadEnv } = require('../lib/loadEnv');

loadEnv();

const bcrypt = require('bcryptjs');
const { Client } = require('pg');

async function main() {
  const [username, password] = process.argv.slice(2);
  if (!username || !password) {
    console.error('Usage: node db/seed-teacher.js <username> <password>');
    process.exit(1);
  }
  if (password.length < 8) {
    console.error('Password must be at least 8 characters.');
    process.exit(1);
  }

  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    console.error('DATABASE_URL is not set (checked .env.local, .env, and the environment).');
    process.exit(1);
  }

  const passwordHash = await bcrypt.hash(password, 12);

  const client = new Client({
    connectionString,
    ssl: connectionString.includes('sslmode=disable') ? false : { rejectUnauthorized: false },
  });
  await client.connect();
  try {
    await client.query(
      `INSERT INTO teachers (username, password_hash)
       VALUES ($1, $2)
       ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash`,
      [username, passwordHash]
    );
    console.log(`Teacher account "${username}" created/updated.`);
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error('Seeding teacher account failed:', err);
  process.exit(1);
});
