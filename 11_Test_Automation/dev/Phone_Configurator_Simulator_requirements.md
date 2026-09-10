# System Requirements Specification (SRS)

## Phone Configurator Simulator — Test-Automation Training Exercise

*Reflects the implemented code as of 2026-09-10, including action logging (§6.11, §5.5), purchase confirmation/history (§6.10), Buy-gating on Calculate Price (§6.3), and the client-side pricing / reduced-Sheets-read performance changes (§3, §6.2).*

---

### 1. Overview & Purpose

A Google Apps Script (GAS) web application that simulates a simple e-commerce "configure and buy a phone" flow, built as a training target for a software test-automation course. Students exercise the simulator two ways: via browser automation (ChromeDriver/Selenium) and via direct HTTP calls "under the UI", written as code (curl, or a VS Code REST Client `.http` file — see §8).

The app has two pages:

- **`student.html`** — the simulator itself: configure a phone, calculate its price, buy it, and (depending on configuration) apply a discount code, return a phone, and use store credit.
- **`teacher.html`** — an instructor control panel that turns simulator features on/off — both legitimate configuration and a dedicated **Induced Bugs** section (§6.8) of deliberately broken behaviors — so the instructor can vary the exercise's difficulty and target specific testing scenarios without any code change.

This spec covers the full target behavior; the instructor may choose to build/assign it incrementally via the Level system in §6.7.

---

### 2. Product Data (fixed reference values)

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

Base price for a configuration = sum of the price of each parameter that currently has a value; any parameter left unselected contributes 0 (§6.2).

---

### 3. Architecture & Tech Stack

