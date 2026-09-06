import sys
import os
import urllib.request
import urllib.parse

check_age_version = "V99"

# Standard ANSI color codes for universal terminal support
GREEN = "\033[32m"  
RED = "\033[31m"
RESET = "\033[0m"

# -----------------------------------------------------------------------------
# GOOGLE FORM INGESTION CONFIGURATION
# -----------------------------------------------------------------------------
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdgKClabX46IJ8YZggzo17ihF3ou9TdquQdBpryFqOsQ-nLtw/formResponse"
ENTRY_EMAIL_ADDRESS = "entry.1038110062"  # Form input field ID for Student's email
ENTRY_INPUT = "entry.1050115853"         # Form input field ID for input parameters (All parameters separated by |)
ENTRY_VERSION = "entry.530224207"   # Form input field ID for code version (v99 or v100)

CACHE_FILE = ".student_id.txt"

def get_or_prompt_email_address():
    """Reads the cached student email or prompts for a new one with domain validation."""
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

def report_test_to_cloud(email_address, test_id):
    """Silently fires an HTTP POST payload to the Google Form ingress queue."""
    form_data = {
        ENTRY_EMAIL_ADDRESS: email_address,
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

def print_usage():
    """Prints a helpful usage guide to the terminal."""
    usage = """
Dynamic Age Rule Validator

Usage:
  python script.py <Code version> <Age1> <Age2> ... [Age6]

Parameters:
  <Code version>  An integer from 0 to 6, or the word 'All' (case-insensitive).
  <Age1>...[Age6] At least 1 and up to 6 age values (integers between 0 and 120).

Constraints:
  - Accepts a minimum of 2 parameters (Code version + 1 Age).
  - Accepts a maximum of 7 parameters (Code version + 6 Ages).
    """
    print(usage.strip())

def color_age(age):
    """
    Applies simplified absolute coloring logic based solely on the age value:
      - Age <= 99  is ALWAYS Green
      - Age >= 100 is ALWAYS Red
    """
    if age <= 99:
        return f"{GREEN}{age}{RESET}"
    else:
        return f"{RED}{age}{RESET}"

def main():
    # Retrieve and prompt for the user identity first
    email_address = get_or_prompt_email_address()

    # Parse and extract script parameters
    args = sys.argv[1:]
    num_params = len(args)
    
    # Log the transmission payload containing all arguments joined by '|'
    test_id = "|".join(args)
    report_test_to_cloud(email_address, test_id)
    
    # 1. Print usage blurb if invoked with no parameters
    if num_params == 0:
        print_usage()
        sys.exit(0)
        
    # Validate parameter count
    if num_params < 2:
        print(f"Error: The script requires at least 2 parameters. You provided {num_params}.", file=sys.stderr)
        sys.exit(1)
        
    if num_params > 7:
        print(f"Error: The script accepts a maximum of 7 parameters. You provided {num_params}.", file=sys.stderr)
        sys.exit(1)

    # 2. Extract and validate 'Code version'
    raw_code_version = args[0]
    code_version = None
    
    try:
        val = int(raw_code_version)
        if 0 <= val <= 6:
            code_version = val
        else:
            print(f"Error: 'Code version' integer must be between 0 and 6. Got {val}.", file=sys.stderr)
            sys.exit(1)
    except ValueError:
        lower_val = raw_code_version.lower()
        if lower_val == "all":
            code_version = "all"
        else:
            print(f"Error: Invalid 'Code version' parameter '{raw_code_version}'. It must be an integer (0-6) or the word 'All'.", file=sys.stderr)
            sys.exit(1)

    # 3. Extract and validate Age parameters (Collecting ALL errors across up to 6 ages)
    raw_ages = args[1:]
    ages = []
    errors = []
    
    for i, raw_age in enumerate(raw_ages, start=1):
        try:
            age_val = int(raw_age)
            if not (0 <= age_val <= 120):
                errors.append(f"Parameter 'Age{i}' ('{age_val}') out of bounds. Age must be between 0 and 120.")
            else:
                ages.append(age_val)
        except ValueError:
            errors.append(f"Parameter 'Age{i}' ('{raw_age}') is not a valid integer.")
            
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    # Determine which code versions need to be executed
    versions_to_run = [code_version] if code_version != "all" else list(range(7))
    
    # We unique the incoming ages to avoid duplicates in the comma-separated lists
    unique_ages = sorted(list(set(ages)))

    # 4. Loop through code versions and age parameters to execute business logic
    table_rows = []
    
    for v in versions_to_run:
        accepted_ages = []
        rejected_ages = []
        
        for age in unique_ages:
            approved = False
            
            if v == 0:
                if age < 99:
                    approved = True
            elif v == 1:
                if age > 99:
                    approved = True
            elif v == 2:
                if age != 99:
                    approved = True
            elif v == 3:                   # This is the correct implementation!
                if age <= 99:
                    approved = True
            elif v == 4:
                if age >= 99:
                    approved = True
            elif v == 5:
                # This code version simulates the case where the age check is incorrectly coded as : "if age := 99"
                # The error sets 'age' to be 99, regardless to the input, so it's alway accepted. 
                # If I actually put this code line in the script (and not commented out), it actually changes to input 
                # age values to 99, for all inputs, and then the output is strange (prints 99 as if these were all the inputs)  
                approved = True
            elif v == 6:
                if age == 99:
                    approved = True
                    
            if approved:
                accepted_ages.append(age)
            else:
                rejected_ages.append(age)
        
        # Colorize ages individually before combining them
        colored_accepted = [color_age(age) for age in sorted(accepted_ages)]
        colored_rejected = [color_age(age) for age in sorted(rejected_ages)]
        
        accepted_str = ", ".join(colored_accepted) if accepted_ages else "-"
        rejected_str = ", ".join(colored_rejected) if rejected_ages else "-"
        
        table_rows.append((v, accepted_str, rejected_str))

    # 5. Sort table rows strictly by Code version value
    table_rows.sort(key=lambda x: x[0])

    # 6. Print the updated formatted table with colored headers
    header_accepted = f"{GREEN}Accepted{RESET}"
    header_rejected = f"{RED}Rejected{RESET}"
    
    # Printing header. Width calculations manual here because color codes skew standard string format formatting lengths
    print(f"{'Code version':<15} {header_accepted:<44} {header_rejected:<44}")
    print("-" * 88)
    
    for v, accepted, rejected in table_rows:
        # Manually calculate padding lengths because ANSI escape codes skew basic len() calculations
        raw_accepted_len = len(accepted.replace(GREEN, "").replace(RED, "").replace(RESET, ""))
        raw_rejected_len = len(rejected.replace(GREEN, "").replace(RED, "").replace(RESET, ""))
        
        pad_accepted = " " * max(0, 35 - raw_accepted_len)
        pad_rejected = " " * max(0, 35 - raw_rejected_len)
        
        print(f"{v:<15} {accepted}{pad_accepted} {rejected}{pad_rejected}")

if __name__ == "__main__":
    main()