#!/usr/bin/env python3
import argparse
import random
import subprocess
import sys
from datetime import datetime, timedelta

SCRIPT_NAME = "get_a_room.py"
START_BOUND = datetime(2026, 10, 1)
END_BOUND = datetime(2028, 9, 30)

def run_search(check_in, check_out, single, double, suite, bugit=0):
    """
    Executes get_a_room.py via CLI subprocess and returns the integer result.
    """
    cmd = [
        sys.executable,
        SCRIPT_NAME,
        check_in.strftime("%d/%m/%Y"),
        check_out.strftime("%d/%m/%Y"),
        "--single", str(single),
        "--double", str(double),
        "--suite", str(suite)
    ]

    if bugit > 0:
        cmd.extend(["--bugit", str(bugit)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse output string "Number of hotels that meet your needs: X"
        for line in result.stdout.strip().split("\n"):
            if "Number of hotels that meet your needs:" in line:
                return int(line.split(":")[-1].strip())
                
        raise ValueError(f"Could not parse count from CLI output: {result.stdout}")

    except subprocess.CalledProcessError as e:
        print(f"\nCLI Execution Error: {e.stderr}")
        sys.exit(1)

def print_test_params(label, check_in, check_out, s, d, st, result):
    """Helper function to print formatted test parameters and output."""
    print(f"  [{label}] Dates: {check_in.strftime('%d/%m/%Y')} -> {check_out.strftime('%d/%m/%Y')} | "
          f"Rooms: (S:{s}, D:{d}, St:{st}) | Result: {result}")

def get_baseline_parameters(max_days_offset, bugit):
    """Generates random valid parameters and runs step 3 baseline search."""
    while True:
        random_start_offset = random.randint(0, max_days_offset - 30)
        check_in_base = START_BOUND + timedelta(days=random_start_offset)
        stay_duration = random.randint(1, 30)
        check_out_base = check_in_base + timedelta(days=stay_duration)

        s_base = random.randint(0, 10)
        d_base = random.randint(0, 10)
        st_base = random.randint(0, 10)

        res_step3 = run_search(check_in_base, check_out_base, s_base, d_base, st_base, bugit=bugit)
        
        if res_step3 >= 10:
            return check_in_base, check_out_base, s_base, d_base, st_base, res_step3

def main():
    parser = argparse.ArgumentParser(description="Automated Metamorphic Test Suite for get_a_room.py")
    parser.add_argument(
        "--num_of_cycles",
        type=int,
        default=100,
        help="Number of test cycles per parameter expansion (1 to 100). Default: 100"
    )
    parser.add_argument(
        "--bugit",
        type=int,
        default=0,
        choices=range(0, 16),
        metavar="[0-15]",
        help="Integer bitmask (0-15) enabling specific bugs. Default: 0"
    )

    args = parser.parse_args()

    # Validate num_of_cycles range
    if not (1 <= args.num_of_cycles <= 100):
        print(f"Error: --num_of_cycles must be an integer between 1 and 100. Got: {args.num_of_cycles}")
        sys.exit(1)

    max_days_offset = (END_BOUND - START_BOUND).days
    found_bugs = {}
    attempts = {'date': 0, 'single': 0, 'double': 0, 'suite': 0}

    print(f"Starting test suite execution (Max cycles per parameter: {args.num_of_cycles}, --bugit bitmask: {args.bugit})...\n")

    # ==========================================================================
    # PHASE 1: DATE EXPANSION TESTS
    # ==========================================================================
    for cycle in range(1, args.num_of_cycles + 1):
        attempts['date'] = cycle
        print(f"\rRunning day-expansion tests. Cycle: {cycle}", end="", flush=True)

        check_in_base, check_out_base, s_base, d_base, st_base, res_step3 = get_baseline_parameters(max_days_offset, args.bugit)
        
        current_check_out = check_out_base
        prev_check_out = check_out_base
        previous_res = res_step3

        bug_found_in_run = False
        while True:
            current_check_out += timedelta(days=1)
            res_current = run_search(check_in_base, current_check_out, s_base, d_base, st_base, bugit=args.bugit)

            if res_current == 0 or current_check_out >= END_BOUND:
                break

            if res_current <= previous_res:
                previous_res = res_current
                prev_check_out = current_check_out
                continue
            else:
                found_bugs['date'] = {
                    'baseline': (check_in_base, check_out_base, s_base, d_base, st_base, res_step3),
                    'one_before': (check_in_base, prev_check_out, s_base, d_base, st_base, previous_res),
                    'failing': (check_in_base, current_check_out, s_base, d_base, st_base, res_current)
                }
                print("\nFound a day-expansion bug")
                bug_found_in_run = True
                break

        if bug_found_in_run:
            break

    if 'date' not in found_bugs:
        print(f"\nNo bugs in {args.num_of_cycles} test cycles of day expansion")

    # ==========================================================================
    # PHASE 2-4: ROOM EXPANSION TESTS
    # ==========================================================================
    def run_room_phase(room_type):
        for cycle in range(1, args.num_of_cycles + 1):
            attempts[room_type] = cycle
            print(f"\rRunning {room_type}-expansion tests. Cycle: {cycle}", end="", flush=True)

            check_in_base, check_out_base, s_base, d_base, st_base, res_step3 = get_baseline_parameters(max_days_offset, args.bugit)

            curr_s, curr_d, curr_st = s_base, d_base, st_base
            prev_s, prev_d, prev_st = s_base, d_base, st_base
            prev_res = res_step3

            bug_found_in_run = False
            while True:
                if room_type == "single":
                    curr_s += 1
                    target_val = curr_s
                elif room_type == "double":
                    curr_d += 1
                    target_val = curr_d
                elif room_type == "suite":
                    curr_st += 1
                    target_val = curr_st

                if target_val > 30:
                    break

                res_curr = run_search(check_in_base, check_out_base, curr_s, curr_d, curr_st, bugit=args.bugit)

                if res_curr == 0:
                    break

                if res_curr <= prev_res:
                    prev_res = res_curr
                    prev_s, prev_d, prev_st = curr_s, curr_d, curr_st
                    continue
                else:
                    found_bugs[room_type] = {
                        'baseline': (check_in_base, check_out_base, s_base, d_base, st_base, res_step3),
                        'one_before': (check_in_base, check_out_base, prev_s, prev_d, prev_st, prev_res),
                        'failing': (check_in_base, check_out_base, curr_s, curr_d, curr_st, res_curr)
                    }
                    print(f"\nFound a {room_type}-expansion bug")
                    bug_found_in_run = True
                    break

            if bug_found_in_run:
                break

        if room_type not in found_bugs:
            print(f"\nNo bugs in {args.num_of_cycles} test cycles of {room_type} expansion")

    # Run remaining room expansions sequentially
    run_room_phase("single")
    run_room_phase("double")
    run_room_phase("suite")

    # ==========================================================================
    # FINAL RESULTS SUMMARY
    # ==========================================================================
    print("\n\n" + "=" * 60)
    print("TEST SUITE EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Total BUGS Found: {len(found_bugs)} / 4")
    for category in ['date', 'single', 'double', 'suite']:
        print(f"  - {category.capitalize()} Escalation Attempts: {attempts[category]}/{args.num_of_cycles}")

    if found_bugs:
        print("\n" + "!" * 40)
        print("DISCOVERED BUG DETAILS")
        print("!" * 40)

        for bug_type, bug_data in found_bugs.items():
            print(f"\n--- BUG TYPE: {bug_type.upper()} EXPANSION ---")
            print_test_params("Baseline Test (Step 3)", *bug_data['baseline'])
            print_test_params("One-Before-Failing Test", *bug_data['one_before'])
            print_test_params("Failing Test", *bug_data['failing'])

    print("\nExecution complete.")

if __name__ == "__main__":
    main()