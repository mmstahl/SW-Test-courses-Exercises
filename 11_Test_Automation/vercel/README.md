# Phone Configurator Simulator — Vercel + Postgres

Ported from `reference-appsscript-version/` (Google Apps Script). See
`MIGRATION_BRIEF.md` for why, and `reference-appsscript-version/Phone_Configurator_Simulator_requirements.md`
for the full behavioral spec this port preserves.

## First-time setup

1. **Install dependencies**

   ```bash
   npm install
   ```

2. **Get a Postgres database.** Any standard Postgres connection string
   works (Neon, Vercel Postgres/Neon integration, Supabase, a local
   `docker run postgres`, ...). Use a **separate database for local dev** —
   never point it at whatever becomes the real class database.

3. **Configure environment variables.** Copy `.env.example` to `.env.local`
   and fill in:
   - `DATABASE_URL` — your dev database's connection string.
   - `SESSION_SECRET` — generate with:
     ```bash
     node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
     ```

4. **Apply the schema:**

   ```bash
   npm run db:migrate
   ```

5. **Create a teacher account** (also doubles as a password reset — safe to
   re-run):

   ```bash
   npm run db:seed-teacher -- <username> <password>
   ```

6. **Run locally:**

   ```bash
   npm run dev
   ```

   This starts `vercel dev`, serving the static pages from `public/` and
   the API functions from `api/`. Visit `http://localhost:3000` for the
   student page and `http://localhost:3000/teacher.html` for the teacher
   console.

## Deploying

1. `vercel link` the project, then set `DATABASE_URL` and `SESSION_SECRET`
   as environment variables in the Vercel project settings (production —
   and preview, if you want preview deployments to work — pointing at
   whichever database is the "real" one for that environment).
2. Run `npm run db:migrate` and `npm run db:seed-teacher -- <username> <password>`
   against that database (e.g. by setting `DATABASE_URL` locally to the
   production connection string for just those two commands).
3. `vercel --prod`.

## Project layout

- `db/` — schema (`schema.sql`), migration runner, teacher-account seeding.
- `lib/` — shared server logic (pricing, discount codes, purchases, store
  credit, action logging, auth), reused across the `api/` endpoints.
- `api/` — one file per REST endpoint (see the requirements doc's §8-style
  API contract, now per-action REST instead of the old `?action=X` style).
- `public/` — the student (`index.html`) and teacher (`teacher.html`) pages
  and their JS, using the same element `id`s as the reference app so
  existing Selenium-facing course material doesn't need updating.
