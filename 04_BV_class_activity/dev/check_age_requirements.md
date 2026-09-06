# Requirements Specification: Dynamic Age Rule Validator (v99 & v100)

## 1. Functional Overview
The Dynamic Age Rule Validator application evaluates a set of arbitrary age parameters against 7 different boundary-checking implementations (Code versions 0–6) to determine whether each input age is accepted or rejected based on configured boundary thresholds.

## 2. Command Line Interface & Input Constraints
* **Syntax:** `python script.py <Code version> <Age1> <Age2> ... [Age6]`
* **Parameter Volume Controls:**
  * Minimum: 2 parameters (1 Code version + 1 Age entry)
  * Maximum: 7 parameters (1 Code version + 6 Age entries)
  * Invocation without parameters displays a detailed usage guide via `print_usage()` and exits gracefully (`sys.exit(0)`).
* **Code Version Rules:**
  * Must be an integer between `0` and `6` inclusive, or the string token `"All"` (evaluated case-insensitively).
  * Any alternate string or out-of-bounds numerical input generates a targeted error to standard error (`sys.stderr`) and terminates process execution with an exit code of `1`.
* **Age Rules:**
  * Every provided age must parse successfully into a baseline base-10 integer.
  * Age entries must fall within the range `0 <= age <= 120`.
  * The script processes all provided ages simultaneously, aggregates all parsing or boundary errors across the batch, prints them to `sys.stderr`, and terminates (`sys.exit(1)`) if any anomalies are detected.
  * Inputs are sorted and deduplicated before testing against evaluation thresholds.

## 3. User Identity Caching & Institutional Filtering
* Before verifying parameters or performing calculations, the application prompts the user for identity credentials.
* **Validation Constraint:** The input string must be an email address concluding explicitly with the institutional domain suffix `@post.jce.ac.il`. 
* **Persistence Mechanism:** 
  * If valid, the text string is stored locally inside a tracking file named `.student_id.txt`.
  * Subsequent executions read from this tracking file to completely bypass the prompt. 
  * If the file is altered or missing the required suffix, the user is continuously re-prompted until a valid string matches the structural criteria.

## 4. Cloud Integration Telemetry
Upon reading or gathering the verified student identity, the script instantly constructs and fires a silent `POST` transmission payload to an external Google Form telemetry ingress queue:
* **Target Endpoint URL:** `https://docs.google.com/forms/d/e/1FAIpQLSdgKClabX46IJ8YZggzo17ihF3ou9TdquQdBpryFqOsQ-nLtw/formResponse`
* **Form Entry Fields:**
  * `entry.1038110062` (Student Name): Transmits the verified email address.
  * `entry.1050115853` (Input Payload): Contains all raw arguments passed to `sys.argv[1:]`, joined by a pipe character delimiter (`|`).
  * `entry.530224207` (Code Architecture Version): Identifies the executing script base (`V99` or `V100`).

## 5. Output Formatting & Terminal UX Colors
Calculations output to standard output utilizing a manual spacing framework to build tabular summaries despite invisible ANSI terminal escape sequences.
* **Color Definitions:**
  * Ages `<= 99` are wrapped in universal terminal Green (`\033[32m`).
  * Ages `>= 100` are wrapped in universal terminal Red (`\033[31m`).
* Empty evaluation queues display as a single hyphen token (`-`).

---

## 6. Logic Threshold Matrices

### Version 99 Evaluation Logic (`check_age_version = "V99"`)
The age execution framework for Version 99 is centered around a critical evaluation boundary of **99**:

| Code Version | Code Definition / Evaluation Check | Intended Logic Category |
| :---: | :--- | :--- |
| **0** | `if age < 99` | Strict Under-Boundary |
| **1** | `if age > 99` | Strict Over-Boundary |
| **2** | `if age != 99` | Non-Equality |
| **3** | `if age <= 99` | **Correct Inclusive Age Target** |
| **4** | `if age >= 99` | Inclusive Upper-Boundary |
| **5** | `approved = True` | Simulated Assignment Bug (`if age := 99`) |
| **6** | `if age == 99` | Absolute Equality Match |

### Version 100 Evaluation Logic (`check_age_version = "V100"`)
The age execution framework for Version 100 shifts its evaluation boundary upward to **100**:

| Code Version | Code Definition / Evaluation Check | Intended Logic Category |
| :---: | :--- | :--- |
| **0** | `if age > 100` | Strict Over-Boundary |
| **1** | `if age < 100` | **Correct Inclusive Age Target** |
| **2** | `if age != 100` | Non-Equality |
| **3** | `if age <= 100` | Inclusive Under-Boundary |
| **4** | `if age >= 100` | Inclusive Upper-Boundary |
| **5** | `approved = True` | Simulated Assignment Bug (`if age := 100`) |
| **6** | `if age == 100` | Absolute Equality Match |