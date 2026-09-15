# Phone Configurator Simulator — Vercel + Postgres

Ported from `reference-appsscript-version/` (Google Apps Script). See
`MIGRATION_BRIEF.md` for why, and `Phone_Configurator_Simulator_requirements.md`
for the full current behavioral spec.

## First-time setup

**If the app is already deployed on Vercel** (i.e. someone has already done
this once), you almost certainly don't need most of these steps — see
[Adding a teacher / setting up on a new machine](#adding-a-teacher--setting-up-on-a-new-machine)
instead.

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
   npx vercel dev
   ```

   Run this directly (not via an `npm run dev` script) — `vercel dev` is
   itself the dev server, and Vercel's dashboard often auto-populates a
   project's **Development Command** setting to `npm run dev` on import;
   if `package.json` also had a `dev` script that ran `vercel dev`, the
   two would call each other forever ("recursive invocation of
   commands"). If you ever hit that error, check Project Settings →
   Build and Deployment → Development Command in the Vercel dashboard and
   make sure it isn't overridden to something that loops back here.

   Also make sure **Settings → Build and Deployment → Root Directory** is
   set to `11_Test_Automation/dev` — `vercel dev` resolves the project
   root from this setting (relative to the Git repo root), not from
   wherever your shell happens to be sitting, so a stale value here
   causes `vercel dev` to fail looking for a folder that doesn't exist.

   This serves the static pages from `public/` and the API functions from
   `api/`. Visit `http://localhost:3000` for the student page and
   `http://localhost:3000/teacher.html` for the teacher console.

## Deploying

1. `vercel link` the project, then set `DATABASE_URL` and `SESSION_SECRET`
   as environment variables in the Vercel project settings (production —
   and preview, if you want preview deployments to work — pointing at
   whichever database is the "real" one for that environment).
2. Run `npm run db:migrate` and `npm run db:seed-teacher -- <username> <password>`
   against that database (e.g. by setting `DATABASE_URL` locally to the
   production connection string for just those two commands).
3. `vercel --prod`.

## Adding a teacher / setting up on a new machine

Once the app is deployed and its database exists, most of "First-time
setup" above no longer applies — that's for standing the whole thing up
the first time. What you actually need depends on what you're doing:

**Just adding a new teacher/TA login (no code involved):**

Only step 5 applies, and *you* run it — they don't need to install
anything or touch the repo at all:

```bash
node db/seed-teacher.js <their-username> <a-password>
```

They then just log into `<your-deployment-url>/teacher.html` with those
credentials.

**Developing or running the code on a new PC** (you on a new machine, or a
collaborator touching the code):

| Step | Do it? |
|---|---|
| 1. `npm install` | Yes — always, it's per-machine. |
| 2. Create a database | **Skip.** There's already one shared database — reuse it, don't create a new one. |
| 3. `.env.local` | Yes, but use the *existing* `DATABASE_URL` (copy it over securely — a password manager, not Slack/email in plaintext). `SESSION_SECRET` can be freshly generated per machine; it only needs to be internally consistent with what's running locally, and doesn't need to match Vercel's. |
| 4. `npm run db:migrate` | **Skip** — schema's already applied. Harmless to re-run if unsure (every statement is idempotent), just not necessary. |
| 5. Seed a teacher | Only if *that person* needs their own login; otherwise skip. |
| 6. `npx vercel dev` | Yes, to actually run/test locally. |

## Project layout

- `db/` — schema (`schema.sql`), migration runner, teacher-account seeding.
- `lib/` — shared server logic (pricing, discount codes, purchases, store
  credit, action logging, auth), reused across the `api/` endpoints.
- `api/` — one file per REST endpoint (see the requirements doc's §8-style
  API contract, now per-action REST instead of the old `?action=X` style).
- `public/` — the student (`index.html`) and teacher (`teacher.html`) pages
  and their JS, using the same element `id`s as the reference app so
  existing Selenium-facing course material doesn't need updating.
