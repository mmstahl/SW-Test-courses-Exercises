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

    # 3. Category Validations & Mappings
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
    # M represents the "healthy" bracket (36.5 to 37.5)
    temp_category = "healthy" if temp_input == 'M' else "unhealthy"
    has_chest_pain = (chest_pain_input == 'Y')

    # 4. Triage Rules
    triage_destination = ""
    
    if triage_destination == "":
        # Rule 1: healthy temp (M) and low BP (L) -> send home, unless they report chest pains
        if temp_category == "healthy" and bp_input == 'L':
            if has_chest_pain:
                triage_destination = "doctor"
            else:
                triage_destination = "home"
                
    if triage_destination == "":
        # Rule 2: Anyone with chest pains -> see doctor
        if has_chest_pain:
            triage_destination = "doctor"
            
    if triage_destination == "":
        # Rule 3: High temperature (H) and high blood pressure (H) -> see doctor
        if temp_input == 'H' and bp_input == 'H':
            triage_destination = "doctor"
            
    if triage_destination == "":
        # Rule 4: anything else -> see nurse
        triage_destination = "nurse"

    # 5. Treatment Rules (Accumulative)
    treatments = []

    # Rule A: Doctor flow
    if triage_destination == "doctor":
        # The previous boundary was < 37.500001 for EKG. 
        # In categorical terms, this maps strictly to 'L' (low) and 'M' (medium/healthy).
        # Only 'H' (High) is explicitly >= 37.500001.
        if temp_input in ['L', 'M']:
            treatments.append("Do EKG")
        else:
            treatments.append("Hospitalize")

    # Rule B: High temperature (H) -> Acamol
    if temp_input == 'H':
        treatments.append("Give Acamol")

    # Rule C: Low BP (L) and temperature below 36.5 (L) -> give Vodka
    if bp_input == 'L' and temp_input == 'L':
        treatments.append("Give Vodka")

    # Format the final text output strings
    triage_action = "Send home" if triage_destination == "home" else f"See {triage_destination.capitalize()}"
    treatment_action = ", ".join(treatments) if treatments else "None required"

    # 6. Printing the Header (if not suppressed)
    if not args.noheader:
        print("Temperature   Blood pressure    Chest pains   Triage Action   Treatment")
        print("-------------------------------------------------------------------------------------------------------")

    # 7. Printing the Data Row (Aligned to match column spacing)
    print(f"{temp_input:<14}{bp_input:<18}{chest_pain_input:<14}{triage_action:<16}{treatment_action}")
    


if __name__ == "__main__":
    triage_and_treat()