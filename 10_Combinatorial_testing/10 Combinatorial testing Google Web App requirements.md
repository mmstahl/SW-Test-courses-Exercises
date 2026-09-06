# System Requirements Specification (SRS)

## Interactive Classroom Polling & Submission System

*Reflects the deployed application as of 2026-09-03.*

### 1. Overview & Purpose

This Google Apps Script (GAS) web application provides a real-time, interactive classroom assessment tool for course instructors. It enables an instructor to present dynamic questions during a live lecture, receive student responses in real time, apply automatic scoring with speed bonuses (including partial-credit scoring for combinatorial test-suite questions and flat per-bug rewards, net of a per-test-run cost, for black-box price-testing questions), render live leaderboard rankings, present customized post-question digestion analytics, and reveal each question's answer key — to the instructor only — once the question closes.

---

### 2. System Architecture & Tech Stack

* **Platform:** Google Apps Script (GAS)
* **Database & Storage:** Google Sheets (Spreadsheet container) & Script Properties API
* **Frontend:** HTML5, CSS3, JavaScript (ES6) served via `HtmlService`
* **Media:** Optional per-question images, sourced from Google Drive (embedded server-side as base64 `data:` URIs — no public sharing or external hosting required) or from any external image URL
* **Concurrency Control:** Apps Script `LockService` to prevent race conditions during simultaneous class-wide submissions
* **Authentication & Domain Isolation:** Restricted strictly to students with valid institutional `@post.jce.ac.il` email addresses, enforced both client-side (immediate UI feedback) and server-side (authoritative check inside `submitAnswers` and `runPriceTest`)
* **OAuth Scopes:** `spreadsheets.currentonly` (read/write the Questions and Responses sheets) and `drive.readonly` (read image files referenced from the Questions sheet). Adding the Drive scope requires the script owner to complete a one-time authorization (Apps Script editor → run any function → "Review permissions" → Allow) before Drive-sourced images will resolve; this is a one-time grant tied to the owner's account, not something students or repeat lessons ever trigger.
* **Optional-column convention:** several `Questions` sheet columns (`Image`, `Testcase Cost`, `Bugs Definition` — see §4.1) are located by matching their header row text, case-insensitively and whitespace-trimmed, rather than by a fixed column letter. They can be added in any position, in any order, without a code change.
* **Performance note:** per-question images and (for `TABLE_PRICED`) bug/price computation are deliberately kept out of the functions polled every second by every connected client (`getQuestions`, `getSessionState`). Images are fetched on demand, once per question activation, via a separate call (`getQuestionImage`); "Run Test" calls do not write to the spreadsheet at all (§5.1.5), so they hold no lock and cannot contend with other students' requests.

---

### 3. User Roles & Access Control

#### 3.1 Student

