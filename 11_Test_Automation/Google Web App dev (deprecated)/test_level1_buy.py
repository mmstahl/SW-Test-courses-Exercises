"""
Level 1 "under the UI" verification: Calculate Price, then Buy.

Exercises the same two calls as the curl examples given earlier in this
project (email + 5 parameters -> Calculate -> Buy), and independently
recomputes the expected price rather than trusting the server's own number.

NOTE on the "message" check: buyPhone's JSON response has no message field
at all -- the "Congratulations..." text is built entirely client-side, in
student.html's buildCongratsMessage(), never sent by the server. So this
script cannot literally compare a "returned message" against anything.
What it verifies instead: the `config` the server echoes back in its Buy
response matches what was actually requested (the data the message would be
built from) -- and separately reconstructs, using the exact same logic as
student.html, what the congrats message would say, purely so you can see it.
That reconstruction is not a server contract; if you want the message text
itself to be a testable API field, that needs a small server-side change.

calculate_price() shells out to the actual curl command rather than using
the requests library, so the command being run "under the UI" is literal
and visible, not hidden behind a Python HTTP client. buy_phone() still uses
requests directly.

Requires: pip install requests, and curl available on PATH.
"""

import json
import subprocess
import sys
import time
import urllib.parse

import requests

BASE_URL = "https://script.google.com/macros/s/AKfycbyb9Fyf079yquXQ8zUZ8fTTp8NJwVt4US7mbj27vpCMzW_CCDuL71KVHPP-kAjI-m6E/exec"
EMAIL = "student01@post.jce.ac.il"

CONFIG = {
    "model": "Pixel 9",
    "storage": "128GB",
    "color": "Black",
    "network": "5G",
    "accessory": "None",
}

# Mirrors PRICE_TABLE in Code.js exactly -- must be kept in sync by hand if
# that table ever changes, since this is deliberately an independent
# recomputation, not a copy fetched from the server.
PRICE_TABLE = {
    "model": {"Pixel 9": 900, "Pixel 9 Pro": 1050, "Pixel 9 Pro XL": 1430},
    "storage": {"128GB": 0, "256GB": 56, "512GB": 98, "1TB": 164},
    "color": {"Black": 0, "Red": 100, "Silver": 80, "Blue": 60},
    "network": {"5G": 115, "4G": 0},
    "accessory": {"None": 0, "Case": 45, "Charger": 32, "Earbuds": 215},
}


def expected_price(config: dict) -> float:
    """Independently computes the base price, the same way Code.js's
    computeBasePrice_() does: sum each parameter's price, 0 for anything
    missing or not in the table."""
    total = 0
    for param, value in config.items():
        total += PRICE_TABLE[param].get(value, 0)
    return round(total, 2)


def expected_congrats_message(config: dict) -> str:
    """Reconstructs the message student.html's buildCongratsMessage() would
    show -- NOT something the server returns. See module docstring."""
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


def calculate_price(email: str, config: dict) -> dict:
    """Same call as before, but run via the actual `curl` command (through
    subprocess) instead of the requests library, so the exact command being
    executed is visible rather than hidden behind a Python HTTP client.
    Returns the full {"ok": ..., "data"/"error": ...} envelope -- the caller
    decides how to treat ok:false, rather than this raising and hiding that
    as a Python exception instead of a checkable result.
    
    example curl command (run on CMD shell):
    curl -sL https://script.google.com/macros/s/AKfycbyb9Fyf079yquXQ8zUZ8fTTp8NJwVt4US7mbj27vpCMzW_CCDuL71KVHPP-kAjI-m6E/exec?action=calculate&email=student01%40post.jce.ac.il&model=Pixel+9&storage=128GB&color=Black&network=5G&accessory=None

    returns (on cmd shell):
    {"ok":true,"data":{"email":"student01@post.jce.ac.il","config":{"Model":"Pixel 9","Storage":"128GB","Color":"Black","Network":"5G","Accessory":"None"},"basePrice":1015,"discountCode":{"entered":"","valid":false,"message":null},"paidPrice":1015}}

    """
    query = urllib.parse.urlencode({"action": "calculate", "email": email, **config})
    url = f"{BASE_URL}?{query}"
    # -sL: Apps Script /exec URLs respond with a redirect to a
    # script.googleusercontent.com URL that actually serves the JSON; without
    # this, curl returns the (empty-bodied) redirect response instead.
    command = ["curl", "-sL", url]
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
    try:
        return json.loads(stdout_text)
    except json.JSONDecodeError:
        print(f"  !! Non-JSON output from curl. returncode={result.returncode}")
        print(f"  !! stdout (first 500 chars): {stdout_text[:500]!r}")
        print(f"  !! stderr (first 500 chars): {result.stderr.decode('utf-8', errors='replace')[:500]!r}")
        raise


