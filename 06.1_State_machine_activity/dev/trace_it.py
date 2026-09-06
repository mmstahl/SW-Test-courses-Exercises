import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

# --- Simulating the missing environment variables and helper modules ---
TTWEAK_KEY = "state_machine_session"
DB_FILE = "session_state.json"

class ExtraMock:
    """Simulates the 'extra' database utility helper."""
    @staticmethod
    def update_db(strings_list, string):
        if string is None:
            strings_list.clear()
        else:
            strings_list.append(string)

    @staticmethod
    def read_db(strings_list):
        return strings_list

extra = ExtraMock()

class RequestMock:
    """Simulates the web request session for persistence."""
    def __init__(self):
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                try:
                    self.session = json.load(f)
                except json.JSONDecodeError:
                    self.session = {}
        else:
            self.session = {}

    def save(self):
        with open(DB_FILE, "w") as f:
            json.dump(self.session, f, indent=4)


# --- Google Form Ingestion Configuration ---
FORM_URL = "https://docs.google.com/forms/u/0/d/e/1FAIpQLSel5fb4PnWNCAAGMFjkXnyCXOiOQC4D9eJNuqd9IvDpZlVTPw/formResponse"
ENTRY_EMAIL_ADDRESS = "entry.1541405544"  # Form input field ID for Student's email
ENTRY_COMMAND = "entry.230643265"         # Form input field ID for the COMMAND value


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

def report_test_to_cloud(email_address, command):
    """Silently fires an HTTP POST payload to the Google Form ingress queue."""
    form_data = {
        ENTRY_EMAIL_ADDRESS: email_address,
        ENTRY_COMMAND: command
    }
    
    try:
        encoded_data = urllib.parse.urlencode(form_data).encode('utf-8')
        req = urllib.request.Request(FORM_URL, data=encoded_data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        with urllib.request.urlopen(req, timeout=5) as response:
            pass
    except Exception:
        pass

def print_custom_usage():
    """Prints the exact custom blurb required."""
    usage_text = """Usage: 
     trace_it.py COMMAND [--string STRING] [--index INDEX]
 Parameters: 
        COMMAND: one of: add, stop, query, sorry, state
     
      trace_it.py [-h] [--help] : print this usage message"""
    print(usage_text)


# --- The Implemented State Machine Class ---
class StateMachine:
    def __init__(self, request) -> None:
        self.session = request.session
        self.state = "StandBy"

        machine = self.session.get(TTWEAK_KEY)
        if not machine:
            machine = self.session[TTWEAK_KEY] = {"state": "StandBy", "strings": []}
        self.machine = machine

    def __str__(self) -> str:
        strings_content = ", ".join(self.get_strings())
        return f"State: {self.get_state()}, Strings: [{strings_content}]"

    def move_state(self, new_state):
        self.state = new_state
        if "StandBy" == self.state:
            self.clear_strings()
        self.machine["state"] = self.state

    def get_state(self):
        return self.machine["state"]

    def add_string(self, string):
        extra.update_db(self.machine["strings"], string)

    def get_strings(self):
        return extra.read_db(self.machine["strings"])

    def clear_strings(self):
        extra.update_db(self.machine["strings"], None)

    def act(self, command, string="", index=None):
        current_state = self.get_state()
        state_changed_or_handled = False
        
        if "state" == command:
            print(self)
            return "Ok"

        if "StandBy" == current_state:
            if "add" == command:
                state_changed_or_handled = True
                if not string:
                    self.move_state("Input")
                    
        elif "Input" == current_state:
            if "stop" == command:
                self.move_state("StandBy")
                state_changed_or_handled = True
            elif "add" == command:
                state_changed_or_handled = True
                if string:
                    self.add_string(string)
                if len(self.get_strings()) >= 3:
                    self.move_state("Query")
                    
        elif "Query" == current_state:
            if "stop" == command:
                self.move_state("StandBy")
                state_changed_or_handled = True
            elif "add" == command:
                self.move_state("Error")
                state_changed_or_handled = True
            elif "query" == command:
                state_changed_or_handled = True
                
                # Check if the index parameter is explicitly missing
                if index is None or str(index).strip() == "":
                    self.move_state("Error")
                    return "Error"
                
                # Validate numerical format and value boundaries (must be 1, 2, or 3)
                if type(index) == int or str(index).isnumeric():
                    idx_val = int(index)
                    if 1 <= idx_val <= 3 and idx_val <= len(self.get_strings()):
                        return self.get_strings()[idx_val - 1]
                
                # If validations fail, default transition to Error state
                self.move_state("Error")
                return "Error"
                    
        elif "Error" == current_state:
            if "stop" == command:
                self.move_state("StandBy")
                state_changed_or_handled = True
            elif "sorry" == command:
                self.move_state("Query")
                state_changed_or_handled = True

        if not state_changed_or_handled:
            raise RuntimeError(f"The command is not valid in this state ({current_state})")

        if "Error" == self.get_state():
            return "Error"
        return "Ok"


# --- Command Line Interface Execution ---
if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        print_custom_usage()
        sys.exit(0)

    # 1. Retrieve and prompt for the user identity first
    email_address = get_or_prompt_email_address()

    # 2. Log the raw transmission payload containing all system arguments joined by '|'
    raw_args = sys.argv[1:]
    test_id = "|".join(raw_args)
    report_test_to_cloud(email_address, test_id)

    # 3. Handle standard parsing via argparse (with disabled automatic help)
    parser = argparse.ArgumentParser(description="Execute StateMachine actions via CLI.", add_help=False)
    
    parser.add_argument("command", choices=["add", "stop", "query", "sorry", "state"], help="The action command.")
    parser.add_argument("--string", type=str, default="", help="The string to add.")
    parser.add_argument("--index", type=str, default=None, help="The 1-based index to query.")
    parser.add_argument("--reset", action="store_true", help="Force wipe the current session data.")

    try:
        args = parser.parse_args()
    except SystemExit:
        print_custom_usage()
        sys.exit(1)

    if args.reset and os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    request_mock = RequestMock()
    sm = StateMachine(request_mock)

    if args.command == "state":
        sm.act(command=args.command, string=args.string, index=args.index)
        sys.exit(0)

    try:
        before_action_text = f"Before Action -> {sm}"
        result = sm.act(command=args.command, string=args.string, index=args.index)
        
        print(before_action_text)
        request_mock.save()

        print(f"Action Result -> {result}")
        print(f"After Action  -> {sm}")

    except RuntimeError as state_err:
        print(state_err, file=sys.stderr)
        sys.exit(1)