import sys
import os
import urllib.request
import urllib.parse

# -----------------------------------------------------------------------------
# GOOGLE FORM INGESTION CONFIGURATION
# -----------------------------------------------------------------------------
FORM_URL = "https://docs.google.com/forms/u/0/d/e/1FAIpQLSfGezcQHWV8DjRP8iXQ-FZr60Y1JzMOb5naks-IGxBOX4VqCw/formResponse"[cite: 2]
ENTRY_STUDENT_NAME = "entry.1567712013"  # Form input field ID for Student Name[cite: 2]
ENTRY_TEST_ID = "entry.726089351"        # Form input field ID for Test ID[cite: 2]

CACHE_FILE = ".student_id.txt"[cite: 2]

def get_or_prompt_student_name():
    """Reads the cached student name or prompts for a new one with @post.jce.ac.il validation."""
    if os.path.exists(CACHE_FILE):[cite: 2]
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:[cite: 2]
                name = f.read().strip()[cite: 2]
                # Only accept the cached name if it matches the required institutional domain
                if name and name.endswith('@post.jce.ac.il'):
                    return name
        except Exception:[cite: 2]
            pass 

    while True:[cite: 2]
        try:[cite: 2]
            name = input("Please enter your Student Email (must end with @post.jce.ac.il): ").strip()
            if name and name.endswith('@post.jce.ac.il'):
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:[cite: 2]
                    f.write(name)[cite: 2]
                return name[cite: 2]
            else:
                print("Error: Invalid email domain. You must use your @post.jce.ac.il address.", file=sys.stderr)
        except (KeyboardInterrupt, EOFError):[cite: 2]
            print("\nExecution cancelled. Student identity is required.")[cite: 2]
            sys.exit(1)[cite: 2]

def report_test_to_cloud(student_name, test_id):[cite: 2]
    """Silently fires an HTTP POST payload to the Google Form ingress queue."""
    form_data = {[cite: 2]
        ENTRY_STUDENT_NAME: student_name,[cite: 2]
        ENTRY_TEST_ID: test_id[cite: 2]
    }[cite: 2]
    
    try:[cite: 2]
        encoded_data = urllib.parse.urlencode(form_data).encode('utf-8')[cite: 2]
        req = urllib.request.Request(FORM_URL, data=encoded_data, method='POST')[cite: 2]
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')[cite: 2]
        
        with urllib.request.urlopen(req, timeout=5) as response:[cite: 2]
            pass[cite: 2]
    except Exception:[cite: 2]
        pass[cite: 2]

def print_usage():[cite: 2]
    """Prints standard Linux-like usage instructions (FR-14)."""
    usage_text = """Usage: transform_obj.py <input_file.obj> <scale> <translation> [--reset]

Transform a 3D model (.obj) by scaling its size and translating it along the X-axis.

Arguments:
  input_file       Path to the input 3D model file (.obj format)
  scale            Scaling factor as a float (Range: 0.25 to 2.0)
  translation      X-axis translation as an integer (Range: -10 to 10)

Options:
  --reset          Wipes all historical duplicate penalties for the triggered Test ID.
"""[cite: 2]
    print(usage_text, file=sys.stderr)[cite: 2]