def buy_phone(email: str, config: dict) -> dict:
    """POST to /exec, then GET the redirect Location -- confirmed empirically
    (not guessed): the POST already executed doPost() on the first hop; the
    302's Location is a content-serving URL for the already-computed result,
    which only accepts GET. No cookies or preserved-POST tricks needed."""
    payload = {"action": "buy", "email": email, **config}
    resp = requests.post(BASE_URL, json=payload, allow_redirects=False)
    if resp.is_redirect and "Location" in resp.headers:
        resp = requests.get(resp.headers["Location"])
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        # Diagnostic, not a guess: show exactly what came back instead of
        # letting a bare JSONDecodeError hide the actual cause.
        print(f"  !! Non-JSON response. status={resp.status_code}")
        print(f"  !! final URL: {resp.url}")
        print(f"  !! headers: {dict(resp.headers)}")
        print(f"  !! body (first 500 chars): {resp.text[:500]!r}")
        raise


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail and not condition else ""))
    return condition


def call_with_retries(fn, max_attempts: int = 3, backoff_seconds: float = 3.0):
    """Retries transient failures against the Apps Script redirect/delivery
    path -- observed empirically to be erratic for automated (non-browser)
    traffic even though the underlying server-side code itself runs fast
    (confirmed by comparing ActionLog timestamps to when Python actually
    receives the response). This doesn't fix that -- it's Google's own
    infrastructure, not something in this project's control -- but retrying
    is both a reasonable mitigation and a realistic thing any real test
    suite hitting this endpoint should do anyway."""
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                print(f"  (attempt {attempt}/{max_attempts} failed: "
                      f"{exc.__class__.__name__}: {exc}; retrying in {backoff_seconds:.0f}s)")
                time.sleep(backoff_seconds)
    raise last_exc


def main() -> int:
    all_passed = True
    want_price = expected_price(CONFIG)

    # ---- 1) Calculate Price ----
    print("Calculating price...")
    t0 = time.perf_counter()
    calc_body = call_with_retries(lambda: calculate_price(EMAIL, CONFIG))
    calc_elapsed = time.perf_counter() - t0
    print(f"  ({calc_elapsed:.2f}s)")
    if not check("Calculate: request succeeded (ok == true)", calc_body.get("ok") is True,
                  f"server said: {calc_body.get('error')}"):
        print("\nSOME CHECKS FAILED")
        return 1
    calc = calc_body["data"]
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
    # Deliberately NOT retried, unlike Calculate: Buy is not idempotent (it
    # records a purchase every call), and the evidence from ActionLog is
    # that a slow/failed HTTP response often follows a purchase that
    # already completed server-side -- retrying here risks creating a
    # duplicate purchase for what looks, from here, like one failed attempt.
    print("\nBuying...")
    t1 = time.perf_counter()
    buy_body = buy_phone(EMAIL, CONFIG)
    buy_elapsed = time.perf_counter() - t1
    print(f"  ({buy_elapsed:.2f}s)")
    if not check("Buy: request succeeded (ok == true)", buy_body.get("ok") is True,
                  f"server said: {buy_body.get('error')}"):
        print("\nSOME CHECKS FAILED")
        return 1
    bought = buy_body["data"]
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


if __name__ == "__main__":
    sys.exit(main())