* **Access Route:** Base Web App URL (`.../exec`)
* **Privileges & Validation:**
  * Must authenticate via an Azrieli email address (`@post.jce.ac.il`).
  * Non-Azrieli emails trigger an immediate error: `"You must enter your Azrieli email address!"`. This is validated both in the browser and again on the server before any response is recorded.
  * Receive active question prompts via a 1-second client poll of session state (`getSessionState`) — there is no server push channel in Apps Script, so "dynamic" delivery is polling-based.
  * Submit responses: numeric-only inputs for `NUMERIC` QuestionType, free text for `TEXT` QuestionType, multi-row tabular grid entries for `TABLE`/`TABLE_SCORED` QuestionTypes, or the dual-table interface for `TABLE_PRICED` QuestionType (see §5.1.5) — within the designated time limit.
  * Support pasting multiple data rows directly from Microsoft Excel into `TABLE`/`TABLE_SCORED`/`TABLE_PRICED` grid inputs.
  * Receive pass/fail (or partial-pass) feedback and points earned — but **never the answer key itself**. For every question type this feedback is deliberately deferred until the question closes (see §5.5); only `TABLE_PRICED`'s ungraded price-calculator table gives live per-row feedback, since that table is a personal exploration tool, not the graded answer.
  * Pressing **Enter** in a NUMERIC, TEXT, or `TABLE_PRICED` Expected-Price field submits the response, exactly like clicking **Submit Response**. Enter is ignored inside `TABLE`/`TABLE_SCORED`/`TABLE_PRICED` grid cells (so it doesn't interfere with row-by-row/paste data entry).
  * The **Submit Response** button starts disabled and only becomes enabled once the minimum required input has been provided (see §5.1).
  * At most one **graded** submission is accepted per student per question; a second attempt is rejected server-side. `TABLE_PRICED`'s price-calculator "Run Test" activity is not a submission at all — it never touches the `Responses` sheet (see §5.1.5) — so it is entirely unaffected by, and does not count toward, this limit.
  * While a question is `ACTIVE`, an optional illustrative image (if configured for that question) is displayed above the question prompt; it disappears the moment the question closes (see §5.6).

#### 3.2 Teacher / Instructor

* **Access Route:** Web App URL with parameter (`.../exec?role=teacher`), **and** the visiting Google account must be listed on the `Teachers` sheet allowlist — see §7.2. Anyone else requesting this URL transparently receives the ordinary Student Portal instead.
* **Privileges & Controls:**
  * Launch a specific question, selected from a drop-down menu that shows the ID and question text of every question in the `Questions` sheet, with a configurable duration (seconds) pre-filled from that question's `TimeLimitSec` and editable before launch.
  * Advance using the **"Next Challenge"** button, which launches the next sequential question (by array order in the sheet) automatically, using that question's own `TimeLimitSec`. Grayed out when on the final question.
  * **"Add 1 Min"** button: extends the currently active question's remaining time by 60 seconds. Disabled unless a question is currently `ACTIVE`. Every connected student's countdown reflects the extension on their next poll tick automatically — no separate notification mechanism is needed.
  * Launching a `TABLE_PRICED` question (via **Start Question** or **Next Challenge**) is validated first: if that question's `Bugs Definition` cell is blank, missing, or not valid JSON, the question is refused and an explanatory alert is shown instead — it never goes live in a broken state (see §5.2.5).
  * Monitor real-time student submission counts (`Response Count`) while a question is active.
  * Manually stop a question session (**"Stop Question"**), or allow it to auto-expire via its countdown timer.
  * View real-time digestion analytics (bar-chart histograms, question-type-specific) **and** the question's answer key, both only **after** the question session closes. The answer key is never sent to students at any point — this is the only place it's ever displayed (see §5.3.3a).
  * Track real-time leaderboards displaying **Top 10 (Current Question)** and **Top 10 Overall**, shown by student display name (the local part of their email, before `@`) rather than full email address. When the current question is `TABLE_PRICED`, the **Top 10 (Current Question)** table also shows each student's **Bugs Found** and **Tests Run** totals (see §5.3.4).
  * **"Reset for New Class"**: a double-confirmation control (a confirm dialog, followed by typing `RESET` in a prompt) that clears the session state and deletes all rows from the `Responses` sheet, ready for a new class session.
  * See the same optional per-question illustrative image as students, shown while that question is `ACTIVE` (see §5.6).

---

### 4. Data Models & Google Sheet Schema

#### 4.1 `Questions` Sheet Schema

Stores the predefined question bank. Columns A–H are fixed-position; `Image`, `Testcase Cost`, and `Bugs Definition` are optional and located by header text instead (see §2).

| Col | Field Name | Type | Description |
| --- | --- | --- | --- |
| **A** | `QuestionID` | String / Int | Unique identifier for the question (e.g., `1`, `2`, `3`, `4`, `5`, `6`). |
| **B** | `QuestionText` | String | Plain-text prompt displayed to students. |
| **C** | `AcceptableAnswers` | String / JSON | Format depends on `QuestionType` — see below. |
| **D** | `TimeLimitSec` | Integer | Allowed duration for the question in seconds. |
| **E** | `MinAnswersRequired` | Integer | Minimum number of valid/filled inputs required. For `TABLE`/`TABLE_SCORED`/`TABLE_PRICED`'s price-calculator table, this is also how many initial grid rows are rendered, and those initial rows cannot be deleted by the student. (`TABLE_PRICED`'s graded bug-report table is a fixed size and ignores this column — see §5.1.5.) |
| **F** | `MaxAnswersAllowed` | Integer | Maximum number of allowed input fields/table rows (price-calculator table only, for `TABLE_PRICED`). E.g. Q5 allows a smaller number of price-calculator rows; Q6 sets this to `80`. |
| **G** | `QuestionType` | String | Interface & scoring mode: `TEXT`, `NUMERIC`, `TABLE`, `TABLE_SCORED`, or `TABLE_PRICED`. Defaults to `TEXT` if blank. |
| **H** | `BaseScore` | Integer | Base point value (Default: `100`). Meaning depends on type — see §5.2. |
| *(by header: `Image`)* *(optional)* | `Image` | String / Formula / In-cell image | An illustrative image shown on both screens only while this question is `ACTIVE`. See §5.6 for accepted formats. Located by matching a column header of `Image`; if no such header exists, falls back to column I for sheets configured before this became header-driven. |
| *(by header: `Testcase Cost`)* *(optional, `TABLE_PRICED` only)* | `Testcase Cost` | Integer | Per-test-run score deduction (§5.2.5): the final score for a `TABLE_PRICED` submission is reduced by `Testcase Cost × TestsRun`, floored at `0`. Blank or absent → `0` (no deduction). Ignored for other `QuestionType`s. |
| *(by header: `Bugs Definition`)* *(required for `TABLE_PRICED`)* | `Bugs Definition` | String / JSON array | That question's own bug list, replacing any other `TABLE_PRICED` question's bugs — see §5.2.5 for the full format. A `TABLE_PRICED` question with this cell blank, missing, or not valid JSON cannot be launched (§3.2); a question with no bugs at all must say so explicitly with `[]`. |

`AcceptableAnswers` format by `QuestionType`:

* **`NUMERIC` / `TEXT`:** a semicolon-separated string of valid values, e.g. `5;10;15`.
* **`TABLE`:** a JSON object mapping each of the 5 fixed column headers to an array of required values for that column, e.g. `{"Model":["iPhone 15","iPhone 15 Pro"],"Storage":["128GB","256GB"], ...}`.
* **`TABLE_SCORED`:** a JSON array of complete, exact row objects — the full set of valid combinations — e.g. `[{"Model":"Pixel 9","Storage":"128GB","Color":"Black","Network":"5G","Accessory":"None"}, ...]`.
* **`TABLE_PRICED`:** a JSON object with a `priceTable` field mapping each of the 5 fixed headers to a `{value: price}` lookup, e.g. `{"priceTable":{"Model":{"Pixel 9":900,"Pixel 9 Pro":1050},"Storage":{"128GB":0,"256GB":56}, ...}}`. This lookup drives both the price-calculator table's computed price and the dropdown options offered in the graded answer table (plus a literal `"Any"` option, added automatically). `AcceptableAnswers` holds **only** the price table — the question's bugs live in the separate `Bugs Definition` column (see §4.1, §5.2.5), so two `TABLE_PRICED` questions (e.g. Q5 and Q6) can share the same price table but define entirely different bugs, or vice versa.

#### 4.2 `Responses` Sheet Schema

Stores one row per **graded** submission, appended atomically. Every row's `SubmittedData` is JSON — there is no other kind of row. (`TABLE_PRICED`'s price-calculator "Run Test" activity, §5.1.5, is never written to this sheet at all; it exists only transiently on the student's own page until they submit the graded table.)

| Col | Field Name | Type | Description |
| --- | --- | --- | --- |
| **A** | `Timestamp` | Date | Server timestamp of the submission. |
| **B** | `StudentEmail` | String | Lower-case, validated Azrieli email (`@post.jce.ac.il`). |
| **C** | `QuestionID` | String | Target question ID. |
| **D** | `SubmittedData` | String (JSON) | JSON array of submitted text/number inputs or row objects. |
| **E** | `IsCorrect` | Boolean | Pass/fail per §5.2. |
| **F** | `Score` | Integer | Final score per §5.2. |
| **G** | `MissingCount` | Integer | `TABLE`: required column values never covered. `TABLE_SCORED`: required row combinations never covered. Unused (`0`) for `NUMERIC`/`TEXT` and for `TABLE_PRICED` (superseded by the explicit `BugsFound` column below). |
| **H** | `BugsFound` | Integer | `TABLE_PRICED` only: how many of that question's bugs were correctly and uniquely reported (§5.2.5). `0` for all other types. |
| **I** | `TestsRun` | Integer | `TABLE_PRICED` only: how many "Run Test" invocations the student made against the price calculator before submitting the graded table — each row processed during "Run All Tests" counts individually, same as an individual "Run Test" click (§5.1.5, §5.2.5). `0` for all other types. |

`Reset for New Class` clears all data rows and rewrites this header row, so the schema stays consistent even if the sheet pre-dates a schema change.

---

### 5. Functional Requirements

#### 5.1 Student Interface & Question Handling

1. **Domain Access Check:** Enforces email validation (`@post.jce.ac.il`) client-side and server-side. If invalid, displays `"You must enter your Azrieli email address!"`.

2. **Numeric Input Mode (`NUMERIC` QuestionType — e.g. Q1 & Q2):**
   * Restricts each input to digits and at most one decimal point (non-digit, non-`.` characters are stripped as the student types).
   * Generates input fields equal to `MinAnswersRequired`.
   * Enforces `MaxAnswersAllowed` (hides **"+ Add Answer"** button once reached).
   * Suppresses the per-row delete (`✕`) button when `MaxAnswersAllowed == 1`.
   * **Submit Response** stays disabled until at least one answer field is non-empty.

3. **Text Input Mode (`TEXT` QuestionType):**
   * Accepts any text up to 256 characters per field.
   * Generates input fields equal to `MinAnswersRequired`.
   * Enforces `MaxAnswersAllowed` (hides **"+ Add Answer"** button once reached).
   * Suppresses the per-row delete (`✕`) button when `MaxAnswersAllowed == 1`.
   * **Submit Response** stays disabled until at least one answer field is non-empty.

4. **Tabular Grid Mode (`TABLE` QuestionType — e.g. Q3; `TABLE_SCORED` QuestionType — e.g. Q4):**
   * Displays a fixed 5-column table in the exact required order: `Model`, `Storage`, `Color`, `Network`, `Accessory`.
   * Starts with exactly `MinAnswersRequired` rows; these initial rows cannot be deleted by the student.
   * Additional rows (added via **"+ Add Row"** or created automatically while pasting) can be added up to `MaxAnswersAllowed`, and can be deleted individually.
   * Strictly enforces `MaxAnswersAllowed` on table rows (prevents adding or pasting beyond this limit).
   * Supports Clipboard Excel Paste: parses tab-delimited (`\t`) and newline-delimited (`\n`) clipboard data across rows and columns, automatically creating new rows as needed (up to `MaxAnswersAllowed`) so pasting a full block of rows fills the grid in one action.
   * Requires every cell in a submitted (non-empty) row to be filled prior to submission.
   * **Submit Response** stays disabled until every one of the initial `MinAnswersRequired` (locked) rows has all 5 cells filled. Optional rows beyond that do not gate the button.
   * Pressing Enter inside a grid cell does nothing (does not submit).

