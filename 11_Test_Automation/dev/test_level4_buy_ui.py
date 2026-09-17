"""
test_level4_buy_ui.py -- UI verification (ChromeDriver/Selenium) of the
discount-code + store-credit return flow at Level 4:

  Calculate Price -> Buy (no code yet, so this generates one) -> capture
  the generated code -> Calculate/Buy AGAIN with that code applied (15%
  off) -> save the discounted price -> Return with "Store credit"
  selected -> verify the resulting balance equals the saved discounted
  price -> reset the student's own data.

WHY RETURN IS CALLED TWICE
---------------------------
Getting a discount code at all requires buying a FIRST, undiscounted
phone -- a purchase that itself used a valid code never generates a new
one (see requirements.md §6.4). That leaves two purchases with the
*identical* 5-parameter configuration on this student's account. Return
always matches the OLDEST still-Bought purchase with that exact
configuration (the "N identical phones" rule, §6.4/§6.6) -- so a single
Return call would hit the first, undiscounted purchase, not the
discounted one, and a credit assertion against the discounted price
would fail even against a correctly-working app. This script calls
Return twice on purpose: the first clears the undiscounted purchase out
of the way (checked against the undiscounted price), the second is the
one that actually returns the discounted phone -- that result is what
gets checked against the discounted price saved earlier. This mirrors
the exact scenario verify_deployment.py exercises directly against the
API (see its "Return: oldest-match rule" check).

ENVIRONMENT
-----------
This flow needs Level 4 (for discount codes *and* Return/Store credit)
and studentResetEnabled (for the final cleanup step) ALREADY configured
on the target -- this script does not read or change teacher settings
itself. That's deliberate: settings are global to the whole
deployment, so if many students each ran their own script instance in
parallel and every instance also set/restored settings, they'd race
and stomp on each other. Have the teacher configure Level 4 +
studentResetEnabled once for the class before anyone runs this.

--student-name is REQUIRED here, unlike test_level1_buy.py/
test_level1_buy_ui.py's optional default -- this test buys and returns
real purchases and touches store credit, so each run needs to be
unambiguously attributable to one student and not collide with anyone
else's on the shared database.

USAGE
-----
    python test_level4_buy_ui.py --student-name alice01 --target local
    python test_level4_buy_ui.py --student-name alice01 --target remote

Requires: pip install selenium
"""

import argparse
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

REMOTE_BASE_URL = "https://sw-test-courses-exercises.vercel.app"
LOCAL_BASE_URL = "http://localhost:3000"  # offline-server.js or vercel dev

CONFIG = {
    "model": "Pixel 9",
    "storage": "128GB",
    "color": "Black",
    "network": "5G",
    "accessory": "None",
}
# Base price for CONFIG above, computed independently from the app's own
# PRICE_TABLE (Pixel 9 $900 + 128GB $0 + Black $0 + 5G $115 + None $0) --
# used as a static ground truth for the discount check below, rather than
# a value derived from the app's own output.
BASE_PRICE = 1015.00
EXPECTED_DISCOUNTED_PRICE = round(BASE_PRICE * 0.85, 2)

SELECT_IDS = {
    "model": "model-select",
    "storage": "storage-select",
    "color": "color-select",
    "network": "network-select",
    "accessory": "accessory-select",
}


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail and not condition else ""))
    return condition


def pause(interactive: bool, description: str) -> None:
    if interactive:
        input(f"\n[PAUSE] {description} Press ENTER to continue...")


# ---------------------------------------------------------------------
# Page interactions -- element IDs verified against public/index.html.
# ---------------------------------------------------------------------

def fill_form(driver, email: str, config: dict, discount_code: str = "") -> None:
    email_field = driver.find_element(By.ID, "student-email")
    email_field.clear()
    email_field.send_keys(email)
    for key, select_id in SELECT_IDS.items():
        Select(driver.find_element(By.ID, select_id)).select_by_value(config[key])
    discount_field = driver.find_element(By.ID, "discount-code")
    discount_field.clear()
    if discount_code:
        discount_field.send_keys(discount_code)


