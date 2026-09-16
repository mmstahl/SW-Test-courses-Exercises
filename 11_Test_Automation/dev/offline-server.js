#!/usr/bin/env node
// offline-server.js -- a minimal local server for FULLY OFFLINE
// development, used instead of `vercel dev`.
//
// WHY THIS EXISTS: `vercel dev` was tested directly (not assumed) and
// confirmed to hard-require a network round-trip to Vercel's API on
// every startup -- "Retrieving..." project/env info -- even with a
// freshly-logged-in session and a prior successful online run to warm
// any local cache. It fails outright ("fetch failed") with no network.
// That's Vercel CLI's own behavior, not something fixable from this
// project's code.
//
// This script serves the same two things `vercel dev` would (static
// files from public/, and api/*.js as request handlers) using nothing
// but plain Node http -- no package, no CLI, no network call of any
// kind beyond whatever DATABASE_URL in .env.local points at (which,
// per README.md's "Fully offline local development", should be your
// local Postgres instance for this to actually be offline-capable).
//
// SCOPE: this is not a clone of Vercel's runtime -- it doesn't replicate
// header/streaming/size-limit edge cases Vercel's actual Node runtime
// enforces. It's a faithful substitute for what THIS app's api/*.js
// files actually use (req.query, req.body, res.status().json(),
// res.setHeader()), which is all of them. If the app ever grows to
// depend on more of Vercel's runtime surface, this would need updating
// too -- or just use `vercel dev` again once you're back online.
//
// USAGE
//     node offline-server.js [--port 3000]
const http = require('http');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

require('./lib/loadEnv').loadEnv();

const PROJECT_ROOT = __dirname;
const PUBLIC_DIR = path.join(PROJECT_ROOT, 'public');
const API_DIR = path.join(PROJECT_ROOT, 'api');

const portArgIndex = process.argv.indexOf('--port');
const PORT = portArgIndex !== -1 ? Number(process.argv[portArgIndex + 1]) : 3000;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

function augmentResponse(res) {
  res.status = function (code) {
    this.statusCode = code;
    return this;
  };
  res.json = function (obj) {
    const body = JSON.stringify(obj);
    this.setHeader('Content-Type', 'application/json; charset=utf-8');
    this.end(body);
  };
  return res;
}

async function serveStatic(reqPath, res) {
  let filePath = reqPath === '/' ? '/index.html' : reqPath;
  filePath = path.join(PUBLIC_DIR, decodeURIComponent(filePath));
  if (!filePath.startsWith(PUBLIC_DIR)) {
    res.statusCode = 403;
    res.end('Forbidden');
    return;
  }
  try {
    const data = await fs.promises.readFile(filePath);
    const ext = path.extname(filePath);
    res.setHeader('Content-Type', MIME[ext] || 'application/octet-stream');
    res.statusCode = 200;
    res.end(data);
  } catch (e) {
    res.statusCode = 404;
    res.end('Not found');
  }
}

const handlerCache = new Map();
function loadHandler(apiPath) {
  const filePath = path.join(API_DIR, apiPath + '.js');
  if (!filePath.startsWith(API_DIR)) return null;
  if (!fs.existsSync(filePath)) return null;
  if (!handlerCache.has(filePath)) {
    handlerCache.set(filePath, require(filePath));
  }
  return handlerCache.get(filePath);
}

const server = http.createServer(async (req, res) => {
  augmentResponse(res);
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (url.pathname.startsWith('/api/')) {
    const apiPath = url.pathname.slice('/api/'.length);
    const handler = loadHandler(apiPath);
    if (!handler) {
      res.status(404).json({ error: 'Not found' });
      return;
    }
    req.query = Object.fromEntries(url.searchParams.entries());
    const rawBody = await readBody(req);
    req.body = {};
    if (rawBody) {
      try {
        req.body = JSON.parse(rawBody);
      } catch (e) {
        // leave req.body as {}
      }
    }
    try {
      await handler(req, res);
    } catch (err) {
      console.error('Unhandled error in', apiPath, err);
      if (!res.headersSent) res.status(500).json({ error: 'Internal server error.' });
    }
    return;
  }

  await serveStatic(url.pathname, res);
});

server.listen(PORT, () => {
  console.log(`Offline dev server listening on http://localhost:${PORT}`);
  console.log(`Student page:  http://localhost:${PORT}/`);
  console.log(`Teacher page:  http://localhost:${PORT}/teacher.html`);
});
