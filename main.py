"""
LogiSync — Entry Point
=======================
Run this file to start the application:
    python main.py

This file does exactly THREE things:
  1. Sets up the Python import path (so all modules can find each other)
  2. Initialises the logger
  3. Launches the GUI

Nothing else. All real logic lives in the appropriate modules.

Professional rule: Keep main.py minimal.
It is the "front door" — not a room where work happens.
"""

import os
import sys

# ── Path Setup ────────────────────────────────────────────────────────────────
# Insert the project root into Python's search path.
# This makes "from config.settings import ..." work from any module,
# regardless of which directory the user runs the script from.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# ── Imports (after path setup) ────────────────────────────────────────────────
from config.settings import APP_NAME, APP_VERSION
from utils.logger import get_logger

logger = get_logger("main")


def main() -> None:
    """Application entry point."""
    logger.info("=" * 50)
    logger.info(f"  {APP_NAME} v{APP_VERSION} — Starting")
    logger.info("=" * 50)

    # Import here (after sys.path is set) to avoid import errors
    from gui.app_window import AppWindow

    app = AppWindow()
    app.run()

    logger.info(f"{APP_NAME} closed.")


if __name__ == "__main__":
    main()
