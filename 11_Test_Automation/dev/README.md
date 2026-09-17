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

2. **Log into Vercel and link this folder to the project** (one-time per
   machine — needed for both running locally and deploying):

   ```bash
   npx vercel login
   npx vercel link
   ```

   `link` will ask which project this folder belongs to; pick the existing
   one if it's already been created (e.g. via the Vercel dashboard's
   Import Git Repository flow), rather than creating a new one.

   Two Vercel project settings matter for `vercel dev` to work correctly
   afterward (**Settings → Build and Deployment** in the dashboard):
   - **Root Directory** must be `11_Test_Automation/dev` — `vercel dev`
     resolves the project root from this setting (relative to the Git
     repo root), not from wherever your shell happens to be sitting, so a
     stale value here makes it fail looking for a folder that doesn't
     exist.
   - **Development Command** should not be overridden to something like
     `npm run dev` — if `package.json` also had a `dev` script that ran
     `vercel dev`, the two would call each other forever ("recursive
     invocation of commands"). This project's `package.json` deliberately
     has no `dev` script for that reason; always run `vercel dev` directly
     (see step 7).

3. **Get a Postgres database.** Any standard Postgres connection string
   works (Neon, Vercel Postgres/Neon integration, Supabase, a local
   `docker run postgres`, ...). Use a **separate database for local dev** —
   never point it at whatever becomes the real class database. (This
   project's own setup instead deliberately shares one database across
   local/Preview/Production — see [Adding a teacher / setting up on a new
   machine](#adding-a-teacher--setting-up-on-a-new-machine) if that's the
   situation you're in. If you want local dev to work with **no internet
   at all**, see [Fully offline local development](#fully-offline-local-development)
   instead — it needs a real local Postgres, not a cloud one.)

4. **Configure environment variables.** Copy `.env.example` to `.env.local`
   and fill in:
   - `DATABASE_URL` — your dev database's connection string.
   - `SESSION_SECRET` — generate with:
     ```bash
     node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
     ```

5. **Apply the schema:**

   ```bash
   npm run db:migrate
   ```

6. **Create a teacher account** (also doubles as a password reset — safe to
   re-run):

   ```bash
   npm run db:seed-teacher -- <username> <password>
   ```

7. **Run locally:**

   ```bash
   npx vercel dev
   ```

   This serves the static pages from `public/` and the API functions from
   `api/`. Visit `http://localhost:3000` for the student page and
   `http://localhost:3000/teacher.html` for the teacher console.

## Deploying

### First deploy (one-time)

Step 2 above (`vercel login` + `vercel link`) already covers login/linking
— no need to repeat it here.

1. In the Vercel dashboard, set `DATABASE_URL` and `SESSION_SECRET` as
   **project environment variables** (Settings → Environment Variables) —
   this is separate from your local `.env.local`; it's what the deployed
   functions actually read. Set them for Production — and Preview, if you
   want preview deployments to work — pointing at whichever database is
   the "real" one for that environment.
2. **Only if that's a different database than the one you already set up
   locally**, apply the schema and create a teacher account against it too
   (e.g. by temporarily setting `DATABASE_URL` in your shell to the
   production connection string for just these two commands):
   ```bash
   npm run db:migrate
   npm run db:seed-teacher -- <username> <password>
   ```
   If you're sharing one database across environments (this project's own
   setup), skip this — it's already done.
3. Connect the project to this GitHub repo, if it isn't already (Vercel
   dashboard → Add New → Project → Import Git Repository), with **Root
   Directory** set to `11_Test_Automation/dev`. This is what turns on
   push-to-deploy — see below — so ordinarily this is the *only* time
   you'd manually trigger a deploy at all.

### Ongoing deploys — just `git push`

Once the project is connected to GitHub (step 3 above), **every push to
`main` automatically triggers a new Production deployment** — no command
needed beyond your normal git workflow:

```bash
git add <files>
git commit -m "..."
git push
```

Production updates itself within a minute or two. Watch it happen (and
see build logs if something fails) in the Vercel dashboard's
**Deployments** tab — each entry shows which commit it came from.

`npx vercel --prod` is a separate, *manual* path: it deploys whatever's
in your local working directory right now, committed or not. It's not
part of the normal workflow — reach for it only if you want to push up
uncommitted local changes for a quick check without going through git,
or if the project somehow isn't connected to GitHub for automatic
deploys at all.

## Adding a teacher / setting up on a new machine

Once the app is deployed and its database exists, most of "First-time
setup" above no longer applies — that's for standing the whole thing up
the first time. What you actually need depends on what you're doing:

**Just adding a new teacher/TA login (no code involved):**

Only step 6 applies, and *you* run it — they don't need to install
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
| 2. `vercel login` + `vercel link` | Yes — always, it's per-machine (though you're logging into the *same* Vercel account/project each time, not creating a new one). |
| 3. Create a database | **Skip.** There's already one shared database — reuse it, don't create a new one. |
| 4. `.env.local` | Yes, but use the *existing* `DATABASE_URL` (copy it over securely — a password manager, not Slack/email in plaintext). `SESSION_SECRET` can be freshly generated per machine; it only needs to be internally consistent with what's running locally, and doesn't need to match Vercel's. |
| 5. `npm run db:migrate` | **Skip** — schema's already applied. Harmless to re-run if unsure (every statement is idempotent), just not necessary. |
| 6. Seed a teacher | Only if *that person* needs their own login; otherwise skip. |
| 7. `npx vercel dev` | Yes, to actually run/test locally. |

