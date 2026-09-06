#!/usr/bin/env python3
import csv
import subprocess
import sys
import argparse

SCRIPT_TO_RUN = "Get_a_room.py"

def run_test_case(check_in, check_out, single=0, double=0, suite=0, debug=False):
    """
    Executes Get_a_room.py via subprocess and returns captured output.
    """
    cmd = [
        sys.executable,  # Uses current Python interpreter
        SCRIPT_TO_RUN,
        str(check_in),
        str(check_out),
        "--single", str(single),
        "--double", str(double),
        "--suite", str(suite)
    ]

    # Add --bugit flag if debug column is True / 1 / yes
    if str(debug).strip().lower() in ["true", "1", "yes"]:
        cmd.append("--bugit")

    try:
        # Capture stdout; stderr is hidden to keep stdout output clean if PRINT_DB is active
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return f"EXIT {result.returncode}"
        
        # Take the final line of output (handles cases where PRINT_DB is active)
        lines = result.stdout.strip().splitlines()
        return lines[-1] if lines else "NO OUTPUT"

    except Exception as e:
        return f"ERROR: {e}"

def main():
    parser = argparse.ArgumentParser(description="Run test cases against Get_a_room.py from a CSV file.")
    parser.add_argument(
        "csv_file", 
        nargs="?", 
        default="test_cases.csv", 
        help="Path to test cases CSV file (default: test_cases.csv)"
    )
    args = parser.parse_args()

    csv_filename = args.csv_file
    results_table = []

    try:
        with open(csv_filename, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)

            for row in reader:
                check_in = row.get('check_in', '')
                check_out = row.get('check_out', '')
                single = row.get('single', '0')
                double = row.get('double', '0')
                suite = row.get('suite', '0')
                debug = row.get('debug', 'False')

                # Execute test case and capture output
                output = run_test_case(check_in, check_out, single, double, suite, debug)

                # Store row and result for tabular display
                results_table.append({
                    'check_in': check_in,
                    'check_out': check_out,
                    'single': single,
                    'double': double,
                    'suite': suite,
                    'debug': debug,
                    'output': output
                })

        # Display Collected Results Table
        header = f"{'Check-in':<10} | {'Check-out':<10} | {'Single':<7} | {'Double':<7} | {'Suite':<7} | {'Debug':<6} | Output"
        divider = "-" * len(header)

        print(divider)
        print(f"TEST EXECUTION RESULTS ({csv_filename})")
        print(divider)
        print(header)
        print(divider)

        for res in results_table:
            print(f"{res['check_in']:<10} | {res['check_out']:<10} | {res['single']:<7} | {res['double']:<7} | {res['suite']:<7} | {str(res['debug']):<6} | {res['output']}")
        
        print(divider)

    except FileNotFoundError:
        print(f"Error: Could not find file '{csv_filename}'. Ensure it exists in the working directory.")
    except KeyError as e:
        print(f"Error: Missing expected column in CSV header: {e}")

if __name__ == "__main__":
    main()