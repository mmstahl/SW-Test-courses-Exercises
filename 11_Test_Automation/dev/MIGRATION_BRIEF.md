# Migration Brief: Phone Configurator Simulator → Vercel

*Written as a handoff to a new conversation. Start that new session with this
folder as the working directory, and open with something like "read
MIGRATION_BRIEF.md and let's get started."*

---

## Why this migration

The app (a phone-configurator test-automation exercise: student self-service
page + teacher control console) was built and iterated on Google Apps
Script. It works correctly and the browser-based UI is fast and reliable.
But the "under the UI" HTTP path — students hitting the public `/exec` URL
directly via curl/Python, which is a core part of the exercise's pedagogy —
turned out to be genuinely unreliable: Apps Script's `/exec` endpoint
responds with a redirect to a `script.googleusercontent.com` content-serving
URL, and that hop was empirically observed to take anywhere from ~2 to ~58
seconds for the exact same trivial request, with occasional outright
failures (wrong HTTP status, HTML error pages instead of JSON). This was
confirmed (via ActionLog timestamps vs. when the HTTP client actually
received a response) to be downstream of Apps Script's own delivery
infrastructure, not a bug in the app's server-side logic, and not fixable
from application code. Full diagnostic history is in this conversation's
transcript if it's ever needed, but shouldn't be — the requirements doc
below is the complete, current spec; nothing about *what* the app does
depends on *why* we're moving it.

Decision: move to a real, self-hosted server (Vercel) so "under the UI"
testing is against normal, reliable HTTP — no redirect dance, no
platform-specific flakiness to teach around before the actual lesson
(data-driven and keyword-driven test automation) can start.

## What must be preserved

Everything currently in the app. The authoritative spec is
`reference-appsscript-version/Phone_Configurator_Simulator_requirements.md`
(also copied here: `Code.js`, `student.html`, `teacher.html` — the actual
working implementation). Read the requirements doc first; it's current and
detailed. Summary, so nothing gets lost by accident:

* **Product data**: 5 configuration parameters (Model, Storage, Color,
  Network, Accessory), each with a fixed price table (§2 of the requirements
  doc).
* **4 progressive Levels** (§6.7): Level 1 = dropdowns + price + Buy only;
  Level 2 = + discount codes; Level 3 = + purchase tracking (functionally
  same as Level 2 currently — see the doc's own note on this); Level 4 = +
  Return / Refund / Store Credit.
* **Discount code lifecycle** (§6.4): generation formula (email-prefix +
  sequence number), single-use by default, invalidated if the originating
  purchase is returned, with distinct student-facing messages for each
  failure reason.
* **Store credit**: accumulates on store-credit returns, mandatorily applied
  at next purchase (partial if insufficient).
* **Return/Refund flow** (§6.6), including the "N identical phones" oldest-
  match behavior.
* **Teacher console** (`teacher.html`): Level selector, configuration
  settings, and a dedicated **Induced Bugs** section — 5 toggleable bugs,
  each with a specific, real effect (see §6.8). These are the pedagogical
  core of the exercise; get their exact behavior right, not just their
  names.
* **Action logging**: every button-press action logged (§6.11) for the
  teacher to review — used by students to cross-reference client-observed
  behavior against server-side timing/outcome.
* **Purchase history, congrats message, buy-button-enablement rules,
  "blink" feedback on Calculate Price** — all in `student.html`, all part of
  the intended UX.
* **The "under the UI" JSON API contract** (§8) that students write
  curl/Python/REST-Client tests against — `getUiConfig`, `calculate`,
  `getStudentStatus`, `buy`, `return`, `resetStudent`. Whether the *shape*
  of this API changes is an open decision below, but the *actions and
  their behavior* must not silently drift from the current spec.

## What does NOT need to carry over as-is

Most of the identity/auth complexity in the current app was working *around*
Apps Script-specific constraints (no reliable way to know a caller's
identity under anonymous access; no way to scope OAuth to just the teacher
route without breaking anonymous student access). None of that applies on a
normal server — this is a good opportunity to simplify, not an obligation to
replicate the workaround:

* Teacher auth was a real Google-identity allowlist (`Session.getActiveUser()`
  against a `Teachers` sheet) specifically because that was the *reference
  app's* mechanism and consistency was explicitly preferred over inventing
  something new — worth revisiting now, since a normal server can just do
  real login (username/password, a simple session cookie, whatever's
  appropriate) without any of the platform contortions that motivated past
  decisions in this app.
* Students still shouldn't need to log in — that requirement was about
  keeping curl/ChromeDriver simple for the exercise, not an Apps Script
  workaround, and it still matters here.

## Open decisions for the new conversation to resolve first

Don't guess at these — they're exactly the kind of thing worth a short
clarifying round before writing code, same as this conversation did for the
original app:

1. **Persistence.** Vercel serverless functions have no persistent local
   filesystem between invocations, so SQLite-on-disk won't work as-is.
   Options: a hosted Postgres/SQLite-compatible service (e.g. Vercel
   Postgres, Turso), Vercel KV, or continuing to use the existing Google
   Sheet via the Sheets API (keeps the "instructor can eyeball a
   spreadsheet" property the current app has, at the cost of needing a
   Google Cloud service-account credential).
2. **Framework.** Plain Vercel serverless functions + static HTML/vanilla
   JS (closest to what exists now, fewest new concepts) vs. a framework
   (e.g. Next.js). Given the app's actual complexity, plain functions are
   probably the right call, but worth confirming rather than assuming.
3. **API shape.** Keep the current single-endpoint `?action=X` style
   (minimal change, but not idiomatic REST) vs. proper per-action REST
   endpoints (`POST /api/buy`, `GET /api/calculate`, etc. — arguably better
   now that there's no Apps Script `doGet`/`doPost` constraint forcing one
   endpoint). Changes what students' test scripts look like, so decide
   deliberately.
4. **Teacher auth mechanism** — see above; needs an actual decision, not a
   default.

## Practical notes

* This folder currently only contains this brief and the reference
  snapshot — no other setup has been done yet (no `package.json`, no Vercel
  config). That's deliberate; framework/structure depends on the decisions
  above.
* The reference files in `reference-appsscript-version/` are a frozen copy
  as of the migration decision — don't edit them; they're for comparison
  while porting, not the working app going forward.
* The live Apps Script version stays deployed and untouched during this
  work — no reason to take it down while the port is in progress.