def _wait_for_settled_price(driver, timeout: float = 15.0, poll: float = 0.05) -> float:
    """Polls #total-price for a value that shows up AFTER the field has
    read empty at least once.

    Why not simpler: #price-breakdown's "hidden" attribute only clears
    the FIRST time a calculation ever renders (useless as a completion
    signal on every call after that -- e.g. this script's second
    Calculate, with a discount code, at Level 4, when the panel is
    already visible from a prior action). And "wait for two consecutive
    identical non-empty reads" (a prior version of this function) is
    unsound: student.js's blinkText() only clears #total-price once the
    awaited server response actually arrives, so while that request is
    still in flight the OLD value just sits there completely unchanged
    -- two polls landing before the clear happens look exactly as
    "stable" as a genuinely settled new value, and the function returns
    the stale pre-click price before the real one has even arrived
    (confirmed happening against production, where the awaited round
    trip regularly outlasts a couple of poll intervals). Requiring an
    observed empty read before accepting any value as final rules that
    out, since blinkText's clear is the only thing that can ever
    produce one. Polling at a fine interval (default 50ms) keeps the
    ~150ms empty window from being stepped over even in a fast local
    round trip, while the generous default timeout covers slower
    production network latency.
    """
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


def calculate_price(driver, email: str, config: dict, discount_code: str = "", interactive: bool = False) -> float:
    pause(interactive, f"About to fill the form and click Calculate Price (discount code: {discount_code!r}).")
    fill_form(driver, email, config, discount_code)
    driver.find_element(By.ID, "calc-price-btn").click()
    return _wait_for_settled_price(driver)


def buy_phone(driver, interactive: bool = False) -> str:
    pause(interactive, "About to click Buy.")
    history_before = len(driver.find_elements(By.CSS_SELECTOR, "#purchase-history-list li"))
    driver.find_element(By.ID, "buy-btn").click()
    WebDriverWait(driver, 10).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, "#purchase-history-list li")) > history_before
    )
    return driver.find_elements(By.CSS_SELECTOR, "#purchase-history-list li")[-1].text


def extract_generated_code(driver) -> str:
    """Reads #generated-code directly -- the field the app actually uses
    (public/js/student.js: els.generatedCode.textContent = result.generatedCode)."""
    row = driver.find_element(By.ID, "generated-code-row")
    if row.get_attribute("hidden") is not None:
        return ""
    return driver.find_element(By.ID, "generated-code").text.strip()


def select_refund_type(driver, value: str) -> None:
    """value is 'Refund' or 'StoreCredit' -- matches the radio inputs'
    actual value= attributes exactly (case-sensitive)."""
    radio = driver.find_element(By.CSS_SELECTOR, f'input[name="refund-type"][value="{value}"]')
    radio.click()


def return_phone(driver, interactive: bool = False) -> dict:
    """Clicks Return with Store credit selected. Returns
    {store_credit_balance, message}, read from the real elements
    (#store-credit-balance, #return-message)."""
    pause(interactive, "About to select 'Store credit' and click Return.")
    select_refund_type(driver, "StoreCredit")
    old_message = driver.find_element(By.ID, "return-message").text
    driver.find_element(By.ID, "return-btn").click()
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "return-message").text != old_message
        and d.find_element(By.ID, "return-message").text.strip() != ""
    )
    message = driver.find_element(By.ID, "return-message").text
    balance_text = driver.find_element(By.ID, "store-credit-balance").text.strip()
    balance = float(balance_text) if balance_text else 0.0
    return {"balance": balance, "message": message}