5. **Dual-Table Mode (`TABLE_PRICED` QuestionType — e.g. Q5, Q6):** a black-box testing exercise with two independent tables on one question. Any number of `TABLE_PRICED` questions may exist side by side, each with its own price table and its own, independently configured set of bugs (§5.2.5) — Q5 and Q6 need not share either.
   * **Price Calculator table (ungraded, "explore freely")** — labeled as not graded:
     * Same 5 fixed columns as `TABLE`/`TABLE_SCORED`, plus three extra columns: **Expected Price** (free-text — the student's own prediction), **Price** (read-only, filled in by the server), and **Result** (read-only, `Pass`/`Fail`).
     * Starts with `MinAnswersRequired` locked rows (cannot be deleted); additional rows up to `MaxAnswersAllowed` can be added or pasted in, same mechanics as §5.1.4 (e.g. up to 80 for Q6).
     * **"▶ Run Test"** (per row) or **"▶ Run All Tests"** (whole grid) sends that row's 5 field values plus the student's Expected Price to the server, which computes the actual price (see §5.2.5) and returns it immediately. The row is colored green (`Pass`) if the actual price matches the student's Expected Price exactly (case-insensitive text comparison — this also covers the "error message"/literal-text and "no price shown" outcomes), or red (`Fail`) otherwise. This is the **only** immediate, non-deferred feedback anywhere in the app, since it's the student's own private exploration tool, not the graded answer.
     * Running a test is a pure, stateless computation — it is **not** logged as a `Responses` row and does not count toward, or interact with, the one-submission-per-question rule. It is, however, **counted**: the browser tallies every "Run Test" invocation (each row processed by "Run All Tests" counts individually) for the current question, and submits that running total alongside the graded answer as `TestsRun` (§4.2, §5.2.5) — this count is what the per-test cost deduction is based on, so testing is free to repeat but not free of consequence.
   * **"Report the Bugs You Found" table (graded, one-time submission):**
     * Always exactly 3 rows; no adding, removing, or pasting. (Every `TABLE_PRICED` question in this app is expected to define exactly 3 bugs, matching this fixed table size.)
     * Each cell is a dropdown populated from that column's valid values (drawn from the same `priceTable` used by the calculator above) plus a literal `"Any"` option. The student must select a value for every field in every row, including explicitly choosing `"Any"` for a field they judge irrelevant to a given bug — comparison against the answer key is exact on all 5 fields (see §5.2.5).
     * **Submit Response** governs only this table and is always enabled (dropdowns always have a value selected).
     * Subject to the same one-submission-per-student-per-question rule, deferred-reveal, and auto-submit-on-timeout behavior as every other graded question type (§5.4, §5.5).

6. **Countdown Timer:**
   * Displays remaining time formatted as `mm:ss` (e.g., `01:15`).
   * Automatically disables input submission upon timer expiration.
   * If a teacher extends time via **"Add 1 Min"** before a student's countdown reaches zero, the extension is picked up on the student's next poll tick and the countdown continues seamlessly.
   * For `NUMERIC`/`TEXT`/`TABLE` questions, reaching zero without a manual submission shows a local **Fail** result immediately (no data is sent to the server — nothing is recorded for that student/question). This is a purely local, time-management message, not an answer-correctness reveal, so it is not deferred.
   * For `TABLE_SCORED` and `TABLE_PRICED` (graded table) questions, reaching zero without a manual submission triggers an **automatic submission** of whatever is currently in the grid — see §5.5.

7. **Student Feedback (all graded question types, deferred — see §5.5):**
   * **Pass:** Displays submitted answers, `Result: All conditions were met! (Pass)`, and points earned.
   * **Fail:** Displays submitted answers and `Result: So sad! Your answer is incorrect! (Fail)`.
   * **Partial Pass** (`TABLE_SCORED` and `TABLE_PRICED` only): Displays submitted answers, `Result: Partially correct! (Partial Pass)`, and points earned, styled in orange.
   * For `TABLE`/`TABLE_SCORED`/`TABLE_PRICED` (graded table), the submitted answers are shown as a table; for `TABLE_SCORED` and `TABLE_PRICED` specifically, each row is additionally tagged and colored green/"Correct" or red/"Incorrect" based on whether it matched a required, not-yet-counted valid combination or bug signature.
   * None of this feedback — for any type — ever states what the *correct* values were, nor how many "Run Test" calls factored into the score. That's shown only to the teacher, only after the question closes (§5.3.3a).

#### 5.2 Dynamic Validation & Scoring Algorithm (`Code.js`)

1. **`NUMERIC` Type Rules:**
   * Validates that every submitted value is digits-only (with an optional decimal point) and that submission count meets $Min \le Count \le Max$.
   * Matches entries against `AcceptableAnswers` (case-insensitive).
   * **Pass Condition:** all inputs are valid, non-empty, contain no duplicates, count is within bounds, and every value is in `AcceptableAnswers`. Any violation → **Fail**.

2. **`TEXT` Type Rules:**
   * Ensures every value is non-empty and at most 256 characters, and that submission count meets $Min \le Count \le Max$.
   * Matches entries against `AcceptableAnswers` (case-insensitive).
   * **Pass Condition:** same as `NUMERIC` — all valid, no duplicates, count in bounds, every value accepted. Any violation → **Fail**.

3. **`TABLE` Type Rules:**
   * Evaluates the array of row objects against the required column values specified in the `AcceptableAnswers` JSON.
   * Calculates `MissingCount`: the number of required values, across all 5 categories, never covered by any submitted row.
   * Also fails if any submitted cell holds a value that is not in that column's valid list, regardless of `MissingCount`.
   * **Pass Condition:** `MissingCount == 0` **and** every submitted cell value is valid for its column.

4. **`TABLE_SCORED` Type Rules (combinatorial test-suite scoring, e.g. Q4):**
   * `AcceptableAnswers` is a JSON array of the exact valid row combinations (the target test suite).
   * A submitted row is counted **correct** only if it exactly matches one of the valid combinations **and** is the first row in the submission to match that particular combination. Any later row repeating an already-counted combination is a **duplicate** and counts as incorrect.
   * `IncorrectCount` = number of submitted rows that are either not a valid combination, or a duplicate of one already counted.
   * `MissingCount` = number of valid combinations never covered by any submitted row.
   * $$\text{Points} = \text{BaseScore} - 10 \times (\text{IncorrectCount} + \text{MissingCount})$$
   * Tiers scale proportionally to `BaseScore`, preserving a fixed ~47% fail / 100% pass ratio at any `BaseScore` value:
     * `Points < ⌈BaseScore × 61 / 130⌉` → **Fail** — `Score = 0`.
     * `⌈BaseScore × 61 / 130⌉ ≤ Points < BaseScore` → **Partial Pass** — $\text{Score} = \text{Points} + \lfloor \text{Seconds Remaining} / 2 \rfloor$.
     * `Points ≥ BaseScore` → **Pass** — $\text{Score} = \text{BaseScore} + \text{Seconds Remaining}$.
   * At the recommended `BaseScore = 130` (a 13-row combinatorial suite, 10 points per row), this reproduces the original fixed 61/130 thresholds exactly. A submission reaches full credit only by containing exactly the complete set of valid combinations, each exactly once.

5. **`TABLE_PRICED` Type Rules (black-box bug hunting, e.g. Q5, Q6):**

   Each `TABLE_PRICED` question defines its own bugs in its `Bugs Definition` column (§4.1) — a JSON array, in priority order, of:
   ```json
   { "conditions": { "Model": "Any", "Storage": "1TB", "Color": "Any", "Network": "Any", "Accessory": "Any" },
     "effect": { "type": "flat", "value": 100 } }
   ```
   * `conditions` maps some or all of the 5 fixed headers to a required value. Recommended practice is to specify all 5 headers explicitly, using the literal value `"Any"` for a field that doesn't matter to that bug — see the matching rules below for why this matters.
   * `effect.type` is one of:
     * `"flat"` — the price is always `effect.value`, ignoring the price table entirely.
     * `"string"` — the price cell shows the literal text in `effect.value` (e.g. `"Error: Invalid configuration"`, or any other message such as `"Sold out"`).
     * `"null"` — no price is shown for that row at all.
     * `"delta"` — the price is the normally-computed (price-table-sum) price plus `effect.value`, which may be negative; if the normal computation itself errors (e.g. a blank/unmatched cell), that error is shown as-is rather than trying to add to it.
   * A `TABLE_PRICED` question with no bugs at all must set `Bugs Definition` to `[]` explicitly; a blank/missing/invalid `Bugs Definition` instead prevents the question from being launched at all (§3.2).

   * **Price computation** (`computeRowPrice`, used by the price-calculator table only — not scored): the question's bugs are checked in array order, first match wins, using **loose matching** — only the headers a bug's `conditions` actually names are checked, and any header it omits is ignored regardless of that row's concrete value (there is no `"Any"` concept on this table; students always enter concrete values). If no bug matches, the price is the sum of each column's looked-up value from `priceTable`; a blank or unmatched cell makes the row `"Error: Invalid configuration"`.
   * **Bug-report scoring** (`scoreBugReports`, used by the graded 3-row answer table): each submitted row is checked against the same bug list using **strict matching** — all 5 fixed headers must match, and a header a bug's `conditions` omits is treated as requiring the literal value `"Any"`, not as a wildcard. Concretely: a bug whose `conditions` only specifies `Storage = "1TB"` is reported correctly only by a row where Storage is `1TB` **and** every other field is explicitly `Any` — a row with a concrete (non-`"Any"`) value in an unrelated field does not count, even though that field has no bearing on the actual pricing bug, because the student did not correctly identify that it doesn't matter. A row counts as a correctly reported bug only if it exactly matches a bug's signature **and** is the first row in the submission to match that particular bug — a later row repeating an already-claimed bug earns nothing (no penalty either; submissions are one-shot, so there's no retry to protect against).
   * $$\text{RawScore} = \sum_{\text{correctly \& uniquely reported bugs}} (\text{BaseScore} + \text{Seconds Remaining})$$
     (each qualifying row earns its own full time bonus — finding all bugs early nets one bonus per bug.)
   * **Testcase-cost deduction:** $\text{Score} = \max(0,\ \text{RawScore} - \text{Testcase Cost} \times \text{TestsRun})$, where `TestsRun` is the number of "Run Test" invocations the student made against that question's price calculator (§5.1.5, §4.2). A question with no `Testcase Cost` configured (§4.1) has no deduction.
   * **Tier** (for Pass/Partial/Fail display and leaderboard-adjacent `IsCorrect`) is based on `BugsFound` alone, unaffected by the testcase-cost deduction: `bugsFound == (that question's total bug count)` → Pass; `1` up to `total − 1` → Partial Pass; `0` → Fail.
   * Recommended `BaseScore = 100` (matching "100 points per correctly reported bug").

