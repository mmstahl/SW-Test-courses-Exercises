import sys
import csv
import io
import urllib.request
import tkinter as tk
from tkinter import ttk
import threading

# -----------------------------------------------------------------------------
# GRAPHICAL DISPLAY CONFIGURATION
# -----------------------------------------------------------------------------
WINDOW_TITLE = "Live Test Efficiency Scoreboard"
REFRESH_INTERVAL_MS = 2000  # Refresh every 2 seconds
DEFAULT_FONT_SIZE = 11

class ScoreboardApp:
    def __init__(self, root, spreadsheet_id, base_font_size):
        self.root = root
        self.spreadsheet_id = spreadsheet_id
        self.base_font_size = base_font_size
        self.students = []

        self.setup_window()
        self.create_widgets()
        
        # Start the background data polling loop
        self.poll_data_loop()

    def setup_window(self):
        """Initializes window dimensions and applies custom light theme styling."""
        self.root.title(WINDOW_TITLE)
        self.root.geometry("1200x580")  # Expanded horizontally for 3 columns
        self.root.configure(bg="#ffffff")

        # Configure scaling typography based on command-line argument overrides
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background="#ffffff", foreground="#222222")
        self.style.configure("Title.TLabel", font=("Helvetica", 18, "bold"), background="#ffffff", foreground="#007a87")

    def create_widgets(self):
        """Constructs a three-table (7-column container grid) presentation canvas."""
        # Top header banner
        title_frame = tk.Frame(self.root, bg="#ffffff", padx=15, pady=15)
        title_frame.pack(fill="x")
        
        title_label = ttk.Label(title_frame, text="*** LIVE TEST EFFICIENCY SCOREBOARD ***", style="Title.TLabel")
        title_label.pack(side="left")

        # Main horizontal distribution layout container
        self.main_container = tk.Frame(self.root, bg="#ffffff", padx=20, pady=10)
        self.main_container.pack(fill="both", expand=True)

        # Build column frame panels
        # Table Module 1: Left (Positions 1-15)
        self.t1_names = tk.Frame(self.main_container, bg="#ffffff")
        self.t1_scores = tk.Frame(self.main_container, bg="#ffffff")
        
        # Spacer 1
        self.spacer1 = tk.Frame(self.main_container, width=35, bg="#ffffff")

        # Table Module 2: Center (Positions 16-30)
        self.t2_names = tk.Frame(self.main_container, bg="#ffffff")
        self.t2_scores = tk.Frame(self.main_container, bg="#ffffff")
        
        # Spacer 2
        self.spacer2 = tk.Frame(self.main_container, width=35, bg="#ffffff")

        # Table Module 3: Right (Positions 31-45)
        self.t3_names = tk.Frame(self.main_container, bg="#ffffff")
        self.t3_scores = tk.Frame(self.main_container, bg="#ffffff")

        # Map panels precisely onto grid channels
        self.t1_names.grid(row=0, column=0, sticky="nsew", padx=(0,2))
        self.t1_scores.grid(row=0, column=1, sticky="nsew")
        self.spacer1.grid(row=0, column=2, sticky="nsew")
        
        self.t2_names.grid(row=0, column=3, sticky="nsew", padx=(0,2))
        self.t2_scores.grid(row=0, column=4, sticky="nsew")
        self.spacer2.grid(row=0, column=5, sticky="nsew")
        
        self.t3_names.grid(row=0, column=6, sticky="nsew", padx=(0,2))
        self.t3_scores.grid(row=0, column=7, sticky="nsew")

        # Align column scaling factors across table blocks uniformly
        self.main_container.columnconfigure(0, weight=3)
        self.main_container.columnconfigure(1, weight=1)
        self.main_container.columnconfigure(2, weight=0)
        self.main_container.columnconfigure(3, weight=3)
        self.main_container.columnconfigure(4, weight=1)
        self.main_container.columnconfigure(5, weight=0)
        self.main_container.columnconfigure(6, weight=3)
        self.main_container.columnconfigure(7, weight=1)

        # Footer Status bar
        self.footer = tk.Frame(self.root, bg="#eaeaea", height=25)
        self.footer.pack(fill="x", side="bottom")
        self.status_label = tk.Label(self.footer, text="Initializing stream connection...", bg="#eaeaea", fg="#555555", font=("Helvetica", 9), anchor="w", padx=10)
        self.status_label.pack(fill="x")

    def poll_data_loop(self):
        """Fires off asynchronous data gathering requests to keep interface completely responsive."""
        def thread_target():
            data = self.fetch_public_scoreboard_csv(self.spreadsheet_id)
            self.root.after(0, self.update_display, data)
            
        threading.Thread(target=thread_target, daemon=True).start()
        self.root.after(REFRESH_INTERVAL_MS, self.poll_data_loop)

    def fetch_public_scoreboard_csv(self, spreadsheet_id):
        """Downloads public Google CSV and extracts columns dynamically mapping headers."""
        csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet=Scoreboard"
        try:
            req = urllib.request.Request(csv_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as response:
                csv_data = response.read().decode('utf-8')
            
            reader = csv.reader(io.StringIO(csv_data))
            rows = list(reader)
            if not rows or len(rows) < 2: return []

            # Resolve dynamic column positions from Header strings
            header_row = rows[0]
            name_col_idx = 0
            score_col_idx = -1

            for idx, header in enumerate(header_row):
                clean_header = header.strip().lower()
                if clean_header == "student name":
                    name_col_idx = idx
                elif clean_header == "total score":
                    score_col_idx = idx

            if score_col_idx == -1:
                score_col_idx = len(header_row) - 1 # Fallback to terminal column index

            scoreboard_data = []
            max_search_row = min(51, len(rows))
            
            for row in rows[1:max_search_row]:
                if len(row) > max(name_col_idx, score_col_idx):
                    name = row[name_col_idx].strip()
                    raw_score = row[score_col_idx].strip()
                    
                    if name and name != '""' and name != '0' and raw_score:
                        try:
                            score = int(raw_score)
                            scoreboard_data.append((name, score))
                        except ValueError:
                            continue
            
            scoreboard_data.sort(key=lambda x: x[1], reverse=True)
            return scoreboard_data
        except Exception:
            return None

    def get_color_hex(self, score, max_pos, max_neg):
        """Calculates dynamic gradient background pairs targeting clean light-theme contrast metrics."""
        if score == 0:
            return "#e0e0e0", "#222222"
        if score > 0:
            ratio = min(score / max_pos, 1.0)
            r = int(232 - (156 * ratio))
            g = int(245 - (70 * ratio))
            b = int(233 - (153 * ratio))
            return f"#{r:02x}{g:02x}{b:02x}", "#0e3a10"
        else:
            ratio = min(abs(score) / max_neg, 1.0)
            r = int(255 - (11 * ratio))
            g = int(235 - (168 * ratio))
            b = int(238 - (184 * ratio))
            return f"#{r:02x}{g:02x}{b:02x}", "#4a0d0d"

    def update_display(self, data):
        """Clears existing UI frame panels and splits records into three tables of 15 entries."""
        if data is None:
            self.status_label.config(text="Re-trying cloud data handshake... (Network Timeout)")
            return
            
        self.students = data
        self.status_label.config(text=f"Scoreboard Synced. Refreshing live every 2s. Font size: {self.base_font_size}pt.")

        # Wipe old widgets cleanly
        target_frames = [self.t1_names, self.t1_scores, self.t2_names, self.t2_scores, self.t3_names, self.t3_scores]
        for f in target_frames:
            for child in f.winfo_children():
                child.destroy()

        # Generate structural column header descriptors
        headers_config = [
            (self.t1_names, "STUDENT NAME", "w"), (self.t1_scores, "SCORE", "center"),
            (self.t2_names, "STUDENT NAME", "w"), (self.t2_scores, "SCORE", "center"),
            (self.t3_names, "STUDENT NAME", "w"), (self.t3_scores, "SCORE", "center")
        ]
        for frame, text, side in headers_config:
            tk.Label(frame, text=text, bg="#ffffff", fg="#555555", font=("Helvetica", 10, "bold"), anchor=side).pack(fill="x", pady=(0,5))

        pos_scores = [s[1] for s in self.students if s[1] > 0]
        neg_scores = [abs(s[1]) for s in self.students if s[1] < 0]
        max_pos = max(pos_scores) if pos_scores else 1
        max_neg = max(neg_scores) if neg_scores else 1

        # Partition entries into groups of 15 slots apiece
        col1_data = self.students[:15]
        col2_data = self.students[15:30]
        col3_data = self.students[30:45]

        # Consolidated rendering pipeline looping down the 15 vertical layout rows
        for idx in range(15):
            # Render Column Table 1 (Positions 1 to 15)
            if idx < len(col1_data):
                name, score = col1_data[idx]
                bg_hex, fg_hex = self.get_color_hex(score, max_pos, max_neg)
                tk.Label(self.t1_names, text=f" {idx+1:2d}. {name}", bg="#f7f7f7", fg="#222222", font=("Consolas", self.base_font_size), anchor="w", height=1).pack(fill="x", pady=2)
                tk.Label(self.t1_scores, text=f"{score:+d}", bg=bg_hex, fg=fg_hex, font=("Consolas", self.base_font_size, "bold"), width=8, height=1).pack(pady=2)

            # Render Column Table 2 (Positions 16 to 30)
            if idx < len(col2_data):
                name, score = col2_data[idx]
                bg_hex, fg_hex = self.get_color_hex(score, max_pos, max_neg)
                tk.Label(self.t2_names, text=f" {idx+16:2d}. {name}", bg="#f7f7f7", fg="#222222", font=("Consolas", self.base_font_size), anchor="w", height=1).pack(fill="x", pady=2)
                tk.Label(self.t2_scores, text=f"{score:+d}", bg=bg_hex, fg=fg_hex, font=("Consolas", self.base_font_size, "bold"), width=8, height=1).pack(pady=2)

            # Render Column Table 3 (Positions 31 to 45)
            if idx < len(col3_data):
                name, score = col3_data[idx]
                bg_hex, fg_hex = self.get_color_hex(score, max_pos, max_neg)
                tk.Label(self.t3_names, text=f" {idx+31:2d}. {name}", bg="#f7f7f7", fg="#222222", font=("Consolas", self.base_font_size), anchor="w", height=1).pack(fill="x", pady=2)
                tk.Label(self.t3_scores, text=f"{score:+d}", bg=bg_hex, fg=fg_hex, font=("Consolas", self.base_font_size, "bold"), width=8, height=1).pack(pady=2)

def main():
    if len(sys.argv) < 2:
        print("Usage: python show_scoreboard.py <GOOGLE_SHEET_ID> [FONT_SIZE]", file=sys.stderr)
        sys.exit(1)
        
    spreadsheet_id = sys.argv[1]
    
    # Process optional parameter for typography sizing
    base_font_size = DEFAULT_FONT_SIZE
    if len(sys.argv) >= 3:
        try:
            base_font_size = int(sys.argv[2])
            if base_font_size <= 4 or base_font_size > 32:
                base_font_size = DEFAULT_FONT_SIZE
        except ValueError:
            pass # Use standard baseline if non-numeric value parsed
            
    root = tk.Tk()
    app = ScoreboardApp(root, spreadsheet_id, base_font_size)
    root.mainloop()

if __name__ == '__main__':
    main()