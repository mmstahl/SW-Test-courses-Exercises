# System Requirements Specification (SRS)

## Interactive Classroom Polling & Submission System

*Reflects the deployed application as of 2026-08-17.*

### 1. Overview & Purpose

This Google Apps Script (GAS) web application provides a real-time, interactive classroom assessment tool for course instructors. It enables an instructor to present dynamic questions during a live lecture, receive student responses in real time, apply automatic scoring with speed bonuses (including partial-credit scoring for combinatorial test-suite questions and flat per-bug rewards for black-box price-testing questions), render live leaderboard rankings, present customized post-question digestion analytics, and reveal each question's answer key — to the instructor only — once the question closes.

---

### 2. System Architecture & Tech Stack

* **Platform:** Google Apps Script (GAS)
* **Database & Storage:** Google Sheets (Spreadsheet container) & Script Properties API
* **Frontend:** HTML5, CSS3, JavaScript (ES6) served via `HtmlService`
* **Media:** Optional per-question images, sourced from Google Drive (embedded server-side as base64 `data:` URIs — no public sharing or external hosting required) or from any external image URL
* **Concurrency Control:** Apps Script `LockService` to prevent race conditions during simultaneous class-wide submissions
* **Authentication & Domain Isolation:** Restricted strictly to students with valid institutional `@post.jce.ac.il` email addresses, enforced both client-side (immediate UI feedback) and server-side (authoritative check inside `submitAnswers` and `runPriceTest`)
* **OAuth Scopes:** `spreadsheets.currentonly` (read/write the Questions and Responses sheets) and `drive.readonly` (read image files referenced from the Questions sheet). Adding the Drive scope requires the script owner to complete a one-time authorization (Apps Script editor → run any function → "Review permissions" → Allow) before Drive-sourced images will resolve; this is a one-time grant tied to the owner's account, not something students or repeat lessons ever trigger.

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
  * At most one **graded** submission is accepted per student per question; a second attempt is rejected server-side. (`TABLE_PRICED`'s ungraded price-test log entries are explicitly exempt from this limit — see §5.1.5 and §5.4.)
  * While a question is `ACTIVE`, an optional illustrative image (if configured for that question) is displayed above the question prompt; it disappears the moment the question closes (see §5.6).

#### 3.2 Teacher / Instructor

* **Access Route:** Web App URL with parameter (`.../exec?role=teacher`)
* **Privileges & Controls:**
  * Launch a specific question, selected from a drop-down menu that shows the ID and question text of every question in the `Questions` sheet, with a configurable duration (seconds) pre-filled from that question's `TimeLimitSec` and editable before launch.
  * Advance using the **"Next Challenge"** button, which launches the next sequential question (by array order in the sheet) automatically, using that question's own `TimeLimitSec`. Grayed out when on the final question.
  * **"Add 1 Min"** button: extends the currently active question's remaining time by 60 seconds. Disabled unless a question is currently `ACTIVE`. Every connected student's countdown reflects the extension on their next poll tick automatically — no separate notification mechanism is needed.
  * Monitor real-time student submission counts (`Response Count`) while a question is active.
  * Manually stop a question session (**"Stop Question"**), or allow it to auto-expire via its countdown timer.
  * View real-time digestion analytics (bar-chart histograms, question-type-specific) **and** the question's answer key, both only **after** the question session closes. The answer key is never sent to students at any point — this is the only place it's ever displayed (see §5.3.3a).
  * Track real-time leaderboards displaying **Top 10 (Current Question)** and **Top 10 Overall**, shown by student display name (the local part of their email, before `@`) rather than full email address.
  * **"Reset for New Class"**: a double-confirmation control (a confirm dialog, followed by typing `RESET` in a prompt) that clears the session state and deletes all rows from the `Responses` sheet, ready for a new class session.
  * See the same optional per-question illustrative image as students, shown while that question is `ACTIVE` (see §5.6).

---

### 4. Data Models & Google Sheet Schema

#### 4.1 `Questions` Sheet Schema

Stores the predefined question bank.

| Col | Field Name | Type | Description |
| --- | --- | --- | --- |
| **A** | `QuestionID` | String / Int | Unique identifier for the question (e.g., `1`, `2`, `3`, `4`, `5`). |
| **B** | `QuestionText` | String | Plain-text prompt displayed to students. |
| **C** | `AcceptableAnswers` | String / JSON | Format depends on `QuestionType` — see below. |
| **D** | `TimeLimitSec` | Integer | Allowed duration for the question in seconds. |
| **E** | `MinAnswersRequired` | Integer | Minimum number of valid/filled inputs required. For `TABLE`/`TABLE_SCORED`/`TABLE_PRICED`'s price-calculator table, this is also how many initial grid rows are rendered, and those initial rows cannot be deleted by the student. (`TABLE_PRICED`'s graded 3-row answer table is a fixed size and ignores this column — see §5.1.5.) |
| **F** | `MaxAnswersAllowed` | Integer | Maximum number of allowed input fields/table rows (price-calculator table only, for `TABLE_PRICED`). |
| **G** | `QuestionType` | String | Interface & scoring mode: `TEXT`, `NUMERIC`, `TABLE`, `TABLE_SCORED`, or `TABLE_PRICED`. Defaults to `TEXT` if blank. |
| **H** | `BaseScore` | Integer | Base point value (Default: `100`). Meaning depends on type — see §5.2. |
| **I** | `Image` *(optional)* | String / Formula / In-cell image | An illustrative image shown on both screens only while this question is `ACTIVE`. See §5.6 for accepted formats. |

