"""
keyword_runner.py -- Keyword-Driven Test Automation Framework for Phone Shop UI.

Reads keyword commands from a text file and executes Selenium test actions.

Usage:
    python keyword_runner.py --email alice@post.jce.ac.il --tests-file test_cases.txt
    python keyword_runner.py -h
    python keyword_runner.py --help
"""

import argparse
import os
import re
import sys
import time

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

# ---------------------------------------------------------------------
# Global Test Automation State Variables
# ---------------------------------------------------------------------
CONFIG = {
    "model": "Pixel 9",
    "storage": "128GB",
    "color": "Black",
    "network": "5G",
    "accessory": "None",
}
PRICE = 0.0
DISCOUNT_CODE = ""
CREDIT = 0.0

SELECT_IDS = {
    "model": "model-select",
    "storage": "storage-select",
    "color": "color-select",
    "network": "network-select",
    "accessory": "accessory-select",
}

REMOTE_BASE_URL = "https://sw-test-courses-exercises.vercel.app"
LOCAL_BASE_URL = "http://localhost:3000"
REQUIRED_EMAIL_DOMAIN = "@post.jce.ac.il"

# ANSI escape codes for PASS/FAIL coloring. Everything else keeps
# printing in the terminal's default color (no code = no change).
if sys.platform == "win32":
    # Windows' own console (unlike Windows Terminal/git-bash/most others)
    # doesn't interpret ANSI escapes until this is switched on -- this is
    # the well-known no-dependency way to do that (what colorama does
    # internally), cheaper than adding a new pip dependency for it.
    os.system("")
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_RESET = "\033[0m"


def colorize(text: str, passed: bool) -> str:
    return f"{COLOR_GREEN if passed else COLOR_RED}{text}{COLOR_RESET}"


# Same shape execute_keyword() parses steps with -- reused so a
# keyword-shaped line found outside any # test/# end test block (where
# only Reset() is valid) gets the same case-insensitive name check.
KEYWORD_LINE_RE = re.compile(r"^([a-zA-Z0-9_]+)\s*\((.*?)\)\s*$")

KEYWORD_HELP_TEXT = """
======================================================================
Supported Automation Keywords Reference
======================================================================

  phoneConfig( model, storage, color, network, accessory )
      Updates the global CONFIG dictionary with 5 comma-separated configuration values.
      Arguments can be quoted or unquoted, and are case-insensitive.

  calculatePrice( [code] )
      Fills the form using global CONFIG and optional discount code, clicks 'Calculate Price',
      and updates the global PRICE variable.

  checkPrice( value )
      Compares 'value' against the global PRICE variable (e.g. checkPrice(1015.00) or checkPrice(PRICE)).
      Passes if equal, fails if not.

  buy( [code] )
      Performs the Buy action using global CONFIG and optional discount code.
      Updates the global DISCOUNT_CODE variable if a new code is generated.

  returnPhone( mode )
      Returns a phone with the given mode ('store credit' or 'refund').
      In 'store credit' mode, updates the global CREDIT variable with the updated store credit balance.

  checkCredit( value )
      Compares 'value' against the global CREDIT variable (e.g. checkCredit(862.75) or checkCredit(CREDIT)).
      Passes if equal, fails if not.

  Reset()
      Resets the student's own data immediately, right where it appears --
      same as clicking the app's own "Reset my data" button. Valid both
      as a step inside a # test/# end test block (execution then
      continues with the next step in that test) and as a standalone
      line outside any test block, e.g. between two tests or at the end
      of the file (execution then continues to the next test). Can be
      used more than once in the same script. If Reset() never appears
      in the script at all, nothing is ever reset.
"""


# ---------------------------------------------------------------------
# Selenium Helper Functions
# ---------------------------------------------------------------------

def select_by_value_case_insensitive(select_element: Select, target_value: str) -> None:
    """Selects an option in a drop-down menu regardless of case."""
    clean_target = target_value.strip().lower()
    for option in select_element.options:
        opt_val = option.get_attribute("value") or ""
        opt_text = option.text or ""
        if opt_val.strip().lower() == clean_target or opt_text.strip().lower() == clean_target:
            select_element.select_by_value(opt_val)
            return
    raise ValueError(f"Could not find select option matching: '{target_value}'")


def fill_form(driver, email: str, config: dict, discount_code: str = "") -> None:
    email_field = driver.find_element(By.ID, "student-email")
    email_field.clear()
    email_field.send_keys(email)
    for key, select_id in SELECT_IDS.items():
        select_elem = Select(driver.find_element(By.ID, select_id))
        select_by_value_case_insensitive(select_elem, config[key])
        
    discount_field = driver.find_element(By.ID, "discount-code")
    discount_field.clear()
    if discount_code:
        discount_field.send_keys(discount_code)