6. **Time-Bonus Scoring Formula — `NUMERIC` / `TEXT` / `TABLE`:**
   * If **Fail**: `Score = 0`.
   * If **Pass**:
     $$\text{Score} = \text{BaseScore} + \lfloor \text{Seconds Remaining at Submission} \rfloor$$

#### 5.3 Teacher Control & Digestion Analytics

1. **Live Question Controls:**
   * **Launch Question:** starts the active timer and opens the question to students. Selected from a drop-down menu showing the ID and text of every question in the `Questions` sheet; the duration field is pre-filled from that question's `TimeLimitSec` but can be overridden before launch. For a `TABLE_PRICED` question, this validates `Bugs Definition` first and refuses to launch (with an explanatory alert) if it's missing or invalid (§3.2, §5.2.5).
   * **Next Challenge:** advances to the next sequential question (by sheet order) and launches it automatically using that question's own `TimeLimitSec`, subject to the same `TABLE_PRICED` validation as above. Disabled when on the last question.
   * **Add 1 Min:** extends the current question's countdown by 60 seconds. Disabled unless a question is currently `ACTIVE`.
   * **Stop Question:** immediately closes the session for the current question; digestion analytics and the answer key for it become available.

2. **Active State Masking:**
   * While a question is active (`ACTIVE` status and timer running), the Teacher view displays **only** the live submission count (`Response Count`), the leaderboards, and the question's illustrative image (if any) — all updating/visible in real time. Digestion analytics and the answer key are hidden until the session is closed.

