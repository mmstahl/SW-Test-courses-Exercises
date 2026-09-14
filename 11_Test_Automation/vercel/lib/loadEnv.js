// Tiny .env loader for standalone scripts (db/migrate.js, db/seed-teacher.js)
// run outside `vercel dev`, which loads .env.local automatically for API
// functions but not for plain `node` invocations. No dependency needed for
// a format this simple.
const fs = require('fs');
const path = require('path');

function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return;
  const contents = fs.readFileSync(filePath, 'utf8');
  for (const rawLine of contents.split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}

function loadEnv() {
  const root = path.join(__dirname, '..');
  // .env.local takes precedence (checked first, since existing keys are
  // never overwritten), falling back to .env.
  loadEnvFile(path.join(root, '.env.local'));
  loadEnvFile(path.join(root, '.env'));
}

module.exports = { loadEnv };