def wait_for_settled_price(driver, timeout: float = 15.0, poll: float = 0.05) -> float:
    deadline = time.time() + timeout
    seen_empty = False
    while time.time() < deadline:
        current = driver.find_element(By.ID, "total-price").text.strip()
        if not current:
            seen_empty = True
        elif seen_empty:
            return float(current)
        time.sleep(poll)
    raise TimeoutError("#total-price never showed a value after clearing in time.")


def extract_generated_code(driver) -> str:
    row = driver.find_element(By.ID, "generated-code-row")
    if row.get_attribute("hidden") is not None:
        return ""
    return driver.find_element(By.ID, "generated-code").text.strip()


def select_refund_type(driver, mode_str: str) -> None:
    val = "StoreCredit" if "credit" in mode_str.lower() else "Refund"
    radio = driver.find_element(By.CSS_SELECTOR, f'input[name="refund-type"][value="{val}"]')
    radio.click()


# ---------------------------------------------------------------------
# Keyword Implementation Actions
# ---------------------------------------------------------------------

def clean_arg(arg_str: str) -> str:
    """Strips whitespace and surrounding quotes from an argument."""
    s = arg_str.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    return s


def kw_phone_config(param_str: str):
    """phoneConfig( model, storage, color, network, accessory )"""
    global CONFIG
    raw_params = param_str.split(",")
    if len(raw_params) != 5:
        raise ValueError(f"phoneConfig requires 5 comma-separated arguments, got {len(raw_params)}: {param_str}")
    
    params = [clean_arg(p) for p in raw_params]
    CONFIG["model"] = params[0]
    CONFIG["storage"] = params[1]
    CONFIG["color"] = params[2]
    CONFIG["network"] = params[3]
    CONFIG["accessory"] = params[4]
    print(f"    [ACTION] Updated CONFIG -> {CONFIG}")


def kw_calculate_price(driver, email: str, code: str = "") -> float:
    """calculatePrice( [code] )"""
    global PRICE
    print(f"    [ACTION] Calculating price with code: {code!r}")
    fill_form(driver, email, CONFIG, discount_code=code)
    driver.find_element(By.ID, "calc-price-btn").click()
    PRICE = wait_for_settled_price(driver)
    print(f"    [RESULT] Global PRICE set to: ${PRICE:.2f}")
    return PRICE


def kw_check_price(value_str: str) -> bool:
    """checkPrice( value )"""
    target_val = float(clean_arg(value_str).replace("$", ""))
    match = abs(PRICE - target_val) < 0.01
    status = "PASS" if match else "FAIL"
    print(colorize(f"    [{status}] checkPrice: expected {target_val:.2f}, got {PRICE:.2f}", match))
    return match


def kw_buy(driver, email: str, code: str = ""):
    """buy( [code] )

    Deliberately does NOT re-fill the form: the app's Buy button only
    stays enabled if Calculate Price has already run for the CURRENT
    inputs, and ANY change to a field -- even clearing then re-typing
    the exact same discount code -- fires input events that invalidate
    that state and silently re-disable Buy (confirmed empirically: a
    preceding calculatePrice(code) followed by a re-filling buy(code)
    clicked a disabled button and timed out waiting for the purchase
    history to grow). A calculatePrice([code]) call establishing the
    same config/code must always immediately precede buy([code])."""
    global DISCOUNT_CODE
    print(f"    [ACTION] Performing Buy with discount code: {code!r}")

    history_before = len(driver.find_elements(By.CSS_SELECTOR, "#purchase-history-list li"))
    driver.find_element(By.ID, "buy-btn").click()
    
    WebDriverWait(driver, 10).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, "#purchase-history-list li")) > history_before
    )
    
    gen_code = extract_generated_code(driver)
    if gen_code:
        DISCOUNT_CODE = gen_code
        print(f"    [RESULT] Generated new DISCOUNT_CODE: {DISCOUNT_CODE!r}")


def kw_return_phone(driver, mode_str: str):
    """returnPhone( mode )"""
    global CREDIT
    mode_clean = clean_arg(mode_str).lower()
    print(f"    [ACTION] Returning phone with mode: {mode_str!r}")
    select_refund_type(driver, mode_clean)
    
    old_message = driver.find_element(By.ID, "return-message").text
    driver.find_element(By.ID, "return-btn").click()
    
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "return-message").text != old_message
        and d.find_element(By.ID, "return-message").text.strip() != ""
    )
    
    if "credit" in mode_clean:
        balance_text = driver.find_element(By.ID, "store-credit-balance").text.strip()
        new_balance = float(balance_text) if balance_text else 0.0
        CREDIT = new_balance
        print(f"    [RESULT] Updated global CREDIT to: ${CREDIT:.2f}")


