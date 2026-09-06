import sys
import os
import urllib.request
import urllib.parse

# -----------------------------------------------------------------------------
# GOOGLE FORM INGESTION CONFIGURATION
# -----------------------------------------------------------------------------
FORM_URL = "https://docs.google.com/forms/u/0/d/e/1FAIpQLSfGezcQHWV8DjRP8iXQ-FZr60Y1JzMOb5naks-IGxBOX4VqCw/formResponse"
ENTRY_STUDENT_NAME = "entry.1567712013"  # Form input field ID for Student Name
ENTRY_TEST_ID = "entry.726089351"        # Form input field ID for Test ID

CACHE_FILE = ".student_id.txt"

def get_or_prompt_student_name():
    """Reads the cached student name or prompts for a new one with @post.jce.ac.il validation."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                name = f.read().strip()
                # Only accept the cached name if it matches the required institutional domain
                if name and name.endswith('@post.jce.ac.il'):
                    return name
        except Exception:
            pass 

    while True:
        try:
            name = input("Please enter your Student Email (must end with @post.jce.ac.il): ").strip()
            if name and name.endswith('@post.jce.ac.il'):
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                    f.write(name)
                return name
            else:
                print("Error: Invalid email domain. You must use your @post.jce.ac.il address.", file=sys.stderr)
        except (KeyboardInterrupt, EOFError):
            print("\nExecution cancelled. Student identity is required.")
            sys.exit(1)

def report_test_to_cloud(student_name, test_id):
    """Silently fires an HTTP POST payload to the Google Form ingress queue."""
    form_data = {
        ENTRY_STUDENT_NAME: student_name,
        ENTRY_TEST_ID: test_id
    }
    
    try:
        encoded_data = urllib.parse.urlencode(form_data).encode('utf-8')
        req = urllib.request.Request(FORM_URL, data=encoded_data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        with urllib.request.urlopen(req, timeout=5) as response:
            pass
    except Exception:
        pass

def print_usage():
    """Prints standard Linux-like usage instructions (FR-14)."""
    usage_text = """Usage: transform_obj.py <input_file.obj> <scale> <translation> [--reset]

Transform a 3D model (.obj) by scaling its size and translating it along the X-axis.

Arguments:
  input_file       Path to the input 3D model file (.obj format)
  scale            Scaling factor as a float (Range: 0.25 to 2.0)
  translation      X-axis translation as an integer (Range: -10 to 10)

Options:
  --reset          Wipes all historical duplicate penalties for the triggered Test ID.
