# System Requirements Specification (SRS)

## Interactive Classroom Polling & Submission System

*Reflects the deployed application as of 2026-08-14.*

### 1. Overview & Purpose

This Google Apps Script (GAS) web application provides a real-time, interactive classroom assessment tool for course instructors. It enables an instructor to present dynamic questions during a live lecture, receive student responses in real time, apply automatic scoring with speed bonuses (including partial-credit scoring for combinatorial test-suite questions), render live leaderboard rankings, and present customized post-question digestion analytics.

---

### 2. System Architecture & Tech Stack

* **Platform:** Google Apps Script (GAS)
* **Database & Storage:** Google Sheets (Spreadsheet container) & Script Properties API
* **Frontend:** HTML5, CSS3, JavaScript (ES6) served via `HtmlService`
* **Concurrency Control:** Apps Script `LockService` to prevent race conditions during simultaneous class-wide submissions
* **Authentication & Domain Isolation:** Restricted strictly to students with valid institutional `@post.jce.ac.il` email addresses, enforced both client-side (immediate UI feedback) and server-side (authoritative check inside `submitAnswers`)

---

### 3. User Roles & Access Control

#### 3.1 Student

* **Access Route:** Base Web App URL (`.../exec`)
* **Privileges & Validation:**
  * Must authenticate via an Azrieli email address (`@post.jce.ac.il`).
  * Non-Azrieli emails trigger an immediate error: `"You must enter your Azrieli email address!"`. This is validated both in the browser and again on the server before any response is recorded.
  * Receive active question prompts via a 1-second client poll of session state (`getSessionState`) — there is no server push channel in Apps Script, so "dynamic" delivery is polling-based.
  * Submit responses: numeric-only inputs for `NUMERIC` QuestionType, free text for `TEXT` QuestionType, or multi-row tabular grid entries for `TABLE` and `TABLE_SCORED` QuestionTypes — within the designated time limit.
  * Support pasting multiple data rows directly from Microsoft Excel into `TABLE`/`TABLE_SCORED` grid inputs.
  * Receive pass/fail (or partial-pass) feedback and points earned. For `TABLE_SCORED` questions this feedback is deliberately deferred — see §5.5.
  * Pressing **Enter** in a NUMERIC or TEXT answer field submits the response, exactly like clicking **Submit Response**. Enter is ignored inside `TABLE`/`TABLE_SCORED` grid cells (so it doesn't interfere with row-by-row/paste data entry).
  * The **Submit Response** button starts disabled and only becomes enabled once the minimum required input has been provided (see §5.1).
  * At most one submission is accepted per student per question; a second attempt is rejected server-side.

#### 3.2 Teacher / Instructor

* **Access Route:** Web App URL with parameter (`.../exec?role=teacher`)
* **Privileges & Controls:**
  * Launch a specific question, selected from a drop-down menu that shows the ID and question text of every question in the `Questions` sheet, with a configurable duration (seconds) pre-filled from that question's `TimeLimitSec` and editable before launch.
  * Advance using the **"Next Challenge"** button, which launches the next sequential question (by array order in the sheet) automatically, using that question's own `TimeLimitSec`. Grayed out when on the final question.
  * **"Add 1 Min"** button: extends the currently active question's remaining time by 60 seconds. Disabled unless a question is currently `ACTIVE`. Every connected student's countdown reflects the extension on their next poll tick automatically — no separate notification mechanism is needed.
  * Monitor real-time student submission counts (`Response Count`) while a question is active.
  * Manually stop a question session (**"Stop Question"**), or allow it to auto-expire via its countdown timer.
  * View real-time digestion analytics (bar-chart histograms, question-type-specific) only **after** the question session closes.
  * Track real-time leaderboards displaying **Top 10 (Current Question)** and **Top 10 Overall**, shown by student display name (the local part of their email, before `@`) rather than full email address.
  * **"Reset for New Class"**: a double-confirmation control (a confirm dialog, followed by typing `RESET` in a prompt) that clears the session state and deletes all rows from the `Responses` sheet, ready for a new class session.

---

### 4. Data Models & Google Sheet Schema

#### 4.1 `Questions` Sheet Schema

Stores the predefined question bank.

| Col | Field Name | Type | Description |
| --- | --- | --- | --- |
| **A** | `QuestionID` | String / Int | Unique identifier for the question (e.g., `1`, `2`, `3`, `4`). |
| **B** | `QuestionText` | String | Plain-text prompt displayed to students. |
| **C** | `AcceptableAnswers` | String / JSON | Format depends on `QuestionType` — see below. |
| **D** | `TimeLimitSec` | Integer | Allowed duration for the question in seconds. |
| **E** | `MinAnswersRequired` | Integer | Minimum number of valid/filled inputs required. For `TABLE`/`TABLE_SCORED`, this is also how many initial grid rows are rendered, and those initial rows cannot be deleted by the student. |
| **F** | `MaxAnswersAllowed` | Integer | Maximum number of allowed input fields/table rows. |
| **G** | `QuestionType` | String | Interface & scoring mode: `TEXT`, `NUMERIC`, `TABLE`, or `TABLE_SCORED`. Defaults to `TEXT` if blank. |
| **H** | `BaseScore` | Integer | Base point value awarded for a fully correct answer (Default: `100`). For `TABLE_SCORED` questions, set this to `10 × (number of valid row combinations)` — e.g. `130` for a 13-row combinatorial suite — since the PASS tier boundary is a fixed `130`, independent of this column (see §5.2.4). |

`AcceptableAnswers` format by `QuestionType`:

* **`NUMERIC` / `TEXT`:** a semicolon-separated string of valid values, e.g. `5;10;15`.
* **`TABLE`:** a JSON object mapping each of the 5 fixed column headers to an array of required values for that column, e.g. `{"Model":["iPhone 15","iPhone 15 Pro"],"Storage":["128GB","256GB"], ...}`.
* **`TABLE_SCORED`:** a JSON array of complete, exact row objects — the full set of valid combinations — e.g. `[{"Model":"Pixel 9","Storage":"128GB","Color":"Black","Network":"5G","Accessory":"None"}, ...]`.

#### 4.2 `Responses` Sheet Schema

Stores submission records appended atomically upon submission (own row per header below).

| Col | Field Name | Type | Description |
| --- | --- | --- | --- |
| **A** | `Timestamp` | Date | Server timestamp of the submission. |
| **B** | `StudentEmail` | String | Lower-case, validated Azrieli email (`@post.jce.ac.il`). |
| **C** | `QuestionID` | String | Target question ID. |
| **D** | `SubmittedData` | String (JSON) | Serialized array of submitted text/number inputs or array of row objects. |
| **E** | `IsCorrect` | Boolean | For `NUMERIC`/`TEXT`/`TABLE`: pass/fail (`true`/`false`). For `TABLE_SCORED`: `true` only when the submission reached the PASS tier (`false` for both FAIL and PARTIAL). |
| **F** | `Score` | Integer | Final score awarded (see scoring formulas in §5.2). |
| **G** | `MissingCount` | Integer | For `TABLE`: count of required column values never covered. For `TABLE_SCORED`: count of the required row combinations never covered by the submission. Unused (`0`) for `NUMERIC`/`TEXT`. |

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

5. **Countdown Timer:**
   * Displays remaining time formatted as `mm:ss` (e.g., `01:15`).
   * Automatically disables input submission upon timer expiration.
   * If a teacher extends time via **"Add 1 Min"** before a student's countdown reaches zero, the extension is picked up on the student's next poll tick and the countdown continues seamlessly.
   * For `NUMERIC`/`TEXT`/`TABLE` questions, reaching zero without a manual submission shows a local **Fail** result (no data is sent to the server — nothing is recorded for that student/question).
   * For `TABLE_SCORED` questions, reaching zero without a manual submission triggers an **automatic submission** of whatever is currently in the grid — see §5.5.

6. **Student Feedback:**
   * **Pass:** Displays submitted answers, `Result: All conditions were met! (Pass)`, and points earned.
   * **Fail:** Displays submitted answers and `Result: So sad! Your answer is incorrect! (Fail)`.
   * **Partial Pass** (`TABLE_SCORED` only): Displays submitted answers, `Result: Partially correct! (Partial Pass)`, and points earned, styled in orange.
   * For `TABLE`/`TABLE_SCORED` questions, the submitted answers are shown as a table; for `TABLE_SCORED` specifically, each row is additionally tagged and colored green/"Correct" or red/"Incorrect" based on whether it matched a required, not-yet-counted valid combination.

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
   * A submission reaches full credit (`Points \ge 130`) only by containing exactly the complete set of valid combinations, each exactly once — extra, wrong, or duplicate rows, and any missing required row, all cost 10 points each.

5. **Time-Bonus Scoring Formula — `NUMERIC` / `TEXT` / `TABLE`:**
   * If **Fail**: `Score = 0`.
   * If **Pass**:
     $$\text{Score} = \text{BaseScore} + \lfloor \text{Seconds Remaining at Submission} \rfloor$$

6. **Tiered Scoring Formula — `TABLE_SCORED` only:**
   * If `Points < 61`: **Fail** — `Score = 0`.
   * If `61 \le Points < 130`: **Partial Pass** —
     $$\text{Score} = \text{Points} + \left\lfloor \frac{\text{Seconds Remaining}}{2} \right\rfloor$$
   * If `Points \ge 130`: **Pass** —
     $$\text{Score} = 130 + \text{Seconds Remaining}$$
     (the base of this final formula is the fixed value `130`, not `Points` — a submission with more than 130 points, e.g. from a `BaseScore` greater than `130`, still scores `130 + Seconds Remaining`.)

#### 5.3 Teacher Control & Digestion Analytics

1. **Live Question Controls:**
   * **Launch Question:** starts the active timer and opens the question to students. Selected from a drop-down menu showing the ID and text of every question in the `Questions` sheet; the duration field is pre-filled from that question's `TimeLimitSec` but can be overridden before launch.
   * **Next Challenge:** advances to the next sequential question (by sheet order) and launches it automatically using that question's own `TimeLimitSec`. Disabled when on the last question.
   * **Add 1 Min:** extends the current question's countdown by 60 seconds. Disabled unless a question is currently `ACTIVE`.
   * **Stop Question:** immediately closes the session for the current question; digestion analytics for it become available.

2. **Active State Masking:**
   * While a question is active (`ACTIVE` status and timer running), the Teacher view displays **only** the live submission count (`Response Count`) and the leaderboards, both updating in real time. Digestion analytics are hidden until the session is closed.

3. **Question-Specific Digestion Analytics** (available only once the current question's session is closed):
   * **`NUMERIC` / `TEXT`:** a bar-chart histogram of submitted answer values.
   * **`TABLE`:** a bar-chart histogram of `MissingCount` values (`0` missing indicates a PASS; higher values show the distribution of incomplete answers).
   * **`TABLE_SCORED`:** a bar-chart histogram of result tiers — count of **Fail** / **Partial** / **Pass** submissions.

4. **Leaderboards:**
   * **Top 10 (Current Question):** ranks the top 10 scoring students for the active/last question.
   * **Top 10 Overall:** ranks the top 10 highest cumulative scores across all questions in the session, sorted descending.
   * Leaderboards are displayed on the Teacher page at all times (including while a question is `ACTIVE`) and update dynamically as students submit their answers. Students are identified by display name (email local-part) rather than full email address.

*(An itemized per-student response matrix was considered but is intentionally not part of the Teacher UI — digestion is histogram-only, by design.)*

#### 5.4 Race Condition Prevention & Locking

* Prevents multiple submissions for the same question per student email — checked server-side before any write is made.
* Uses `LockService.getScriptLock().waitLock(10000)` around the duplicate-check-and-write, to handle concurrent class-wide submissions safely.

#### 5.5 Deferred Feedback & Auto-Submit (`TABLE_SCORED` only)

This behavior applies only to `TABLE_SCORED` questions; all other question types show feedback immediately upon submission as described in §5.1.6.

1. **Deferred Reveal:** upon submitting (manually or automatically), the student sees a placeholder message (`"Answer submitted! Results will be shown once the current question closes."`) instead of their result. Their answer is scored and stored immediately, exactly as with any other question type — only the *display* of the result to that student is withheld.
2. **Reveal Trigger:** each student's 1-second poll loop detects when the question's status transitions away from `ACTIVE` (via the teacher's **Stop Question**, or natural timer expiration). At that point, the student's already-computed result is fetched and displayed, using the same Pass / Partial Pass / Fail presentation as §5.1.6.
3. **Auto-Submit on Timeout:** if a student's countdown reaches zero before they submit, the current contents of their grid (however complete) are submitted automatically on their behalf, through the same validation, locking, and duplicate-prevention path as a manual submission. The student sees `"Time's up! Your answer was submitted automatically. Results will be shown once the question closes."` until the deferred reveal fires.
4. **Rationale:** deferring the reveal prevents students who finish early from seeing (and potentially sharing) correct/incorrect answers while classmates are still working; auto-submit ensures a timed-out student is still scored on their in-progress work rather than being silently excluded.

---

### 6. Deployment & Configuration

1. **Execution Privileges:** Execute as **Me** (Script Owner) so students can write responses to the sheet without needing direct access to the underlying Google Spreadsheet.
2. **Access Scope:** Anyone with link (restricted programmatically via `@post.jce.ac.il` domain check, enforced both client- and server-side).