`AcceptableAnswers` format by `QuestionType`:

* **`NUMERIC` / `TEXT`:** a semicolon-separated string of valid values, e.g. `5;10;15`.
* **`TABLE`:** a JSON object mapping each of the 5 fixed column headers to an array of required values for that column, e.g. `{"Model":["iPhone 15","iPhone 15 Pro"],"Storage":["128GB","256GB"], ...}`.
* **`TABLE_SCORED`:** a JSON array of complete, exact row objects — the full set of valid combinations — e.g. `[{"Model":"Pixel 9","Storage":"128GB","Color":"Black","Network":"5G","Accessory":"None"}, ...]`.
* **`TABLE_PRICED`:** a JSON object with a `priceTable` field mapping each of the 5 fixed headers to a `{value: price}` lookup, e.g. `{"priceTable":{"Model":{"Pixel 9":900,"Pixel 9 Pro":1050},"Storage":{"128GB":0,"256GB":56}, ...}}`. This lookup drives both the price-calculator table's computed price and the dropdown options offered in the graded answer table (plus a literal `"Any"` option, added automatically). The 3 known pricing-engine bugs that the graded table is scored against are **hardcoded in `Code.js`**, not read from this JSON — see §5.2.5.

#### 4.2 `Responses` Sheet Schema

Stores submission records appended atomically. Two different *kinds* of row can appear for the same student/question pair when the question is `TABLE_PRICED`: a **graded submission** row (JSON-encoded `SubmittedData`) and any number of **price-test log** rows (plain-text `SubmittedData`) from that student's price-calculator activity. The two are told apart by checking whether `SubmittedData` is valid JSON — this check is what lets `TABLE_PRICED`'s repeatable test-running coexist with the one-submission-per-question rule enforced for every type's graded answer (see §5.4).

| Col | Field Name | Type | Description |
| --- | --- | --- | --- |
| **A** | `Timestamp` | Date | Server timestamp of the submission/log entry. |
| **B** | `StudentEmail` | String | Lower-case, validated Azrieli email (`@post.jce.ac.il`). |
| **C** | `QuestionID` | String | Target question ID. |
| **D** | `SubmittedData` | String (JSON) or String (plain) | For a graded submission: JSON array of submitted text/number inputs or row objects. For a `TABLE_PRICED` price-test log entry: a plain `Model\|Storage\|Color\|Network\|Accessory\|ActualPrice\|PASS_or_FAIL` string (not JSON) — see §5.1.5. |
| **E** | `IsCorrect` | Boolean | Graded submissions: pass/fail per §5.2. Price-test log entries: always `true` (unused placeholder — the real result is the trailing `PASS`/`FAIL` field inside `SubmittedData`). |
| **F** | `Score` | Integer | Graded submissions: final score per §5.2. Price-test log entries: always `0`. |
| **G** | `MissingCount` | Integer | `TABLE`: required column values never covered. `TABLE_SCORED`: required row combinations never covered. `TABLE_PRICED` graded submission: number of the 3 bugs *not* found (`3 − bugsFound`). Unused (`0`) for `NUMERIC`/`TEXT` and for `TABLE_PRICED` price-test log entries. |

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

