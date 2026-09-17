"""
Level 1 "under the UI" verification: Calculate Price, then Buy -- against
the new Vercel + Postgres deployment instead of the old Apps Script one.

Mirrors ../dev/test_level1_buy.py's structure and intent (same two calls,
independently recomputed price, same "message is reconstructed, not
server-returned" caveat) but reflects what's actually different in the new
API:

* No {"ok": ..., "data"/"error": ...} envelope. A call either returns its
  data directly with HTTP 200, or {"error": "..."} with 400/401/500 -- this
  script checks the HTTP status code, not an "ok" field.
* Calculate is GET /api/calculate (query params); Buy is POST /api/buy
  (JSON body) -- one endpoint per action, no ?action=X dispatch and no
  dual GET/POST support on the same URL.
* No redirect dance. The old buy_phone() had to POST, then separately GET
  the redirect Location Apps Script's /exec sent back. That hop -- and its
  2-58s latency variance -- was the actual reason for this migration (see
  MIGRATION_BRIEF.md); here a single requests.post() is the whole call.
* No retry-for-flakiness wrapper around Calculate. The old version's
  call_with_retries() existed specifically because Apps Script's /exec
  redirect was empirically flaky, confirmed to be Google's infrastructure
  and not this app's own logic. Plain HTTP to Vercel doesn't have that
  problem, so there's nothing to retry around.

calculate_price() still shells out to the actual curl command (not the
requests library) so the literal "under the UI" command is visible, not
hidden behind a Python HTTP client -- same reasoning as the original.
buy_phone() uses requests directly, same as the original (Buy is a
mutating action, so it's POST there too -- that didn't change).

--student-name is REQUIRED (not defaulted): this script buys a real
phone under that email, and always resets that student's own data at
the end (POST /api/reset, no auth needed -- it's the same self-service
call the "Reset my data" button makes) so repeated runs start from a
clean slate, rather than stepping on other students' or other runs'
purchase history. That reset needs studentResetEnabled turned on --
this script does NOT set that itself (or any other setting): settings
are global to the whole deployment, so if every student's script
instance also toggled them, many running in parallel would race and
stomp on each other. Have the teacher turn studentResetEnabled on for
the class once, ahead of time. This never touches action_log: /api/reset
only deletes from purchases/discount_codes/store_credit, and the Reset
call itself adds a new action_log row rather than removing any.

Requires: pip install requests, and curl available on PATH.
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.parse

import requests

REMOTE_BASE_URL = "https://sw-test-courses-exercises.vercel.app"
LOCAL_BASE_URL = "http://localhost:3000"  # offline-server.js or vercel dev
BASE_URL = REMOTE_BASE_URL  # overwritten in main() based on --target/--base-url

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
    buildCongratsMessage() would show -- NOT something the server
    returns; the congrats text is still built entirely client-side."""
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


def calculate_price(email: str, config: dict):
    """GET /api/calculate via the actual `curl` command (through
    subprocess) instead of the requests library, so the exact command
    being executed is visible rather than hidden behind a Python HTTP
    client. Returns (http_status, parsed_json_body).

    example curl command (run on a shell):
    curl -s -w "\\n%{http_code}" "https://sw-test-courses-exercises.vercel.app/api/calculate?email=student01%40example.com&model=Pixel+9&storage=128GB&color=Black&network=5G&accessory=None"

    returns (body on its own line, HTTP status on the last line):
    {"email":"student01@example.com","config":{"Model":"Pixel 9","Storage":"128GB","Color":"Black","Network":"5G","Accessory":"None"},"basePrice":1015,"discountCode":{"entered":"","valid":false,"message":null},"paidPrice":1015}
    200
    """
    query = urllib.parse.urlencode({"email": email, **config})
    url = f"{BASE_URL}/api/calculate?{query}"
    command = ["curl", "-s", "-w", "\n%{http_code}", url]
    print(f"  $ {' '.join(command)}")
    # Deliberately NOT text=True: that makes subprocess decode curl's output
    # using the OS's default codepage (e.g. cp1255 on a Hebrew-locale
    # Windows machine) inside a background reader thread -- if any byte
    # doesn't fit that codepage, the thread crashes and stdout silently
    # comes back as None instead of raising cleanly. Our server always
    # emits UTF-8 JSON regardless of machine locale, so capture raw bytes
    # and decode as UTF-8 ourselves, with a fallback that turns anything
    # genuinely undecodable into a readable error instead of a crash.
    result = subprocess.run(command, capture_output=True, check=True)
    try:
        stdout_text = result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        stdout_text = result.stdout.decode("utf-8", errors="replace")
        print(f"  !! curl output was not valid UTF-8; decoded with replacement chars: {stdout_text[:500]!r}")
    body_text, _, status_text = stdout_text.rpartition("\n")
    try:
        status_code = int(status_text)
    except ValueError:
        print(f"  !! Could not parse HTTP status from curl output: {status_text!r}")
        raise
    try:
        return status_code, json.loads(body_text)
    except json.JSONDecodeError:
        print(f"  !! Non-JSON body from curl. status={status_code}")
        print(f"  !! body (first 500 chars): {body_text[:500]!r}")
        raise


def buy_phone(email: str, config: dict):
    """POST /api/buy directly -- no redirect handling needed (that was
    entirely an Apps Script /exec quirk; see MIGRATION_BRIEF.md). Returns
    (http_status, parsed_json_body)."""
    payload = {"email": email, **config}
    resp = requests.post(f"{BASE_URL}/api/buy", json=payload)
    try:
        return resp.status_code, resp.json()
    except ValueError:
        print(f"  !! Non-JSON response. status={resp.status_code}")
        print(f"  !! body (first 500 chars): {resp.text[:500]!r}")
        raise


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail and not condition else ""))
    return condition


