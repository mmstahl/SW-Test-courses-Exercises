#!/usr/bin/env python3
"""
triplet_coverage_monitor.py -- live widget that watches the Phone
Configurator Simulator's action_log and shows a horizontal bar chart of
each student's all-triplets (3-way) combinatorial coverage for the
Level 1 exercise.

USAGE
    python triplet_coverage_monitor.py [options]

    Reads DATABASE_URL from .env.local in this folder by default (the
    same file `vercel dev` uses), or pass --database-url / set the
    DATABASE_URL environment variable explicitly.

WHAT "ALL TRIPLETS" MEANS HERE
    Level 1 has 5 parameters (Model, Storage, Color, Network, Accessory).
    For every one of the C(5,3) = 10 distinct 3-parameter subsets, has
    every possible combination of values for those 3 parameters been
    exercised by at least one Calculate Price call? Working that out from
    the actual option counts (Model=3, Storage=4, Color=4, Network=2,
    Accessory=4) gives TOTAL_TRIPLETS = 376 distinct triplets across all
    10 subsets, computed below rather than hardcoded.

WHY CALCULATE PRICE ONLY (not Buy)
    Calculate Price is where a well-written student test has an
    independently computed expected price to assert against (see
    test_level1_buy.py) -- a bug in the price calculation for a given
    parameter combination shows up there. Buy is a side-effecting action,
    not the coverage signal for this exercise, so it's excluded even
    though it also submits a full config.

HOW IT READS THE DATA
    Connects directly to Postgres (the same DATABASE_URL db/migrate.js
    uses) and reads action_log on its own schedule -- it never goes
    through the app's API at all, so it adds zero load to whatever
    students' own requests are doing; it's a completely separate
    resource. Coverage is recomputed from scratch on every poll (cheap at
    class-sized data volumes), so there's no incremental state to drift
    out of sync.

    By default, only rows logged AFTER THIS SCRIPT STARTS are counted
    (--since defaults to "now") -- action_log accumulates rows from
    development/testing that have nothing to do with any real class.
    Pass --since-start-of-day to count everything logged today instead.

    Note: a student's own self-reset does NOT clear action_log (only
    their Purchases/Codes/Credit), so coverage tracking is unaffected by
    students resetting their data mid-exercise. Only a teacher's "Reset
    simulator data" wipes action_log too, which would legitimately zero
    everyone's coverage here.

DESIGN
    Follows sheet_monitor.py's pattern: a background thread fetches on
    its own schedule and hands off a fully-formed "state" dict (protected
    by a lock, versioned so the UI thread can tell when something new has
    arrived) to a fast, independent UI-thread poll loop -- so a
    slow/stalled database read never freezes the window. Bar thickness is
    held at a fixed pixel value via ROW_HEIGHT_IN regardless of window
    size or student count; a scrollbar appears instead of bars shrinking
    when more students are being tracked than comfortably fit.

Requires: pip install psycopg2-binary matplotlib
"""

import argparse
import colorsys
import hashlib
import itertools
import os
import threading
import tkinter as tk
from collections import defaultdict
from datetime import datetime, date, time as dtime
from pathlib import Path

import psycopg2
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

# --- Coverage universe -------------------------------------------------
# Mirrors PRICE_TABLE in lib/priceTable.js -- only the value lists are
# needed here (not the prices), to define what "all triplets" covers.
PARAM_OPTIONS = {
    "Model": ["Pixel 9", "Pixel 9 Pro", "Pixel 9 Pro XL"],
    "Storage": ["128GB", "256GB", "512GB", "1TB"],
    "Color": ["Black", "Red", "Silver", "Blue"],
    "Network": ["5G", "4G"],
    "Accessory": ["None", "Case", "Charger", "Earbuds"],
}
# Order matters: matches configToLogString()'s
# Model|Storage|Color|Network|Accessory join order in lib/validation.js.
PARAM_NAMES = list(PARAM_OPTIONS.keys())

# All C(5,3) = 10 distinct 3-parameter subsets, as index-triples into
# PARAM_NAMES.
SUBSETS = list(itertools.combinations(range(5), 3))