## Fully offline local development

Two separate things stand between you and working with no internet at
all, and only one of them is actually fixable from this project's side:

1. **`DATABASE_URL` pointing at a cloud Postgres database (Neon)** —
   literally every API call (Calculate, Buy, ...) needs it. Fixable: point
   it at a real local Postgres instead (below).
2. **`vercel dev` itself.** This was tested directly, not assumed: even
   with a freshly-logged-in session and a prior successful *online* run
   of `vercel dev` (to give it every chance to cache something locally),
   it still fails outright the moment the network is gone — it does a
   mandatory "Retrieving..." step (pulling project/session info from
   Vercel's API) before it'll serve anything at all, no flag or cached
   state avoids it. That's Vercel CLI's own hard requirement, not a bug
   in this project, and not something fixable here. **So for offline
   work, don't use `vercel dev`** — use `offline-server.js` instead (see
   "Running it" below), a small plain-Node server with zero network
   dependency of its own, serving the exact same `public/` and `api/`
   files.

The database fix is a **second, genuinely local Postgres** that only your
machine can see, with `DATABASE_URL` pointed at it instead. This is a
real, separate database from the cloud one — purchases, settings,
everything you do locally after this point stay local and never appear in
Production, and vice versa. That's an intentional trade-off, not a bug:
there's no way to have both "shares live state with Production" and
"works with the network off" at the same time.

**One-time setup:**

1. Download the **portable Postgres binaries** (not the installer) for
   whatever major version your production database runs — check with:
   ```bash
   node -e "require('./lib/loadEnv').loadEnv(); const {Pool}=require('pg'); new Pool({connectionString:process.env.DATABASE_URL}).query('SELECT version()').then(r=>{console.log(r.rows[0].version); process.exit()})"
   ```
   from **https://www.enterprisedb.com/download-postgresql-binaries** (Windows x86-64). This is a plain ZIP — no installer, no admin rights needed, nothing registered as a Windows service. Extract it somewhere simple with no spaces in the path, and **outside any OneDrive-synced folder** (a database actively writing files while OneDrive tries to sync them is a bad combination — the same class of problem we hit renaming the `vercel` folder earlier).

2. Initialize a data directory and create the database (adjust paths to
   wherever you extracted the binaries):
   ```bash
   "<PGBIN>\initdb.exe" -D "<PGDATA_LOCAL>" -U postgres --pwfile=<a file containing a password, one line> -A scram-sha-256 -E UTF8
   "<PGBIN>\pg_ctl.exe" -D "<PGDATA_LOCAL>" -l "<PGDATA_LOCAL>\..\pglog.txt" -o "-p 5432" start
   "<PGBIN>\createdb.exe" -h localhost -p 5432 -U postgres phone_sim
   ```

