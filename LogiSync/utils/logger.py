"""
LogiSync — Logging Setup
=========================
Configures a single logger that:
  • Writes detailed DEBUG logs to a date-stamped file in /logs/
  • Prints INFO+ messages to the console during development

Usage anywhere in the project:
    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Something happened")
    logger.error("Something broke")
"""

import logging
import os
from datetime import datetime

from config.settings import LOG_FOLDER, LOG_FILE, LOG_LEVEL


def setup_logger(name: str = "LogiSync") -> logging.Logger:
    """
    Creates and returns a configured logger instance.

    Python's logging module uses a hierarchy of named loggers.
    Using __name__ as the name gives us "core.tracker", "gui.app_window",
    etc. — so log messages tell you exactly where they came from.

    Args:
        name: Logger name, usually __name__ from the calling module.

    Returns:
        A fully configured logging.Logger instance.
    """
    # Create the /logs directory if it doesn't already exist
    os.makedirs(LOG_FOLDER, exist_ok=True)

    # Build log filename: e.g. "logs/2024-06-15_logisync.log"
    today    = datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(LOG_FOLDER, f"{today}_{LOG_FILE}")

    # Get the named logger (creates it if new, returns existing one if not)
    logger = logging.getLogger(name)

    # Guard: don't add duplicate handlers if this logger was already set up
    if logger.handlers:
        return logger

    # Translate the string level ("DEBUG") to a logging constant (10)
    level = getattr(logging, LOG_LEVEL.upper(), logging.DEBUG)
    logger.setLevel(level)

    # ── Log Message Format ────────────────────────────────────────────────────
    # Example output:
    #   2024-06-15 14:32:01 | INFO     | excel_handler       | Loaded 5 rows
    formatter = logging.Formatter(
        fmt     = "%(asctime)s | %(levelname)-8s | %(module)-20s | %(message)s",
        datefmt = "%Y-%m-%d %H:%M:%S"
    )

    # ── File Handler ──────────────────────────────────────────────────────────
    # Writes ALL messages (DEBUG and above) to the log file.
    # utf-8 encoding handles special characters and emoji in log messages.
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # ── Console Handler ───────────────────────────────────────────────────────
    # Prints INFO and above to the terminal.
    # Useful during development; can be removed for production builds.
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(module_name: str = "LogiSync") -> logging.Logger:
    """
    Convenience wrapper — import and call this from any module.

    Example:
        from utils.logger import get_logger
        logger = get_logger(__name__)
    """
    return setup_logger(module_name)
