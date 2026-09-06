# Software Requirements Specification (SRS): 3D OBJ Transformer Script (`transform_obj.py`)

## 1. Scope & Execution Mechanics
1.1 The script **shall** accept three mandatory positional arguments via the command line interface in the following strict order:
1. `input_file_path` (string)
2. `scale` (float parsing candidate)
3. `translation` (integer parsing candidate)
1.2 The script **shall** dynamically evaluate the optional flag `--reset` according to its presence and the total count of arguments passed:
* If `--reset` is the **only** argument provided, it **shall** override all standard operation, set the Test ID strictly to `"RESET"`, immediately dispatch cloud telemetry, print usage information, and terminate cleanly with exit code `0`.
* If `--reset` is provided alongside **any other** command line arguments, it **shall** be completely ignored and stripped from the argument stream without modifying or prefixing any subsequent Test IDs.

## 2. Ingestion & Cloud Telemetry Queue Configuration
2.1 The script **shall** silently transmit execution outcomes and partition logs to the specified cloud ingestion gateway using an HTTP POST request:
    * **Target Ingress URL:** `https://docs.google.com/forms/u/0/d/e/1FAIpQLSfGezcQHWV8DjRP8iXQ-FZr60Y1JzMOb5naks-IGxBOX4VqCw/formResponse`
    * **Student Name Field Identifier:** `entry.1567712013`
    * **Test / Partition ID Field Identifier:** `entry.726089351`
2.2 The script **shall** prompt the operator for their "Student ID / Name" if a local configuration cache file named `.student_id.txt` is missing or empty. The validated string **shall** be cached inside `.student_id.txt` for all subsequent runs.
2.3 A standalone `--reset` sets the Test ID exclusively to `"RESET"`, and a mixed `--reset` argument (mixed with other parameters) is ignored.

## 3. Structural Argument Evaluation & Prerequisite Error Paths
3.1 The script **shall** validate arguments sequentially and emit structural error IDs to `sys.stderr` before terminating with exit code `1`:
* **EP-IMPLICIT-HELP (No Arguments Passed):** Triggered if exactly 0 arguments are passed to the script (excluding an ignored mixed `--reset` flag). The script **shall** assign the partition Test ID `EP_IMPLICIT_HELP`, transmit it to the cloud telemetry queue, print standard usage syntax, and exit cleanly with code `0`.
* **ER-9.1 (Missing scale & translation):** Triggered if exactly 1 parameter is provided (which is not the --reset parameter). It **shall** log `ER_9_1_MISSING_SCALE_TRANS`, print standard usage syntax, and exit with `1`.
* **ER-9.2 (Missing translation):** Triggered if exactly 2 parameters are provided (both not the --reset parameter). It **shall** log `ER_9_2_MISSING_TRANS`, print standard usage syntax, and exit with `1`.
* **ER-11 (Non-Numeric Scale):** Triggered if the scale parameter cannot be parsed as a float. It **shall** log `ER_11_NON_NUMERIC_SCALE`.
* **ER-12 (Non-Numeric Translation):** Triggered if the translation parameter cannot be parsed as a float or integer. It **shall** log `ER_12_NON_NUMERIC_TRANS`.
3.2 **FR-15 (Float Translation Handling):** If the translation parameter contains a decimal dot but is numerically valid, the script **shall** round the value to the nearest integer, print an informational message to `sys.stdout`, and log `EP_TRANS_FLOAT` as the partition identifier (unless overridden by out-of-bounds clamping logic).

## 4. File System & Object Validation Rules
4.1 The script **shall** enforce the following file system constraints in sequence before reading file contents:
    * **ER-6 (Invalid Extension):** Triggered if `input_file_path` does not possess a case-insensitive `.obj` extension. Logs `ER_6_INFILE_NOT_OBJ`.
    * **ER-2 (File Missing):** Triggered if the input file path does not exist on disk. Logs `ER_2_INFILE_NOT_EXISTING`.
    * **ER-3 (Access Denied):** Triggered if the operating system reports the file is unreadable. Logs `ER_3_INFILE_NO_ACCESS`.
    * **ER-8.1 (Zero-Size Integrity Check):** Triggered if the file exists but has an absolute size of 0 bytes. Logs `ER_8_1_INFILE_EMPTY`.

## 5. Input Clamping & Boundary Partitions
5.1 The script **shall** enforce numerical limits on operational inputs by clamping values and setting the corresponding tracking partition ID:
    * If `scale` > 2.0, clamp to 2.0 and assign Test ID `EP_SCALE_OVER_CLAMP`.
    * If `scale` < 0.25, clamp to 0.25 and assign Test ID `EP_SCALE_UNDER_CLAMP`.
    * If `translation` > 10, clamp to 10 and assign Test ID `EP_TRANS_OVER_CLAMP`.
    * If `translation` < -10, clamp to -10 and assign Test ID `EP_TRANS_UNDER_CLAMP`.
5.2 If inputs fall completely within nominal ranges, the tracking partition ID **shall** default to `EP_VALID_NORMAL`.
5.3 If any boundary parameter is clamped, the script **shall** print an explanatory warning to `sys.stdout`.

## 6. Output File Generation Rules
6.1 The script **shall** generate a unique output filename using the following structural template: `<original_filename>_<actual_scale>_<actual_translation>.obj`. The target path **shall** reside within the parent folder of the input file.
6.2 **ER-4 (Filename Limit):** If the length of the generated output filename string exceeds 255 characters, the script **shall** log `ER_4_OUTFILE_NAME_TOO_LONG` and exit with `1`.
6.3 **ER-10 (Duplicate File Overwrite Protection):** If the target output path already exists on disk, the script **shall** log `ER_10_OUTFILE_EXISTS` and exit with `1`.
6.4 **ER-5 (Creation Failure):** If the output stream fails to write due to directory permissions or system limits, the script **shall** log `ER_5_OUTFILE_CANT_CREATE` and exit with `1`.

## 7. Line-by-Line 3D Geometry Processing & Corruption Tests
7.1 The script **shall** parse the input file line-by-line using a UTF-8 token stream, safely ignoring encoding errors.
7.2 **ER-7 (Corrupted/Incomplete Data Engine):** If a line begins with the token element type `v`, the script **shall** verify that exactly three distinct numerical, space coordinates follow it. If fewer than three components exist, or if they cannot be successfully parsed into valid floating-point values, execution **shall** terminate immediately, logging `ER_INFILE_INCOMPLETE_OBJ` with exit code `1`.
7.3 For geometric vertex coordinates (`v`), the transformation formula applied **shall** mathematically match:
    $$X_{new} = X_{old} \times \text{scale} + \text{translation}$$
    $$Y_{new} = Y_{old} \times \text{scale}$$
    $$Z_{new} = Z_{old} \times \text{scale}$$
    The output fields **shall** preserve trailing geometric tokens and format coordinates to 6 decimal places.
7.4 **ER-8.2 (Missing Core Vertices Check):** After reaching the end of the file stream, if the total count of processed vertex elements (`v`) is exactly 0, the script **shall** log `ER_8_2_INFILE_MISSING_VERTICES` and exit with `1`.
7.5 All unrecognized tokens, comments (`#`), and structural properties (`f`, `vt`, `vn`, `g`) **shall** pass through to the output array completely unchanged.