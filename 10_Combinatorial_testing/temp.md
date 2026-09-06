# System Requirements Specification (SRS)

## Interactive Classroom Polling & Submission System

### 1. Overview & Purpose

This Google Apps Script (GAS) web application provides a real-time, interactive classroom assessment tool for course instructors. It enables an instructor to present dynamic questions during a live lecture, receive student responses in real time, apply automatic scoring with speed bonuses, render live leaderboard rankings, and present customized post-question digestion analytics.

---

### 2. System Architecture & Tech Stack

* **Platform:** Google Apps Script (GAS)
* **Database & Storage:** Google Sheets (Spreadsheet container) & Script Properties API
* **Frontend:** HTML5, CSS3, JavaScript (ES6) served via `HtmlService`
* **Concurrency Control:** Apps Script `LockService` to prevent race conditions during simultaneous class-wide submissions
* **Authentication & Domain Isolation:** Restricted strictly to students with valid institutional `@post.jce.ac.il` email addresses

---

### 3. User Roles & Access Control

#### 3.1 Student

* **Access Route:** Base Web App URL (`.../exec`)
* **Privileges & Validation:**
* Must authenticate via an Azrieli email address (`@post.jce.ac.il`).
* Non-Azrieli emails trigger an immediate error: `"You must enter your Azrieli email address!"`.
* Receive active question prompts pushed dynamically by the instructor.
* Submit responses (numeric inputs for `TEXT` mode or multi-row tabular grid entries for `TABLE` mode) within the designated time limit.
* Support pasting multiple data rows directly from Microsoft Excel into `TABLE` inputs.
* Receive pass/fail feedback and points earned upon submission.



#### 3.2 Teacher / Instructor

* **Access Route:** Web App URL with parameter (`.../exec?role=teacher`)
* **Privileges & Controls:**
* Launch specific questions from the predefined question bank or advance using the **"Next Challenge"** button (grayed out on the final question).
* Monitor real-time student submission counts while the question is active.
* Manually stop a question session or allow it to auto-expire via countdown timer.
* View real-time digestion analytics (histograms and itemized response tables) only **after** the question session closes.
* Track real-time leaderboards displaying **Top 10 (Current Question)** and **Top 10 Overall**.



---

### 4. Data Models & Google Sheet Schema

#### 4.1 `Questions` Sheet Schema

Stores the predefined question bank.

| Col | Field Name | Type | Description |
| --- | --- | --- | --- |
| **A** | `QuestionID` | String / Int | Unique identifier for the question (e.g., `1`, `2`, `3`). |
| **B** | `QuestionText` | String | Plain-text prompt displayed to students. |
| **C** | `AcceptableAnswers` | String / JSON | Semicolon-separated valid values (for `TEXT` questions) OR JSON object mapping fixed headers to arrays of required values (for `TABLE` questions). |
| **D** | `TimeLimitSec` | Integer | Allowed duration for the question in seconds. |
| **E** | `MinAnswersRequired` | Integer | Minimum number of valid/filled inputs required. |
| **F** | `MaxAnswersAllowed` | Integer | Maximum number of allowed input fields/table rows. |
| **G** | `QuestionType` | String | Interface mode (`TEXT` or `TABLE`). Defaults to `TEXT`. |
| **H** | `BaseScore` | Integer | Base point value awarded for a fully correct answer (Default: `10`). |

#### 4.2 `Responses` Sheet Schema

Stores submission records appended atomically upon submission.

| Col | Field Name | Type | Description |
| --- | --- | --- | --- |
| **A** | `Timestamp` | Date | Server timestamp of the submission. |
| **B** | `StudentEmail` | String | Lower-case, validated Azrieli email (`@post.jce.ac.il`). |
| **C** | `QuestionID` | String | Target question ID. |
| **D** | `SubmittedAnswers` | String (JSON) | Serialized array of submitted text/number inputs or array of row objects. |
| **E** | `IsOverallCorrect` | Boolean | Pass/Fail evaluation result (`true` / `false`). |
| **F** | `Score` | Integer | Final score awarded (Base Score + Time Remaining bonus). |
| **G** | `MissingCount` | Integer | Count of missing required values (used for Q3 digestion). |

---

### 5. Functional Requirements

