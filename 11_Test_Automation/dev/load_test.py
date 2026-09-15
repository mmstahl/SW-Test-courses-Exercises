"""
load_test.py -- Concurrent load test for the Phone Configurator Simulator.

Simulates N "students" (virtual users), each running in its own thread,
each in a tight closed loop: build a random valid 5-parameter
configuration, send either Calculate Price or Buy, wait for the response,
then immediately send the next request. That's the actual access pattern
30 students' independent ChromeDriver/curl/requests test scripts produce
during a live class -- not a fixed request rate, but N clients each
firing as fast as *their own* previous response allows.

This is a direct test of the concurrency design in lib/db.js: every Buy
takes a per-student Postgres advisory lock inside one transaction. If
that's wrong or the connection pool is undersized, this is where you'd
see it -- duplicate purchase-sequence numbers, timeouts, connection-pool
exhaustion, or rising latency under concurrent load.

IMPORTANT -- read before running against production
-----------------------------------------------------
This sends real traffic and, for Buy actions, creates real purchase rows.
All virtual users use clearly-tagged emails
(load-test-user-01@example.com, ...), and if you supply teacher
credentials (--teacher-username/--teacher-password), the script cleans
up all of that data via student self-reset when it stops, and restores
whatever studentResetEnabled was set to beforehand. Without teacher
credentials, no cleanup happens -- the load-test purchases are left in
place (same as real students' data would be), which is harmless but
worth knowing.

This also generates genuine load on the shared production database.
Don't run a large --users count against production while a class is
actively using the app.

USAGE
-----
    python load_test.py --base-url https://sw-test-courses-exercises.vercel.app --users 10
    python load_test.py --base-url http://localhost:3000 --users 30

Runs until you press Ctrl+C (each virtual user finishes its in-flight
request, then a final summary is printed), or until --duration seconds
have elapsed if you pass that instead.

Requires: pip install requests
"""

import argparse
import random
import statistics
import threading
import time

import requests

DEFAULT_OPTIONS = {
    "Model": ["Pixel 9", "Pixel 9 Pro", "Pixel 9 Pro XL"],
    "Storage": ["128GB", "256GB", "512GB", "1TB"],
    "Color": ["Black", "Red", "Silver", "Blue"],
    "Network": ["5G", "4G"],
    "Accessory": ["None", "Case", "Charger", "Earbuds"],
}

ACTIONS = ("calculate", "buy")

stop_event = threading.Event()
stats_lock = threading.Lock()
stats = {action: {"success": 0, "error": 0, "latencies": []} for action in ACTIONS}


def record(action: str, elapsed: float, ok: bool) -> None:
    with stats_lock:
        bucket = stats[action]
        bucket["latencies"].append(elapsed)
        bucket["success" if ok else "error"] += 1


def random_config(options: dict) -> dict:
    return {
        "model": random.choice(options["Model"]),
        "storage": random.choice(options["Storage"]),
        "color": random.choice(options["Color"]),
        "network": random.choice(options["Network"]),
        "accessory": random.choice(options["Accessory"]),
    }


def user_loop(user_id: int, base_url: str, options: dict, buy_weight: float,
              think_time: float, timeout: float) -> None:
    email = f"load-test-user-{user_id:02d}@example.com"
    session = requests.Session()
    while not stop_event.is_set():
        config = random_config(options)
        action = "buy" if random.random() < buy_weight else "calculate"
        t0 = time.perf_counter()
        try:
            if action == "calculate":
                params = dict(config, email=email, discountCode="")
                resp = session.get(f"{base_url}/api/calculate", params=params, timeout=timeout)
            else:
                body = dict(config, email=email, discountCode="")
                resp = session.post(f"{base_url}/api/buy", json=body, timeout=timeout)
            elapsed = time.perf_counter() - t0
            ok = resp.status_code == 200
            record(action, elapsed, ok)
            if not ok:
                print(f"  [user {user_id:02d}] {action} -> HTTP {resp.status_code}: {resp.text[:150]}")
        except requests.RequestException as exc:
            elapsed = time.perf_counter() - t0
            record(action, elapsed, False)
            print(f"  [user {user_id:02d}] {action} -> EXCEPTION: {exc}")
        if think_time > 0:
            time.sleep(think_time)


def percentile(data, p):
    if not data:
        return float("nan")
    data = sorted(data)
    k = (len(data) - 1) * p
    f, c = int(k), min(int(k) + 1, len(data) - 1)
    if f == c:
        return data[f]
    return data[f] + (data[c] - data[f]) * (k - f)


def snapshot():
    """Returns a deep-enough copy of `stats` for safe reporting outside the lock."""
    with stats_lock:
        return {
            action: {
                "success": bucket["success"],
                "error": bucket["error"],
                "latencies": list(bucket["latencies"]),
            }
            for action, bucket in stats.items()
        }


def format_bucket(label: str, bucket: dict, latencies_since=None) -> str:
    total = bucket["success"] + bucket["error"]
    lat = latencies_since if latencies_since is not None else bucket["latencies"]
    if lat:
        mean = statistics.fmean(lat)
        p50 = percentile(lat, 0.50)
        p95 = percentile(lat, 0.95)
        mx = max(lat)
        lat_str = f"mean={mean * 1000:.0f}ms p50={p50 * 1000:.0f}ms p95={p95 * 1000:.0f}ms max={mx * 1000:.0f}ms"
    else:
        lat_str = "no samples yet"
    return f"{label:10s} total={total:6d} ok={bucket['success']:6d} err={bucket['error']:5d}  {lat_str}"


