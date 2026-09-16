"""
test_level1_buy_ui.py -- Level 1 UI verification via a real browser
(ChromeDriver/Selenium): fill the form, Calculate Price, then Buy --
exactly what a student does by hand. Same idea as test_level1_buy.py,
which exercises the same two actions "under the UI" via curl/requests
instead of a browser.

Kept in the same shape as test_level1_buy.py on purpose -- same CONFIG,
same independently-recomputed PRICE_TABLE, same
expected_price()/expected_congrats_message() helpers, same check()
reporting. What actually changes is HOW each action is performed and
verified: calculate_price() and buy_phone() now drive the real page
(fill fields, click buttons, read the DOM) instead of calling the API
directly.

WHY THIS FILE EXISTS ON TOP OF test_level1_buy.py
---------------------------------------------------
"Under the UI" testing verifies what the SERVER does -- the JSON
contract. It cannot verify what happens entirely in the BROWSER, because
none of it is visible in an HTTP response:

  * The Buy button's enabled/disabled state machine (requirements.md
    §6.3) -- starts disabled, only enabled after Calculate Price has run
    for the CURRENT inputs, re-disabled by any dropdown/discount-code
    change (even a change that's immediately reverted back), NOT
    re-disabled by clicking Buy itself. This is pure client-side JS
    (public/js/student.js) with no server-side equivalent to query.
  * The congratulations message (§6.10) -- built entirely client-side in
    buildCongratsMessage(), from the config the Buy response echoes
    back. The server's JSON response has no "message" field at all; the
    text a student actually sees only ever exists in the DOM.
  * Client-side email validation -- an empty/malformed email is rejected
    by student.js's own regex check BEFORE any network request is even
    made, so there's no HTTP response to inspect for that case at all.

The verify_*() functions below exist specifically to check these three
things. Everything else (price correctness, etc.) is still independently
recomputed, same as test_level1_buy.py -- Buy always talks to the real
server regardless of which client drove it, so purchase integrity isn't
what's being demonstrated here; the UI behavior wrapped around it is.

Requires: pip install selenium
Chrome must be installed. Selenium 4.6+'s built-in Selenium Manager
downloads a matching chromedriver automatically -- no separate
chromedriver install or PATH setup needed.
"""

import argparse
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

REMOTE_BASE_URL = "https://sw-test-courses-exercises.vercel.app"
LOCAL_BASE_URL = "http://localhost:3000"  # offline-server.js or vercel dev
DEFAULT_STUDENT_NAME = "student01"

CONFIG = {
    "model": "Pixel 9",
    "storage": "128GB",
    "color": "Black",
    "network": "5G",
    "accessory": "None",
}

# Mirrors PRICE_TABLE in lib/priceTable.js exactly -- must be kept in sync
# by hand if that table ever changes, since this is deliberately an
# independent recomputation, not a copy fetched from the server.
PRICE_TABLE = {
    "model": {"Pixel 9": 900, "Pixel 9 Pro": 1050, "Pixel 9 Pro XL": 1430},
    "storage": {"128GB": 0, "256GB": 56, "512GB": 98, "1TB": 164},
    "color": {"Black": 0, "Red": 100, "Silver": 80, "Blue": 60},
    "network": {"5G": 115, "4G": 0},
    "accessory": {"None": 0, "Case": 45, "Charger": 32, "Earbuds": 215},
}

SELECT_IDS = {
    "model": "model-select",
    "storage": "storage-select",
    "color": "color-select",
    "network": "network-select",
    "accessory": "accessory-select",
}


def expected_price(config: dict) -> float:
    """Independently computes the base price, the same way
    lib/pricing.js's computeBasePrice() does: sum each parameter's price,
    0 for anything missing or not in the table."""
    total = 0
    for param, value in config.items():
        total += PRICE_TABLE[param].get(value, 0)
    return round(total, 2)


