# System Requirements Specification (SRS)

## Phone Configurator Simulator — Vercel + Postgres Version

*Reflects the implemented code as of 2026-09-15. Supersedes
`reference-appsscript-version/Phone_Configurator_Simulator_requirements.md`
for this app going forward — that document is frozen and describes the
retired Google Apps Script implementation now kept under `Google Web App
dev (deprecated)/`. Everything the app *does* is preserved from that
version; what changed is entirely about *how* it's built and deployed. See
`MIGRATION_BRIEF.md` for why.*

---

### 1. Overview & Purpose

A self-hosted web application that simulates a simple e-commerce "configure
and buy a phone" flow, built as a training target for a software
test-automation course. Students exercise the simulator two ways: via
browser automation (ChromeDriver/Selenium) and via direct HTTP calls "under
the UI", written as code (curl, Python's `requests`, or a VS Code REST
Client `.http` file — see §8).

The app has two pages:

- **`public/index.html`** — the simulator itself: configure a phone,
  calculate its price, buy it, and (depending on configuration) apply a
  discount code, return a phone, and use store credit.
- **`public/teacher.html`** — an instructor control panel that turns
  simulator features on/off — both legitimate configuration and a
  dedicated **Induced Bugs** section (§6.8) of deliberately broken
  behaviors — so the instructor can vary the exercise's difficulty and
  target specific testing scenarios without any code change.

This spec covers the full target behavior; the instructor may choose to
build/assign it incrementally via the Level system in §6.7.

---

### 2. Product Data (fixed reference values)

Unchanged from the original app.

| Parameter | Options |
|---|---|
| Model | Pixel 9, Pixel 9 Pro, Pixel 9 Pro XL |
| Storage | 128GB, 256GB, 512GB, 1TB |
| Color | Black, Red, Silver, Blue |
| Network | 5G, 4G |
| Accessory | None, Case, Charger, Earbuds |

Component pricing:

```json
{"Model":{"Pixel 9":900,"Pixel 9 Pro":1050,"Pixel 9 Pro XL":1430},
 "Storage":{"128GB":0,"256GB":56,"512GB":98,"1TB":164},
 "Color":{"Black":0,"Red":100,"Silver":80,"Blue":60},
 "Network":{"5G":115,"4G":0},
 "Accessory":{"None":0,"Case":45,"Charger":32,"Earbuds":215}}
```

Base price for a configuration = sum of the price of each parameter that
currently has a value; any parameter left unselected contributes 0
(§6.2). Defined once, server-side, in `lib/priceTable.js`.

---

### 3. Architecture & Tech Stack

* **Platform:** Vercel — plain Node.js serverless functions (one file per
  endpoint under `api/`), no framework (no Next.js/React). Static pages and
  client-side JS are served as-is from `public/`.
* **Frontend:** Plain HTML5/CSS3/vanilla JS, two pages (`public/index.html`,
  `public/teacher.html`), each with its own script (`public/js/student.js`,
  `public/js/teacher.js`) calling the REST API via `fetch()`.
* **Storage:** Postgres (`db/schema.sql`), accessed via the standard `pg`
  (node-postgres) driver — not `@vercel/postgres`, which is deprecated in
  favor of Neon's own SDKs; `pg` works with any Postgres connection string
  regardless of host. Purchase/discount-code/action-log history is
  row-shaped, growing data, one table each; teacher settings are a single
  singleton row (`settings`, `id = 1`) since they aren't row data.
* **Identity:** students identify themselves by **self-reporting an email
  address as a required parameter on every action** (Calculate/Buy/
  Return/Reset) — unchanged from the original app. This means **no login
  is required for students**, which is what makes both ChromeDriver and
  plain HTTP calls work with no auth flow at all.
* **Deployment:** A public Vercel project — the whole app (student and
  teacher pages, and every API endpoint) is reachable by anyone; the
  teacher-only endpoints are what's actually protected (§7), not the page
  route.
* **Teacher authentication — real, not identity-based:** since this isn't
  Apps Script, there's no platform constraint pushing toward
  `Session.getActiveUser()`-style identity checks. Teachers log in with a
  username and password (bcrypt-hashed, stored in the `teachers` table);
  a successful login sets an `httpOnly`, `Secure`, signed session cookie.
  See §7.