def reset_student_data(driver, interactive: bool = False) -> bool:
    """Clicks 'Reset my data' and accepts the two native confirm/alert
    dialogs student.js's handler uses (confirm(...) then alert(...))."""
    reset_buttons = driver.find_elements(By.ID, "reset-btn")
    if not reset_buttons or not reset_buttons[0].is_displayed():
        print("  [INFO] Reset button not available (studentResetEnabled may be off) -- skipping.")
        return False

    pause(interactive, "About to click 'Reset my data'.")
    reset_buttons[0].click()

    try:
        WebDriverWait(driver, 5).until(EC.alert_is_present())
        confirm_dialog = driver.switch_to.alert
        confirm_dialog.accept()
    except Exception:
        print("  [WARN] Expected confirm() dialog did not appear.")
        return False

    try:
        WebDriverWait(driver, 5).until(EC.alert_is_present())
        ack_dialog = driver.switch_to.alert
        ack_dialog.accept()
    except Exception:
        print("  [WARN] Expected acknowledgement alert() did not appear.")
        return False

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--student-name", required=True,
                         help="Local part of the student email to use, e.g. --student-name alice01. "
                              "Required (not defaulted) -- this test touches real purchases/credit.")
    parser.add_argument("--target", choices=["local", "remote"], default="remote",
                         help=f"'local' = {LOCAL_BASE_URL} (offline-server.js or vercel dev), "
                              f"'remote' = {REMOTE_BASE_URL} (default).")
    parser.add_argument("--base-url", default=None, help="Explicit base URL, overrides --target.")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True,
                         help="Run Chrome headless (default), or visibly with --no-headless "
                              "(also enables interactive pause-and-inspect prompts).")
    args = parser.parse_args()

    base_url = args.base_url or (LOCAL_BASE_URL if args.target == "local" else REMOTE_BASE_URL)
    email = f"{args.student_name}@example.com"
    interactive = not args.headless
    all_passed = True

    print(f"Target: {base_url}")
    print(f"Student: {email}")

    options = webdriver.ChromeOptions()
    if args.headless:
        options.add_argument("--headless=new")
    # Suppresses harmless Chrome-internal log noise (GCM push-notification
    # registration errors) -- the automated profile has no signed-in
    # Google account, unrelated to this test.
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(base_url)
        WebDriverWait(driver, 10).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#model-select option")) > 1
        )

        # ---- 1) Buy an undiscounted phone -> generates a discount code ----
        print("\n1. Buying an undiscounted phone to generate a discount code...")
        calculate_price(driver, email, CONFIG, interactive=interactive)
        buy_phone(driver, interactive=interactive)
        code = extract_generated_code(driver)
        print(f"   Captured discount code: {code!r}")
        all_passed &= check("A discount code was generated", bool(code), f"got {code!r}")

        # ---- 2) Buy again, applying the code -> 15% off ----
        print("\n2. Calculating and buying again with the discount code applied...")
        discounted_price = calculate_price(driver, email, CONFIG, discount_code=code, interactive=interactive)
        print(f"   Discounted price: ${discounted_price:.2f}")
        all_passed &= check(
            "Discounted price reflects 15% off",
            abs(discounted_price - EXPECTED_DISCOUNTED_PRICE) < 0.01,
            f"expected {EXPECTED_DISCOUNTED_PRICE:.2f}, got {discounted_price:.2f}",
        )
        buy_phone(driver, interactive=interactive)

        # ---- 3) Return #1: clears the OLDEST (undiscounted) purchase ----
        # See module docstring: Return matches oldest-still-Bought first,
        # so this first call is expected to hit the undiscounted phone,
        # not the one we actually want to check.
        print("\n3. Returning once (expected to match the OLDEST purchase -- the undiscounted one)...")
        first_return = return_phone(driver, interactive=interactive)
        print(f"   Balance after return #1: ${first_return['balance']:.2f}")
        all_passed &= check(
            "Return #1 succeeded",
            "can be returned" in first_return["message"],
            first_return["message"],
        )

        # ---- 4) Return #2: this is the discounted purchase ----
        print("\n4. Returning again (this should match the discounted purchase)...")
        second_return = return_phone(driver, interactive=interactive)
        print(f"   Balance after return #2: ${second_return['balance']:.2f}")
        all_passed &= check(
            "Return #2 succeeded",
            "can be returned" in second_return["message"],
            second_return["message"],
        )
        credit_from_second_return = round(second_return["balance"] - first_return["balance"], 2)
        all_passed &= check(
            "Store credit added by the SECOND return equals the saved discounted price",
            abs(credit_from_second_return - discounted_price) < 0.01,
            f"expected {discounted_price:.2f}, got {credit_from_second_return:.2f}",
        )

        # ---- 5) Clean up this student's own data ----
        print("\n5. Resetting this student's data...")
        reset_ok = reset_student_data(driver, interactive=interactive)
        all_passed &= check("Student data reset", reset_ok)

        print("\n" + ("ALL CHECKS PASSED" if all_passed else "SOME CHECKS FAILED"))
        return 0 if all_passed else 1
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