def expected_congrats_message(config: dict) -> str:
    """Reconstructs the message public/js/student.js's
    buildCongratsMessage() builds -- NOT something the server returns;
    see the module docstring."""
    msg = (
        f"Congratulations! You are now the owner of a {config['network']} "
        f"{config['color']} {config['model']} with {config['storage']}"
    )
    accessory = config.get("accessory")
    if accessory and accessory != "None":
        article = "a " if accessory in ("Case", "Charger") else ""
        msg += f" and {article}{accessory}"
    msg += "."
    return msg


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail and not condition else ""))
    return condition


# ---------------------------------------------------------------------
# Page interactions -- these replace calculate_price()/buy_phone() from
# test_level1_buy.py's curl/requests calls with real browser actions.
# ---------------------------------------------------------------------

def fill_form(driver, email: str, config: dict) -> None:
    email_field = driver.find_element(By.ID, "student-email")
    email_field.clear()
    email_field.send_keys(email)
    for key, select_id in SELECT_IDS.items():
        Select(driver.find_element(By.ID, select_id)).select_by_value(config[key])


def calculate_price(driver, email: str, config: dict) -> float:
    """Fills the form and clicks Calculate Price, exactly as a student
    would. Returns the Total Price read back from the DOM -- what the
    student actually sees, not an HTTP response."""
    fill_form(driver, email, config)
    driver.find_element(By.ID, "calc-price-btn").click()
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "price-breakdown").get_attribute("hidden") is None
    )
    # student.js's blinkText() clears #total-price then refills it
    # BLINK_DELAY_MS (150ms) later -- even when the new value is the same
    # as the old one, so waiting for "the text changed" isn't reliable.
    # A short, deliberate pause past that delay is simpler and more
    # robust than racing to catch the transient empty state.
    time.sleep(0.5)
    total_text = driver.find_element(By.ID, "total-price").text
    return float(total_text)


def buy_phone(driver) -> str:
    """Clicks Buy and returns the newest purchase-history line's text --
    the congratulations message, which only ever exists in the DOM (see
    module docstring)."""
    history_before = len(driver.find_elements(By.CSS_SELECTOR, "#purchase-history-list li"))
    driver.find_element(By.ID, "buy-btn").click()
    WebDriverWait(driver, 10).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, "#purchase-history-list li")) > history_before
    )
    items = driver.find_elements(By.CSS_SELECTOR, "#purchase-history-list li")
    return items[-1].text


# ---------------------------------------------------------------------
# UI-only verifications -- nothing here has an "under the UI" equivalent;
# each one checks something that exists only in the browser, never in an
# HTTP response. See the module docstring for why each matters.
# ---------------------------------------------------------------------

def verify_buy_button_enabled(driver, expected: bool, label: str) -> bool:
    is_enabled = driver.find_element(By.ID, "buy-btn").is_enabled()
    return check(f"Buy button {label}", is_enabled == expected,
                 f"expected enabled={expected}, got {is_enabled}")


def verify_congrats_message(driver, actual_message: str, config: dict) -> bool:
    want = expected_congrats_message(config)
    return check("Purchase history shows the correct congratulations message",
                 actual_message == want, f"expected {want!r}, got {actual_message!r}")