* **Pricing computation:** same split as the original app and for the same
  reason — the base-price arithmetic runs instantly client-side (the same
  `PRICE_TABLE`, fetched once from `GET /api/product-options` on page
  load) whenever no discount code is entered and the level is below 4; a
  server round-trip (`GET /api/calculate`) only happens when server-held
  data is actually needed (discount-code validity, or Level 4 credit).
  Buy always independently recomputes everything server-side regardless
  of what was previewed, so purchase integrity (§7) doesn't depend on this
  optimization.
* **Concurrency:** every mutating action (Buy, Return, Reset) runs inside a
  single Postgres transaction that first takes a **per-student advisory
  lock** (`SELECT pg_advisory_xact_lock(hashtext(email))`, transaction-
  scoped — auto-released on commit or rollback, no manual unlock, no leak
  risk on a crashed function). This replaces the original app's single
  *global* `LockService` lock (a platform necessity of Apps Script, which
  offered no per-key locking) with a strictly better-scoped equivalent:
  two different students' actions no longer block each other at all. See
  `lib/db.js`.
* **Action logging:** unchanged in spirit — a logging failure must never
  break the action it's recording. The `action_log` insert runs as its
  own separate statement, *after* the main transaction has already
  committed or rolled back, wrapped in its own try/catch that swallows
  errors — so a `ROLLBACK` on a failed Buy never erases the log row that
  records the failure, and one student's logging never contends with
  another's purchase transaction. See `lib/actionLog.js`.
* **Scale:** no Apps Script-style platform ceiling (concurrent execution
  caps, per-minute quotas) applies here — ordinary Vercel serverless
  function and Postgres connection limits are the only ceiling, and are
  far higher than anything a single class generates.

---

### 4. User Roles & Access Control

#### 4.1 Student
* **Access route:** the public site root (`/`) and every student-facing
  API endpoint — reachable by anyone, no login.
* **Identity:** a required **Email** field, validated as looking like an
  email address and, if the teacher has set a required domain suffix
  (§5.2 — blank by default, meaning any format is accepted), against that
  suffix too. This string is what drives purchase history, discount-code
  generation/redemption, store credit, and student-level reset (§6.9) —
  unchanged from the original app.
* **Accepted trade-off:** because this is self-reported rather than
  authenticated, a student *could* type another student's email and act
  "as" them. This is an explicit, unchanged trade-off from the original
  app, made to keep both ChromeDriver and HTTP-level testing simple and
  login-free — call it out to the class if it matters for your grading
  model.
* Sees only `public/index.html`, scoped to the feature set the teacher
  currently has enabled (§6.7, §6.8), and only their own purchase/credit
  data — never another student's.

#### 4.2 Teacher / Instructor
* **Access route:** `public/teacher.html`, gated by logging in with a
  username/password (`POST /api/teacher/login`). The page itself is
  publicly reachable (there's nothing sensitive in its markup — it's just
  a login form until authenticated), but every settings-changing or
  data-reading teacher action requires a valid session cookie, checked
  independently on the server for every call (§7).
* Controls the Level, the Induced Bugs section, and all other toggles in
  §6.7–§6.9, and can trigger a full data reset.
* Accounts are created/reset only via a local CLI script
  (`node db/seed-teacher.js <username> <password>`) — there is no
  self-registration endpoint.

---

### 5. Data Model

Postgres tables, defined in `db/schema.sql`.

#### 5.1 `purchases`
One row per phone bought (kept even after return, for history/debugging).

| Column | Type | Notes |
|---|---|---|
| purchase_id | UUID (PK) | `gen_random_uuid()`. |
| student_email | text | Self-reported, as submitted with the Buy request. |
| purchase_seq | integer | This student's purchase counter — 1 for their first purchase ever, 2 for their second, etc. Used to build their discount code. |
| model / storage / color / network / accessory | text | The bought configuration. Blank for any component omitted under the partial-configuration bug (§6.8). |
| base_price | numeric(10,2) | Sum of the *selected* components' prices at time of purchase (0 for any left unselected). |
| discount_code_used | text | Blank if none applied. |
| paid_price | numeric(10,2) | base_price minus 15% if a valid discount code was applied; equals base_price otherwise. This is the figure store credit is based on when `creditBasis = paid` (§6.6) — i.e. *before* any store credit is deducted. |
| credit_applied | numeric(10,2) | Store credit consumed at purchase time (Level 4). |
| requested_payment | numeric(10,2) | paid_price − credit_applied, floored at 0. |
| code_generated | text | The new discount code generated by this purchase, if any (Level 2+). |
| status | text | `Bought` / `Returned`. |
| created_at | timestamptz | |