3. In `.env.local`, point `DATABASE_URL` at it instead of the cloud
   connection string, and add the variables `db/local-db.ps1` (see below)
   needs to find your install:
   ```
   DATABASE_URL=postgresql://postgres:<your password>@localhost:5432/phone_sim?sslmode=disable
   PGBIN=<PGBIN>
   PGDATA_LOCAL=<PGDATA_LOCAL>
   PGPORT_LOCAL=5432
   ```
   Keep your old cloud connection string too, under a different variable
   name, `CLOUD_DATABASE_URL` — `triplet_coverage_monitor.py` (the only
   one of these scripts that talks to Postgres directly rather than over
   HTTP) reads it automatically for `--target remote` now that plain
   `DATABASE_URL` means "local" instead. Without it, that script would
   have no way to tell "remote" and "local" apart.

4. Apply the schema and seed a teacher account against it, same commands
   as always — they'll pick up the new local `DATABASE_URL` automatically:
   ```bash
   npm run db:migrate
   npm run db:seed-teacher -- <username> <password>
   ```

**Running it, each time you want to work offline:**

```bash
.\db\local-db.ps1 start
node offline-server.js
```

(`db\local-db.ps1 status` / `stop` also work — it's a plain background
process, not a service, so it won't auto-start on its own and stops if
you stop it or reboot.) `offline-server.js` serves on
`http://localhost:3000` by default (`--port` to change it) — same URLs as
`vercel dev` would: `/` for the student page, `/teacher.html` for the
teacher console.

`test_level1_buy.py`, `test_level1_buy_ui.py`, `load_test.py`, and
`verify_deployment.py` all accept `--target local` (this server) or
`--target remote` (production, the default) — or `--base-url <anything>`
for an explicit override, e.g. a different port:
```bash
python test_level1_buy.py --target local
python test_level1_buy_ui.py --target local
python load_test.py --target local --users 10
python verify_deployment.py --target local
```

`triplet_coverage_monitor.py` accepts the same `--target local`/`remote`
(it talks to Postgres directly rather than over HTTP, so "remote" there
means reading `CLOUD_DATABASE_URL` — see step 3 above):
```bash
python triplet_coverage_monitor.py --target local
```

**What this actually guarantees, confirmed by testing rather than
assumed:** the database dependency is fully eliminated (a test Buy landed
in the local database, verified directly — not the cloud one, which still
had zero new rows), and `offline-server.js` has no network dependency of
its own — it's plain Node `http`, nothing more. Together that's a real,
verified, fully-offline path to running and testing this app. `vercel
dev` is deliberately **not** part of that path, because it can't be —
see above. Vercel CLI telemetry was also disabled
(`npx vercel telemetry disable`, a global setting for your whole machine,
not just this project; `npx vercel telemetry enable` to opt back in) —
harmless either way now that `vercel dev` isn't in the offline path at
all, but no reason to leave it on.

## Project layout

- `db/` — schema (`schema.sql`), migration runner, teacher-account seeding.
- `lib/` — shared server logic (pricing, discount codes, purchases, store
  credit, action logging, auth), reused across the `api/` endpoints.
- `api/` — one file per REST endpoint (see the requirements doc's §8-style
  API contract, now per-action REST instead of the old `?action=X` style).
- `public/` — the student (`index.html`) and teacher (`teacher.html`) pages
  and their JS, using the same element `id`s as the reference app so
  existing Selenium-facing course material doesn't need updating.
- `offline-server.js` — a plain-Node substitute for `vercel dev`, used
  only for fully offline local development (`vercel dev` itself can't run
  without network — see [Fully offline local development](#fully-offline-local-development)).
- `test_level1_buy.py`, `test_level1_buy_ui.py`, `load_test.py`,
  `verify_deployment.py`, `triplet_coverage_monitor.py` — the Python
  scripts covered elsewhere in this README. `pip install -r requirements.txt`
  installs everything all five need in one shot (each also documents its
  own subset in its module docstring, if you only want one of them).