5. **Dual-Table Mode (`TABLE_PRICED` QuestionType — e.g. Q5):** a black-box testing exercise with two independent tables on one question.
   * **Price Calculator table (ungraded, "explore freely")** — labeled as not graded:
     * Same 5 fixed columns as `TABLE`/`TABLE_SCORED`, plus three extra columns: **Expected Price** (free-text — the student's own prediction), **Price** (read-only, filled in by the server), and **Result** (read-only, `Pass`/`Fail`).
     * Starts with `MinAnswersRequired` locked rows (cannot be deleted); additional rows up to `MaxAnswersAllowed` can be added or pasted in, same mechanics as §5.1.4.
     * **"▶ Run Test"** (per row) or **"▶ Run All Tests"** (whole grid) sends that row's 5 field values plus the student's Expected Price to the server, which computes the actual price (see §5.2.5) and returns it immediately. The row is colored green (`Pass`) if the actual price matches the student's Expected Price exactly (case-insensitive text comparison — this also covers the "error message" and "no price shown" outcomes), or red (`Fail`) otherwise. This is the **only** immediate, non-deferred feedback anywhere in the app, since it's the student's own private exploration tool, not the graded answer.
     * Every Run Test click (on a row with at least one filled cell) is permanently logged as its own row in `Responses` — unlike every other submission in this app, there is no limit on how many times a student can run tests, and no single one of them is "the" answer.
   * **"Report the 3 Bugs You Found" table (graded, one-time submission):**
     * Always exactly 3 rows; no adding, removing, or pasting.
     * Each cell is a dropdown populated from that column's valid values (drawn from the same `priceTable` used by the calculator above) plus a literal `"Any"` option, which the student must select explicitly to represent "this field doesn't matter" in a bug's signature — see §5.2.5.
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
   * None of this feedback — for any type — ever states what the *correct* values were. That's shown only to the teacher, only after the question closes (§5.3.3a).

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

5. **`TABLE_PRICED` Type Rules (black-box bug hunting, e.g. Q5):**
   * **Price computation** (`computeRowPrice`, used by the price-calculator table only — not scored): 3 known bugs are checked first, in this order, each overriding the default calculation entirely:
     1. `Storage == "1TB"` → price is a flat `100`.
     2. `Model == "Pixel 9 Pro XL"` AND `Color == "Blue"` → price is the literal string `"Error: Invalid configuration"`.
     3. `Storage == "256GB"` AND `Network == "5G"` AND `Accessory == "Charger"` → no price is shown or logged (blank).
     * If none apply, the price is the sum of each column's looked-up value from `priceTable`; a blank or unmatched cell makes the row `"Error: Invalid configuration"`.
     * These 3 conditions are hardcoded in `Code.js`, not configurable via the sheet.
   * **Bug-report scoring** (`scoreBugReports`, used by the graded 3-row answer table): each submitted row is checked against the same 3 bug signatures above, expressed as exact-match row templates with `"Any"` as a literal wildcard value the student must select (e.g. bug 1's signature is `Storage="1TB"`, all other fields `="Any"`). A row counts as a correctly reported bug only if it exactly matches a signature **and** is the first row in the submission to match that particular bug — a later row repeating an already-claimed bug earns nothing (no penalty either; submissions are one-shot, so there's no retry to protect against).
   * $$\text{Score} = \sum_{\text{correctly \& uniquely reported bugs}} (\text{BaseScore} + \text{Seconds Remaining})$$
     (each qualifying row earns its own full time bonus — finding all 3 bugs early nets three separate bonuses.)
   * **Tier** (for Pass/Partial/Fail display and leaderboard-adjacent `IsCorrect`): `bugsFound == 3` → Pass; `1–2` → Partial Pass; `0` → Fail.
   * Recommended `BaseScore = 100` (matching "100 points per correctly reported bug").

6. **Time-Bonus Scoring Formula — `NUMERIC` / `TEXT` / `TABLE`:**
   * If **Fail**: `Score = 0`.
   * If **Pass**:
     $$\text{Score} = \text{BaseScore} + \lfloor \text{Seconds Remaining at Submission} \rfloor$$

#### 5.3 Teacher Control & Digestion Analytics

1. **Live Question Controls:**
   * **Launch Question:** starts the active timer and opens the question to students. Selected from a drop-down menu showing the ID and text of every question in the `Questions` sheet; the duration field is pre-filled from that question's `TimeLimitSec` but can be overridden before launch.
   * **Next Challenge:** advances to the next sequential question (by sheet order) and launches it automatically using that question's own `TimeLimitSec`. Disabled when on the last question.
   * **Add 1 Min:** extends the current question's countdown by 60 seconds. Disabled unless a question is currently `ACTIVE`.
   * **Stop Question:** immediately closes the session for the current question; digestion analytics and the answer key for it become available.

2. **Active State Masking:**
   * While a question is active (`ACTIVE` status and timer running), the Teacher view displays **only** the live submission count (`Response Count`), the leaderboards, and the question's illustrative image (if any) — all updating/visible in real time. Digestion analytics and the answer key are hidden until the session is closed.

3. **Question-Specific Digestion Analytics** (available only once the current question's session is closed):
   * **`NUMERIC` / `TEXT`:** a bar-chart histogram of submitted answer values.
   * **`TABLE`:** a bar-chart histogram of `MissingCount` values (`0` missing indicates a PASS; higher values show the distribution of incomplete answers).
   * **`TABLE_SCORED`:** a bar-chart histogram of result tiers — count of **Fail** / **Partial** / **Pass** submissions.
   * **`TABLE_PRICED`:** a bar-chart histogram of **how many of the 3 known bugs each student found**, grouped by student across all of their price-calculator test runs for that question (`0 bugs found` / `1 bug found` / `2 bugs found` / `3 bugs found`) — independent of what price they predicted, whether an individual test passed, or what they ultimately reported in the graded table. A student "found" a bug the moment any of their logged test rows triggers that bug's condition.

3a. **Answer Key Reveal** (available only once the current question's session is closed, alongside digestion): a plain-text "✅ Correct Answer" box, formatted per type:
   * **`NUMERIC` / `TEXT`:** the accepted values, comma-joined.
   * **`TABLE`:** each column's required values, e.g. `Model: iPhone 15, iPhone 15 Pro | Storage: 128GB, 256GB | ...`.
   * **`TABLE_SCORED`:** every valid row combination, one comma-joined row per entry, pipe-separated.
   * **`TABLE_PRICED`:** a fixed, hardcoded description of the 3 bugs (not derived from the sheet), e.g. `Bug 1: Storage = 1TB (all other fields = Any) | Bug 2: ...`.
   * This is the **only** place the answer key is ever displayed — it is never sent to, or derivable by, a student at any point.

4. **Leaderboards:**
   * **Top 10 (Current Question):** ranks the top 10 scoring students for the active/last question.
   * **Top 10 Overall:** ranks the top 10 highest cumulative scores across all questions in the session, sorted descending.
   * Leaderboards are displayed on the Teacher page at all times (including while a question is `ACTIVE`) and update dynamically as students submit their answers. Students are identified by display name (email local-part) rather than full email address.

*(An itemized per-student response matrix was considered but is intentionally not part of the Teacher UI — digestion is histogram-plus-answer-key, by design.)*

#### 5.4 Race Condition Prevention & Locking

* Prevents multiple **graded** submissions for the same question per student email — checked server-side before any write is made, guarded by `LockService.getScriptLock().waitLock(10000)` around the duplicate-check-and-write.
* `TABLE_PRICED`'s price-calculator "Run Test" log entries are explicitly exempt from this limit (any number of log rows per student per question is expected and normal); the dedup check and the "does a submission already exist" lookup both distinguish a real graded submission from a log entry by checking whether `SubmittedData` parses as JSON (log entries are a plain pipe-delimited string, never valid JSON) — see §4.2.

#### 5.5 Deferred Feedback & Auto-Submit (all graded question types)

1. **Deferred Reveal:** upon submitting a graded answer (manually or automatically), the student sees a placeholder message (`"Answer submitted! Results will be shown once the current question closes."`) instead of their result. Their answer is scored and stored immediately — only the *display* of the result to that student is withheld. This applies uniformly to every `QuestionType`, including `NUMERIC`/`TEXT`/`TABLE` (previously immediate) as well as `TABLE_SCORED`/`TABLE_PRICED`: even a bare Pass/Fail badge, shown live, is enough for an early finisher to tip off classmates who haven't answered yet, so nothing about correctness is ever shown before the question closes. (`TABLE_PRICED`'s ungraded price-calculator table is the one exception — see §5.1.5.)
2. **Reveal Trigger:** each student's 1-second poll loop detects when the question's status transitions away from `ACTIVE` (via the teacher's **Stop Question**, or natural timer expiration). At that point, the student's already-computed result is fetched and displayed, using the same Pass / Partial Pass / Fail presentation as §5.1.7.
3. **Auto-Submit on Timeout:** for `TABLE_SCORED` and `TABLE_PRICED` (graded table), if a student's countdown reaches zero before they submit, the current contents of their grid (however complete) are submitted automatically on their behalf, through the same validation, locking, and duplicate-prevention path as a manual submission. The student sees `"Time's up! Your answer was submitted automatically. Results will be shown once the question closes."` until the deferred reveal fires. (`NUMERIC`/`TEXT`/`TABLE` do not auto-submit on timeout — see §5.1.6.)
4. **Rationale:** deferring the reveal prevents students who finish early from seeing (and potentially sharing) correct/incorrect answers while classmates are still working; auto-submit ensures a timed-out student on a scored-table question is still scored on their in-progress work rather than being silently excluded. The answer key itself is withheld from students permanently — see §5.3.3a for where and when it does appear.

#### 5.6 Per-Question Images

* Optional, configured per question via `Questions` column I (§4.1). Applies to **every** `QuestionType` — the display logic is entirely data-driven, not tied to any specific question.
* Shown on both the Student and Teacher screens **only** while that question's status is `ACTIVE`; hidden the instant it's stopped or times out.
* Accepted formats in column I, in order of resolution:
  1. A Google Drive file ID or share link (a bare file ID, a `/file/d/ID/...` link, or a `...?id=ID` link), found as the cell's plain text, inside an `=IMAGE("...")` formula (which also gives a live thumbnail preview in the sheet itself), or via Sheets' native "Insert image in cell" **if** that image was itself inserted by URL (one inserted by uploading a file or picking from Drive/Photos has no recoverable URL).
  2. A Drive reference is resolved **server-side**: the script (running with the deploying teacher's own permissions) reads the file via `DriveApp` and embeds it directly in the page as a base64 `data:` URI. This means the file does **not** need to be shared publicly, and there is no dependency on external hotlinking (which Google Drive's own sharing links block unreliably when loaded cross-origin).
  3. If the cell instead contains a plain external `http(s)` URL that isn't a Drive reference (e.g., an Imgur link), it's used as-is.
* Changing which image a question shows — including replacing the underlying Drive file's contents — takes effect immediately on the next page load, with no code deployment required; it's a live sheet read like any other question field. A student who already has the page open when the image changes will only see the update after refreshing.

---

### 6. Deployment & Configuration

1. **Execution Privileges:** Execute as **Me** (Script Owner) so students can write responses to the sheet, and the script can read Drive-hosted images, without needing direct access to the underlying Google Spreadsheet or Drive files themselves.
2. **Access Scope:** Anyone with link (restricted programmatically via `@post.jce.ac.il` domain check, enforced both client- and server-side).
3. **OAuth Scopes:** `spreadsheets.currentonly` and `drive.readonly` (§2). The Drive scope requires a one-time manual authorization by the script owner — see §2 — after which it persists indefinitely with no further action needed.