Indexed on `student_email`.

#### 5.2 `discount_codes`
One row per generated code. Primary key is `(student_email, code)` — codes
are always looked up scoped to their owning student, so this is the
natural key rather than a synthetic id.

| Column | Type | Notes |
|---|---|---|
| student_email | text | Owner (part of PK). |
| code | text | 7 chars: 5-char email-prefix + 2-digit sequence (§6.4) (part of PK). |
| generated_by_purchase_id | UUID | FK → `purchases.purchase_id`. |
| status | text | `Active` / `Redeemed` (single-use by default) / `Disabled` (its purchase was returned). |
| created_at | timestamptz | |

#### 5.3 `store_credit`
One row per student.

| Column | Type | Notes |
|---|---|---|
| student_email | text (PK) | |
| balance | numeric(10,2) | Accumulative; increased on a store-credit return, decreased when auto-applied to a purchase. |

#### 5.4 `settings`
Singleton row (`id = 1`, enforced by `CHECK (id = 1)`) — teacher-configurable
settings, one row instead of Apps Script's Script-Properties JSON blob.

| Column | Type | Notes |
|---|---|---|
| level | integer | 1–4, see §6.7. |
| required_email_domain | text | `''` = any email format accepted; e.g. `post.jce.ac.il` to restrict. |
| student_reset_enabled | boolean | |
| discount_code_mode | text | `normal` \| `acceptAny` \| `acceptNone`. |
| allow_buy_with_partial_config | boolean | |
| return_stays_available_when_empty | boolean | |
| allow_discount_code_reuse | boolean | |
| credit_basis | text | `paid` (correct) \| `base` (bug). |
| updated_at | timestamptz | |

`required_email_domain` is teacher-configurable at any time (§4.1): blank
accepts any email-shaped string; set to e.g. `post.jce.ac.il` to require
that suffix.

`credit_basis` decides what a returned phone's store credit is based on
(§6.6, §6.8): `paid` (correct, default) = what the student actually paid
after the 15% discount; `base` (induced bug) = the phone's original
component-sum price, ignoring any discount used at purchase — this lets a
student buy at a discount and get back more credit than they paid, a real
arbitrage exploit.

#### 5.5 `action_log`
One row per button-press action, success or failure — see §6.11 for the
full column list and the write-ordering rationale (§3).

Indexed on `student_email` and `created_at DESC` (the latter specifically
so a future teacher live-monitor dashboard could poll `WHERE created_at >
$since` with no migration needed — not built yet, but the schema doesn't
preclude it).

#### 5.6 `teachers`
The teacher account table — username + bcrypt password hash. Managed only
via `db/seed-teacher.js`; never created automatically and never exposed to
any student-facing endpoint.

---

### 6. Functional Requirements

Sections 6.1–6.11 below describe **unchanged behavior** from the original
app unless a subsection explicitly calls out a difference. The product
logic — what a student can do and what each induced bug does — was a hard
requirement of this migration (see `MIGRATION_BRIEF.md`) and was ported
line-for-line from `reference-appsscript-version/Code.js` into
`lib/*.js`.

#### 6.1 Parameter fields (`public/index.html`)
* Model, Storage, Color, Network, Accessory are all **dropdowns**
  (`<select>`), populated from §2 via `GET /api/product-options` on page
  load — no free text, no invalid values possible. Each starts with no
  value selected (a blank/placeholder option, `-- select --`), and can be
  reset back to that blank option by the student at any time.
* **Discount code** is the only free-text field, max length 7 characters
  (matches the valid code length).

#### 6.2 Calculate Price
* A **Calculate Price** button is always enabled — it can be clicked
  regardless of how many of the 5 parameters currently have a value, and
  never mutates any stored data (no purchase, no code redemption).
* Base price = sum of the price of each parameter that currently has a
  value; any parameter left unselected contributes **0**.