TOTAL_TRIPLETS = sum(
    len(PARAM_OPTIONS[PARAM_NAMES[a]]) * len(PARAM_OPTIONS[PARAM_NAMES[b]]) * len(PARAM_OPTIONS[PARAM_NAMES[c]])
    for (a, b, c) in SUBSETS
)

# --- Fixed layout constants (all in inches, at a constant DPI) --------
# Because every one of these is a constant number of inches, and DPI is
# fixed, each bar always occupies exactly ROW_HEIGHT_IN * DPI pixels,
# regardless of how many bars there are or how the window is resized.
DPI = 100
ROW_HEIGHT_IN = 0.5        # vertical space reserved per bar (bar + gap)
BAR_FRACTION = 0.7         # fraction of a row's height the bar itself fills
TOP_MARGIN_IN = 0.55       # room for the title
BOTTOM_MARGIN_IN = 0.75    # room for the x-axis label/ticks
LEFT_FRACTION = 0.32       # fraction of figure width reserved for name labels
RIGHT_FRACTION = 0.95
BARS_TO_FIT = 12           # default window is sized to comfortably fit this many
MIN_WIDTH_IN = 6.0
DEFAULT_WIDTH_IN = 9.0


def color_for_label(label: str):
    """Deterministic color per label so each student keeps the same bar
    color across refreshes, regardless of sort order or how many other
    students are shown."""
    digest = hashlib.md5(label.encode("utf-8")).hexdigest()
    hue = (int(digest, 16) % 360) / 360.0
    return colorsys.hsv_to_rgb(hue, 0.6, 0.85)


class FetchError(Exception):
    """Raised whenever we can't get a clean coverage snapshot from the DB."""


