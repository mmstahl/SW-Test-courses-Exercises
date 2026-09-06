#!/usr/bin/env python3
"""
Hotel Reservation CLI Search Tool (Metamorphic Testing Testbed)
==============================================================
This tool queries hotel availability across 100 hotels for specified date ranges
and room requirements.
"""

import sys
import argparse
import random
import re
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

# ==============================================================================
# GOOGLE FORM INGESTION CONFIGURATION
# ==============================================================================
FORM_URL = "https://docs.google.com/forms/u/0/d/e/1FAIpQLSeF6rrxLdsWROGjIm5WiNkSq2tCG9YzcwhHMWOXy9ehG2OA-Q/formResponse"
ENTRY_EMAIL_ADDRESS = "entry.1115292615"
ENTRY_INPUT = "entry.814246440"

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

def report_test_to_cloud(email_address, input_data):
    """Silently fires an HTTP POST payload to the Google Form ingress queue."""
    form_data = {
        ENTRY_EMAIL_ADDRESS: email_address,
        ENTRY_INPUT: input_data
    }
    
    try:
        encoded_data = urllib.parse.urlencode(form_data).encode('utf-8')
        req = urllib.request.Request(FORM_URL, data=encoded_data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        with urllib.request.urlopen(req, timeout=5) as response:
            pass
    except Exception:
        pass

# ==============================================================================
# BUG CONFIGURATION PANEL
# ==============================================================================
ACTIVATE_BUGS = 0  # Default bitmask (0 = No bugs, 15 = All bugs activated)
PRINT_DB = False   # Debug switch (True = Print full database table, False = Normal execution)

# Bug Thresholds & Limits

# Bug A
# When date span X > BUG_A_MAX_DAYS, reduce checkout date by BUG_A_MAX_DAYS,
# unless it makes checkout <= checkin.
BUG_A_MAX_DAYS = 10

# Bug B
# Single Room Reduction
# When single rooms Y > 2 * BUG_B_SINGLE_THRESHOLD, reduce requested single rooms by BUG_B_SINGLE_THRESHOLD (bounded below by 1).
BUG_B_SINGLE_THRESHOLD = 4

# Bug C
# Double Room Range Reduction
# If double rooms Z is between BUG_C_DOUBLE_MIN and BUG_C_DOUBLE_MAX (inclusive), reduce it by 2.
#  NOTE: need to make sure when setting the MIN and MAX that MIN-2 does not end up with 0 or less.
BUG_C_DOUBLE_MIN = 4
BUG_C_DOUBLE_MAX = 7


# Bug D
# Studio/Suite Check-in Shift
# If studio/suite count W > BUG_D_SUITE_THRESHOLD, advance check-in date by W-BUG_D_SUITE_THRESHOLD days,
# but stop when check-in date is one day before check-out date. If the initial requested length of stay is 1 day, do not shift check-in.
BUG_D_SUITE_THRESHOLD = 2


# ==============================================================================
# DATA ARCHITECTURE & SEEDED GENERATOR
# ==============================================================================
START_DATE = datetime(2026, 10, 1)

# END_DATE = datetime(2026, 11, 15)  # Extended window for Bug A shifting
END_DATE = datetime(2028, 10, 31)  # Extended window for Bug A shifting
#CLI_VALID_END_DATE = datetime(2026, 11, 10)
CLI_VALID_END_DATE = datetime(2028, 9, 30)

def generate_hotel_database(seed=42):
    """
    Generates deterministic in-memory hotel data for 100 hotels.
    """
    random.seed(seed)
    
    # 1. Generate Hotel Room Capacities
    hotels = {}
    for hotel_id in range(1, 101):
        total_rooms = random.randint(20, 80)
        # Every hotel must have at least 5 of each room type
        singles = 5
        doubles = 5
        suites = 5
        remaining = total_rooms - 15
        
        # Distribute remaining rooms randomly
        for _ in range(remaining):
            choice = random.choice(['single', 'double', 'suite'])
            if choice == 'single':
                singles += 1
            elif choice == 'double':
                doubles += 1
            else:
                suites += 1
                
        hotels[hotel_id] = {
            'max_single': singles,
            'max_double': doubles,
            'max_suite': suites,
            'availability': {} # Date string -> {'single': int, 'double': int, 'suite': int}
        }

    # 2. Generate 4-Month Baseline Room Availability (Oct 2026 - Jan 2027)
    # Baseline months: Oct(31 days), Nov(30 days), Dec(31 days), Jan(31 days)
    baseline_data = {} # (month, day) -> {hotel_id: {'single': x, 'double': y, 'suite': z}}
    
    # Oct 2026 (m=10, 31d), Nov 2026 (m=11, 30d), Dec 2026 (m=12, 31d), Jan 2027 (m=1, 31d)
    baseline_months = [(10, 31), (11, 30), (12, 31), (1, 31)]
    
    for month, days_in_m in baseline_months:
        for day in range(1, days_in_m + 1):
            day_avail = {}
            for h_id, h_info in hotels.items():
                # Random free rooms bounded by max capacity. At least 3 are free at any date. 
                free_s = random.randint(0, h_info['max_single'])
                free_d = random.randint(0, h_info['max_double'])
                free_st = random.randint(0, h_info['max_suite'])
                day_avail[h_id] = {'single': free_s, 'double': free_d, 'suite': free_st}
            baseline_data[(month, day)] = day_avail

    # 3. Map Baseline Data across Full Range (Oct 1, 2026 to Oct 31, 2028)
    current_curr = START_DATE
    while current_curr <= END_DATE:
        m = current_curr.month
        d = current_curr.day
        
        # Determine mapping based on month length
        if m in [1, 3, 5, 7, 8, 10, 12]:  # 31-day months mirror Oct baseline (m=10)
            mapped_key = (10, min(d, 31))
        elif m in [4, 6, 9, 11]:          # 30-day months mirror Nov baseline (m=11)
            mapped_key = (11, min(d, 30))
        else:                             # Feb (28 days) mirrors Jan baseline (m=1) first 28 days
            mapped_key = (1, min(d, 28))
            
        daily_snapshot = baseline_data[mapped_key]
        
        date_str = current_curr.strftime('%Y-%m-%d')
        for h_id in hotels:
            hotels[h_id]['availability'][date_str] = daily_snapshot[h_id]
            
        current_curr += timedelta(days=1)

    return hotels


# ==============================================================================
# DEBUG / PRINT DATABASE TABLE
# ==============================================================================
def print_database_table(db):
    """
    Prints a structured text table of room availability per hotel across dates.
    """
    all_dates = sorted(list(next(iter(db.values()))['availability'].keys()))
    
    header = f"{'Hotel ID':<10} | {'Date':<10} | {'Free Single':<12} | {'Free Double':<12} | {'Free Suite':<12}"
    divider = "-" * len(header)
    
    print(divider)
    print("DATABASE AVAILABILITY TABLE")
    print(divider)
    print(header)
    print(divider)
    
    for h_id in sorted(db.keys()):
        h_data = db[h_id]
        for date_str in all_dates:
            avail = h_data['availability'][date_str]
            s = avail['single']
            d = avail['double']
            st = avail['suite']
            print(f"{h_id:<10} | {date_str:<10} | {s:<12} | {d:<12} | {st:<12}")
        print(divider)


# ==============================================================================
# CLI PARSER & INPUT VALIDATION
# ==============================================================================
def parse_date(date_str):
    """
    Parses date string formatted as d/mm/yy, dd/mm/yy, d/mm/yyyy, dd/mm/yyyy,
    as well as single-digit months (d/m/yy, dd/m/yy, etc.).
    Accepts leading zeros on the day and month component.
    Strictly validates month (1..12), day validity per month/year, 
    and year bounds (2026..2028 or 26..28).
    """
    try:
        if not re.match(r"^\d{1,2}/\d{1,2}/(\d{2}|\d{4})$", date_str):
            raise ValueError("Date must be formatted as dd/mm/yy or dd/mm/yyyy (e.g., 01/10/26, 1/10/26, or 01/10/2026).")

        parts = date_str.split('/')
        day = int(parts[0])
        month = int(parts[1])
        year_val = int(parts[2])
        
        # 1. Validate Year Range (accepts 26-28 or 2026-2028)
        if year_val in [26, 27, 28]:
            full_year = 2000 + year_val
        elif year_val in [2026, 2027, 2028]:
            full_year = year_val
        else:
            raise ValueError(f"Year '{parts[2]}' is out of range. Year must be between 2026 and 2028 (or 26 and 28).")
            
        # 2. Validate Month Range
        if not (1 <= month <= 12):
            raise ValueError(f"Month '{month}' is invalid. Month must be between 1 and 12.")
        
        # 3. Validate Day Range per Month/Year
        # 31-day months: Jan(1), Mar(3), May(5), Jul(7), Aug(8), Oct(10), Dec(12)
        # 30-day months: Apr(4), Jun(6), Sep(9), Nov(11)
        # Feb(2): 2028 is a leap year (29 days), 2026/2027 are not (28 days)
        if month in [1, 3, 5, 7, 8, 10, 12]:
            max_days = 31
        elif month in [4, 6, 9, 11]:
            max_days = 30
        elif month == 2:
            # Leap year check for 2028
            is_leap = (full_year % 4 == 0 and (full_year % 100 != 0 or full_year % 400 == 0))
            max_days = 29 if is_leap else 28
            
        if not (1 <= day <= max_days):
            raise ValueError(f"Invalid day {day} for month {month} in year {full_year}.")

        # Construct and return datetime object
        dt = datetime(full_year, month, day)
        return dt

    except ValueError as ve:
        print(f"Error parsing date '{date_str}': {ve}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error parsing date '{date_str}': {e}")
        sys.exit(1)

# ==============================================================================
# SEARCH ENGINE & BUG IMPLEMENTATION
# ==============================================================================
def count_available_hotels(db, check_in, check_out, single, double, suite, bugit_mask=0):
    """
    Evaluates hotel availability for requested date range and rooms.
    bugit_mask is an integer bitmask (0..15):
      Bit 3 (8): Bug A (Date Span Truncation)
      Bit 2 (4): Bug B (Single Room Reduction)
      Bit 1 (2): Bug C (Double Room Range Reduction)
      Bit 0 (1): Bug D (Suite Check-in Shift)
    """
    # Parse and Validate Room Counts
    req_s = max(0, single)
    req_d = max(0, double)
    req_st = max(0, suite)

    # --------------------------------------------------------------------------
    # PREMEDITATED BUG INJECTIONS
    # --------------------------------------------------------------------------
    if bugit_mask > 0:
        # Bug A (Bit 3 / Value 8): Date Span Truncation
        if (bugit_mask & 8) != 0:
            date_span = (check_out - check_in).days
            if date_span > BUG_A_MAX_DAYS:
                new_check_out = check_out - timedelta(days=BUG_A_MAX_DAYS)
                if new_check_out > check_in:
                    check_out = new_check_out

        # Bug B (Bit 2 / Value 4): Single Room Reduction
        if (bugit_mask & 4) != 0:
            if req_s > BUG_B_SINGLE_THRESHOLD:
                req_s = max(1, 2 * BUG_B_SINGLE_THRESHOLD - req_s)

        # Bug C (Bit 1 / Value 2): Double Room Range Reduction
        if (bugit_mask & 2) != 0:
            if BUG_C_DOUBLE_MIN <= req_d <= BUG_C_DOUBLE_MAX:
                req_d -= 2

        # Bug D (Bit 0 / Value 1): Studio/Suite Check-in Shift
        if (bugit_mask & 1) != 0:
            if req_st > BUG_D_SUITE_THRESHOLD:
                stay_days = (check_out - check_in).days
                if stay_days > 1:
                    desired_shift = req_st - BUG_D_SUITE_THRESHOLD
                    max_shift = stay_days - 1
                    actual_shift = min(desired_shift, max_shift)
                    check_in += timedelta(days=actual_shift)

    # Build List of Stay Nights (check-in up to check-out - 1 day)
    stay_nights = []
    curr = check_in
    while curr < check_out:
        stay_nights.append(curr.strftime('%Y-%m-%d'))
        curr += timedelta(days=1)

    available_count = 0

    # Evaluate Each Hotel
    for h_id, h_data in db.items():
        is_hotel_suitable = True
        
        for night_str in stay_nights:
            # Fallback for unexpected date lookup safety
            night_avail = h_data['availability'].get(night_str, {'single': 0, 'double': 0, 'suite': 0})
            free_s = night_avail['single']
            free_d = night_avail['double']
            free_st = night_avail['suite']

            if not (free_s >= req_s and free_d >= req_d and free_st >= req_st):
                is_hotel_suitable = False
                break
                    
        if is_hotel_suitable:
            available_count += 1

    return available_count


# ==============================================================================
# MAIN CLI ENTRY POINT
# ==============================================================================
def main():
    global ACTIVATE_BUGS

    # 1. Retrieve user identity and log raw command line input to Google Form
    email_address = get_or_prompt_email_address()
    raw_args = sys.argv[1:]
    input= "|".join(raw_args)
    report_test_to_cloud(email_address, input)

    parser = argparse.ArgumentParser(
        prog="Get_a_room.exe",
        description="Hotel Reservation CLI Search System",
        usage="Get_a_room.exe check_in_date check_out_date [--single SINGLE] [--double DOUBLE] [--suite SUITE] [--bugit BUGIT] [-h]"
    )
    
    parser.add_argument(
        "check_in", 
        metavar="check_in_date", 
        help="Check-in date formatted as d/mm/yy, dd/mm/yy, d/mm/yyyy, or dd/mm/yyyy (leading zeros accepted)."
    )
    parser.add_argument(
        "check_out", 
        metavar="check_out_date", 
        help="Check-out date formatted as d/mm/yy, dd/mm/yy, d/mm/yyyy, or dd/mm/yyyy (leading zeros accepted)."
    )
    parser.add_argument(
        "--single", 
        type=int, 
        default=0, 
        help="Number of single rooms requested (integer)."
    )
    parser.add_argument(
        "--double", 
        type=int, 
        default=0, 
        help="Number of double rooms requested (integer)."
    )
    parser.add_argument(
        "--suite", 
        type=int, 
        default=0, 
        help="Number of suite rooms requested (integer)."
    )
    parser.add_argument(
        "--bugit", 
        type=int,
        default=0,
        choices=range(0, 16),
        metavar="[0-15]",
        help=argparse.SUPPRESS
    )

    # Print help blurb if no arguments are provided
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    ACTIVATE_BUGS = args.bugit

    # Parse and Validate Input Dates
    dt_check_in = parse_date(args.check_in)
    dt_check_out = parse_date(args.check_out)

    # Validate CLI Boundaries & Date Order
    start_str = START_DATE.strftime('%d/%m/%Y')
    end_str = CLI_VALID_END_DATE.strftime('%d/%m/%Y')

    if dt_check_in < START_DATE or dt_check_in > CLI_VALID_END_DATE:
        print(f"Error: Check-in date ({args.check_in}) must be within the valid search window ({start_str} to {end_str}).")
        sys.exit(1)
    if dt_check_out < START_DATE or dt_check_out > CLI_VALID_END_DATE:
        print(f"Error: Check-out date ({args.check_out}) must be within the valid search window ({start_str} to {end_str}).")
        sys.exit(1)
    if dt_check_out <= dt_check_in:
        print(f"Error: Check-out date ({args.check_out}) must be strictly after check-in date ({args.check_in}).")
        sys.exit(1)

    # Generate Deterministic In-Memory Database
    db = generate_hotel_database(seed=42)

    # Optional DB Print
    if PRINT_DB:
        print_database_table(db)

    # Calculate Availability
    result_count = count_available_hotels(
        db, 
        dt_check_in, 
        dt_check_out, 
        args.single, 
        args.double, 
        args.suite,
        bugit_mask=ACTIVATE_BUGS
    )

    # Output exact integer count
    print(f'\nNumber of hotels that meet your needs: {result_count}' )

if __name__ == "__main__":
    main()