import sys
import os
import argparse
import urllib.request
import urllib.parse

# -----------------------------------------------------------------------------
# GOOGLE FORM INGESTION CONFIGURATION
# -----------------------------------------------------------------------------
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdgKClabX46IJ8YZggzo17ihF3ou9TdquQdBpryFqOsQ-nLtw/formResponse"
ENTRY_STUDENT_NAME = "entry.1038110062"  # Form input field ID for Student Name[cite: 1]
ENTRY_INPUT = "entry.1050115853"         # Form input field ID for data parameters[cite: 1]

CACHE_FILE = ".student_id.txt"[cite: 1]

def get_or_prompt_student_name():
    """Reads the cached student name or prompts for a new one with domain validation."""
    if os.path.exists(CACHE_FILE):[cite: 1]
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:[cite: 1]
                name = f.read().strip()[cite: 1]
                if name and name.endswith('@post.jce.ac.il'):[cite: 1]
                    return name[cite: 1]
        except Exception:
            pass 

    while True:
        try:
            name = input("Please enter your username (email ending with @post.jce.ac.il): ").strip()[cite: 1]
            if name and name.endswith('@post.jce.ac.il'):[cite: 1]
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:[cite: 1]
                    f.write(name)[cite: 1]
                return name[cite: 1]
            else:
                print("Error: Invalid username. The email must end with @post.jce.ac.il", file=sys.stderr)[cite: 1]
        except (KeyboardInterrupt, EOFError):[cite: 1]
            print("\nExecution cancelled. Student identity is required.")[cite: 1]
            sys.exit(1)[cite: 1]

def report_test_to_cloud(student_name, payload):
    """Silently fires an HTTP POST payload to the Google Form ingress queue."""
    form_data = {
        ENTRY_STUDENT_NAME: student_name,[cite: 1]
        ENTRY_INPUT: payload[cite: 1]
    }
    
    try:
        encoded_data = urllib.parse.urlencode(form_data).encode('utf-8')[cite: 1]
        req = urllib.request.Request(FORM_URL, data=encoded_data, method='POST')[cite: 1]
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')[cite: 1]
        
        with urllib.request.urlopen(req, timeout=5) as response:[cite: 1]
            pass
    except Exception:
        pass


def triage_and_treat():
    # 1. Setup Argument Parser
    parser = argparse.ArgumentParser(
        description="Emergency ward triage and treatment calculator.",
        add_help=False
    )
    
    # Optional flag to suppress header
    parser.add_argument('--noheader', action='store_true', help='Suppress the output table header')
    
    # Positional arguments
    parser.add_argument('temp_input', nargs='?', help='Temperature category')
    parser.add_argument('bp_input', nargs='?', help='Blood pressure category')
    parser.add_argument('chest_pain_input', nargs='?', help='Chest pains')

    args = parser.parse_args()

    # Verify all positional arguments exist with the updated usage guidance
    if args.temp_input is None or args.bp_input is None or args.chest_pain_input is None:
        print("Error: Missing inputs.")
        print("Usage: python script.py [--noheader] <temperature> <blood_pressure> <chest_pains>")
        print("Allowed values:")
        print("  <temperature>    : L (Low), M (Medium/Healthy), H (High) [Case-insensitive]")
        print("  <blood_pressure> : L (Low), H (High)                     [Case-insensitive]")
        print("  <chest_pains>    : Y (Yes), N (No)                       [Case-insensitive]")
        print("Example: python script.py M L N")
        return

    # Normalize inputs to uppercase and strip whitespace
    temp_input = args.temp_input.strip().upper()
    bp_input = args.bp_input.strip().upper()
    chest_pain_input = args.chest_pain_input.strip().upper()

    # 2. Category Validations & Mappings
    if temp_input not in ['L', 'M', 'H']:
        print(f"Error: Invalid temperature value '{args.temp_input}'. Must be L, M, or H (case-insensitive).")
        return
        
    if bp_input not in ['L', 'H']:
        print(f"Error: Invalid blood pressure value '{args.bp_input}'. Must be L or H (case-insensitive).")
        return

    if chest_pain_input not in ['Y', 'N']:
        print(f"Error: Invalid chest pains value '{args.chest_pain_input}'. Must be Y or N (case-insensitive).")
        return

    # Map the user categorical variables to structural flags
    temp_category = "healthy" if temp_input == 'M' else "unhealthy"
    has_chest_pain = (chest_pain_input == 'Y')

    # 3. Triage Rules
    triage_destination = ""
    
    if triage_destination == "":
        if temp_category == "healthy" and bp_input == 'L':
            if has_chest_pain:
                triage_destination = "doctor"
            else:
                triage_destination = "home"
                
    if triage_destination == "":
        if has_chest_pain:
            triage_destination = "doctor"
            
    if triage_destination == "":
        if temp_input == 'H' and bp_input == 'H':
            triage_destination = "doctor"
            
    if triage_destination == "":
        triage_destination = "nurse"

    # 4. Treatment Rules (Accumulative)
    treatments = []

    if triage_destination == "doctor":
        if temp_input in ['L', 'M']:
            treatments.append("Do EKG")
        else:
            treatments.append("Hospitalize")

    if temp_input == 'H':
        treatments.append("Give Acamol")

    if bp_input == 'L' and temp_input == 'L':
        treatments.append("Give Vodka")

    # Format output strings
    triage_action = "Send home" if triage_destination == "home" else f"See {triage_destination.capitalize()}"
    treatment_action = ", ".join(treatments) if treatments else "None required"

    # 5. Determine Tn value from Matrix Table mapping
    tn_map = {
        ('H', 'H', 'N'): 'T1',
        ('H', 'H', 'Y'): 'T2',
        ('H', 'L', 'N'): 'T3',
        ('H', 'L', 'Y'): 'T4',
        ('L', 'H', 'N'): 'T5',
        ('L', 'H', 'Y'): 'T6',
        ('L', 'L', 'N'): 'T7',
        ('L', 'L', 'Y'): 'T8',
        ('M', 'H', 'N'): 'T9',
        ('M', 'H', 'Y'): 'T10',
        ('M', 'L', 'N'): 'T11',
        ('M', 'L', 'Y'): 'T12',
    }
    tn_value = tn_map.get((temp_input, bp_input, chest_pain_input), "Unknown")

    # 6. Cloud Logging Integration
    student_name = get_or_prompt_student_name()[cite: 1]
    
    # Pack parameters explicitly to avoid lost columns
    input_str = f"Input: {temp_input},{bp_input},{chest_pain_input}"
    output_str = f"Output: {triage_action}|{treatment_action}"
    tn_str = f"Tn: {tn_value}"
    
    # Combine everything to be set into the ingress parameter field
    log_payload = f"{input_str} | {output_str} | {tn_str}"
    
    report_test_to_cloud(student_name, log_payload)

    # 7. Printing the Header (if not suppressed)
    if not args.noheader:
        print("Temperature   Blood pressure    Chest pains   Triage Action   Treatment")
        print("-------------------------------------------------------------------------------------------------------")

    # 8. Printing the Data Row
    print(f"{temp_input:<14}{bp_input:<18}{chest_pain_input:<14}{triage_action:<16}{treatment_action}")
    

if __name__ == "__main__":
    triage_and_treat()