3. **Question-Specific Digestion Analytics** (available only once the current question's session is closed):
   * **`NUMERIC` / `TEXT`:** a bar-chart histogram of submitted answer values.
   * **`TABLE`:** a bar-chart histogram of `MissingCount` values (`0` missing indicates a PASS; higher values show the distribution of incomplete answers).
   * **`TABLE_SCORED`:** a bar-chart histogram of result tiers — count of **Fail** / **Partial** / **Pass** submissions.
   * **`TABLE_PRICED`:** a bar-chart histogram of **how many of that question's bugs each student correctly and uniquely reported** in their graded submission (`0 bugs found` up to `N bugs found`, where `N` is that question's own bug count from `Bugs Definition`) — read directly from each student's stored `BugsFound` value (§4.2), one entry per student.

3a. **Answer Key Reveal** (available only once the current question's session is closed, alongside digestion): a plain-text "✅ Correct Answer" box, formatted per type:
   * **`NUMERIC` / `TEXT`:** the accepted values, comma-joined.
   * **`TABLE`:** each column's required values, e.g. `Model: iPhone 15, iPhone 15 Pro | Storage: 128GB, 256GB | ...`.
   * **`TABLE_SCORED`:** every valid row combination, one comma-joined row per entry, pipe-separated.
   * **`TABLE_PRICED`:** a description generated from that question's own `Bugs Definition`, one bug per segment, e.g. `Bug 1: Storage = 1TB (all other fields = Any) -> price is set to 100 | Bug 2: Model = Pixel 9 Pro XL AND Color = Blue (all other fields = Any) -> price shows "Error: Invalid configuration" | ...`.
   * This is the **only** place the answer key is ever displayed — it is never sent to, or derivable by, a student at any point.

4. **Leaderboards:**
   * **Top 10 (Current Question):** ranks the top 10 scoring students for the active/last question. When that question is `TABLE_PRICED`, this table also shows each student's **Bugs Found** and **Tests Run** totals alongside their score.
   * **Top 10 Overall:** ranks the top 10 highest cumulative scores across all questions in the session, sorted descending. Never shows Bugs Found/Tests Run, since it spans every question type and those figures are only meaningful for a single `TABLE_PRICED` question.
   * Leaderboards are displayed on the Teacher page at all times (including while a question is `ACTIVE`) and update dynamically as students submit their answers. Students are identified by display name (email local-part) rather than full email address.

*(An itemized per-student response matrix was considered but is intentionally not part of the Teacher UI — digestion is histogram-plus-answer-key, by design.)*

#### 5.4 Race Condition Prevention & Locking

* Prevents multiple **graded** submissions for the same question per student email — checked server-side before any write is made, guarded by `LockService.getScriptLock().waitLock(10000)` around the duplicate-check-and-write.
* `TABLE_PRICED`'s price-calculator "Run Test" activity performs no spreadsheet write and takes no lock at all (§5.1.5) — it is a pure, stateless computation, so it cannot contend with, or be affected by, any other student's concurrent activity, including their own graded submission.

#### 5.5 Deferred Feedback & Auto-Submit (all graded question types)

1. **Deferred Reveal:** upon submitting a graded answer (manually or automatically), the student sees a placeholder message (`"Answer submitted! Results will be shown once the current question closes."`) instead of their result. Their answer is scored and stored immediately — only the *display* of the result to that student is withheld. This applies uniformly to every `QuestionType`, including `NUMERIC`/`TEXT`/`TABLE` (previously immediate) as well as `TABLE_SCORED`/`TABLE_PRICED`: even a bare Pass/Fail badge, shown live, is enough for an early finisher to tip off classmates who haven't answered yet, so nothing about correctness is ever shown before the question closes. (`TABLE_PRICED`'s ungraded price-calculator table is the one exception — see §5.1.5.)
2. **Reveal Trigger:** each student's 1-second poll loop detects when the question's status transitions away from `ACTIVE` (via the teacher's **Stop Question**, or natural timer expiration). At that point, the student's already-computed result is fetched and displayed, using the same Pass / Partial Pass / Fail presentation as §5.1.7.
3. **Auto-Submit on Timeout:** for `TABLE_SCORED` and `TABLE_PRICED` (graded table), if a student's countdown reaches zero before they submit, the current contents of their grid (however complete), along with that question's accumulated `TestsRun` count (for `TABLE_PRICED`), are submitted automatically on their behalf, through the same validation, locking, and duplicate-prevention path as a manual submission. The student sees `"Time's up! Your answer was submitted automatically. Results will be shown once the question closes."` until the deferred reveal fires. (`NUMERIC`/`TEXT`/`TABLE` do not auto-submit on timeout — see §5.1.6.)
4. **Rationale:** deferring the reveal prevents students who finish early from seeing (and potentially sharing) correct/incorrect answers while classmates are still working; auto-submit ensures a timed-out student on a scored-table question is still scored on their in-progress work rather than being silently excluded. The answer key itself is withheld from students permanently — see §5.3.3a for where and when it does appear.

#### 5.6 Per-Question Images

* Optional, configured per question via the `Questions` sheet's `Image` column, located by header text (falling back to column I for sheets configured before this became header-driven — see §4.1, §2). Applies to **every** `QuestionType` — the display logic is entirely data-driven, not tied to any specific question.
* Shown on both the Student and Teacher screens **only** while that question's status is `ACTIVE`; hidden the instant it's stopped or times out. Fetched separately from the question's other data, and only once per question activation (not on every 1-second poll), to keep image resolution off the hot polling path (§2).
* Accepted formats in the `Image` column, in order of resolution:
  1. A Google Drive file ID or share link (a bare file ID, a `/file/d/ID/...` link, or a `...?id=ID` link), found as the cell's plain text, inside an `=IMAGE("...")` formula (which also gives a live thumbnail preview in the sheet itself), or via Sheets' native "Insert image in cell" **if** that image was itself inserted by URL (one inserted by uploading a file or picking from Drive/Photos has no recoverable URL).
  2. A Drive reference is resolved **server-side**: the script (running with the deploying teacher's own permissions) reads the file via `DriveApp` and embeds it directly in the page as a base64 `data:` URI. This means the file does **not** need to be shared publicly, and there is no dependency on external hotlinking (which Google Drive's own sharing links block unreliably when loaded cross-origin).
  3. If the cell instead contains a plain external `http(s)` URL that isn't a Drive reference (e.g., an Imgur link), it's used as-is.
* Changing which image a question shows — including replacing the underlying Drive file's contents — takes effect immediately on the next page load, with no code deployment required; it's a live sheet read like any other question field. A student who already has the page open when the image changes will only see the update after refreshing.

---

### 6. Deployment & Configuration

1. **Execution Privileges:** Execute as **Me** (Script Owner) so students can write responses to the sheet, and the script can read Drive-hosted images, without needing direct access to the underlying Google Spreadsheet or Drive files themselves.
2. **Access Scope:** Anyone with link (restricted programmatically via `@post.jce.ac.il` domain check, enforced both client- and server-side).
3. **OAuth Scopes:** `spreadsheets.currentonly` and `drive.readonly` (§2). The Drive scope requires a one-time manual authorization by the script owner — see §2 — after which it persists indefinitely with no further action needed.

---

### 7. Security Model, Known Protections & Accepted Risks

Apps Script's `google.script.run` bridge exposes **every** top-level server function (except one ending in `_` — see §7.1) to whichever page calls it, and to anyone who opens that page's browser console and calls it directly by name — regardless of which HTML file the server intended it for, and regardless of the `role` URL parameter. Nothing about which `.html` file was served is itself a security boundary. Every protection below either relies on that trailing-underscore convention (a real, platform-enforced exception) or on an explicit identity check inside the function itself; anything without one of those two is openly acknowledged as unprotected in §7.3.

#### 7.1 Fixed: the answer-key leak via `getQuestions()`

Before this section was added, `getQuestions()` — polled every second by both pages — returned each question's full `AcceptableAnswers` and (once introduced) `BugsDefinition` fields verbatim, for **every** question in the bank, including ones not yet launched. This wasn't visible in page source, but was trivially readable from the Network tab, or by typing `google.script.run.withSuccessHandler(x=>console.log(x)).getQuestions()` into the console at any time during class.

**Fix:** the function that reads the full row data from the `Questions` sheet was renamed `getQuestionsInternal_()`. The trailing underscore is not a naming convention here — Apps Script's `google.script.run` bridge refuses to expose any top-level function whose name ends in `_` to client-side code at all, so no client can call it under any name. Every scoring/validation/digestion function that genuinely needs the real answers (`submitAnswers`, `runPriceTest`, `computeRowPrice`, `scoreBugReports`, `scoreCombinatorialTable`, `validateTableAnswers`, `validateSimpleAnswers`, `buildCorrectAnswerText`, `getQuestionDigestion`, `getStudentSubmission`, `setActiveQuestion`, `launchNextQuestion`, `getStudentResponseCount`, `getLeaderboards`) now calls this internal function directly.

A new, separate `getQuestions()` (same name the client already called, so no client-side change was needed for this part) wraps it and strips every answer-bearing field — `AcceptableAnswers`, `BugsDefinition`, `Testcase Cost` — before returning to a client. `TABLE_PRICED` still needs to populate its graded table's dropdowns from the price table's known values, so a `priceTableOptions` field is included for that type: just the value **names** per header, with no prices attached. The real prices are computed server-side, per row, only when "Run Test" is actually clicked.

#### 7.2 Fixed: the `?role=teacher` bypass

Before this section was added, `doGet` decided which page to serve purely by reading the `role` query parameter, with no check on who was asking — appending `?role=teacher` to the base URL handed anyone the full Teacher Dashboard, including **Reset for New Class** (which deletes all response data). Separately, none of the teacher-only server functions checked caller identity either, so even without the URL trick, a student could open the console on the ordinary Student page and invoke `stopQuestion()`, `resetSessionForNewClass()`, or any other teacher action directly, exploiting the same "every function is globally callable" property described above.

**Fix:** a `Teachers` sheet tab (email addresses, one per row, any header text in row 1) is the authorization allowlist. `isAuthorizedTeacher()` compares `Session.getActiveUser().getEmail()` — the signed-in Google identity of whoever is actually loading the page, already used elsewhere in the app to prefill a student's own email — against that list. `requireTeacher()` throws if the check fails, and is now the first line of every teacher-only or student-privacy-sensitive server function: `setActiveQuestion`, `launchNextQuestion`, `stopQuestion`, `addTime`, `resetSessionForNewClass`, `getLeaderboards`, and `getQuestionDigestion`. `doGet` itself only serves the Teacher Dashboard when both `role=teacher` **and** `isAuthorizedTeacher()` hold; otherwise it transparently serves the ordinary Student Portal, with no error message hinting that a teacher mode exists to try to bypass.

`getLeaderboards` (raw student emails) and `getQuestionDigestion` (the answer key, once a question closes) were brought under this same gate even though they weren't the specific function named when this was first raised — they're the identical class of problem: teacher-only data, directly callable by anyone via console, regardless of which page loaded.

**Sheet-sharing note:** the `Teachers` tab lives in the same spreadsheet as `Questions`/`Responses`, read only by server-side code running as the script owner — a visiting student never gets spreadsheet-level access through the web app itself, only through the spreadsheet's own Google Drive sharing settings (a separate, already-verified concern, unrelated to the web app's own access control). Adding this tab does not create a new avenue to the answer key or to teacher actions.