# ---------------------------------------------------------------------
# Per-student reset (plain requests, not curl -- this isn't one of the
# "under the UI" calls this script exists to demonstrate, just teardown
# around them). No auth needed: same self-service call the "Reset my
# data" button makes for the currently-typed-in email.
# ---------------------------------------------------------------------

def reset_student(base_url: str, email: str):
    resp = requests.post(f"{base_url}/api/reset", json={"email": email})
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, {}


def main() -> int:
    global BASE_URL
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", choices=["local", "remote"], default="remote",
                         help=f"'local' = {LOCAL_BASE_URL} (offline-server.js or vercel dev), "
                              f"'remote' = {REMOTE_BASE_URL} (default).")
    parser.add_argument("--base-url", default=None,
                         help="Explicit base URL, overrides --target.")
    parser.add_argument("--student-name", required=True,
                         help="Local part of the student email to use, e.g. --student-name alice01. "
                              "Required (not defaulted) -- this test buys a real phone and always "
                              "resets that student's data afterward, so each run needs to be "
                              "unambiguously attributable to one student.")
    args = parser.parse_args()
    BASE_URL = args.base_url or (LOCAL_BASE_URL if args.target == "local" else REMOTE_BASE_URL)
    email = f"{args.student_name}@example.com"

    all_passed = True
    want_price = expected_price(CONFIG)

    print(f"Target: {BASE_URL}")

    try:
        # ---- 1) Calculate Price ----
        print(f"Calculating price for {email}...")
        t0 = time.perf_counter()
        calc_status, calc = calculate_price(email, CONFIG)
        calc_elapsed = time.perf_counter() - t0
        print(f"  ({calc_elapsed:.2f}s)")
        if not check("Calculate: request succeeded (HTTP 200)", calc_status == 200,
                      f"status={calc_status}, server said: {calc.get('error')}"):
            print("\nSOME CHECKS FAILED")
            return 1
        print(f"  Server returned basePrice={calc['basePrice']}, paidPrice={calc['paidPrice']}")
        all_passed &= check(
            "Calculate: basePrice matches independently computed price",
            calc["basePrice"] == want_price,
            f"expected {want_price}, got {calc['basePrice']}",
        )
        all_passed &= check(
            "Calculate: paidPrice equals basePrice (no discount at Level 1)",
            calc["paidPrice"] == want_price,
            f"expected {want_price}, got {calc['paidPrice']}",
        )

        # ---- 2) Buy ----
        # Deliberately not retried: Buy is not idempotent (it records a
        # purchase every call). Unlike the old Apps Script version, there's
        # also no known infrastructure flakiness here to retry around in the
        # first place.
        print("\nBuying...")
        t1 = time.perf_counter()
        buy_status, bought = buy_phone(email, CONFIG)
        buy_elapsed = time.perf_counter() - t1
        print(f"  ({buy_elapsed:.2f}s)")
        if not check("Buy: request succeeded (HTTP 200)", buy_status == 200,
                      f"status={buy_status}, server said: {bought.get('error')}"):
            print("\nSOME CHECKS FAILED")
            return 1
        print(f"  Server returned basePrice={bought['basePrice']}, paidPrice={bought['paidPrice']}")
        all_passed &= check(
            "Buy: basePrice matches independently computed price",
            bought["basePrice"] == want_price,
            f"expected {want_price}, got {bought['basePrice']}",
        )
        all_passed &= check(
            "Buy: paidPrice equals basePrice (no discount at Level 1)",
            bought["paidPrice"] == want_price,
            f"expected {want_price}, got {bought['paidPrice']}",
        )

        # "Message" check -- see module docstring: this verifies the echoed
        # config, then reconstructs (does not fetch) the message it implies.
        returned_config = {
            "model": bought["config"]["Model"],
            "storage": bought["config"]["Storage"],
            "color": bought["config"]["Color"],
            "network": bought["config"]["Network"],
            "accessory": bought["config"]["Accessory"],
        }
        all_passed &= check(
            "Buy: echoed config matches what was requested",
            returned_config == CONFIG,
            f"expected {CONFIG}, got {returned_config}",
        )
        print(f"  Reconstructed (not server-returned) message: "
              f"{expected_congrats_message(returned_config)!r}")

        print(f"\nTiming: calculate={calc_elapsed:.2f}s, buy={buy_elapsed:.2f}s, "
              f"total={calc_elapsed + buy_elapsed:.2f}s")
        print("\n" + ("ALL CHECKS PASSED" if all_passed else "SOME CHECKS FAILED"))
        return 0 if all_passed else 1
    finally:
        # Always reset this student's own data -- not a reset-ALL, just
        # the same per-student cleanup the "Reset my data" button
        # performs -- so the next run starts from a clean slate. Never
        # touches action_log (see module docstring). Requires
        # studentResetEnabled to already be on; if it isn't, this just
        # warns rather than failing the whole run.
        reset_status, reset_body = reset_student(BASE_URL, email)
        if reset_status == 200:
            print(f"\nReset {email}'s data (clean slate for next run).")
        else:
            print(f"\n[WARN] Could not reset {email}'s data: "
                  f"HTTP {reset_status} {reset_body.get('error')}")


if __name__ == "__main__":
    sys.exit(main())