* If a discount code is entered, it's evaluated using the same rules as
  Buy (§6.4): a non-empty, invalid code shows **"Unknown code"** (0%
  discount, calculation still proceeds); a valid code applies the 15%
  discount. (Relevant from Level 2 up — the discount field doesn't exist
  at Level 1.)
* Level 1: shows just **Total Price**.
* Level 4: also auto-applies the student's current store credit, using
  the same mechanics as Buy (§6.5), and shows **Phone price**, **Applied
  credit**, **Requested payment** — exactly the breakdown Buy would
  produce, just without recording anything.
* **Where the computation happens (§3):** when no discount code is
  entered and the level is below 4, the base price is computed
  **instantly, client-side**, using the same component price table the
  server uses — no round trip, no wait. The client still fires
  `GET /api/calculate` unawaited ("fire-and-forget") purely so the action
  gets logged (§6.11), without making the student wait for it. A server
  call is *awaited* only when server-held data is actually needed: a
  discount code, or Level 4. Buy is unaffected either way — it always
  independently recomputes everything server-side regardless of what
  Calculate Price displayed, so this doesn't weaken purchase integrity
  (§7).

#### 6.3 Buy button enablement
* **Buy** starts disabled. Two independent conditions must both hold for
  it to be enabled:
  1. All 5 parameter dropdowns have a real (non-blank) value — **unless**
     the "Enable Buy for partial configuration" bug is active (§6.8), in
     which case, once this condition has been met at least once, a field
     going blank again no longer breaks it.
  2. **Calculate Price has been run for the *current* inputs.** Changing
     any parameter dropdown or the discount code re-disables Buy, even if
     the change is reverted back to a previously-calculated value —
     Calculate Price must be clicked again regardless. Clicking **Buy
     itself does not** re-disable it, so repeated Buy clicks against an
     already-calculated configuration are allowed (e.g. buying several
     identical phones in a row) — see §6.10 for how each purchase is
     displayed.

#### 6.4 Discount codes (Level 2+)
* **Validity rule:** exactly 7 characters, and — depending on the
  `discountCodeMode` bug setting (§6.8):
  * `normal` (default): must exist in `discount_codes` for *this* student
    (by self-reported email). Given a code that exists, its `status`
    decides the outcome (default behavior — see the
    `allowDiscountCodeReuse` bug in §6.8 for the override):
    * `Active` → valid, 15% discount applies.
    * `Redeemed` (already used once) → invalid, shows **"This code was
      already used"**.
    * `Disabled` (the purchase that generated it was returned, §6.6) →
      invalid, shows **"Invalid code. The phone that got you this code
      was returned."**
  * `acceptAny`: any 7-character string is treated as valid, regardless
    of whether it was ever generated (and regardless of the
    `allowDiscountCodeReuse` bug — this mode doesn't consult stored codes
    at all).
  * `acceptNone`: no code is ever accepted, even a genuinely valid one —
    discount is always 0%.
* A valid code gives a flat **15% discount** off the base price.
* A non-empty code that doesn't exist at all for this student (typo,
  wrong student, never generated) shows the generic **"Unknown code"** —
  only a code that *does* exist gets one of the two specific messages
  above.
* **Single-use is the default from Level 2 up** (not Level-3-gated — see
  the Level table, §6.7): a code is marked `Redeemed` the moment it's
  successfully used on a Buy, regardless of level. The
  `allowDiscountCodeReuse` induced bug (§6.8) is what makes codes
  reusable.
* **Code generation (on Buy):** first 5 characters of the student's
  email, taken before the `@`, as-is (no case change), right-padded with
  the literal character `Z` if shorter than 5, followed by a 2-digit
  zero-padded sequence number equal to that student's purchase count so
  far (`01`, `02`, …). Example: `michael.stahl@gmail.com` → prefix
  `micha`; 3rd purchase → code `micha03`.
* **A purchase that itself used a valid discount code generates no new
  code** — handing out a fresh code every time one was just spent would be
  equivalent to letting the same code be applied repeatedly. The student
  instead sees **"No discount codes for discounted purchases"** where a
  new code would otherwise appear. A purchase made with *no* code (or an
  invalid one, 0% discount) still generates a code as normal.
* **N identical phones, one returned:** if a student has bought the same
  configuration more than once (so has N still-active discount codes, one
  per purchase), returning one of them disables the **oldest still-
  `Bought`** matching purchase's code — i.e. the first one chronologically,
  not an arbitrary one — following naturally from Return (§6.6) always
  matching the earliest eligible purchase (`purchases` is read ordered by
  `purchase_seq ASC`).