def verify_client_side_email_validation(driver) -> bool:
    """An empty email is rejected by student.js's own regex check BEFORE
    any network request -- there's no server response to inspect for
    this case at all; it has to be read from the DOM."""
    email_field = driver.find_element(By.ID, "student-email")
    email_field.clear()
    error_el = driver.find_element(By.ID, "error-message")
    driver.find_element(By.ID, "calc-price-btn").click()
    WebDriverWait(driver, 5).until(lambda d: error_el.get_attribute("hidden") is None)
    text = error_el.text
    return check("Client-side email validation shows the expected error",
                 text == "A valid email address is required.", f"got {text!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True,
                         help="Run Chrome headless (default), or visibly with --no-headless.")
    parser.add_argument("--target", choices=["local", "remote"], default="remote",
                         help=f"'local' = {LOCAL_BASE_URL} (offline-server.js or vercel dev), "
                              f"'remote' = {REMOTE_BASE_URL} (default).")
    parser.add_argument("--base-url", default=None,
                         help="Explicit base URL, overrides --target.")
    parser.add_argument("--student-name", default=DEFAULT_STUDENT_NAME,
                         help=f"Local part of the student email to use (default: {DEFAULT_STUDENT_NAME}). "
                              "The full email typed into the form is <student-name>@example.com.")
    args = parser.parse_args()
    base_url = args.base_url or (LOCAL_BASE_URL if args.target == "local" else REMOTE_BASE_URL)
    email = f"{args.student_name}@example.com"

    all_passed = True
    want_price = expected_price(CONFIG)

    options = webdriver.ChromeOptions()
    if args.headless:
        options.add_argument("--headless=new")
    # Suppresses harmless Chrome-internal log noise (e.g. GCM
    # "PHONE_REGISTRATION_ERROR") that has nothing to do with this test --
    # the automated profile has no signed-in Google account, so Chrome's
    # background push-notification registration always fails.
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(options=options)
    try:
        print(f"Target: {base_url}")
        driver.get(base_url)
        # The dropdown <option>s are populated asynchronously (student.js
        # fetches /api/product-options and /api/ui-config on load) -- wait
        # for that to actually finish before trying to select anything,
        # rather than just for the static page markup to be present.
        WebDriverWait(driver, 10).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#model-select option")) > 1
        )

        all_passed &= verify_buy_button_enabled(driver, False, "starts disabled")

        # ---- 1) Calculate Price ----
        print("\nCalculating price...")
        total = calculate_price(driver, email, CONFIG)
        print(f"  UI shows Total Price: {total}")
        all_passed &= check(
            "Calculate: Total Price matches independently computed price",
            total == want_price, f"expected {want_price}, got {total}",
        )
        all_passed &= verify_buy_button_enabled(driver, True, "enabled after Calculate Price")

        # ---- 2) Buy-button state machine (UI-only -- see docstring) ----
        print("\nChanging a dropdown without recalculating...")
        Select(driver.find_element(By.ID, "color-select")).select_by_value("Red")
        all_passed &= verify_buy_button_enabled(driver, False, "re-disabled after a dropdown change")
        Select(driver.find_element(By.ID, "color-select")).select_by_value(CONFIG["color"])
        all_passed &= verify_buy_button_enabled(
            driver, False, "still disabled after reverting the value (must recalculate regardless)"
        )

        print("\nRecalculating...")
        calculate_price(driver, email, CONFIG)
        all_passed &= verify_buy_button_enabled(driver, True, "enabled again after recalculating")

        # ---- 3) Buy ----
        print("\nBuying...")
        message = buy_phone(driver)
        print(f"  Purchase history shows: {message!r}")
        all_passed &= verify_congrats_message(driver, message, CONFIG)
        all_passed &= verify_buy_button_enabled(driver, True, "stays enabled after Buy itself")

        # ---- 4) Repeated Buy against an already-calculated configuration ----
        print("\nBuying the same configuration again (repeated Buy is allowed)...")
        message2 = buy_phone(driver)
        all_passed &= verify_congrats_message(driver, message2, CONFIG)
        history_count = len(driver.find_elements(By.CSS_SELECTOR, "#purchase-history-list li"))
        all_passed &= check("Purchase history has two entries after two Buys",
                             history_count == 2, f"got {history_count}")

        # ---- 5) Client-side email validation (UI-only -- see docstring) ----
        print("\nTesting client-side email validation...")
        all_passed &= verify_client_side_email_validation(driver)

        print("\n" + ("ALL CHECKS PASSED" if all_passed else "SOME CHECKS FAILED"))
        return 0 if all_passed else 1
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