def print_report(elapsed_total: float, prev_snapshot: dict, prev_time: float) -> dict:
    now = time.perf_counter()
    interval = now - prev_time
    current = snapshot()
    print(f"\n--- {elapsed_total:6.0f}s elapsed ---")
    for action in ACTIONS:
        bucket = current[action]
        prev = prev_snapshot[action]
        delta_count = (bucket["success"] + bucket["error"]) - (prev["success"] + prev["error"])
        rps = delta_count / interval if interval > 0 else 0.0
        # Latencies for just this interval (recent tail of the list).
        recent = bucket["latencies"][len(prev["latencies"]):]
        print(f"  {format_bucket(action, bucket, latencies_since=recent)}  ({rps:.1f} req/s last {interval:.0f}s)")
    return current


def print_final_summary(start_time: float) -> None:
    elapsed = time.perf_counter() - start_time
    final = snapshot()
    print(f"\n{'=' * 70}")
    print(f"FINAL SUMMARY -- {elapsed:.0f}s total")
    total_requests = 0
    total_errors = 0
    for action in ACTIONS:
        bucket = final[action]
        total_requests += bucket["success"] + bucket["error"]
        total_errors += bucket["error"]
        print(f"  {format_bucket(action, bucket)}")
    overall_rps = total_requests / elapsed if elapsed > 0 else 0.0
    print(f"\n  {total_requests} total requests, {total_errors} errors, {overall_rps:.1f} req/s average.")
    print("=" * 70)


def cleanup(base_url: str, num_users: int, teacher_username: str, teacher_password: str,
            original_reset_enabled) -> None:
    print("\nCleaning up load-test data...")
    session = requests.Session()
    resp = session.post(f"{base_url}/api/teacher/login",
                         json={"username": teacher_username, "password": teacher_password})
    if resp.status_code != 200:
        print(f"  Could not log in as teacher for cleanup ({resp.status_code}); skipping.")
        return

    if not original_reset_enabled:
        session.put(f"{base_url}/api/teacher/settings", json={"studentResetEnabled": True})

    for i in range(1, num_users + 1):
        email = f"load-test-user-{i:02d}@example.com"
        session.post(f"{base_url}/api/reset", json={"email": email})
    print(f"  Reset {num_users} load-test user(s).")

    session.put(f"{base_url}/api/teacher/settings", json={"studentResetEnabled": bool(original_reset_enabled)})
    print("  Restored studentResetEnabled to its original value.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True,
                         help="e.g. https://sw-test-courses-exercises.vercel.app or http://localhost:3000")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent virtual users. Default 10.")
    parser.add_argument("--buy-weight", type=float, default=0.3,
                         help="Fraction (0-1) of requests that are Buy rather than Calculate. Default 0.3.")
    parser.add_argument("--think-time", type=float, default=0.0,
                         help="Seconds to wait after each response before sending the next request. "
                              "Default 0 -- immediate, closed-loop, matching 'once the answer is received'.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout in seconds. Default 30.")
    parser.add_argument("--report-interval", type=float, default=5.0,
                         help="Seconds between progress reports. Default 5.")
    parser.add_argument("--duration", type=float, default=None,
                         help="Stop automatically after this many seconds, instead of running until Ctrl+C.")
    parser.add_argument("--teacher-username", default=None,
                         help="If given (with --teacher-password), load-test data is cleaned up automatically on stop.")
    parser.add_argument("--teacher-password", default=None)
    args = parser.parse_args()

    print(f"Target: {args.base_url}")
    print(f"Virtual users: {args.users}  |  buy-weight: {args.buy_weight}  |  think-time: {args.think_time}s")
    if args.users > 15:
        print(f"NOTE: {args.users} concurrent users is real load on a shared, likely-live deployment. "
              "Make sure nobody's mid-class right now.")

    try:
        resp = requests.get(f"{args.base_url}/api/product-options", timeout=10)
        resp.raise_for_status()
        options = resp.json()["options"]
    except Exception as exc:
        print(f"Could not fetch product options ({exc}); using built-in defaults.")
        options = DEFAULT_OPTIONS

    original_reset_enabled = None
    if args.teacher_username and args.teacher_password:
        probe = requests.Session()
        resp = probe.post(f"{args.base_url}/api/teacher/login",
                           json={"username": args.teacher_username, "password": args.teacher_password})
        if resp.status_code != 200:
            print(f"Teacher login failed ({resp.status_code}): {resp.json().get('error')} "
                  "-- continuing without auto-cleanup.")
        else:
            settings = probe.get(f"{args.base_url}/api/teacher/settings").json()
            original_reset_enabled = settings.get("studentResetEnabled")
            print("Teacher login OK -- load-test data will be cleaned up automatically on stop.")

    threads = []
    for i in range(1, args.users + 1):
        t = threading.Thread(
            target=user_loop,
            args=(i, args.base_url, options, args.buy_weight, args.think_time, args.timeout),
            daemon=True,
        )
        t.start()
        threads.append(t)

    print(f"\nStarted {args.users} virtual users. "
          + (f"Running for {args.duration:.0f}s." if args.duration else "Press Ctrl+C to stop.") + "\n")

    start_time = time.perf_counter()
    prev_snapshot = snapshot()
    prev_time = start_time
    try:
        while args.duration is None or (time.perf_counter() - start_time) < args.duration:
            time.sleep(args.report_interval)
            prev_snapshot = print_report(time.perf_counter() - start_time, prev_snapshot, prev_time)
            prev_time = time.perf_counter()
    except KeyboardInterrupt:
        print("\n\nStopping (letting in-flight requests finish)...")

    stop_event.set()
    for t in threads:
        t.join(timeout=args.timeout + 5)

    print_final_summary(start_time)

    if original_reset_enabled is not None:
        cleanup(args.base_url, args.users, args.teacher_username, args.teacher_password, original_reset_enabled)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