#### 7.3 Known, accepted gaps (not fixed — left as-is by design decision)

1. **No caller-identity check on student-submitted email parameters.** `submitAnswers(email, qId, payload, testsRun)`, `runPriceTest(email, qId, row, expectedPrice)`, and `getStudentSubmission(email, qId)` all take `email` as a plain string argument and only validate that it matches the `@post.jce.ac.il` domain pattern (`isValidStudentEmail`) — never that it's actually the calling student's own identity. Concretely, this means: (a) a student could submit an answer, or run price-calculator tests, under a classmate's email instead of their own; (b) once a question closes, a student could call `getStudentSubmission('classmate@post.jce.ac.il', qId)` directly from the console to see that specific classmate's individual graded result, without needing the master answer key at all. This is a real, exploitable gap, deliberately left unfixed by explicit instruction.
2. **Client-side `TestsRun` tracking.** The count behind the `TABLE_PRICED` testcase-cost deduction (§5.2.5, §4.2) is a plain JavaScript variable (`testsRunCount`) on the student's own page, incremented in the browser after each successful "Run Test" response. A student could brute-force "Run Test" via the console to reverse-engineer an entire price table and bug set programmatically, then run `testsRunCount = 0` in the console immediately before clicking Submit, fully evading the per-test cost penalty regardless of how many tests were actually run server-side. Deliberately left unfixed — this session's stated intent is to potentially use it as a security-testing exercise for students, rather than remediate it.

Both gaps share the same root cause as everything in §7.1–§7.2 before they were fixed: Apps Script gives a server function no way to know that a request "really" came from the page and workflow it was written for, only what that request's arguments and the caller's Google identity say — and these two gaps are cases where the code trusts the former (unverified arguments, or client-tracked state) instead of checking the latter.
