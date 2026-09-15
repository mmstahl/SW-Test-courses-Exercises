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
   situation you're in.)

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

## Project layout

- `db/` — schema (`schema.sql`), migration runner, teacher-account seeding.
- `lib/` — shared server logic (pricing, discount codes, purchases, store
  credit, action logging, auth), reused across the `api/` endpoints.
- `api/` — one file per REST endpoint (see the requirements doc's §8-style
  API contract, now per-action REST instead of the old `?action=X` style).
- `public/` — the student (`index.html`) and teacher (`teacher.html`) pages
  and their JS, using the same element `id`s as the reference app so
  existing Selenium-facing course material doesn't need updating.