#### 5.1 Student Interface & Question Handling

1. **Domain Access Check:** Enforces email validation (`@post.jce.ac.il`). If invalid, displays `"You must enter your Azrieli email address!"`.
2. **Numeric Input Mode (`TEXT` Questions - Q1 & Q2):**
* Enforces numeric input (`type="number"`).
* Generates input fields equal to `MinAnswersRequired`.
* Enforces `MaxAnswersAllowed` (hides **"+ Add Answer"** button once reached).
* Suppresses individual row deletion buttons when `MaxAnswersAllowed == 1`.


3. **Tabular Grid Mode (`TABLE` Questions - Q3):**
* Displays a fixed 5-column table in the exact required order: `Model`, `Storage`, `Color`, `Network`, `Accessory`.
* Strictly enforces `MaxAnswersAllowed` on table rows (prevents adding or pasting beyond this limit).
* Supports Clipboard Excel Paste: Parses tab-delimited (`\t`) and newline-delimited (`\n`) clipboard data directly across rows and columns.
* Requires every cell in a submitted row to be filled prior to submission.


4. **Countdown Timer:**
* Displays remaining time formatted as `mm:ss` (e.g., `01:15`).
* Automatically disables input submission upon timer expiration.


5. **Student Feedback:**
* **Pass:** Displays submitted answers, `Result: All conditions were met! (Pass)`, and points earned.
* **Fail:** Displays submitted answers and `Result: So sad! Your answer is incorrect! (Fail)`.



#### 5.2 Dynamic Validation & Scoring Algorithm (`Code.gs`)

1. **`TEXT` Type Rules (Q1 & Q2):**
* Validates numeric input type and ensures length meets $Min \le Count \le Max$.
* Matches entries against `AcceptableAnswers` (case-insensitive, duplicates ignored).
* **Pass Condition:** All inputs valid, no duplicates, count meets bounds.


2. **`TABLE` Type Rules (Q3):**
* Evaluates array of row objects against required column values specified in `AcceptableAnswers` JSON.
* Calculates `MissingCount`: counts how many required values across all categories were omitted from the submission.
* **Pass Condition:** `MissingCount == 0` (100% complete coverage across all 5 column categories).


3. **Time-Bonus Scoring Formula:**
* If `IsOverallCorrect == false`: `Score = 0`.
* If `IsOverallCorrect == true`:

$$\text{Score} = \text{BaseScore} + \lfloor \text{Seconds Remaining at Submission} \rfloor$$





#### 5.3 Teacher Control & Digestion Analytics

1. **Live Question Controls:**
* **Launch Question:** Starts active timer and opens question to students.
* **Next Challenge:** Advances to the next sequential question and launches it automatically. Button is disabled when on the last question.
* **Stop Question:** Immediately closes session and displays full digestion.


2. **Active State Masking:**
* While a question is active (`ACTIVE` status and timer running), the Teacher view displays **only** the live submission count (`Response Count`). Digestion summaries and individual responses are hidden until the session is closed.


3. **Question-Specific Digestion Analytics:**
* **Q1 & Q2:** Generates a bar-chart histogram of submitted numerical answers.
* **Q3:** Generates a bar-chart histogram of `MissingCount` values (where `0 missing` indicates a PASS, and higher values show the distribution of incomplete answers).


4. **Leaderboards:**
* **Top 10 (Current Question):** Ranks top 10 scoring students for the active question.
* **Top 10 Overall:** Ranks top 10 highest cumulative scores across all questions in the session.


5. **Itemized Response Matrix:**
* Renders full student response table including email, submitted structure, pass/fail status tag (`✓ Pass` / `✗ Fail`), and score awarded.



#### 5.4 Race Condition Prevention & Locking

* Prevents multiple submissions for the same question per student email.
* Uses `LockService.getScriptLock().waitLock(10000)` prior to writing to the `Responses` sheet to handle concurrent class-wide submissions safely.

---

### 6. Deployment & Configuration

1. **Execution Privileges:** Execute as **Me** (Script Owner) so students can write responses to the sheet without needing direct access to the underlying Google Spreadsheet.
2. **Access Scope:** Anyone with link (restricted programmatically via `@post.jce.ac.il` domain check).