def main():[cite: 2]
    args = sys.argv[1:][cite: 2]
    student_name = get_or_prompt_student_name()[cite: 2]

    # --- Handle --reset scenarios ---
    is_reset_mode = False[cite: 2]
    if len(args) == 1 and args[0] == "--reset":[cite: 2]
        # Rule: Only argument -> Test ID is "RESET", does nothing else
        report_test_to_cloud(student_name, "RESET")[cite: 2]
        print("Reset done. All your previous entries are forgotten. Your score is 0", file=sys.stderr)[cite: 2]
        sys.exit(0)[cite: 2]
    elif "--reset" in args:[cite: 2]
        # Rule: Provided with other arguments -> ignored
        args.remove("--reset")[cite: 2]

    active_test_id = "EP_VALID_NORMAL"[cite: 2]

    # --- ER-9.1 & ER-9.2 & FR-14 & EP_IMPLICIT_HELP: Structural Argument Evaluation ---
    if len(args) == 0:[cite: 2]
        # Implicit help triggered when invoked without any parameters
        active_test_id = "EP_IMPLICIT_HELP"[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        print_usage()[cite: 2]
        sys.exit(0)[cite: 2]
    elif len(args) == 1:[cite: 2]
        active_test_id = "ER_9_1_MISSING_SCALE_TRANS"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-9.1: Missing scale and Translation parameters.", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        print_usage()[cite: 2]
        sys.exit(1)[cite: 2]
    elif len(args) == 2:[cite: 2]
        active_test_id = "ER_9_2_MISSING_TRANS"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-9.2: Missing Translation parameter.", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        print_usage()[cite: 2]
        sys.exit(1)[cite: 2]

    input_file_path = args[0][cite: 2]
    raw_scale = args[1][cite: 2]
    raw_translation = args[2][cite: 2]

    # --- ER-11: Scale Parameter Numeric Validation ---
    try:[cite: 2]
        scale = float(raw_scale)[cite: 2]
    except ValueError:[cite: 2]
        active_test_id = "ER_11_NON_NUMERIC_SCALE"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-11: The scale input contains non-numeric data.", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        sys.exit(1)[cite: 2]

    # --- ER-12 & FR-15: Translation Parameter Processing & Clamping ---
    is_float_translation = False[cite: 2]
    try:[cite: 2]
        translation_float = float(raw_translation)[cite: 2]
        if '.' in raw_translation:[cite: 2]
            is_float_translation = True[cite: 2]
            translation = int(round(translation_float))[cite: 2]
            print(f"[INFO] Translation input '{raw_translation}' given as a float. Rounded to nearest integer: {translation}.")[cite: 2]
        else:[cite: 2]
            translation = int(translation_float)[cite: 2]
    except ValueError:[cite: 2]
        active_test_id = "ER_12_NON_NUMERIC_TRANS"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-12: The translation input contains non-numeric data.", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        sys.exit(1)[cite: 2]

    # --- ER-6: Object File Extension Verification ---
    if not input_file_path.lower().endswith('.obj'):[cite: 2]
        active_test_id = "ER_6_INFILE_NOT_OBJ"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-6: The input file is not an .obj file.", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        sys.exit(1)[cite: 2]

    # --- ER-2: File Existence Verification ---
    if not os.path.exists(input_file_path):[cite: 2]
        active_test_id = "ER_2_INFILE_NOT_EXISTING"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-2: The input file does not exist.", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        sys.exit(1)[cite: 2]

    # --- ER-3: System Access Verification ---
    if not os.access(input_file_path, os.R_OK):[cite: 2]
        active_test_id = "ER_3_INFILE_NO_ACCESS"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-3: The input file cannot be accessed.", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        sys.exit(1)[cite: 2]

    # --- ER-8.1: Empty File Integrity Check ---
    if os.path.getsize(input_file_path) == 0:[cite: 2]
        active_test_id = "ER_8_1_INFILE_EMPTY"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-8.1: The input file is empty (0-size file).", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        sys.exit(1)[cite: 2]

    # --- Boundary Clamping Logical Assertions (FR-10, FR-11, FR-12.1, FR-12.2) ---
    adjusted = False[cite: 2]
    
    if scale > 2.0:[cite: 2]
        scale = 2.0[cite: 2]
        active_test_id = "EP_SCALE_OVER_CLAMP"[cite: 2]
        adjusted = True[cite: 2]
    elif scale < 0.25:[cite: 2]
        scale = 0.25[cite: 2]
        active_test_id = "EP_SCALE_UNDER_CLAMP"[cite: 2]
        adjusted = True[cite: 2]

    if translation > 10:[cite: 2]
        translation = 10[cite: 2]
        if not adjusted or active_test_id == "EP_VALID_NORMAL":[cite: 2]
            active_test_id = "EP_TRANS_OVER_CLAMP"[cite: 2]
        adjusted = True[cite: 2]
    elif translation < -10:[cite: 2]
        translation = -10[cite: 2]
        if not adjusted or active_test_id == "EP_VALID_NORMAL":[cite: 2]
            active_test_id = "EP_TRANS_UNDER_CLAMP"[cite: 2]
        adjusted = True[cite: 2]

    if is_float_translation and active_test_id == "EP_VALID_NORMAL":[cite: 2]
        active_test_id = "EP_TRANS_FLOAT"[cite: 2]

    if adjusted:[cite: 2]
        print(f"[INFO] In case of scale or translation input out-of-range, save the output file with the actual scale and translation values in its name, and print an information message to the screen to explain what was done.")[cite: 2]

    input_dir, input_filename = os.path.split(input_file_path)[cite: 2]
    filename_no_ext, ext = os.path.splitext(input_filename)[cite: 2]
    
    output_filename = f"{filename_no_ext}_{scale}_{translation}{ext}"[cite: 2]
    output_file_path = os.path.join(input_dir, output_filename) if input_dir else output_filename[cite: 2]

    # --- ER-4: Filename Length Verification ---
    if len(output_filename) > 255:[cite: 2]
        active_test_id = "ER_4_OUTFILE_NAME_TOO_LONG"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-4: The output file name is too long.", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        sys.exit(1)[cite: 2]

    # --- ER-10: Output Duplicate Protection Check ---
    if os.path.exists(output_file_path):[cite: 2]
        active_test_id = "ER_10_OUTFILE_EXISTS"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-10: Output file already exists.", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        sys.exit(1)[cite: 2]

    # --- ER-1: File Open Stream Validation ---
    try:[cite: 2]
        with open(input_file_path, 'r', encoding='utf-8', errors='ignore') as f:[cite: 2]
            lines = f.readlines()[cite: 2]
    except Exception:[cite: 2]
        active_test_id = "ER_1_INFILE_OPEN_FAIL"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-1: The input file fails to open.", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        sys.exit(1)[cite: 2]

    transformed_lines = [][cite: 2]
    vertex_count = 0[cite: 2]
    face_count = 0[cite: 2]

    for line_idx, line in enumerate(lines, 1):[cite: 2]
        tokens = line.strip().split()[cite: 2]
        if not tokens:[cite: 2]
            transformed_lines.append(line)[cite: 2]
            continue[cite: 2]

        element_type = tokens[0][cite: 2]

        if element_type == 'v':[cite: 2]
            vertex_count += 1[cite: 2]
            if len(tokens) < 4:[cite: 2]
                active_test_id = "ER_7_INFILE_INCOMPLETE_OBJ"[cite: 2]
                if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
                print(f"Error ER-7: The input file is a corrupted .obj file (incomplete data).", file=sys.stderr)[cite: 2]
                report_test_to_cloud(student_name, active_test_id)[cite: 2]
                sys.exit(1)[cite: 2]
            try:[cite: 2]
                x = float(tokens[1]) * scale + translation[cite: 2]
                y = float(tokens[2]) * scale[cite: 2]
                z = float(tokens[3]) * scale[cite: 2]
                
                extra = " " + " ".join(tokens[4:]) if len(tokens) > 4 else ""[cite: 2]
                transformed_lines.append(f"v {x:.6f} {y:.6f} {z:.6f}{extra}\n")[cite: 2]
            except ValueError:[cite: 2]
                active_test_id = "ER_7_INFILE_INCOMPLETE_OBJ"[cite: 2]
                if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
                print(f"Error ER-7: The input file is a corrupted .obj file (incomplete data).", file=sys.stderr)[cite: 2]
                report_test_to_cloud(student_name, active_test_id)[cite: 2]
                sys.exit(1)[cite: 2]

        elif element_type == 'f':[cite: 2]
            face_count += 1[cite: 2]
            transformed_lines.append(line)[cite: 2]
        else:[cite: 2]
            transformed_lines.append(line)[cite: 2]

    # --- ER-8_2: Check for Complete Absence of Vertex Positions ---
    if vertex_count == 0:[cite: 2]
        active_test_id = "ER_8_2_INFILE_MISSING_VERTICES"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-8.2: No v lines in the file.", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        sys.exit(1)[cite: 2]

    # --- ER-5: File Creation Integrity Check ---
    try:[cite: 2]
        with open(output_file_path, 'w', encoding='utf-8') as out_f:[cite: 2]
            out_f.writelines(transformed_lines)[cite: 2]
        print(f"Success: File successfully processed and generated as '{output_file_path}'.")[cite: 2]
    except Exception:[cite: 2]
        active_test_id = "ER_5_OUTFILE_CANT_CREATE"[cite: 2]
        if is_reset_mode: active_test_id = f"RESET_{active_test_id}"[cite: 2]
        print("Error ER-5: The output file cannot be created (fails to open).", file=sys.stderr)[cite: 2]
        report_test_to_cloud(student_name, active_test_id)[cite: 2]
        sys.exit(1)[cite: 2]

    # Wrap up execution mapping flag updates if --reset was triggered
    if is_reset_mode:[cite: 2]
        active_test_id = f"RESET_{active_test_id}"[cite: 2]

    # Report final resolved successful path partition
    report_test_to_cloud(student_name, active_test_id)[cite: 2]

if __name__ == '__main__':
    main()[cite: 2]