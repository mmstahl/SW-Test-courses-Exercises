"""
verify_deployment.py -- Full functional verification of the Phone
Configurator Simulator server, against either a local `vercel dev`
instance or the live Vercel deployment.

This is the same battery of checks that was run by hand (via curl and
direct database queries) while building and verifying this app -- saved
here so it can be re-run any time: after a code change, before/after a
deploy, or just to confirm nothing regressed. Unlike test_level1_buy.py
(a small, student-facing example of the "under the UI" testing pattern),
this file is a maintainer/instructor tool: it exercises every level, every
induced bug toggle, teacher auth, and the discount-code/return/credit
lifecycles end to end, using the real HTTP API only (no direct database
access, so it has no extra dependency beyond `requests` and works
identically against local or deployed instances).

USAGE
-----
    python verify_deployment.py --base-url http://localhost:3000
    python verify_deployment.py --base-url https://sw-test-courses-exercises.vercel.app

Teacher credentials are required (settings must be flipped across levels
and bug toggles to exercise everything). Supply them via environment
variables (recommended -- keeps them out of shell history):

    set TEACHER_USERNAME=mstahl        (Windows cmd)
    $env:TEACHER_USERNAME="mstahl"     (PowerShell)
    export TEACHER_USERNAME=mstahl     (bash)

...and similarly TEACHER_PASSWORD, or just let the script prompt you
(it uses getpass, so nothing is echoed or persisted). --username and
--password flags are also accepted if you'd rather pass them explicitly.

IMPORTANT -- this shares state with whoever is using the app right now:
--------------------------------------------------------------------
This script flips the *shared* teacher settings (Level, every induced bug
toggle, the required-email-domain) while it runs, then restores whatever
they were before it started. If you run this against the live production
URL while a class is actively using the simulator, they will briefly see
different behavior (wrong level, bugs toggled on) during the run. Prefer
running it against a local `vercel dev` instance for routine checks; only
run it against production when nobody's actively using the app (e.g.
right after a deploy, before a class starts).

All test data uses generated `verify-<run-id>-...@example.com` addresses
(never a real-looking student email), and is cleaned up via the student
self-reset endpoint at the end of a run. Nothing here ever deletes real
student data -- the one truly destructive check (teacher reset-all, which
wipes *every* student's data) is opt-in only, via --wipe-all-data, and
still requires typing RESET interactively, exactly like the UI itself
does. Omit that flag (the default) and reset-all is never called.

Requires: pip install requests
"""

import argparse
import getpass
import os
import sys
import uuid

import requests

RUN_ID = uuid.uuid4().hex[:8]

PRICE_TABLE = {
    "Model": {"Pixel 9": 900, "Pixel 9 Pro": 1050, "Pixel 9 Pro XL": 1430},
    "Storage": {"128GB": 0, "256GB": 56, "512GB": 98, "1TB": 164},
    "Color": {"Black": 0, "Red": 100, "Silver": 80, "Blue": 60},
    "Network": {"5G": 115, "4G": 0},
    "Accessory": {"None": 0, "Case": 45, "Charger": 32, "Earbuds": 215},
}

BASE_CONFIG = {
    "model": "Pixel 9",
    "storage": "128GB",
    "color": "Black",
    "network": "5G",
    "accessory": "None",
}


def base_price(config: dict) -> float:
    keymap = {"model": "Model", "storage": "Storage", "color": "Color",
              "network": "Network", "accessory": "Accessory"}
    total = 0
    for k, v in config.items():
        table_key = keymap.get(k)
        if table_key:
            total += PRICE_TABLE[table_key].get(v, 0)
    return round(total, 2)


# ---------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------

_all_results = []  # list of (status, label)


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    _all_results.append((status, label))
    print(f"  [{status}] {label}" + (f" -- {detail}" if detail and status == "FAIL" else ""))
    return condition


def section(title: str) -> None:
    print(f"\n=== {title} ===")


_created_emails = []


def new_email(tag: str) -> str:
    email = f"verify-{RUN_ID}-{tag}@example.com"
    _created_emails.append(email)
    return email


# ---------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------

