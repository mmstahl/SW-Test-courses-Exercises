import sys
import os
import argparse
import urllib.request
import urllib.parse

# -----------------------------------------------------------------------------
# GOOGLE FORM INGESTION CONFIGURATION
# -----------------------------------------------------------------------------
check_age_version = "V99"  # Maintaining the required version string from check_age
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdgKClabX46IJ8YZggzo17ihF3ou9TdquQdBpryFqOsQ-nLtw/formResponse"
ENTRY_STUDENT_NAME = "entry.1038110062"  # Form input field ID for Student Name
ENTRY_INPUT = "entry.1050115853"         # Form input field ID for input parameters
ENTRY_VERSION = "entry.530224207"       # Form input field ID for code version

CACHE_FILE = ".student_id.txt"

def get_or_prompt_student_name():
    """Reads the cached student name or prompts for a new one with domain validation."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                name = f.read().strip()
                if name and name.endswith('@post.jce.ac.il'):
                    return name
        except Exception:
            pass 

    while True:
        try:
            name = input("Please enter your username (email ending with @post.jce.ac.il): ").strip()
            if name and name.endswith('@post.jce.ac.il'):
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                    f.write(name)
                return name
            else:
                print("Error: Invalid username. The email must end with @post.jce.ac.il", file=sys.stderr)
        except (KeyboardInterrupt, EOFError):
            print("\nExecution cancelled. Student identity is required.")
            sys.exit(1)

def report_test_to_cloud(student_name, test_id):
    """Silently fires an HTTP POST payload to the Google Form ingress queue."""
    form_data = {
        ENTRY_STUDENT_NAME: student_name,
        ENTRY_INPUT: test_id,
        ENTRY_VERSION: check_age_version
    }
    
    try:
        encoded_data = urllib.parse.urlencode(form_data).encode('utf-8')
        req = urllib.request.Request(FORM_URL, data=encoded_data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        with urllib.request.urlopen(req, timeout=5) as response:
            pass
    except Exception:
        pass


def triage_and_treat():
    # 1. Retrieve and prompt for the user identity first
    student_name = get_or_prompt_student_name()

    # Log the transmission payload containing all command line arguments joined by '|'
    args_list = sys.argv[1:]
    test_id = "|".join(args_list)
    report_test_to_cloud(student_name, test_id)

    # 2. Setup Argument Parser
    parser = argparse.ArgumentParser(
        description="Emergency ward triage and treatment calculator.",
        add_help=False # Disabling default help to handle validation errors cleanly via print
    )
    
    # Optional flag to suppress header
    parser.add_argument('--noheader', action='store_true', help='Suppress the output table header')
    
    # Positional arguments (only gathered if flags aren't missing, but parsed as strings first for custom error logic)
    parser.add_argument('bp_input', nargs='?', help='Blood pressure (integer)')
    parser.add_argument('temp_input', nargs='?', help='Temperature (float)')
    parser.add_argument('chest_pain_input', nargs='?', help='Chest pains (Y/N)')

    args = parser.parse_args()

    # Verify all positional arguments exist
    if args.bp_input is None or args.temp_input is None or args.chest_pain_input is None:
        print("Error: Missing inputs.")
        print("Usage: python script.py [--noheader] <blood_pressure> <temperature> <chest_pains>")
        print("Example: python script.py 120 36.8 N")
        return

    bp_input = args.bp_input.strip()
    temp_input = args.temp_input.strip()
    chest_pain_input = args.chest_pain_input.strip().upper()

    # 2. DataType and Number Validations
    # Validate Blood Pressure
    try:
        if '.' in bp_input:
            print("Error: Blood pressure must be an integer, not a float.")
            return
        bp = int(bp_input)
    except ValueError:
        print("Error: Blood pressure must be a valid number.")
        return

    # Validate Temperature
    try:
        temp = float(temp_input)
    except ValueError:
        print("Error: Temperature must be a valid number.")
        return

    # Validate Chest Pains
    if chest_pain_input not in ['Y', 'N']:
        print("Error: Chest pains must be 'Y' or 'N' (case-insensitive).")
        return

    # 3. Range Validations
    if not (0 <= bp <= 250):
        print(f"Error: Blood pressure {bp} is outside the defined range (0-250).")
        return

    if not (35.0 <= temp <= 42.0):
        print(f"Error: Temperature {temp} is outside the defined range (35.0-42.0).")
        return

    # 4. Categorization
    bp_category = "low" if bp <= 100 else "high"
    
    if 36.5 <= temp <= 37.5:
        temp_category = "healthy"
    else:
        temp_category = "unhealthy"

    has_chest_pain = (chest_pain_input == 'Y')

    # 5. Triage Rules
    triage_destination = ""
    
    if triage_destination == "":
        if temp_category == "healthy" and bp_category == "low":
            if has_chest_pain:
                triage_destination = "doctor"
            else:
                triage_destination = "home"
                
    if triage_destination == "":
        if has_chest_pain:
            triage_destination = "doctor"
            
    if triage_destination == "":
        if temp > 37.5 and bp_category == "high":
            triage_destination = "doctor"
            
    if triage_destination == "":
        triage_destination = "nurse"

    # 6. Treatment Rules (Accumulative)
    treatments = []

    if triage_destination == "doctor":
        if temp < 37.500001:
            treatments.append("Do EKG")
        else:
            treatments.append("Hospitalize")

    if temp > 37.5:
        treatments.append("Give Acamol")

    if bp_category == "low" and temp < 36.5:
        treatments.append("Give Vodka")

    # Format the dynamic actions
    triage_action = "Send home" if triage_destination == "home" else f"See {triage_destination.capitalize()}"
    treatment_action = ", ".join(treatments) if treatments else "None required"

    # 7. Printing the Header (if not suppressed)
    if not args.noheader:
        print("Temperature   Blood pressure    Chest pains   Triage Action   Treatment")
        print("-------------------------------------------------------------------------------------------------------")

    # 8. Printing the Data Row (Aligned dynamically to match header spacing)
    # Spacing pattern: 16 chars, 24 chars, 22 chars, 34 chars, rest
    print(f"{temp:<14}{bp:<18}{chest_pain_input:<14}{triage_action:<16}{treatment_action}")

if __name__ == "__main__":
    triage_and_treat()