#### 6.5 Buy Now (all levels)
Server-side, using the self-reported `email` field as identity (required
on every call), inside one Postgres transaction (§3):
1. Take the per-student advisory lock.
2. Recompute base price from the submitted configuration (server is
   authoritative — never trusts a client-submitted price). Under the
   partial-configuration bug, missing components simply contribute 0.
3. Resolve discount per §6.4; compute paid price.
4. (Level 4) Auto-apply the student's current store credit, mandatorily
   (not optional): deduct from `requested_payment` in full if the balance
   covers it, otherwise partially (down to 0); reduce the balance by
   exactly the amount applied.
5. Record the purchase in `purchases`.
6. (Level 2+, and only if no valid discount code was used on this
   purchase) Generate and store a new discount code for this student.
7. Commit. Return the price breakdown, any newly generated code, and
   (Level 4) the updated store-credit balance to the page.

#### 6.6 Return, Refund / Store Credit (Level 4 only)
* A **Return** button plus two radio buttons, **Refund** and **Store
  credit**.
* Disabled until the student has bought at least one phone (lifetime, not
  "currently holds one") — see the toggle below for what happens once
  their bought list later becomes empty again.
* On click, the server checks whether the *currently selected* field
  values match one of this student's purchases with `status = Bought`:
  * **No match:** returns `{success: false, message: "Return action
    failed. The stated configuration does not match a phone you
    bought."}` — a normal `200` response, not an HTTP error; this is a
    legitimate business outcome (§8).
  * **Match:**
    * `success: true`, message `"The phone can be returned"`.
    * Set that purchase's `status = Returned`.
    * Disable the discount code generated by that purchase
      (`status = Disabled` in `discount_codes`), even if it was never
      used — a later attempt to use it reads as invalid.
    * If **Refund** selected: `refundMessage: "Refund will be completed
      within 5 business days"` (no credit change).
    * If **Store credit** selected: add an amount to the student's store
      credit balance (accumulative across multiple returns) and return
      `refundMessage: "Your store credit is now $X"`. The amount is that
      purchase's **paid_price** — base price minus discount if one was
      applied, *before* any store credit that was applied at that
      purchase — unless the `creditBasis` induced bug (§6.8) is set to
      `base`, in which case it's the phone's **base_price** instead,
      ignoring any discount that was used.
* **Default behavior:** once a student's Return button has been enabled by
  their first purchase, it becomes disabled again once their bought list
  is empty (button greyed out/hidden, matching its pre-first-purchase
  state). The "Return stays available when empty" induced bug (§6.8)
  overrides this — see there.

#### 6.7 Levels (`public/teacher.html`)

A single **Level** selector, 1–4, each building on the previous:

| Level | Adds |
|---|---|
| **1** | Parameter dropdowns, Calculate Price → Total Price, Buy button only. No discount field, no return, no credit. |
| **2** | + Discount code field/validation. First purchase by a student is necessarily unvalidated (no code exists yet, unless the `acceptAny` bug is set). Buy generates a code, single-use by default (§6.4). |
| **3** | Same as 2, + full purchase tracking. *(Single-use enforcement is a Level-2+ default controlled by the `allowDiscountCodeReuse` bug, not this level's own gate — see the note below.)* |
| **4** | Same as 3, + Return/Refund/Store-credit functionality (§6.6), which is also what makes a discount code `Disabled`-able in the first place. |

Lowering the Level does **not** delete any recorded data — it only
hides/disables the corresponding UI and validation.

**Note on Levels 2 vs 3:** since single-use enforcement is a bug toggle
(§6.4, §6.8) rather than Level-3-exclusive, Levels 2 and 3 are
functionally identical for discount codes in the current implementation —
purchases are recorded at every level regardless, so nothing currently
distinguishes 2 from 3 beyond the label. Unchanged from the original app;
flag if a real distinguishing behavior is wanted at Level 3.

#### 6.8 Induced Bugs (`public/teacher.html`)

A dedicated section of deliberately-breakable behaviors, toggleable on the
fly, independent of Level (each is only *observable* once its related
feature is reached, but can be pre-armed at any time):

| Bug | Effect when ON |
|---|---|
| **Accept any discount code** | Any 7-character string in the discount field is treated as a valid code (15% off), whether or not it was ever generated. (Relevant from Level 2 up.) |
| **Never accept discount codes** | No code is ever accepted, even a genuinely correct one — discount is always 0%. (Relevant from Level 2 up. Mutually exclusive with the bug above — only one `discountCodeMode` can be active; selecting one clears the other, `normal` being the default with neither on.) |
| **Enable Buy for partial configuration** | Buy stays enabled even after a fully-configured phone has one of its 5 parameters reselected back to blank (§6.3), overriding the normal rule that a partial configuration can't be bought. Clicking Buy in that state does not error: it proceeds as if a partially-configured phone can be bought, with the missing component(s) contributing 0 to the price and stored blank on the purchase record. |
| **Return stays available when empty** | Once a student's Return button has been enabled by their first purchase, it never goes back to disabled — even after every purchase has been returned. Clicking it with nothing left to return falls into the ordinary "no match" branch (§6.6) and returns the same failure result, rather than the button being greyed out/hidden as it normally would be. |
| **Store credit based on base price** (`creditBasis = base`) | A store-credit return pays out the phone's original, undiscounted price instead of what the student actually paid (§6.6). This lets a student buy at a 15% discount, return it for store credit, and net more credit than they spent — a real pricing exploit, not just a cosmetic difference. |
| **Allow discount code reuse** | A code stays valid indefinitely: neither using it once (§6.4, normally → `Redeemed`) nor its originating purchase being returned (normally → `Disabled`) ever invalidates it. Default (off) enforces both: a used code shows **"This code was already used"**; a code whose phone was returned shows **"Invalid code. The phone that got you this code was returned."** Has no effect when `discountCodeMode` is `acceptAny`/`acceptNone`, since those modes don't consult stored codes at all. |

*(`studentResetEnabled` (§6.9) remains a legitimate configuration choice
about how the store behaves, not deliberately broken behavior, so it's
kept out of this section.)*

**Implementation note:** every bug flag above is enforced server-side and
only ever observable through the *outcome* of an action (a code being
accepted/rejected, a credit amount, a return message) — except
`allowBuyWithPartialConfig`, which the client must know in order to
render the Buy button's live enabled/disabled state (§6.3) correctly;
that one flag alone is exposed via `GET /api/ui-config`. No other bug flag
is exposed to the client.

Settings changes (Level, bugs, or other toggles) take effect immediately
for all students on their next action — no push channel exists (same as
the original app), but none is needed since there's no live timer; each
Calculate/Buy/Return simply reads current settings fresh from `settings`.

#### 6.9 Reset controls
* **Teacher — "Reset simulator data"** (`POST /api/teacher/reset-all`):
  wipes *all* students' purchases, discount codes, credit balances, and
  the action log (`TRUNCATE` on all four tables in one statement; the
  `settings` and `teachers` tables are untouched). Double-confirmation
  (confirm dialog + typing `RESET`) in the UI, mirroring the original
  app.
* **Student — "Reset" button** (`POST /api/reset`): visible on
  `public/index.html` only when `studentResetEnabled` is on
  (teacher-controlled, independent of Level). Clears **only the calling
  student's own** data (their purchases, their codes, their credit, their
  purchase counter back to 0), scoped server-side by the self-reported
  `email` parameter. Inherits the same accepted trade-off as §4.1: a
  student could in principle reset another student's data by submitting
  that student's email. Also clears the on-screen purchase history list
  (§6.10) and re-disables Buy until Calculate Price is run again.

#### 6.10 Purchase confirmation & history (all levels)
* On a successful Buy, the page shows a confirmation message in this exact
  template (values substituted from the *actual recorded purchase*, not
  just whatever was on-screen):

  > Congratulations! You are now the owner of a `<Network>` `<Color>`
  > `<Model>` with `<Storage>`[ and [a] `<Accessory>`]

  * The trailing `and ... <Accessory>` clause is **omitted entirely**
    when Accessory is `None`.
  * The article before the accessory is `a` for **Case** and
    **Charger**; no article at all before **Earbuds** (a plural noun —
    "and Earbuds", not "and a Earbuds").
  * Shown at every level, not just Level 1 — at Level 1 it's the *only*
    success feedback there is; at higher levels it supplements the
    numeric price/code/credit breakdown that's already shown.
  * **Built entirely client-side** (`public/js/student.js`'s
    `buildCongratsMessage()`) from the `config` the Buy response echoes
    back — the server never returns the message text itself, only the
    data it's built from.
