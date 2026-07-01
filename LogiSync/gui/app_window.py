"""
LogiSync — Main Application Window
=====================================
Builds the full Tkinter GUI and wires all backend components together.

Key design decisions:
  • All long-running work runs in a background thread (threading.Thread).
    This prevents the GUI from "freezing" during API calls.
  • The background thread NEVER touches Tkinter widgets directly.
    Instead it uses root.after(0, fn) to schedule updates on the main thread.
    (Tkinter is not thread-safe — this is a critical rule.)
  • The Tracker callbacks are the bridge between backend and GUI.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd

from config.settings import (
    APP_NAME, APP_VERSION, DEMO_MODE, WINDOW_HEIGHT, WINDOW_TITLE, WINDOW_WIDTH,
)
from core.api.aftership_api import AfterShipAPI
from core.tracker import Tracker, TrackingSession
from core.api.base_api import TrackingResult
from utils.logger import get_logger

logger = get_logger(__name__)


# ─── Colour Palette ───────────────────────────────────────────────────────────
# All colours defined in one place — changing a theme means changing this dict.
C = {
    "bg"            : "#12121F",   # Window background
    "surface"       : "#1E1E30",   # Card / panel surface
    "surface2"      : "#252538",   # Slightly lighter surface
    "border"        : "#2E2E48",   # Subtle border
    "input_bg"      : "#1A1A2C",   # Input field background
    "accent"        : "#6C63FF",   # Primary purple
    "accent_dim"    : "#4B44CC",   # Darker purple (pressed / hover)
    "accent_light"  : "#9B94FF",   # Lighter purple (text on dark)
    "success"       : "#3DDC84",   # Green
    "success_dim"   : "#2BAD64",   # Darker green
    "warning"       : "#FFB347",   # Amber
    "error"         : "#FF5C5C",   # Red
    "text"          : "#E8E8F0",   # Primary text
    "text_muted"    : "#7070A0",   # Dimmed / secondary text
    "log_default"   : "#B0C4DE",   # Log text (steel blue)
    "log_success"   : "#3DDC84",
    "log_error"     : "#FF7070",
    "log_warning"   : "#FFB347",
    "log_dim"       : "#444466",
    "log_info"      : "#9B94FF",
}

FONT_UI     = ("Segoe UI",  10)
FONT_BOLD   = ("Segoe UI",  10, "bold")
FONT_TITLE  = ("Segoe UI",  18, "bold")
FONT_SMALL  = ("Segoe UI",   9)
FONT_LABEL  = ("Segoe UI",   9, "bold")
FONT_MONO   = ("Consolas",   9)


class AppWindow:
    """
    The LogiSync application window.

    Responsibilities:
      • Build and display all UI widgets
      • Respond to user actions (file select, start button, etc.)
      • Start the Tracker in a background thread
      • Receive progress updates from the Tracker and display them
    """

    def __init__(self):
        self.root       = tk.Tk()
        self.file_path  = tk.StringVar()
        self._running   = False          # Prevents double-clicks starting two runs

        self._configure_window()
        self._build_style()
        self._build_ui()

        logger.info(f"{APP_NAME} v{APP_VERSION} GUI ready.")

    # ══════════════════════════════════════════════════════════════════════════
    # WINDOW & STYLE SETUP
    # ══════════════════════════════════════════════════════════════════════════

    def _configure_window(self) -> None:
        """Set size, title, position, and background of the root window."""
        self.root.title(WINDOW_TITLE)
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)

        # Centre the window on screen
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - WINDOW_WIDTH)  // 2
        y  = (sh - WINDOW_HEIGHT) // 2
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

    def _build_style(self) -> None:
        """Configure ttk styles (progress bar uses ttk — needs special setup)."""
        style = ttk.Style(self.root)
        style.theme_use("clam")   # "clam" is the most customisable built-in theme

        style.configure(
            "LS.Horizontal.TProgressbar",
            troughcolor = C["input_bg"],
            background  = C["accent"],
            lightcolor  = C["accent_light"],
            darkcolor   = C["accent_dim"],
            bordercolor = C["border"],
            thickness   = 18,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        """Assemble the full window layout top-to-bottom."""
        self._build_header()

        # A scrollable content area between header and footer
        self.content = tk.Frame(self.root, bg=C["bg"])
        self.content.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        self._build_file_card()
        self._build_controls_card()
        self._build_progress_card()
        self._build_log_card()
        self._build_footer()

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        hf = tk.Frame(self.root, bg=C["accent"], pady=0)
        hf.pack(fill=tk.X)

        # Left: icon + title + subtitle
        left = tk.Frame(hf, bg=C["accent"])
        left.pack(side=tk.LEFT, padx=20, pady=14)

        tk.Label(
            left, text=f"📦  {APP_NAME}",
            font=FONT_TITLE, bg=C["accent"], fg="white"
        ).pack(side=tk.LEFT)

        tk.Label(
            left, text="  Shipment Tracker",
            font=("Segoe UI", 11), bg=C["accent"], fg=C["accent_light"]
        ).pack(side=tk.LEFT, pady=4)

        # Right: version + mode badge
        right = tk.Frame(hf, bg=C["accent"])
        right.pack(side=tk.RIGHT, padx=16, pady=14)

        badge_text  = "⚗  DEMO MODE"  if DEMO_MODE else "⚡  LIVE MODE"
        badge_color = C["warning"]     if DEMO_MODE else C["success"]

        tk.Label(
            right, text=badge_text,
            font=FONT_LABEL, bg=badge_color, fg="white", padx=10, pady=4
        ).pack(side=tk.RIGHT, padx=(8, 0))

        tk.Label(
            right, text=f"v{APP_VERSION}",
            font=FONT_SMALL, bg=C["accent"], fg=C["accent_light"]
        ).pack(side=tk.RIGHT)

    # ── File Selection Card ───────────────────────────────────────────────────

    def _build_file_card(self) -> None:
        card = self._card(self.content, "📂   SELECT EXCEL FILE")

        tk.Label(
            card,
            text="Choose the Excel workbook containing your tracking numbers.",
            font=FONT_SMALL, bg=C["surface"], fg=C["text_muted"]
        ).pack(anchor=tk.W, pady=(0, 10))

        # Row: path entry + Browse button
        row = tk.Frame(card, bg=C["surface"])
        row.pack(fill=tk.X)

        self.file_entry = tk.Entry(
            row,
            textvariable = self.file_path,
            font         = FONT_UI,
            bg           = C["input_bg"],
            fg           = C["text"],
            insertbackground = "white",
            relief       = tk.FLAT,
            bd           = 0,
        )
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=9, padx=(0, 10))

        self._btn(row, "Browse…", self._browse_file, C["accent"], w=10).pack(side=tk.RIGHT)

        # "Create sample file" helper link
        hint_row = tk.Frame(card, bg=C["surface"])
        hint_row.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            hint_row, text="No file yet?",
            font=FONT_SMALL, bg=C["surface"], fg=C["text_muted"]
        ).pack(side=tk.LEFT)

        tk.Button(
            hint_row,
            text            = "  Create a sample demo file  →",
            font            = ("Segoe UI", 9, "underline"),
            bg              = C["surface"],
            fg              = C["accent_light"],
            relief          = tk.FLAT,
            bd              = 0,
            cursor          = "hand2",
            activebackground = C["surface"],
            activeforeground = C["accent"],
            command         = self._create_sample,
        ).pack(side=tk.LEFT)

    # ── Controls Card ─────────────────────────────────────────────────────────

    def _build_controls_card(self) -> None:
        card = self._card(self.content, "⚙️   CONTROLS")

        row = tk.Frame(card, bg=C["surface"])
        row.pack(fill=tk.X)

        self.start_btn = self._btn(
            row, "▶   Start Update", self._start_update,
            C["success"], hover=C["success_dim"], w=18, fs=11
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.clear_btn = self._btn(
            row, "🗑  Clear Log", self._clear_log,
            C["surface2"], hover=C["border"], w=12
        )
        self.clear_btn.pack(side=tk.LEFT)

        self.status_lbl = tk.Label(
            row,
            text = "Idle — select a file to begin",
            font = ("Segoe UI", 9, "italic"),
            bg   = C["surface"],
            fg   = C["text_muted"],
        )
        self.status_lbl.pack(side=tk.RIGHT)

    # ── Progress Card ─────────────────────────────────────────────────────────

    def _build_progress_card(self) -> None:
        card = self._card(self.content, "📊   PROGRESS")

        meta_row = tk.Frame(card, bg=C["surface"])
        meta_row.pack(fill=tk.X, pady=(0, 8))

        self.progress_lbl = tk.Label(
            meta_row, text="Waiting for task…",
            font=FONT_SMALL, bg=C["surface"], fg=C["text_muted"]
        )
        self.progress_lbl.pack(side=tk.LEFT)

        self.pct_lbl = tk.Label(
            meta_row, text="0 %",
            font=("Segoe UI", 9, "bold"), bg=C["surface"], fg=C["accent_light"]
        )
        self.pct_lbl.pack(side=tk.RIGHT)

        self.progress_bar = ttk.Progressbar(
            card,
            style  = "LS.Horizontal.TProgressbar",
            orient = tk.HORIZONTAL,
            mode   = "determinate",
        )
        self.progress_bar.pack(fill=tk.X)

    # ── Log Card ──────────────────────────────────────────────────────────────

    def _build_log_card(self) -> None:
        # Outer wrapper — expands to fill remaining space
        outer = tk.Frame(self.content, bg=C["bg"], padx=16, pady=6)
        outer.pack(fill=tk.BOTH, expand=True)

        # Section label
        tk.Label(
            outer, text="📋   ACTIVITY LOG",
            font=("Segoe UI", 8, "bold"),
            bg=C["bg"], fg=C["text_muted"],
        ).pack(anchor=tk.W, pady=(0, 4))

        # Surface card
        card = tk.Frame(outer, bg=C["surface"], padx=0, pady=0)
        card.pack(fill=tk.BOTH, expand=True)

        # Inner frame with border colour
        inner = tk.Frame(card, bg=C["border"], bd=1)
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        self.log_box = tk.Text(
            inner,
            font             = FONT_MONO,
            bg               = C["input_bg"],
            fg               = C["log_default"],
            insertbackground = "white",
            relief           = tk.FLAT,
            bd               = 6,
            wrap             = tk.WORD,
            state            = tk.DISABLED,
        )
        self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = tk.Scrollbar(inner, command=self.log_box.yview, bg=C["surface"])
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_box.config(yscrollcommand=sb.set)

        # Colour tags for different message types
        self.log_box.tag_config("success", foreground=C["log_success"])
        self.log_box.tag_config("error",   foreground=C["log_error"])
        self.log_box.tag_config("warning", foreground=C["log_warning"])
        self.log_box.tag_config("info",    foreground=C["log_info"])
        self.log_box.tag_config("dim",     foreground=C["log_dim"])

    # ── Footer ────────────────────────────────────────────────────────────────

    def _build_footer(self) -> None:
        ft = tk.Frame(self.root, bg=C["surface"], pady=7)
        ft.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Label(
            ft, text=f"  {APP_NAME} — Built with Python & Tkinter",
            font=("Segoe UI", 8), bg=C["surface"], fg=C["text_muted"]
        ).pack(side=tk.LEFT, padx=10)

        tk.Label(
            ft, text="🔒 Your data stays on your machine  ",
            font=("Segoe UI", 8), bg=C["surface"], fg=C["text_muted"]
        ).pack(side=tk.RIGHT, padx=10)

    # ══════════════════════════════════════════════════════════════════════════
    # HELPER WIDGET BUILDERS
    # ══════════════════════════════════════════════════════════════════════════

    def _card(self, parent: tk.Widget, title: str) -> tk.Frame:
        """
        Creates a labelled card section.
        Returns the inner frame where card content should be placed.
        """
        outer = tk.Frame(parent, bg=C["bg"], pady=4, padx=16)
        outer.pack(fill=tk.X)

        tk.Label(
            outer, text=title,
            font=("Segoe UI", 8, "bold"), bg=C["bg"], fg=C["text_muted"]
        ).pack(anchor=tk.W, pady=(2, 4))

        inner = tk.Frame(outer, bg=C["surface"], padx=16, pady=12)
        inner.pack(fill=tk.X)
        return inner

    def _btn(
        self, parent, text, cmd, color,
        hover=None, w=12, fs=10
    ) -> tk.Button:
        """Creates a flat, styled button with a hover effect."""
        hover_c = hover or color
        b = tk.Button(
            parent,
            text            = text,
            command         = cmd,
            font            = ("Segoe UI", fs, "bold"),
            bg              = color,
            fg              = "white",
            activebackground = hover_c,
            activeforeground = "white",
            relief          = tk.FLAT,
            bd              = 0,
            padx            = 14,
            pady            = 9,
            width           = w,
            cursor          = "hand2",
        )
        b.bind("<Enter>", lambda _: b.config(bg=hover_c))
        b.bind("<Leave>", lambda _: b.config(bg=color))
        return b

    # ══════════════════════════════════════════════════════════════════════════
    # USER ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _browse_file(self) -> None:
        """Opens an OS file picker dialog for Excel files."""
        path = filedialog.askopenfilename(
            title     = "Select Excel Workbook",
            filetypes = [("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")],
        )
        if path:
            self.file_path.set(path)
            self._log(f"📂  File selected: {os.path.basename(path)}", "info")

    def _create_sample(self) -> None:
        """
        Generates a demo Excel file with 8 sample tracking numbers
        and opens it in the file path field automatically.
        """
        path = filedialog.asksaveasfilename(
            title           = "Save Demo File As",
            defaultextension = ".xlsx",
            initialfile     = "logisync_demo.xlsx",
            filetypes       = [("Excel Files", "*.xlsx")],
        )
        if not path:
            return

        try:
            data = {
                "Tracking No": [
                    "TRK-2024-001", "TRK-2024-002", "TRK-2024-003",
                    "TRK-2024-004", "TRK-2024-005", "TRK-2024-006",
                    "INVALID-999",  "TRK-2024-008",
                ],
                "Location"     : [""] * 8,
                "Status"       : [""] * 8,
                "Last Updated" : [""] * 8,
            }
            pd.DataFrame(data).to_excel(path, index=False, engine="openpyxl")

            self.file_path.set(path)
            self._log(f"✅  Demo file created: {os.path.basename(path)}", "success")
            self._log("    Click  ▶ Start Update  to process it.", "info")

        except Exception as e:
            messagebox.showerror("Error", f"Could not create demo file:\n{e}")

    def _start_update(self) -> None:
        """
        Validates inputs and launches the Tracker in a background thread.

        IMPORTANT: Long-running tasks MUST run in a thread.
        If the Tracker ran on the main thread, Tkinter would freeze completely
        and the window would appear to crash until the task finished.
        """
        if self._running:
            return

        fp = self.file_path.get().strip()

        if not fp:
            messagebox.showwarning("No File", "Please select an Excel file first.")
            return

        if not os.path.exists(fp):
            messagebox.showerror("Not Found", f"File not found:\n{fp}")
            return

        # Reset UI to clean state
        self._reset_progress()
        self._set_running(True)
        self._log("═" * 52, "dim")
        self._log(f"🚀  LogiSync update started", "info")

        # daemon=True: thread is killed automatically when the main window closes
        thread = threading.Thread(target=self._bg_run, daemon=True)
        thread.start()

    def _clear_log(self) -> None:
        """Clears the entire log text area."""
        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete("1.0", tk.END)
        self.log_box.config(state=tk.DISABLED)

    # ══════════════════════════════════════════════════════════════════════════
    # BACKGROUND THREAD
    # ══════════════════════════════════════════════════════════════════════════

    def _bg_run(self) -> None:
        """
        Runs in the background thread.
        NEVER call Tkinter widget methods directly here —
        always use root.after(0, fn) to schedule on the main thread.
        """
        try:
            api     = AfterShipAPI()
            tracker = Tracker(api_client=api)

            session = tracker.run(
                file_path         = self.file_path.get(),
                progress_callback = self._on_progress,   # called per tracking number
                log_callback      = self._thread_log,    # thread-safe log relay
            )

            # Schedule the completion handler on the main thread
            self.root.after(0, self._on_done, session)

        except Exception as e:
            logger.exception("Error in background run")
            self.root.after(0, self._on_error, str(e))

    def _thread_log(self, message: str) -> None:
        """
        Called from the background thread to send a log message to the GUI.
        root.after(0, fn) schedules fn to run on the main thread — thread-safe.
        """
        self.root.after(0, self._log, message)

    # ══════════════════════════════════════════════════════════════════════════
    # CALLBACKS (scheduled on main thread via root.after)
    # ══════════════════════════════════════════════════════════════════════════

    def _on_progress(self, current: int, total: int, result: TrackingResult) -> None:
        """Called by Tracker after each tracking number is processed."""
        pct = int((current / total) * 100)

        def _update():
            self.progress_bar["value"] = pct
            self.pct_lbl.config(text=f"{pct} %")
            self.progress_lbl.config(
                text=f"Processed {current} of {total}",
                fg=C["text"]
            )
            self.status_lbl.config(
                text=f"Last: {result.tracking_number}",
                fg=C["text_muted"]
            )

        self.root.after(0, _update)

    def _on_done(self, session: TrackingSession) -> None:
        """Called when the Tracker finishes successfully."""
        self._set_running(False)
        self.progress_bar["value"] = 100
        self.pct_lbl.config(text="100 %")
        self.progress_lbl.config(text=f"Complete — {session.total} records processed")

        color = C["success"] if session.failed == 0 else C["warning"]
        self.status_lbl.config(
            text=f"✅  {session.succeeded} updated, {session.failed} failed",
            fg=color
        )

        self._log("═" * 52, "dim")
        self._log(
            f"🏁  Finished!  {session.succeeded}/{session.total} updated  "
            f"in {session.duration_seconds:.1f}s",
            "success"
        )
        if session.failed:
            self._log(f"    ⚠️   {session.failed} tracking number(s) had errors.", "warning")

        messagebox.showinfo(
            "Update Complete",
            f"LogiSync finished!\n\n"
            f"✅  Updated:   {session.succeeded}\n"
            f"❌  Failed:    {session.failed}\n"
            f"⏱   Duration: {session.duration_seconds:.1f}s\n\n"
            f"The Excel file has been saved automatically."
        )

    def _on_error(self, message: str) -> None:
        """Called when a critical, unrecoverable error occurs."""
        self._set_running(False)
        self._log(f"❌  Critical error: {message}", "error")
        self.status_lbl.config(text="Error — see log for details", fg=C["error"])
        messagebox.showerror("LogiSync Error", f"An error occurred:\n\n{message}")

    # ══════════════════════════════════════════════════════════════════════════
    # UI UTILITIES
    # ══════════════════════════════════════════════════════════════════════════

    def _log(self, message: str, tag: str = "") -> None:
        """
        Appends a message to the log text area.
        Auto-detects message type from content if tag not provided.
        Always called on the main thread.
        """
        self.log_box.config(state=tk.NORMAL)

        # Auto-detect tag from emoji / keywords if not explicitly set
        if not tag:
            low = message.lower()
            if "✅" in message or "saved" in low or "complete" in low:
                tag = "success"
            elif "❌" in message or "error" in low or "failed" in low:
                tag = "error"
            elif "⚠️" in message or "warn" in low:
                tag = "warning"
            elif "🚀" in message or "loading" in low or "fetching" in low:
                tag = "info"

        self.log_box.insert(tk.END, message + "\n", tag)
        self.log_box.see(tk.END)    # Auto-scroll to the newest line
        self.log_box.config(state=tk.DISABLED)

    def _set_running(self, is_running: bool) -> None:
        """Toggles the UI into / out of the 'busy' state."""
        self._running = is_running
        state = tk.DISABLED if is_running else tk.NORMAL

        self.start_btn.config(
            state = state,
            text  = "⏳   Running…" if is_running else "▶   Start Update",
        )
        self.clear_btn.config(state=state)

    def _reset_progress(self) -> None:
        """Resets progress bar and labels to their initial state."""
        self.progress_bar["value"] = 0
        self.pct_lbl.config(text="0 %")
        self.progress_lbl.config(text="Starting…", fg=C["text_muted"])
        self._clear_log()

    # ══════════════════════════════════════════════════════════════════════════
    # ENTRY POINT
    # ══════════════════════════════════════════════════════════════════════════

    def run(self) -> None:
        """Hands control to Tkinter's event loop. Blocks until window closes."""
        logger.info("Entering Tkinter main loop.")
        self.root.mainloop()