class Client:
    """Thin wrapper over requests.Session -- cookies (the teacher session)
    persist automatically across calls once login() succeeds."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def get(self, path: str, **params):
        resp = self.session.get(f"{self.base_url}{path}", params=params)
        return self._unwrap(resp)

    def post(self, path: str, body: dict = None):
        resp = self.session.post(f"{self.base_url}{path}", json=body or {})
        return self._unwrap(resp)

    def put(self, path: str, body: dict = None):
        resp = self.session.put(f"{self.base_url}{path}", json=body or {})
        return self._unwrap(resp)

    @staticmethod
    def _unwrap(resp):
        try:
            body = resp.json()
        except ValueError:
            body = {"error": f"non-JSON response (status {resp.status_code}): {resp.text[:200]!r}"}
        return resp.status_code, body

    # ---- convenience wrappers over the actual endpoints ----

    def login(self, username: str, password: str):
        status, body = self.post("/api/teacher/login", {"username": username, "password": password})
        if status != 200:
            raise SystemExit(f"Teacher login failed (HTTP {status}): {body.get('error')}")
        return body

    def logout(self):
        return self.post("/api/teacher/logout")

    def get_settings(self):
        status, body = self.get("/api/teacher/settings")
        if status != 200:
            raise SystemExit(f"Could not read teacher settings (HTTP {status}): {body.get('error')}")
        return body

    def set_settings(self, overrides: dict):
        status, body = self.put("/api/teacher/settings", overrides)
        if status != 200:
            raise SystemExit(f"Could not update teacher settings (HTTP {status}): {body.get('error')}")
        return body

    def calculate(self, email: str, config: dict, discount_code: str = ""):
        params = dict(config, email=email, discountCode=discount_code)
        return self.get("/api/calculate", **params)

    def buy(self, email: str, config: dict, discount_code: str = ""):
        body = dict(config, email=email, discountCode=discount_code)
        return self.post("/api/buy", body)

    def ret(self, email: str, config: dict, refund_type: str):
        body = dict(config, email=email, refundType=refund_type)
        return self.post("/api/return", body)

    def reset_student(self, email: str):
        return self.post("/api/reset", {"email": email})

    def student_status(self, email: str):
        return self.get("/api/student-status", email=email)


# ---------------------------------------------------------------------
# Test groups
# ---------------------------------------------------------------------

def test_level1_calculate_and_buy(client: Client):
    section("Level 1: Calculate + Buy")
    client.set_settings({"level": 1})
    email = new_email("level1")
    want = base_price(BASE_CONFIG)

    status, calc = client.calculate(email, BASE_CONFIG)
    check("Calculate: HTTP 200", status == 200, f"got {status}: {calc}")
    check("Calculate: basePrice matches independent computation",
          calc.get("basePrice") == want, f"expected {want}, got {calc.get('basePrice')}")
    check("Calculate: paidPrice == basePrice (no discount at Level 1)",
          calc.get("paidPrice") == want, f"expected {want}, got {calc.get('paidPrice')}")

    status, bought = client.buy(email, BASE_CONFIG)
    check("Buy: HTTP 200", status == 200, f"got {status}: {bought}")
    check("Buy: basePrice matches independent computation",
          bought.get("basePrice") == want)
    check("Buy: no discount code generated at Level 1",
          bought.get("generatedCode") is None, f"got {bought.get('generatedCode')}")
    check("Buy: returnEnabled is false below Level 4",
          bought.get("returnEnabled") is False)


def test_email_validation(client: Client):
    section("Email validation")
    status, body = client.calculate("not-an-email", BASE_CONFIG)
    check("Invalid email -> HTTP 400", status == 400, f"got {status}: {body}")
    check("Invalid email -> error message present", bool(body.get("error")))


def test_discount_code_lifecycle(client: Client):
    section("Discount code lifecycle (Level 4, normal mode)")
    client.set_settings({"level": 4, "bugs": {"discountCodeMode": "normal"}})
    email = new_email("codes")

    status, bought1 = client.buy(email, BASE_CONFIG)
    check("Buy #1: HTTP 200", status == 200)
    code = bought1.get("generatedCode")
    check("Buy #1: a discount code was generated", bool(code), f"got {bought1}")

    status, calc = client.calculate(email, BASE_CONFIG, discount_code=code)
    check("Calculate with the code: valid, 15% off",
          calc.get("discountCode", {}).get("valid") is True)
    want_discounted = round(base_price(BASE_CONFIG) * 0.85, 2)
    check("Calculate with the code: paidPrice reflects 15% off",
          calc.get("paidPrice") == want_discounted,
          f"expected {want_discounted}, got {calc.get('paidPrice')}")

    status, bought2 = client.buy(email, BASE_CONFIG, discount_code=code)
    check("Buy #2 (with code): HTTP 200", status == 200)
    check("Buy #2: discount was applied", bought2.get("discountCode", {}).get("valid") is True)
    check("Buy #2: no new code generated for a discounted purchase",
          bought2.get("generatedCode") is None, f"got {bought2}")

    status, calc_reuse = client.calculate(email, BASE_CONFIG, discount_code=code)
    check("Reusing the code: now invalid",
          calc_reuse.get("discountCode", {}).get("valid") is False)
    check("Reusing the code: 'already used' message",
          calc_reuse.get("discountCode", {}).get("message") == "This code was already used",
          f"got {calc_reuse.get('discountCode')}")


def test_return_oldest_match_and_credit(client: Client):
    section("Return: oldest-match rule + store credit accumulation")
    client.set_settings({"level": 4, "bugs": {"discountCodeMode": "normal", "creditBasis": "paid"}})
    email = new_email("return")
    want = base_price(BASE_CONFIG)

    client.buy(email, BASE_CONFIG)  # purchase #1 (oldest)
    client.buy(email, BASE_CONFIG)  # purchase #2 (identical config)

    status, ret1 = client.ret(email, BASE_CONFIG, "StoreCredit")
    check("Return #1 (StoreCredit): HTTP 200", status == 200)
    check("Return #1: matched and succeeded", ret1.get("success") is True, f"got {ret1}")
    check("Return #1: credit added equals paid price of the OLDEST purchase",
          ret1.get("creditAdded") == want, f"expected {want}, got {ret1.get('creditAdded')}")
    check("Return #1: returnEnabled still true (one purchase left)",
          ret1.get("returnEnabled") is True)

    status, status_body = client.student_status(email)
    check("student-status after return #1: returnEnabled true", status_body.get("returnEnabled") is True)

    status, ret2 = client.ret(email, BASE_CONFIG, "Refund")
    check("Return #2 (Refund): matched and succeeded", ret2.get("success") is True)
    check("Return #2: returnEnabled now false (nothing left)", ret2.get("returnEnabled") is False)

    status, ret3 = client.ret(email, BASE_CONFIG, "Refund")
    check("Return #3 (nothing left): HTTP 200, not an error", status == 200)
    check("Return #3: success is false (no match)", ret3.get("success") is False)
    check("Return #3: correct no-match message",
          ret3.get("message", "").startswith("Return action failed"))


def test_discount_bug_accept_any(client: Client):
    section("Bug: discountCodeMode = acceptAny")
    client.set_settings({"level": 4, "requiredEmailDomain": "", "bugs": {"discountCodeMode": "acceptAny"}})
    email = new_email("acceptany")
    status, calc = client.calculate(email, BASE_CONFIG, discount_code="XXXXXXX")
    check("Garbage 7-char code accepted as valid", calc.get("discountCode", {}).get("valid") is True)


def test_discount_bug_accept_none(client: Client):
    section("Bug: discountCodeMode = acceptNone")
    client.set_settings({"bugs": {"discountCodeMode": "acceptNone"}})
    email = new_email("acceptnone")
    status, calc = client.calculate(email, BASE_CONFIG, discount_code="XXXXXXX")
    check("Any code rejected, even a well-formed one",
          calc.get("discountCode", {}).get("valid") is False)
    check("Message is 'Unknown code'", calc.get("discountCode", {}).get("message") == "Unknown code")
    client.set_settings({"bugs": {"discountCodeMode": "normal"}})


def test_partial_config_bug(client: Client):
    section("Bug: allowBuyWithPartialConfig")
    client.set_settings({"level": 1, "bugs": {"allowBuyWithPartialConfig": True}})
    email = new_email("partial-on")
    partial = dict(BASE_CONFIG, accessory="")
    status, bought = client.buy(email, partial)
    check("Bug ON: partial-config Buy succeeds", status == 200, f"got {status}: {bought}")

    client.set_settings({"bugs": {"allowBuyWithPartialConfig": False}})
    email2 = new_email("partial-off")
    status, body = client.buy(email2, partial)
    check("Bug OFF: partial-config Buy rejected (HTTP 400)", status == 400, f"got {status}: {body}")


def test_credit_basis_base_bug(client: Client):
    section("Bug: creditBasis = base (store-credit exploit)")
    client.set_settings({"level": 4, "bugs": {"discountCodeMode": "normal", "creditBasis": "base"}})
    email = new_email("creditbug")

    status, bought1 = client.buy(email, BASE_CONFIG)
    code = bought1["generatedCode"]
    status, bought2 = client.buy(email, BASE_CONFIG, discount_code=code)  # discounted purchase
    want_base = base_price(BASE_CONFIG)
    want_paid = round(want_base * 0.85, 2)
    check("Sanity: purchase #2 was actually discounted",
          bought2.get("paidPrice") == want_paid)

    status, ret = client.ret(email, BASE_CONFIG, "StoreCredit")
    check("Store credit paid out at BASE price (bug), not the discounted price",
          ret.get("creditAdded") == want_base,
          f"expected {want_base} (base), got {ret.get('creditAdded')} (would be {want_paid} if using paid price correctly)")

    client.set_settings({"bugs": {"creditBasis": "paid"}})


def test_return_stays_available_bug(client: Client):
    section("Bug: returnStaysAvailableWhenEmpty")
    client.set_settings({"level": 4, "bugs": {"returnStaysAvailableWhenEmpty": True}})
    email = new_email("staysavail")
    client.buy(email, BASE_CONFIG)
    client.ret(email, BASE_CONFIG, "Refund")
    status, status_body = client.student_status(email)
    check("returnEnabled stays true even with nothing left to return",
          status_body.get("returnEnabled") is True)
    client.set_settings({"bugs": {"returnStaysAvailableWhenEmpty": False}})


def test_allow_code_reuse_bug(client: Client):
    section("Bug: allowDiscountCodeReuse")
    client.set_settings({"level": 4, "bugs": {"allowDiscountCodeReuse": True}})
    email = new_email("reuse")
    status, bought = client.buy(email, BASE_CONFIG)
    code = bought["generatedCode"]
    client.buy(email, BASE_CONFIG, discount_code=code)  # use it once
    status, calc = client.calculate(email, BASE_CONFIG, discount_code=code)  # use it again
    check("A used code is still valid when the reuse bug is on",
          calc.get("discountCode", {}).get("valid") is True)
    client.set_settings({"bugs": {"allowDiscountCodeReuse": False}})


def test_required_email_domain(client: Client):
    section("requiredEmailDomain enforcement")
    client.set_settings({"requiredEmailDomain": "example.com"})
    status, body = client.calculate("student@other.com", BASE_CONFIG)
    check("Wrong domain -> HTTP 400", status == 400, f"got {status}: {body}")
    email = new_email("domain")  # already @example.com
    status, calc = client.calculate(email, BASE_CONFIG)
    check("Matching domain -> HTTP 200", status == 200)
    client.set_settings({"requiredEmailDomain": ""})


def test_student_self_reset(client: Client):
    section("Student self-reset")
    client.set_settings({"level": 4, "studentResetEnabled": True})
    email = new_email("selfreset")
    client.buy(email, BASE_CONFIG)
    status, result = client.reset_student(email)
    check("Reset: HTTP 200", status == 200)
    status, status_body = client.student_status(email)
    check("After reset: returnEnabled false", status_body.get("returnEnabled") is False)
    check("After reset: creditBalance is 0", status_body.get("creditBalance") == 0)

    client.set_settings({"studentResetEnabled": False})
    email2 = new_email("selfreset-disabled")
    status, body = client.reset_student(email2)
    check("Reset while disabled -> HTTP 400", status == 400, f"got {status}: {body}")


def test_teacher_auth(base_url: str, username: str, password: str):
    section("Teacher auth (401 / wrong password / login / logout)")
    anon = Client(base_url)
    status, body = anon.get("/api/teacher/settings")
    check("No session -> HTTP 401", status == 401, f"got {status}: {body}")

    status, body = anon.post("/api/teacher/login", {"username": username, "password": "definitely-wrong"})
    check("Wrong password -> HTTP 401", status == 401, f"got {status}: {body}")

    status, body = anon.post("/api/teacher/login", {"username": username, "password": password})
    check("Correct password -> HTTP 200", status == 200, f"got {status}: {body}")

    status, body = anon.get("/api/teacher/settings")
    check("Authenticated -> settings readable", status == 200)

    anon.logout()
    status, body = anon.get("/api/teacher/settings")
    check("After logout -> HTTP 401 again", status == 401)


def test_wipe_all_data(client: Client):
    section("Teacher reset-all (DESTRUCTIVE -- wipes every student's data)")
    print("  This will permanently delete ALL students' purchases, discount")
    print("  codes, store credit, and the action log on this deployment.")
    typed = input("  Type RESET to confirm, anything else to skip: ")
    if typed != "RESET":
        print("  Skipped.")
        return
    email = new_email("wipe-check")
    client.buy(email, BASE_CONFIG)
    status, body = client.post("/api/teacher/reset-all")
    check("reset-all: HTTP 200", status == 200, f"got {status}: {body}")
    status, status_body = client.student_status(email)
    check("After reset-all: a previously-purchased email now shows returnEnabled false",
          status_body.get("returnEnabled") is False)


# ---------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------

def cleanup_test_data(client: Client, original_settings: dict):
    if not _created_emails:
        return
    section("Cleanup: removing generated test data")
    client.set_settings({"studentResetEnabled": True})
    for email in _created_emails:
        client.reset_student(email)
    print(f"  Reset {len(_created_emails)} test email(s).")
    client.set_settings(original_settings)
    print("  Restored original teacher settings.")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://localhost:3000"),
                         help="e.g. http://localhost:3000 or https://sw-test-courses-exercises.vercel.app")
    parser.add_argument("--username", default=os.environ.get("TEACHER_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("TEACHER_PASSWORD"))
    parser.add_argument("--wipe-all-data", action="store_true",
                         help="Also run the destructive teacher reset-all check (still asks for interactive confirmation).")
    args = parser.parse_args()

    username = args.username or input("Teacher username: ")
    password = args.password or getpass.getpass("Teacher password: ")

    print(f"Target: {args.base_url}")
    print(f"Run ID: {RUN_ID}")

    client = Client(args.base_url)
    client.login(username, password)
    original_settings = client.get_settings()

    try:
        test_level1_calculate_and_buy(client)
        test_email_validation(client)
        test_discount_code_lifecycle(client)
        test_return_oldest_match_and_credit(client)
        test_discount_bug_accept_any(client)
        test_discount_bug_accept_none(client)
        test_partial_config_bug(client)
        test_credit_basis_base_bug(client)
        test_return_stays_available_bug(client)
        test_allow_code_reuse_bug(client)
        test_required_email_domain(client)
        test_student_self_reset(client)
        test_teacher_auth(args.base_url, username, password)
        if args.wipe_all_data:
            test_wipe_all_data(client)
        else:
            print("\n(Skipping the destructive reset-all check -- pass --wipe-all-data to include it.)")
    finally:
        cleanup_test_data(client, original_settings)

    passed = sum(1 for status, _ in _all_results if status == "PASS")
    failed = [label for status, label in _all_results if status == "FAIL"]

    print(f"\n{'=' * 60}")
    print(f"{passed}/{len(_all_results)} checks passed.")
    if failed:
        print("\nFAILED:")
        for label in failed:
            print(f"  - {label}")
        print("\nSOME CHECKS FAILED")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