* **Platform:** Google Apps Script (GAS), bound to the target Google Sheet.
* **Frontend:** HTML5/CSS3/JS served via `HtmlService`, two entry pages (`student.html`, `teacher.html`) selected by `doGet`.
* **Storage:** Google Sheets, used as the system of record (see §5) — purchase/discount-code history is row-shaped, growing data, not a single config blob. Teacher-configurable settings (§6.7, §6.8) are a single small object and are kept in **Script Properties** instead, since they aren't row data.
* **Identity:** students identify themselves by **self-reporting an email address as a required parameter on every action** (Calculate/Buy/Return/Reset) — not via `Session.getActiveUser()`. This means **no Google login is required for students**, which is what makes both ChromeDriver and plain HTTP calls work without OAuth.
* **Deployment:** Execute as **Me**, access **Anyone** (fully anonymous — `ANYONE_ANONYMOUS` in the manifest). This is a hard requirement of the no-login-for-students decision above.
* **Teacher authentication — revised from Google-identity to a shared password:** `Session.getActiveUser()` only reliably returns an identity when a deployment requires a signed-in Google account. Since this deployment is fully anonymous (previous bullet), that call would silently fail to identify anyone — including the teacher. Teacher actions are instead gated by a **shared password**, stored in Script Properties and checked server-side on every teacher-only function call (`teacherGetSettings`, `teacherUpdateSettings`, `teacherResetAll`), changeable from `teacher.html` itself. This preserves the reference app's actual security principle — the boundary is a server-side check inside the function, never which page was served — just with a password in place of an identity lookup that isn't available under this deployment mode. **Change the default password (`teacher123`) immediately after first deploying.**
* **Pricing computation — revised for performance:** originally server-side only; base-price arithmetic now also runs client-side for the common case (see §6.2's "Where the computation happens" note) because every `google.script.run` call carries real, mostly-fixed latency in Apps Script regardless of what the function does — moving pure arithmetic off that path was the actual fix for "Calculate Price feels slow," not a data-volume problem. Discount-code validity and store credit remain server-only (they depend on server-held data), and Buy always independently re-validates everything server-side regardless of what was previewed, so purchase integrity (§7) is unaffected by this change.
* **Concurrency & scale, revised for a 30-student class running many automated tests:** `LockService.getScriptLock()` — the *only* lock primitive Apps Script offers that works across anonymous users (there is no way to create independent named locks) — still guards every read-modify-write against Purchases/DiscountCodes/StoreCredit (Buy, Return, Reset), since Apps Script gives no other way to prevent lost updates on those. Two things were tightened once this became a stated concern:
  * **Fewer Sheets API calls per action.** The original implementation re-read the entire `Purchases` sheet up to three separate times within a single Buy (§6.5) or Return (§6.6) call — once for the sequence number, again to check purchase history, again to find a match — each a real network round trip to the Sheets service, with cost that only grows as the sheet accumulates rows over a class session. Each of those calls now does exactly **one** read, reused in-memory for everything that call needs.
  * **The action log (§6.11, §5.5) never touches this lock at all** — it's a separate, unlocked append, and (for Buy/Return/Reset) is written only *after* the lock is released — so one student's logging or purchase/return processing never makes another student's request wait longer than strictly necessary.
  * **Platform ceiling that no amount of code change removes:** Apps Script still caps simultaneous script executions per project (around 30 on a consumer Google account) and has its own per-minute quotas. If 30 students' automated test suites genuinely fire in the same instant, some requests may still queue briefly or hit a quota error — that's a Google-imposed limit, not a bug in this app, and the fix at that point is a Workspace account (higher quotas) or spacing out test runs, not further optimization here.

---

### 4. User Roles & Access Control

#### 4.1 Student
* **Access route:** base Web App URL (`.../exec`), reachable by anyone — **no Google sign-in required**.
* **Identity:** a required **Email** field, validated as looking like an email address and, if the teacher has set a required domain suffix (§5.4 — blank by default, meaning any format is accepted), against that suffix too. This string is what drives purchase history, discount-code generation/redemption, store credit, and student-level reset (§6.9) — the same self-reported-email pattern the reference app uses for its students (see its §3.1, §7.3.1).
* **Accepted trade-off:** because this is self-reported rather than authenticated, a student *could* type another student's email and act "as" them. This mirrors an explicitly accepted gap in the reference app (§7.3.1 there) rather than a new risk — call it out to the class if it matters for your grading model.
* Sees only `student.html`, scoped to the feature set the teacher currently has enabled (§6.7, §6.8), and only their own purchase/credit data — never another student's.

#### 4.2 Teacher / Instructor
* **Access route:** `.../exec?role=teacher` serves `teacher.html` to anyone (page-serving is not the security boundary — see §3, §7). Every action that reads or changes settings, or wipes data, requires the current **teacher password**, checked server-side; the page is inert without it.
* Controls the Level, the Induced Bugs section, and all other toggles in §6.7–§6.9, and can trigger a full data reset.

---

### 5. Data Model

Google Sheet tabs (no `Teachers` allowlist tab — see §7 for why teacher auth uses a password instead):

#### 5.1 `Purchases`
One row per phone bought (kept even after return, for history/debugging).

| Field | Type | Notes |
|---|---|---|
| PurchaseID | String | Unique per row (e.g. UUID or row number). |
| StudentEmail | String | Self-reported, as submitted with the Buy request. |
| PurchaseSeq | Integer | This student's purchase counter — 1 for their first purchase ever, 2 for their second, etc. Used to build their discount code. |
| Model / Storage / Color / Network / Accessory | String | The bought configuration. Blank for any component omitted under the partial-configuration bug (§6.8). |
| BasePrice | Number | Sum of the *selected* components' prices at time of purchase (0 for any left unselected). |
| DiscountCodeUsed | String | Blank if none applied. |
| PaidPrice | Number | BasePrice minus 15% if a valid discount code was applied; equals BasePrice otherwise. This is the figure store credit is based on when `creditBasis = paid` (§6.6) — i.e. *before* any store credit is deducted. |
| CreditApplied | Number | Store credit consumed at purchase time (Level 4). |
| RequestedPayment | Number | PaidPrice − CreditApplied, floored at 0. |
| CodeGenerated | String | The new discount code generated by this purchase, if any (Level 2+). |
| Status | String | `Bought` / `Returned`. |
| Timestamp | Date | |

#### 5.2 `DiscountCodes`
One row per generated code.

| Field | Type | Notes |
|---|---|---|
| Code | String | 7 chars: 5-char email-prefix + 2-digit sequence (§6.4). |
| StudentEmail | String | Owner. |
| GeneratedByPurchaseID | String | FK into `Purchases`. |
| Status | String | `Active` / `Redeemed` (Level 3+, single-use) / `Disabled` (its purchase was returned). |
| CreatedAt | Date | |

#### 5.3 `StoreCredit`
One row per student.

| Field | Type | Notes |
|---|---|---|
| StudentEmail | String | Unique key. |
| Balance | Number | Accumulative; increased on a store-credit return, decreased when auto-applied to a purchase. |

#### 5.4 Teacher settings (Script Properties, single JSON object)
```json
{
  "level": 1,
  "requiredEmailDomain": "",             // "" = any email format accepted; e.g. "post.jce.ac.il" to restrict
  "studentResetEnabled": false,
  "bugs": {
    "discountCodeMode": "normal",        // "normal" | "acceptAny" | "acceptNone"
    "allowBuyWithPartialConfig": false,
    "returnStaysAvailableWhenEmpty": false,
    "creditBasis": "paid",               // "paid" (correct) | "base" (bug)
    "allowDiscountCodeReuse": false      // false (correct: single-use, invalidated on return) | true (bug)
  }
}
```

`requiredEmailDomain` is teacher-configurable at any time (§4.1): blank accepts any email-shaped string; set to e.g. `post.jce.ac.il` to require that suffix.

`creditBasis` decides what a returned phone's store credit is based on (§6.6, §6.8): `paid` (correct, default) = what the student actually paid after the 15% discount; `base` (induced bug) = the phone's original component-sum price, ignoring any discount used at purchase — this lets a student buy at a discount and get back more credit than they paid, a real arbitrage exploit.

#### 5.5 `ActionLog`
One row per button-press action, success or failure — see §6.11 for the full column list and the performance approach behind how it's written.

---

### 6. Functional Requirements

#### 6.1 Parameter fields (student.html)
* Model, Storage, Color, Network, Accessory are all **dropdowns** (`<select>`) populated from §2 — no free text, no invalid values possible. Each starts with no value selected (a blank/placeholder option, e.g. `-- select --`), and can be reset back to that blank option by the student at any time.
* **Discount code** is the only free-text field, max length 7 characters (matches the valid code length).

#### 6.2 Calculate Price
* A **Calculate Price** button is always enabled ("alive all the time") — it can be clicked regardless of how many of the 5 parameters currently have a value, and never mutates any stored data (no purchase, no code redemption).
* Base price = sum of the price of each parameter that currently has a value; any parameter left unselected contributes **0**.
* If a discount code is entered, it's evaluated using the same rules as Buy (§6.4): a non-empty, invalid code shows **"Unknown code"** (0% discount, calculation still proceeds); a valid code applies the 15% discount. (Relevant from Level 2 up — the discount field doesn't exist at Level 1.)
* Level 1: shows just **Total Price**.
* Level 4: also auto-applies the student's current store credit, using the same mechanics as Buy (§6.5), and shows **Phone price**, **Applied credit**, **Requested payment** — exactly the breakdown Buy would produce, just without recording anything.
* **Where the computation happens (revised for performance — see §3):** when no discount code is entered and the level is below 4, the base price is computed **instantly, client-side**, using the same component price table the server uses — no round trip, no wait. A server call only happens when server-held data is actually needed: a discount code (its validity lives in `DiscountCodes`) or Level 4 (credit lives in `StoreCredit`). Buy is unaffected either way — it always independently recomputes everything server-side regardless of what Calculate Price displayed, so this doesn't weaken purchase integrity (§7).