* Each successful Buy **appends** this message to a running, on-screen
  **purchase history list** rather than replacing the previous one —
  repeated Buy clicks (§6.3) or buying under a changed configuration both
  add to the same list. The list scrolls (rather than growing the page
  indefinitely) once it's tall enough to need it.
* The history list is client-side, per page load — it is not
  reconstructed from server history if the page is reloaded (out of
  scope; the server remains the source of truth for actual purchase
  records regardless of what's currently displayed).

#### 6.11 Action logging (all levels)

Every button-press action a student takes — **Calculate Price, Buy,
Return, Reset** (setting a dropdown/text value is not itself logged, only
pressing a button is) — is appended as one row to `action_log`, whether it
succeeds or fails.

| Column | Content |
|---|---|
| created_at | Server time of the action. |
| student_email | Self-reported email for this action. |
| action | `CalculatePrice` / `Buy` / `Return` / `Reset`. |
| parameters | The 5 configuration values, `\|`-joined, in Model\|Storage\|Color\|Network\|Accessory order (blank for any unset — including under the partial-config bug). |
| discount_code | The code text entered, if any. |
| calculated_price | The resulting monetary figure for that action (Total/Requested Payment for Calculate and Buy; the credit amount added for a Store-credit Return; blank for a Refund Return or a Reset). |
| credit_before / credit_after | Store credit balance immediately before and after the action (Level 4 actions only — populated for Buy, Return, and Reset; a Reset sets credit_after to 0). |
| result | `Success` / `Failed` (a legitimate business-rule failure returned normally, e.g. no matching purchase to return) / `Error` (a thrown validation error, e.g. bad email, disabled student reset, partial config without the bug). |
| message | The error/failure message, when applicable. |

**Write-ordering (see also §3):** logging never blocks or slows down
another student's action. The insert runs **outside** the Postgres
transaction that performs the actual Buy/Return/Reset — as its own
statement, in a `finally`, after that transaction has already committed
or rolled back — so a rolled-back action (e.g. a thrown validation error)
still produces a log row recording the failure, and one student's log
write never contends with another's purchase transaction. For Calculate
Price specifically, when the price was computed instantly client-side
(§6.2, the common case), the logging call is fired to the server
**without the client waiting for it** ("fire-and-forget"). A logging
failure of any kind is swallowed server-side and never surfaces as an
error to the student — logging is best-effort and must never block or
break the action it's recording.

---

### 7. Security Model

* **Teacher auth is real, session-based auth — not identity-based.**
  `POST /api/teacher/login` verifies a bcrypt password hash and, on
  success, sets an `httpOnly; Secure; SameSite=Lax` signed session cookie
  (HMAC-SHA256 over a `{username, iat, exp}` payload, `lib/auth.js`).
  `POST /api/teacher/logout` clears it.
* **Every teacher-only endpoint independently re-verifies the session
  cookie**, via `requireTeacher(req)` as the first line of the handler —
  never trusted as a one-time check at page load. `public/teacher.html`'s
  own client-side "show login form if not authenticated" logic is UX
  only, never the actual security boundary — an expired, forged, or
  missing cookie is rejected server-side regardless of how the request
  was made.
* **Teacher actions ARE reachable via the "under the UI" JSON API** —
  unlike the original app, where identity-based auth meant a bare HTTP
  request had no signed-in browser session to check, and teacher actions
  were only reachable through `teacher.html` itself. Here, `POST
  /api/teacher/login` followed by carrying the returned session cookie on
  subsequent requests works from curl/Python exactly as it does from a
  browser — this is a deliberate consequence of moving to a real,
  cookie-based session rather than a platform-identity check, and is not
  considered a gap (the cookie is still required and still verified on
  every call).
* **Student identity is self-reported by design** (§4.1) — a deliberate,
  unchanged trade-off, made to keep both ChromeDriver and HTTP-level
  testing simple and login-free for students. It is validated for shape
  (and optionally domain), never for ownership.
* **Server is authoritative for price/discount/credit:** the client only
  ever submits raw field selections, the discount-code text, and the
  email; base price, discount validity, credit balance, and match/no-match
  on Return are always recomputed server-side from stored records — never
  trusted from the client.
* **Bug toggles are resolved server-side** from current teacher settings —
  a student cannot force a discount, or a partial-configuration purchase,
  via client-side tampering; the server enforces whatever
  `discountCodeMode`/`allowBuyWithPartialConfig` is currently set,
  regardless of what the page's own JS does.
* **No secrets in the client bundle.** `SESSION_SECRET` and `DATABASE_URL`
  are server-side environment variables only, never sent to or readable
  from the browser.

---

### 8. Test Automation Support

* **ChromeDriver/Selenium:** every field, button, and result element keeps
  the **same stable `id`s** as the original app (`#student-email`,
  `#model-select`, `#discount-code`, `#calc-price-btn`, `#total-price`,
  `#buy-btn`, `#generated-code`, `#store-credit-balance`, `#return-btn`,
  `#return-message`, etc.), so existing Selenium-facing course material
  doesn't need to change. Unlike the original app, there is **no redirect
  to wait for** — the page loads directly, with normal, fast, reliable
  HTTP (see `MIGRATION_BRIEF.md` for why this mattered enough to migrate
  over).
* **"Under the UI" HTTP testing:** one REST endpoint per action, instead
  of a single `?action=X` dispatcher. Every response is either the data
  directly with `HTTP 200`, or `{"error": "..."}` with `400`/`401`/`500`
  — there is no `{ok, data/error}` envelope to unwrap. A business-rule
  "no match" on Return is still a normal `200` with `{success: false,
  ...}`, since that's a legitimate outcome, not a failure.

  | Method | Path | Auth | Notes |
  |---|---|---|---|
  | GET | `/api/ui-config` | none | `{level, studentResetEnabled, requiredEmailDomain, allowBuyWithPartialConfig}`. |
  | GET | `/api/product-options` | none | `{priceTable, options}` — new; lets the client bootstrap without server-side templating. |
  | GET | `/api/calculate` | none | Query: `email, model, storage, color, network, accessory, discountCode`. |
  | GET | `/api/student-status` | none | Query: `email`. `{email, returnEnabled, creditBalance}`. |
  | POST | `/api/buy` | none | JSON body: `{email, model, storage, color, network, accessory, discountCode}`. |
  | POST | `/api/return` | none | JSON body: `{..., refundType: "Refund"\|"StoreCredit"}`. |
  | POST | `/api/reset` | none | JSON body: `{email}`. |
  | POST | `/api/teacher/login` | — | `{username, password}` → sets session cookie. |
  | POST | `/api/teacher/logout` | cookie | Clears it. |
  | GET/PUT | `/api/teacher/settings` | cookie | Full settings object. |
  | POST | `/api/teacher/reset-all` | cookie | Wipes all student data. |

  Since this is a coding-focused exercise, the supported tools are:
  * **curl** (in a shell script, or shelled out to from Python via
    `subprocess`) — fully supported. See `test_level1_buy.py` for a
    worked example (Calculate via curl, Buy via Python's `requests`,
    independent price recomputation, no `{ok, data}` unwrapping needed).
  * **Python's `requests` library** — for POST calls in particular
    (JSON body, following the response directly, no redirect handling
    needed at all).
  * **VS Code REST Client extension** (`.http` files) — a lightweight,
    code-based alternative that stays in the same editor as the
    ChromeDriver code.

  No GUI tool (e.g. Postman) is used, since the exercise is meant to have
  students write the requests themselves.

---

### 9. Open Items

None outstanding for current behavior. Noted as a possible future
addition, not a gap in what's here: a live teacher-facing monitor
dashboard (polling `action_log`/`purchases` for near-real-time visibility
into student activity, replacing the old habit of watching a Google Sheet
update). The schema (§5.5's index on `created_at`) was deliberately kept
compatible with this, but it isn't built.

---

*Reference: the frozen Apps Script version's spec (for historical
comparison only) is
`reference-appsscript-version/Phone_Configurator_Simulator_requirements.md`,
right alongside this file — also duplicated, unfrozen, at
`../Google Web App dev (deprecated)/Phone_Configurator_Simulator_requirements.md`.*
