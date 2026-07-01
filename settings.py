"""
LogiSync — Configuration Settings
==================================
All constants, defaults, and configuration values live here.
To change any behaviour, change THIS file — no hunting through code.

Professional rule: Never hardcode values directly in logic files.
"""

# ─── Application Metadata ─────────────────────────────────────────────────────
APP_NAME        = "LogiSync"
APP_VERSION     = "1.0.0"
APP_AUTHOR      = "Your Company"
APP_DESCRIPTION = "Automated Shipment Tracking for Excel"

# ─── Excel Column Names ───────────────────────────────────────────────────────
# These MUST match the exact column headers in the user's Excel file.
# If the user's file uses "Tracking Number" instead of "Tracking No",
# change ONLY this constant — nothing else in the code needs to change.
COL_TRACKING_NUMBER = "Tracking No"
COL_LOCATION        = "Location"
COL_STATUS          = "Status"
COL_LAST_UPDATED    = "Last Updated"

# ─── API Settings ─────────────────────────────────────────────────────────────
API_TIMEOUT_SECONDS   = 10   # Seconds before giving up on an API call
API_RETRY_COUNT       = 3    # How many times to retry on failure
API_RETRY_DELAY_SECS  = 2    # Pause between retries (seconds)

# ─── Demo / Mock Mode ─────────────────────────────────────────────────────────
# Set DEMO_MODE = True  → Uses fake data, no real API key needed.
# Set DEMO_MODE = False → Makes real HTTP requests to AfterShip.
DEMO_MODE       = True
DEMO_API_DELAY  = 0.6   # Simulated network delay in seconds (feels realistic)

# ─── Logging Configuration ────────────────────────────────────────────────────
LOG_FOLDER = "logs"
LOG_FILE   = "logisync.log"
LOG_LEVEL  = "DEBUG"    # Options: DEBUG | INFO | WARNING | ERROR | CRITICAL

# ─── GUI Window Settings ──────────────────────────────────────────────────────
WINDOW_WIDTH  = 760
WINDOW_HEIGHT = 640
WINDOW_TITLE  = f"{APP_NAME} v{APP_VERSION}  —  Shipment Tracker"

# ─── Status Values Written to Excel ──────────────────────────────────────────
# These are the exact strings that appear in the Status column.
# Changing them here changes them everywhere automatically.
STATUS_DELIVERED         = "Delivered"
STATUS_IN_TRANSIT        = "In Transit"
STATUS_OUT_FOR_DELIVERY  = "Out for Delivery"
STATUS_PENDING           = "Pending"
STATUS_EXCEPTION         = "Exception / Delay"
STATUS_FAILED            = "Failed — Check Tracking No"
STATUS_API_ERROR         = "API Error"