def kw_check_credit(value_str: str) -> bool:
    """checkCredit( value )"""
    target_val = float(clean_arg(value_str).replace("$", ""))
    match = abs(CREDIT - target_val) < 0.01
    status = "PASS" if match else "FAIL"
    print(colorize(f"    [{status}] checkCredit: expected {target_val:.2f}, got {CREDIT:.2f}", match))
    return match


def kw_reset(driver, email: str) -> bool:
    """Reset(). Clicks 'Reset my data' and accepts the two native
    confirm/alert dialogs student.js's handler uses (confirm(...) then
    alert(...)) -- mirrors test_level4_buy_ui.py's reset_student_data().

    Refills #student-email first: the reset handler posts whatever is
    CURRENTLY in that field (els.email.value.trim()), which may not
    match `email` any more after the test script's own steps changed
    it -- if it's empty or wrong, the server-side reset fails and the
    success alert() this function waits for never appears."""
    print("    [ACTION] Resetting this student's data...")
    email_field = driver.find_element(By.ID, "student-email")
    email_field.clear()
    email_field.send_keys(email)

    reset_buttons = driver.find_elements(By.ID, "reset-btn")
    if not reset_buttons or not reset_buttons[0].is_displayed():
        print("    [WARN] Reset button not available (studentResetEnabled may be off) -- skipping.")
        return False

    reset_buttons[0].click()

    try:
        WebDriverWait(driver, 5).until(EC.alert_is_present())
        driver.switch_to.alert.accept()
    except Exception:
        print("    [WARN] Expected confirm() dialog did not appear.")
        return False

    try:
        WebDriverWait(driver, 5).until(EC.alert_is_present())
        driver.switch_to.alert.accept()
    except Exception:
        print("    [WARN] Expected acknowledgement alert() did not appear.")
        return False

    print("    [RESULT] Student data reset.")
    return True


def check_level_4(base_url: str) -> bool:
    """Confirms the app is currently configured for Level 4 -- this
    script's buy()/returnPhone()/checkCredit() keywords only make sense
    there (Return and store credit are hidden below Level 4). Reads the
    public /api/ui-config endpoint, the same config student.js itself
    fetches on page load -- no teacher auth needed, just a plain GET."""
    try:
        resp = requests.get(f"{base_url}/api/ui-config", timeout=10)
        resp.raise_for_status()
        ui_config = resp.json()
    except Exception as exc:
        print(f"[WARN] Could not check the app's level before running (skipping check): {exc}")
        return True

    level = ui_config.get("level")
    if level != 4:
        print(
            "\n[ERROR] This test script requires the app to be running at Level 4, "
            f"but {base_url} is currently set to Level {level}.\n"
            "Ask the teacher to set Level 4 before running these tests.\n"
        )
        return False
    return True


# ---------------------------------------------------------------------
# Keyword Parser and Test Executor
# ---------------------------------------------------------------------

def resolve_argument(arg_str: str) -> str:
    """Resolves variables or cleans literal quoted string values."""
    arg = clean_arg(arg_str)
    if arg == "PRICE":
        return str(PRICE)
    if arg in ("DISCOUNT_CODE", "code"):
        return DISCOUNT_CODE
    if arg == "CREDIT":
        return str(CREDIT)
    return arg


def execute_keyword(driver, email: str, line: str) -> bool:
    """Parses a single keyword line and executes the corresponding action."""
    match = KEYWORD_LINE_RE.match(line.strip())
    if not match:
        # Same "the script itself is broken" reasoning as an unrecognized
        # keyword name below -- a line that isn't even shaped like
        # name(args) is just as much a sign of a bad test script (e.g. a
        # bare word with no parentheses at all) and deserves the same
        # hard stop, not a warning that's easy to miss in scrollback.
        print(f"    [FATAL] Could not parse line as a keyword call: '{line}'. Aborting test run.")
        sys.exit(1)

    kw_name = match.group(1).strip()
    kw_name_lower = kw_name.lower()
    raw_args = match.group(2).strip()

    args = [resolve_argument(a) for a in raw_args.split(",")] if raw_args else []

    if kw_name_lower == "phoneconfig":
        kw_phone_config(raw_args)
        return True

    elif kw_name_lower == "calculateprice":
        code = args[0] if len(args) > 0 else ""
        kw_calculate_price(driver, email, code)
        return True

    elif kw_name_lower == "checkprice":
        return kw_check_price(args[0])

    elif kw_name_lower == "buy":
        code = args[0] if len(args) > 0 else ""
        kw_buy(driver, email, code)
        return True

    elif kw_name_lower == "returnphone":
        mode = args[0] if len(args) > 0 else "store credit"
        kw_return_phone(driver, mode)
        return True

    elif kw_name_lower == "checkcredit":
        return kw_check_credit(args[0])

    elif kw_name_lower == "reset":
        # Same convention as the other action keywords above (buy,
        # returnPhone, ...): always returns True regardless of whether
        # the reset itself succeeded, so a failed reset doesn't flip
        # the containing test's PASS/FAIL -- kw_reset() already prints
        # its own [WARN] if something went wrong.
        kw_reset(driver, email)
        return True

    else:
        # An unknown keyword means the test script itself is broken
        # (typo, or a keyword that doesn't exist) -- continuing past it
        # would just run whatever steps happen to follow against
        # whatever state the app was left in, which isn't meaningful.
        # Abort the whole run rather than downgrade this to a warning.
        print(f"    [FATAL] Unknown keyword: '{kw_name}'. Aborting test run.")
        sys.exit(1)