"""
    print(usage_text, file=sys.stderr)

def main():
    args = sys.argv[1:]
    student_name = get_or_prompt_student_name()

    # --- Handle --reset scenarios ---
    is_reset_mode = False
    if len(args) == 1 and args[0] == "--reset":
        # Rule: Only argument -> Test ID is "RESET", does nothing else
        report_test_to_cloud(student_name, "RESET")
        print("Reset done. All your previous entries are forgotten. Your score is 0", file=sys.stderr)
        sys.exit(0)
    elif "--reset" in args:
        # Rule: Provided with other arguments -> ignored
        args.remove("--reset")

    active_test_id = "EP_VALID_NORMAL"

    # --- ER-9.1 & ER-9.2 & FR-14 & EP_IMPLICIT_HELP: Structural Argument Evaluation ---
    if len(args) == 0:
        # Implicit help triggered when invoked without any parameters
        active_test_id = "EP_IMPLICIT_HELP"
        report_test_to_cloud(student_name, active_test_id)
        print_usage()
        sys.exit(0)
    elif len(args) == 1:
        active_test_id = "ER_9_1_MISSING_SCALE_TRANS"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-9.1: Missing scale and Translation parameters.", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        print_usage()
        sys.exit(1)
    elif len(args) == 2:
        active_test_id = "ER_9_2_MISSING_TRANS"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-9.2: Missing Translation parameter.", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        print_usage()
        sys.exit(1)

    input_file_path = args[0]
    raw_scale = args[1]
    raw_translation = args[2]

    # --- ER-11: Scale Parameter Numeric Validation ---
    try:
        scale = float(raw_scale)
    except ValueError:
        active_test_id = "ER_11_NON_NUMERIC_SCALE"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-11: The scale input contains non-numeric data.", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        sys.exit(1)

    # --- ER-12 & FR-15: Translation Parameter Processing & Clamping ---
    is_float_translation = False
    try:
        translation_float = float(raw_translation)
        if '.' in raw_translation:
            is_float_translation = True
            translation = int(round(translation_float))
        else:
            translation = int(translation_float)
    except ValueError:
        active_test_id = "ER_12_NON_NUMERIC_TRANS"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-12: The translation input contains non-numeric data.", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        sys.exit(1)

    # --- ER-6: Object File Extension Verification ---
    if not input_file_path.lower().endswith('.obj'):
        active_test_id = "ER_6_INFILE_NOT_OBJ"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-6: The input file is not an .obj file.", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        sys.exit(1)

    # --- ER-2: File Existence Verification ---
    if not os.path.exists(input_file_path):
        active_test_id = "ER_2_INFILE_NOT_EXISTING"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-2: The input file does not exist.", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        sys.exit(1)

    # --- ER-3: System Access Verification ---
    if not os.access(input_file_path, os.R_OK):
        active_test_id = "ER_3_INFILE_NO_ACCESS"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-3: The input file cannot be accessed.", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        sys.exit(1)

    # --- ER-8.1: Empty File Integrity Check ---
    if os.path.getsize(input_file_path) == 0:
        active_test_id = "ER_8_1_INFILE_EMPTY"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-8.1: The input file is empty (0-size file).", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        sys.exit(1)

    # --- Boundary Clamping Logical Assertions (FR-10, FR-11, FR-12.1, FR-12.2) ---
    adjusted = False
    
    if scale > 2.0:
        scale = 2.0
        active_test_id = "EP_SCALE_OVER_CLAMP"
        adjusted = True
    elif scale < 0.25:
        scale = 0.25
        active_test_id = "EP_SCALE_UNDER_CLAMP"
        adjusted = True

    if translation > 10:
        translation = 10
        if not adjusted or active_test_id == "EP_VALID_NORMAL":
            active_test_id = "EP_TRANS_OVER_CLAMP"
        adjusted = True
    elif translation < -10:
        translation = -10
        if not adjusted or active_test_id == "EP_VALID_NORMAL":
            active_test_id = "EP_TRANS_UNDER_CLAMP"
        adjusted = True

    if is_float_translation and active_test_id == "EP_VALID_NORMAL":
        active_test_id = "EP_TRANS_FLOAT"

#    if adjusted:
#        print(f"[INFO] In case of scale or translation input out-of-range, save the output file with the actual scale and translation values in its name, and print an information message to the screen to explain what was done.")

    input_dir, input_filename = os.path.split(input_file_path)
    filename_no_ext, ext = os.path.splitext(input_filename)
    
    output_filename = f"{filename_no_ext}_{scale}_{translation}{ext}"
    output_file_path = os.path.join(input_dir, output_filename) if input_dir else output_filename

    # --- ER-4: Filename Length Verification ---
    if len(output_filename) > 255:
        active_test_id = "ER_4_OUTFILE_NAME_TOO_LONG"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-4: The output file name is too long.", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        sys.exit(1)

    # --- ER-10: Output Duplicate Protection Check ---
    if os.path.exists(output_file_path):
        active_test_id = "ER_10_OUTFILE_EXISTS"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-10: Output file already exists.", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        sys.exit(1)

    # --- ER-1: File Open Stream Validation ---
    try:
        with open(input_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        active_test_id = "ER_1_INFILE_OPEN_FAIL"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-1: The input file fails to open.", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        sys.exit(1)

    transformed_lines = []
    vertex_count = 0
    face_count = 0

    for line_idx, line in enumerate(lines, 1):
        tokens = line.strip().split()
        if not tokens:
            transformed_lines.append(line)
            continue

        element_type = tokens[0]

        if element_type == 'v':
            vertex_count += 1
            if len(tokens) < 4:
                active_test_id = "ER_7_INFILE_INCOMPLETE_OBJ"
                if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
                print(f"Error ER-7: The input file is a corrupted .obj file (incomplete data).", file=sys.stderr)
                report_test_to_cloud(student_name, active_test_id)
                sys.exit(1)
            try:
                x = float(tokens[1]) * scale + translation
                y = float(tokens[2]) * scale
                z = float(tokens[3]) * scale
                
                extra = " " + " ".join(tokens[4:]) if len(tokens) > 4 else ""
                transformed_lines.append(f"v {x:.6f} {y:.6f} {z:.6f}{extra}\n")
            except ValueError:
                active_test_id = "ER_7_INFILE_INCOMPLETE_OBJ"
                if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
                print(f"Error ER-7: The input file is a corrupted .obj file (incomplete data).", file=sys.stderr)
                report_test_to_cloud(student_name, active_test_id)
                sys.exit(1)

        elif element_type == 'f':
            face_count += 1
            transformed_lines.append(line)
        else:
            transformed_lines.append(line)

    # --- ER-8_2: Check for Complete Absence of Vertex Positions ---
    if vertex_count == 0:
        active_test_id = "ER_8_2_INFILE_MISSING_VERTICES"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-8.2: No v lines in the file.", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        sys.exit(1)


    # --- ER-5: File Creation Integrity Check ---
    try:
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.writelines(transformed_lines)
        print(f"Success: File successfully processed and generated as '{output_file_path}'.")
    except Exception:
        active_test_id = "ER_5_OUTFILE_CANT_CREATE"
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"
        print("Error ER-5: The output file cannot be created (fails to open).", file=sys.stderr)
        report_test_to_cloud(student_name, active_test_id)
        sys.exit(1)

    # Wrap up execution mapping flag updates if --reset was triggered
    if is_reset_mode:
        active_test_id = f"RESET_{active_test_id}"

    # Report final resolved successful path partition
    report_test_to_cloud(student_name, active_test_id)

if __name__ == '__main__':
    main()