#### 6.3 Buy button enablement
* **Buy** starts disabled. Two independent conditions must both hold for it to be enabled:
  1. All 5 parameter dropdowns have a real (non-blank) value — **unless** the "Enable Buy for partial configuration" bug is active (§6.8), in which case, once this condition has been met at least once, a field going blank again no longer breaks it.
  2. **Calculate Price has been run for the *current* inputs.** Changing any parameter dropdown or the discount code re-disables Buy, even if the change is reverted back to a previously-calculated value — Calculate Price must be clicked again regardless. Clicking **Buy itself does not** re-disable it, so repeated Buy clicks against an already-calculated configuration are allowed (e.g. buying several identical phones in a row, or buying again right after changing nothing) — see §6.10 for how each of those purchases is displayed.

#### 6.4 Discount codes (Level 2+)
* **Validity rule:** exactly 7 characters, and — depending on the `discountCodeMode` bug setting (§6.8):
  * `normal` (default): must exist in `DiscountCodes` for *this* student (by self-reported email). Given a code that exists, its `Status` decides the outcome (default behavior — see the `allowDiscountCodeReuse` bug in §6.8 for the override):
    * `Active` → valid, 15% discount applies.
    * `Redeemed` (already used once) → invalid, shows **"This code was already used"**.
    * `Disabled` (the purchase that generated it was returned, §6.6) → invalid, shows **"Invalid code. The phone that got you this code was returned."**
  * `acceptAny`: any 7-character string is treated as valid, regardless of whether it was ever generated (and regardless of the `allowDiscountCodeReuse` bug — this mode doesn't consult stored codes at all).
  * `acceptNone`: no code is ever accepted, even a genuinely valid one — discount is always 0%.
* A valid code gives a flat **15% discount** off the base price.
* A non-empty code that doesn't exist at all for this student (typo, wrong student, never generated) shows the generic **"Unknown code"** — only a code that *does* exist gets one of the two specific messages above.
* **Single-use is the default from Level 2 up** (not Level-3-gated — see the Level table, §6.7): a code is marked `Redeemed` the moment it's successfully used on a Buy, regardless of level. The `allowDiscountCodeReuse` induced bug (§6.8) is what makes codes reusable, replacing what earlier drafts of this spec tied to Level.
* **Code generation (on Buy):** first 5 characters of the student's email, taken before the `@`, as-is (no case change), right-padded with the literal character `Z` if shorter than 5, followed by a 2-digit zero-padded sequence number equal to that student's purchase count so far (`01`, `02`, …). Example: `michael.stahl@gmail.com` → prefix `micha`; 3rd purchase → code `micha03`.
* **A purchase that itself used a valid discount code generates no new code** — handing out a fresh code every time one was just spent would be equivalent to letting the same code be applied repeatedly. The student instead sees **"No discount codes for discounted purchases"** where a new code would otherwise appear. A purchase made with *no* code (or an invalid one, 0% discount) still generates a code as normal.
* **N identical phones, one returned:** if a student has bought the same configuration more than once (so has N still-active discount codes, one per purchase), returning one of them disables the **oldest still-`Bought`** matching purchase's code — i.e. the first one chronologically, not an arbitrary one — following naturally from Return (§6.6) always matching the earliest eligible purchase.

#### 6.5 Buy Now (all levels)
Server-side, using the self-reported `email` parameter as identity (required on every call):
1. Recompute base price from the submitted configuration (server is authoritative — never trusts a client-submitted price). Under the partial-configuration bug, missing components simply contribute 0.
2. Resolve discount per §6.4; compute paid price.
3. (Level 4) Auto-apply the student's current store credit, mandatorily (not optional): deduct from `RequestedPayment` in full if the balance covers it, otherwise partially (down to 0); reduce `StoreCredit.Balance` by exactly the amount applied.
4. Record the purchase in `Purchases`.
5. (Level 2+, and only if no valid discount code was used on this purchase) Generate and store a new discount code for this student.
6. Return the price breakdown, any newly generated code, and (Level 4) the updated store-credit balance to the page.

#### 6.6 Return, Refund / Store Credit (Level 4 only)
* A **Return** button plus two radio buttons, **Refund** and **Store credit**.
* Disabled until the student has bought at least one phone (lifetime, not "currently holds one") — see the toggle below for what happens once their bought list later becomes empty again.
* On click, the server checks whether the *currently selected* field values match one of this student's purchases with `Status = Bought`:
  * **No match:** show `"Return action failed. The stated configuration does not match a phone you bought."`
  * **Match:**
    * Show `"The phone can be returned"`.
    * Set that purchase's `Status = Returned`.
    * Disable the discount code generated by that purchase (`Status = Disabled` in `DiscountCodes`), even if it was never used — a later attempt to use it reads as invalid.
    * If **Refund** selected: show `"Refund will be completed within 5 business days"` (no credit change).
    * If **Store credit** selected: add an amount to the student's `StoreCredit.Balance` (accumulative across multiple returns) and show `"Your store credit is now $X"`. The amount is that purchase's **PaidPrice** — base price minus discount if one was applied, *before* any store credit that was applied at that purchase — unless the `creditBasis` induced bug (§6.8) is set to `base`, in which case it's the phone's **BasePrice** instead, ignoring any discount that was used.
* **Default behavior:** once a student's Return button has been enabled by their first purchase, it becomes disabled again once their bought list is empty (button greyed out/hidden, matching its pre-first-purchase state). The "Return stays available when empty" induced bug (§6.8) overrides this — see there.

#### 6.7 Levels (teacher.html)

A single **Level** selector, 1–4, each building on the previous:

| Level | Adds |
|---|---|
| **1** | Parameter dropdowns, Calculate Price → Total Price, Buy button only. No discount field, no return, no credit. |
| **2** | + Discount code field/validation. First purchase by a student is necessarily unvalidated (no code exists yet, unless the `acceptAny` bug is set). Buy generates a code, single-use by default (§6.4). |
| **3** | Same as 2, + full purchase tracking. *(Single-use enforcement used to be this level's distinguishing feature; it's now a Level-2+ default controlled by the `allowDiscountCodeReuse` bug instead — see the note after this table.)* |
| **4** | Same as 3, + Return/Refund/Store-credit functionality (§6.6), which is also what makes a discount code `Disabled`-able in the first place. |

Lowering the Level does **not** delete any recorded data — it only hides/disables the corresponding UI and validation.

**Note on Levels 2 vs 3:** since single-use enforcement moved to a bug toggle (§6.4, §6.8) rather than being Level-3-exclusive, Levels 2 and 3 are now functionally identical for discount codes in the current implementation — "full purchase tracking" was never actually a separate functional gate (purchases are recorded at every level regardless), so nothing currently distinguishes 2 from 3 beyond the label. Flag if you'd like a real distinguishing behavior added at Level 3, or if that's fine as-is.

#### 6.8 Induced Bugs (teacher.html)

A dedicated section of deliberately-breakable behaviors, toggleable on the fly, independent of Level (each is only *observable* once its related feature is reached, but can be pre-armed at any time):

| Bug | Effect when ON |
|---|---|
| **Accept any discount code** | Any 7-character string in the discount field is treated as a valid code (15% off), whether or not it was ever generated. (Relevant from Level 2 up.) |
| **Never accept discount codes** | No code is ever accepted, even a genuinely correct one — discount is always 0%. (Relevant from Level 2 up. Mutually exclusive with the bug above — only one `discountCodeMode` can be active; selecting one clears the other, `normal` being the default with neither on.) |
| **Enable Buy for partial configuration** | Buy stays enabled even after a fully-configured phone has one of its 5 parameters reselected back to blank (§6.3), overriding the normal rule that a partial configuration can't be bought. Clicking Buy in that state does not error: it proceeds as if a partially-configured phone can be bought, with the missing component(s) contributing 0 to the price and stored blank on the purchase record. |
| **Return stays available when empty** | Once a student's Return button has been enabled by their first purchase, it never goes back to disabled — even after every purchase has been returned. Clicking it with nothing left to return falls into the ordinary "no match" branch (§6.6) and shows the same `"Return action failed..."` error, rather than the button being greyed out/hidden as it normally would be. |
| **Store credit based on base price** (`creditBasis = base`) | A store-credit return pays out the phone's original, undiscounted price instead of what the student actually paid (§6.6). This lets a student buy at a 15% discount, return it for store credit, and net more credit than they spent — a real pricing exploit, not just a cosmetic difference. |
| **Allow discount code reuse** | A code stays valid indefinitely: neither using it once (§6.4, normally → `Redeemed`) nor its originating purchase being returned (normally → `Disabled`) ever invalidates it. Default (off) enforces both: a used code shows **"This code was already used"**; a code whose phone was returned shows **"Invalid code. The phone that got you this code was returned."** Has no effect when `discountCodeMode` is `acceptAny`/`acceptNone`, since those modes don't consult stored codes at all. |

*(`studentResetEnabled` (§6.9) remains a legitimate configuration choice about how the store behaves, not deliberately broken behavior, so it's kept out of this section.)*

**Implementation note:** every bug flag above is enforced server-side and only ever observable through the *outcome* of an action (a code being accepted/rejected, a credit amount, a return message) — except `allowBuyWithPartialConfig`, which the client must know in order to render the Buy button's live enabled/disabled state (§6.3) correctly; that one flag alone is exposed via the public UI-config call. No other bug flag is exposed to the client.

Settings changes (Level, bugs, or other toggles) take effect immediately for all students on their next action — there's no push channel in GAS, but none is needed here since there's no live timer; each Calculate/Buy/Return simply reads current settings fresh.

#### 6.9 Reset controls
* **Teacher — "Reset simulator data"**: wipes *all* students' purchases, discount codes, credit balances, and the action log (§5.5, §6.11). Double-confirmation (confirm dialog + typing `RESET`), mirroring the reference app.
* **Student — "Reset" button**: visible on `student.html` only when `studentResetEnabled` is on (teacher-controlled, independent of Level). Clears **only the calling student's own** data (their purchases, their codes, their credit, their purchase counter back to 0), scoped server-side by the self-reported `email` parameter. Note this inherits the same accepted trade-off as §4.1: a student could in principle reset another student's data by submitting that student's email. Also clears the on-screen purchase history list (§6.10) and re-disables Buy until Calculate Price is run again.

#### 6.10 Purchase confirmation & history (all levels)
* On a successful Buy, the page shows a confirmation message in this exact template (values substituted from the *actual recorded purchase*, not just whatever was on-screen):

  > Congratulations! You are now the owner of a `<Network>` `<Color>` `<Model>` with `<Storage>`[ and [a] `<Accessory>`]

  * The trailing `and ... <Accessory>` clause is **omitted entirely** when Accessory is `None`.
  * The article before the accessory is `a` for **Case** and **Charger**; no article at all before **Earbuds** (a plural noun — "and Earbuds", not "and a Earbuds").
  * Shown at every level, not just Level 1 — at Level 1 it's the *only* success feedback there is; at higher levels it supplements the numeric price/code/credit breakdown that's already shown.
* Each successful Buy **appends** this message to a running, on-screen **purchase history list** rather than replacing the previous one — repeated Buy clicks (§6.3) or buying under a changed configuration both add to the same list. The list scrolls (rather than growing the page indefinitely) once it's tall enough to need it.
* The history list is client-side, per page load — it is not reconstructed from server history if the page is reloaded (out of scope; the server remains the source of truth for actual purchase records regardless of what's currently displayed).

#### 6.11 Action logging (all levels)

Every button-press action a student takes — **Calculate Price, Buy, Return, Reset** (setting a dropdown/text value is not itself logged, only pressing a button is) — is appended as one row to a dedicated `ActionLog` sheet (§5.5), whether it succeeds or fails.

| Column | Content |
|---|---|
| Timestamp | Server time of the action. |
| StudentEmail | Self-reported email for this action. |
| Action | `CalculatePrice` / `Buy` / `Return` / `Reset`. |
| Parameters | The 5 configuration values, `\|`-joined, in Model\|Storage\|Color\|Network\|Accessory order (blank for any unset — including under the partial-config bug). |
| DiscountCode | The code text entered, if any. |
| CalculatedPrice | The resulting monetary figure for that action (Total/Requested Payment for Calculate and Buy; the credit amount added for a Store-credit Return; blank for a Refund Return or a Reset). |
| CreditBefore / CreditAfter | Store credit balance immediately before and after the action (Level 4 actions only — populated for Buy, Return, and Reset; a Reset sets CreditAfter to 0). |
| Result *(addition beyond the original ask)* | `Success` / `Failed` (a legitimate business-rule failure, e.g. no matching purchase to return) / `Error` (invalid input, e.g. bad email). Included so the log is useful for reviewing failed-attempt testing, not just successful transactions. |
| Message *(addition)* | The error/failure message, when applicable. |

**Performance approach (see also §3):** logging never blocks or slows down another student's action. It's appended **without** taking the `LockService` lock that protects Purchases/StoreCredit correctness (an append-only audit row doesn't need read-modify-write protection the way a balance update does), and for Buy/Return/Reset it's written *after* that lock is released — so one student's log write never makes another student wait. For Calculate Price specifically, when the price was computed instantly client-side (§6.2, the common case), the logging call is fired to the server **without the client waiting for it** ("fire-and-forget" — Apps Script has no true background job queue, so this client-side "don't await the response" pattern is the closest equivalent available, and needs no additional infrastructure). A logging failure of any kind is swallowed server-side and never surfaces as an error to the student — logging is best-effort and must never block or break the action it's recording.

---

### 7. Security Model

Adapted from the approach used in the referenced classroom-polling app (`10 Combinatorial testing Google Web App requirements.md`, §7), with one deliberate deviation explained below.

* **Why not the reference app's identity-allowlist approach:** that app's teacher gate relies on `Session.getActiveUser()`, which only reliably resolves when the deployment requires a signed-in Google account. This app is deployed fully anonymous (§3) specifically so students never need to log in — under that setting, `Session.getActiveUser()` cannot reliably identify anyone, teacher included. So instead of a `Teachers` allowlist sheet, teacher actions are gated by a **shared password** (§4.2), stored in Script Properties and checked inside every teacher-only function.
* **`doGet` page-serving is not the security boundary**, exactly as the reference app itself states (its §7 intro): `?role=teacher` serves `teacher.html` to anyone, unconditionally. The real gate is server-side, inside the functions themselves.
* **Server-side re-check on every privileged function:** `teacherGetSettings`, `teacherUpdateSettings`, `teacherResetAll`, and `changeTeacherPassword` all independently re-verify the password — the client-side "unlock" in `teacher.html` is UX only, never trusted as the actual boundary (Apps Script exposes every top-level server function globally via `google.script.run`, regardless of which page called it).
* **Student identity is self-reported by design** (§4.1) — a deliberate, explicit trade-off (matching the reference app's own accepted gap) made to keep both ChromeDriver and HTTP-level testing simple and login-free for students. It is validated for shape (and optionally domain), never for ownership.
* **Server is authoritative for price/discount/credit:** the client only ever submits raw field selections, the discount-code text, and the email; base price, discount validity, credit balance, and match/no-match on Return are always recomputed server-side from stored records — never trusted from the client.
* **Bug toggles are resolved server-side** from current teacher settings — a student cannot force a discount, or a partial-configuration purchase, via client-side tampering; the server enforces whatever `discountCodeMode`/`allowBuyWithPartialConfig` is currently set, regardless of what the page's own JS does.

---

### 8. Test Automation Support

* **ChromeDriver/Selenium:** every field, button, and result element gets a stable `id` (e.g. `#student-email`, `#model-select`, `#discount-code`, `#calc-price-btn`, `#total-price`, `#buy-btn`, `#generated-code`, `#store-credit-balance`, `#return-btn`, `#return-message`). The `/exec` URL still redirects to a sandboxed `googleusercontent.com` domain — Selenium needs to wait for that redirect before locating elements — but since no Google login is required for students, this no longer needs an authenticated test account.
* **"Under the UI" HTTP testing:** `doGet`/`doPost` implement a small JSON API alongside the HTML pages, selected by an `action` query/body parameter (`getUiConfig`, `calculate`, `getStudentStatus` — GET or POST; `buy`, `return`, `resetStudent`, `teacherGetSettings`, `teacherUpdateSettings`, `teacherResetAll` — POST for anything mutating), taking the same field names the UI submits (`email`, `model`, `storage`, `color`, `network`, `accessory`, `discountCode`, `refundType`) and returning `{ ok, data }` or `{ ok: false, error }` as JSON. See `requests.http` in the project folder for a worked example of every action. Since this is a coding-focused exercise, the supported tools are:
  * **curl** (in a shell script) — fully supported.
  * **VS Code REST Client extension** (`.http` files) — a lightweight, code-based alternative that stays in the same editor as the ChromeDriver code: requests are plain text, version-controllable, and can use variables (e.g. `@email = student@example.com`) so it's supplied once and reused across requests. No GUI tool (e.g. Postman) is used, since the exercise is meant to have students write the requests themselves.

---

### 9. Open Items Requiring Your Decision

None remaining — all prior open items have been resolved in this revision.

---

*Please review and approve (or correct) before implementation begins.*