def run_test_file(driver, email: str, filepath: str) -> None:
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_test_id = None
    test_lines = []
    tests_summary = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        if stripped.lower().startswith("# test"):
            current_test_id = stripped
            test_lines = []
            continue

        if stripped.lower().startswith("# end test"):
            if current_test_id:
                print(f"\n==================================================")
                print(f"RUNNING: {current_test_id}")
                print(f"==================================================")
                
                test_passed = True
                for step_line in test_lines:
                    print(f"  Step: {step_line}")
                    step_result = execute_keyword(driver, email, step_line)
                    if not step_result:
                        test_passed = False

                status = "PASS" if test_passed else "FAIL"
                print(colorize(f"---> {current_test_id} RESULT: {status}", test_passed) + "\n")
                tests_summary.append((current_test_id, status))

                current_test_id = None
                test_lines = []
            continue

        if current_test_id:
            test_lines.append(stripped)
        else:
            kw_match = KEYWORD_LINE_RE.match(stripped)
            if kw_match and kw_match.group(1).strip().lower() == "reset":
                # Reset() written outside any # test/# end test block
                # (e.g. between two tests, or at the end of the file) --
                # executes immediately, right here, then parsing
                # continues on to whatever comes next (the next test,
                # or end of file).
                print(f"\n  Step (outside any test): {stripped}")
                kw_reset(driver, email)
            else:
                # Reset() is the only keyword valid outside a test
                # block -- anything else here (whether it's shaped like
                # name(args) or not, e.g. a bare word with no
                # parentheses) is a script error, same as an unknown or
                # unparseable line inside a test block.
                name = kw_match.group(1) if kw_match else stripped
                print(f"    [FATAL] Unrecognized content outside any test block: "
                      f"'{name}'. Aborting test run.")
                sys.exit(1)

    # Summary Report
    print("\n" + "=" * 50)
    print("FINAL TEST EXECUTION SUMMARY")
    print("=" * 50)
    all_passed = True
    for test_id, status in tests_summary:
        print(colorize(f"  {test_id}: {status}", status == "PASS"))
        if status != "PASS":
            all_passed = False
    print("=" * 50)
    print("OVERALL: " + ("ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED"))


# ---------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Keyword-driven test automation runner.",
        epilog="Use '-h' for short command usage or '--help' for full usage + keyword reference.",
        add_help=False
    )
    parser.add_argument("-h", action="store_true", help="Show CLI command options and exit")
    parser.add_argument("--help", action="store_true", help="Show CLI command options PLUS keyword reference and exit")
    parser.add_argument("--email", required=False,
                         help=f"Student's email address, must end with {REQUIRED_EMAIL_DOMAIN} "
                              f"(e.g. --email alice{REQUIRED_EMAIL_DOMAIN})")
    parser.add_argument("--tests-file", "--tests_file", dest="tests_file", default="test_cases.txt", help="Path to text file containing test cases")
    parser.add_argument("--target", choices=["local", "remote"], default="remote")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)

    # Strictly parse arguments to detect illegal/unrecognized options
    try:
        args, unknown = parser.parse_known_args()
        if unknown:
            parser.error(f"Unrecognized/illegal option(s) provided: {' '.join(unknown)}")
    except SystemExit as e:
        sys.exit(e.code)

    # Handle Help Output Differences
    if args.help or args.h:
        parser.print_help()
        if args.help:
            print(KEYWORD_HELP_TEXT)
        else:
            parser.print_help()
        sys.exit(0)

    # Enforce mandatory options when running tests
    if not args.email:
        parser.error("the following arguments are required: --email")
    if not args.email.lower().endswith(REQUIRED_EMAIL_DOMAIN):
        parser.error(f"--email must end with {REQUIRED_EMAIL_DOMAIN}, got: {args.email!r}")

    base_url = args.base_url or (LOCAL_BASE_URL if args.target == "local" else REMOTE_BASE_URL)
    email = args.email

    if not check_level_4(base_url):
        sys.exit(1)

    options = webdriver.ChromeOptions()
    if args.headless:
        options.add_argument("--headless=new")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(base_url)
        WebDriverWait(driver, 10).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#model-select option")) > 1
        )
        run_test_file(driver, email, args.tests_file)
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())