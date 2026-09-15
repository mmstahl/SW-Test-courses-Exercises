#!/usr/bin/env node
// Applies db/schema.sql to DATABASE_URL. Idempotent — every statement in
// schema.sql uses IF NOT EXISTS / ON CONFLICT, so running this repeatedly
// is safe.
const fs = require('fs');
const path = require('path');
const { loadEnv } = require('../lib/loadEnv');

loadEnv();

const { Client } = require('pg');

async function main() {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    console.error('DATABASE_URL is not set (checked .env.local, .env, and the environment).');
    process.exit(1);
  }

  const schemaPath = path.join(__dirname, 'schema.sql');
  const schema = fs.readFileSync(schemaPath, 'utf8');

  const client = new Client({
    connectionString,
    ssl: connectionString.includes('sslmode=disable') ? false : { rejectUnauthorized: false },
  });
  await client.connect();
  try {
    // schema.sql has no semicolons inside string literals or function
    // bodies, so a naive split is safe here.
    const statements = schema
      .split(';')
      .map((s) => s.trim())
      .filter(Boolean);
    for (const statement of statements) {
      await client.query(statement);
    }
    console.log(`Applied ${statements.length} statement(s) from schema.sql.`);
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error('Migration failed:', err);
  process.exit(1);
});