def load_database_url_from_env_file():
    env_path = Path(__file__).parent / ".env.local"
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def fetch_coverage(database_url: str, since: datetime) -> dict:
    """Returns {student_email: distinct_triplet_count} for CalculatePrice
    actions logged at or after `since`."""
    try:
        conn = psycopg2.connect(database_url, connect_timeout=10)
    except Exception as e:
        raise FetchError(f"Could not connect to the database: {e}")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT student_email, parameters
                FROM action_log
                WHERE action = 'CalculatePrice'
                  AND result <> 'Error'
                  AND created_at >= %s
                """,
                (since,),
            )
            rows = cur.fetchall()
    except Exception as e:
        raise FetchError(f"Query failed: {e}")
    finally:
        conn.close()

    covered = defaultdict(set)
    for email, parameters in rows:
        values = (parameters or "").split("|")
        if len(values) != 5 or not all(values):
            continue  # partial/blank config -- nothing meaningful to count
        for (a, b, c) in SUBSETS:
            covered[email].add((a, b, c, values[a], values[b], values[c]))
    return {email: len(triplets) for email, triplets in covered.items()}


class CoverageMonitorApp:
    """Tkinter widget embedding a matplotlib chart inside a scrollable
    canvas, so bar thickness can be held at a fixed pixel value no matter
    how many students are shown or how the window is resized. Mirrors
    sheet_monitor.py's SheetMonitorApp structure -- see module docstring."""

    def __init__(self, root: tk.Tk, database_url: str, since: datetime, interval: float):
        self.root = root
        self.database_url = database_url
        self.since = since
        self.interval = interval
        self.color_map = {}
        self._last_width_px = None
        self._state_lock = threading.Lock()
        self._state = {"kind": "loading", "message": "Loading data..."}
        self._version = 0
        self._seen_version = -1
        self._stop_event = threading.Event()

        root.title("Level 1 Triplet Coverage Monitor")
        default_height_in = BARS_TO_FIT * ROW_HEIGHT_IN + TOP_MARGIN_IN + BOTTOM_MARGIN_IN
        root.geometry(
            f"{int(DEFAULT_WIDTH_IN * DPI) + 40}x{int(default_height_in * DPI) + 40}"
        )

        self.status_frame = tk.Frame(root, bg="#f5f5f5", bd=1, relief=tk.SUNKEN)
        self.status_frame.pack(fill=tk.X, side=tk.TOP)

        self.count_label = tk.Label(
            self.status_frame, text="Students tracked: 0", bg="#f5f5f5",
            fg="#333333", font=("Helvetica", 10, "bold"),
        )
        self.count_label.pack(side=tk.LEFT, padx=10, pady=5)

        since_text = f"Tracking Calculate Price actions since {since.strftime('%H:%M:%S')}"
        tk.Label(self.status_frame, text=since_text, bg="#f5f5f5", fg="#666666").pack(side=tk.LEFT, padx=10)

        self.update_alert_label = tk.Label(self.status_frame, text="", bg="#f5f5f5", font=("Helvetica", 10, "bold"))
        self.update_alert_label.pack(side=tk.RIGHT, padx=10, pady=5)

        outer = tk.Frame(root)
        outer.pack(fill=tk.BOTH, expand=True)

        self.scroll_canvas = tk.Canvas(outer, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(
            outer, orient=tk.VERTICAL, command=self.scroll_canvas.yview
        )
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner_frame = tk.Frame(self.scroll_canvas)
        self.inner_window = self.scroll_canvas.create_window(
            (0, 0), window=self.inner_frame, anchor="nw"
        )

        self.fig = Figure(figsize=(DEFAULT_WIDTH_IN, default_height_in), dpi=DPI)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.inner_frame)
        self.canvas.get_tk_widget().pack()

        self.scroll_canvas.bind("<Configure>", self._on_viewport_resize)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self._fetch_thread.start()

        self.root.after(150, self._poll)

    # -- background data fetching -------------------------------------
    def _fetch_loop(self):
        while not self._stop_event.is_set():
            try:
                coverage = fetch_coverage(self.database_url, self.since)
                if not coverage:
                    new_state = {"kind": "empty", "message": "No Calculate Price activity yet"}
                else:
                    new_state = {"kind": "data", "counts": coverage}
            except FetchError as e:
                new_state = {"kind": "error", "message": str(e)}
            except Exception as e:
                new_state = {"kind": "error", "message": f"Unexpected error: {e}"}

            with self._state_lock:
                self._state = new_state
                self._version += 1

            self._stop_event.wait(self.interval)

    # -- UI-thread polling / redraw ------------------------------------
    def _clear_update_label(self):
        self.update_alert_label.config(text="")

    def _poll(self):
        with self._state_lock:
            version = self._version
            state = self._state
        if version != self._seen_version:
            self._seen_version = version
            self._redraw(state)
            if state.get("kind") == "data":
                self.update_alert_label.config(text="UPDATED", fg="red")
                self.root.after(500, self._clear_update_label)  # lit for 0.5s

        if not self._stop_event.is_set():
            self.root.after(150, self._poll)

    def _on_viewport_resize(self, event):
        if event.width == self._last_width_px:
            return
        self._last_width_px = event.width
        self.scroll_canvas.itemconfigure(self.inner_window, width=event.width)
        with self._state_lock:
            state = self._state
        self._redraw(state, viewport_height_px=event.height)

    def _current_viewport_size(self):
        w = self.scroll_canvas.winfo_width() or int(DEFAULT_WIDTH_IN * DPI)
        h = self.scroll_canvas.winfo_height() or int(
            (BARS_TO_FIT * ROW_HEIGHT_IN + TOP_MARGIN_IN + BOTTOM_MARGIN_IN) * DPI
        )
        return w, h

    def _redraw(self, state, viewport_height_px=None):
        viewport_w_px, viewport_h_px = self._current_viewport_size()
        if viewport_height_px is not None:
            viewport_h_px = viewport_height_px
        width_in = max(viewport_w_px / DPI, MIN_WIDTH_IN)

        self.ax.clear()

        kind = state.get("kind")
        if kind == "data":
            self._draw_bars(state["counts"], width_in)
            self.count_label.config(text=f"Students tracked: {len(state['counts'])}")
        else:
            self.count_label.config(text="Students tracked: 0")
            height_in = max(viewport_h_px / DPI, 1.0)
            self.fig.set_size_inches(width_in, height_in)
            color = "crimson" if kind == "error" else "dimgray"
            self.ax.text(
                0.5, 0.5, state.get("message", ""),
                ha="center", va="center", transform=self.ax.transAxes,
                color=color, wrap=True,
            )
            self.ax.set_xticks([])
            self.ax.set_yticks([])
            for spine in self.ax.spines.values():
                spine.set_visible(False)

        self.fig.canvas.draw()
        px_w = int(self.fig.get_size_inches()[0] * DPI)
        px_h = int(self.fig.get_size_inches()[1] * DPI)
        self.canvas.get_tk_widget().config(width=px_w, height=px_h)
        self.scroll_canvas.configure(scrollregion=(0, 0, px_w, px_h))

    def _draw_bars(self, counts: dict, width_in: float):
        for label in counts:
            if label not in self.color_map:
                self.color_map[label] = color_for_label(label)

        # Ascending, so the HIGHEST coverage ends up at the TOP of a
        # horizontal bar chart (y increases upward) -- a natural
        # leaderboard reading order, matching "sorted descending".
        items = sorted(counts.items(), key=lambda kv: kv[1])
        labels = [email.split("@")[0] for email, _ in items]
        values = [v for _, v in items]
        colors = [self.color_map[email] for email, _ in items]
        n = len(items)

        height_in = n * ROW_HEIGHT_IN + TOP_MARGIN_IN + BOTTOM_MARGIN_IN
        self.fig.set_size_inches(width_in, height_in)

        top_frac = 1 - (TOP_MARGIN_IN / height_in)
        bottom_frac = BOTTOM_MARGIN_IN / height_in
        self.fig.subplots_adjust(
            left=LEFT_FRACTION, right=RIGHT_FRACTION, top=top_frac, bottom=bottom_frac
        )

        y_positions = range(n)
        self.ax.barh(list(y_positions), values, height=BAR_FRACTION, color=colors)
        self.ax.set_yticks(list(y_positions))
        self.ax.set_yticklabels(labels)
        self.ax.set_ylim(-0.5, n - 0.5)
        self.ax.set_xlabel(f"Distinct triplets covered (of {TOTAL_TRIPLETS})")
        self.ax.set_title("Level 1 -- All-Triplets Coverage by Student (Calculate Price only)")

        self.ax.axvline(TOTAL_TRIPLETS, color="#2ca02c", linestyle="--", linewidth=1,
                         label=f"All triplets ({TOTAL_TRIPLETS})")
        self.ax.legend(loc="lower right", fontsize=8)

        self.ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        max_val = max(values + [TOTAL_TRIPLETS])
        self.ax.set_xlim(0, max_val * 1.1)
        for i, v in enumerate(values):
            self.ax.text(v + max_val * 0.01, i, str(v), va="center", fontsize=8)

    def _on_close(self):
        self._stop_event.set()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(
        description="Live horizontal bar chart of Level 1 all-triplets coverage by student.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--database-url", default=None,
                         help="Defaults to DATABASE_URL from the environment, then .env.local.")
    parser.add_argument("--interval", type=float, default=5.0, help="Refresh interval in seconds (default: 5)")
    parser.add_argument("--since-start-of-day", action="store_true",
                         help="Count all of today's CalculatePrice actions, not just ones logged after this "
                              "monitor starts (the default -- avoids counting old testing/dev noise).")
    args = parser.parse_args()

    database_url = args.database_url or os.environ.get("DATABASE_URL") or load_database_url_from_env_file()
    if not database_url:
        parser.error("No database URL found -- pass --database-url, set DATABASE_URL, "
                      "or make sure .env.local exists in this folder.")

    since = (
        datetime.combine(date.today(), dtime.min).astimezone()
        if args.since_start_of_day
        else datetime.now().astimezone()
    )

    print(f"Tracking Calculate Price coverage since {since.strftime('%Y-%m-%d %H:%M:%S %z')}")
    print(f"Total possible triplets (Level 1, all 10 subsets): {TOTAL_TRIPLETS}")

    root = tk.Tk()
    CoverageMonitorApp(root, database_url, since, args.interval)
    root.mainloop()


if __name__ == "__main__":
    main()
