"""
LogiSync — AfterShip API Client
=================================
Implements BaseCourierAPI for the AfterShip tracking platform.
AfterShip aggregates data from 900+ couriers under one API.
Real docs: https://www.aftership.com/docs/api/4/trackings

CURRENT MODE: DEMO
  Returns realistic fake data — no API key or internet required.
  To switch to live mode: set DEMO_MODE = False in config/settings.py
  and add your AfterShip API key there.
"""

import time
import requests

from config.settings import (
    DEMO_MODE, DEMO_API_DELAY, API_TIMEOUT_SECONDS,
    STATUS_DELIVERED, STATUS_IN_TRANSIT,
    STATUS_OUT_FOR_DELIVERY, STATUS_PENDING,
    STATUS_FAILED, STATUS_API_ERROR, STATUS_EXCEPTION,
)
from core.api.base_api import BaseCourierAPI, TrackingResult
from utils.logger import get_logger

logger = get_logger(__name__)


# ─── Demo Data Pool ───────────────────────────────────────────────────────────
# A realistic set of tracking scenarios used in demo mode.
# Index is chosen deterministically from the tracking number,
# so the same tracking number always yields the same result.
_DEMO_SCENARIOS = [
    {"location": "Mumbai Central Hub",            "status": STATUS_IN_TRANSIT},
    {"location": "Delhi Gateway Facility",        "status": STATUS_OUT_FOR_DELIVERY},
    {"location": "Delivered to Recipient",        "status": STATUS_DELIVERED},
    {"location": "Pune Sorting Centre",           "status": STATUS_IN_TRANSIT},
    {"location": "Chennai Sea Port",              "status": STATUS_PENDING},
    {"location": "Hyderabad Air Cargo Terminal",  "status": STATUS_IN_TRANSIT},
    {"location": "Bangalore Distribution Hub",    "status": STATUS_OUT_FOR_DELIVERY},
    {"location": "Kolkata Customs Clearance",     "status": STATUS_EXCEPTION},
    {"location": "Ahmedabad Regional Centre",     "status": STATUS_IN_TRANSIT},
    {"location": "Jaipur Last-Mile Facility",     "status": STATUS_OUT_FOR_DELIVERY},
]


class AfterShipAPI(BaseCourierAPI):
    """
    AfterShip courier tracking integration.

    Inherits from BaseCourierAPI, meaning it MUST implement:
      • get_tracking_info(tracking_number) → TrackingResult
      • validate_tracking_number(tracking_number) → bool
      • courier_name property → str

    Python will raise TypeError at startup if any are missing.
    """

    BASE_URL = "https://api.aftership.com/v4/trackings"

    def __init__(self, api_key: str = "DEMO_KEY"):
        super().__init__(api_key)
        mode = "DEMO" if DEMO_MODE else "LIVE"
        logger.info(f"AfterShipAPI initialised — mode: {mode}")

    # ── Required Properties ───────────────────────────────────────────────────

    @property
    def courier_name(self) -> str:
        return "AfterShip"

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_tracking_number(self, tracking_number: str) -> bool:
        """
        Basic validation: non-empty and at least 5 characters after stripping.
        A production implementation would check courier-specific patterns
        using regular expressions.
        """
        if not tracking_number or not isinstance(tracking_number, str):
            return False
        return len(tracking_number.strip()) >= 5

    # ── Main Public Method ────────────────────────────────────────────────────

    def get_tracking_info(self, tracking_number: str) -> TrackingResult:
        """
        Entry point called by the Tracker for every tracking number.
        Validates first, then routes to demo or live implementation.
        NEVER raises an exception — all errors are returned in TrackingResult.
        """
        tracking_number = str(tracking_number).strip()
        logger.debug(f"Fetching: {tracking_number}")

        # Step 1 — Validate format before spending an API call
        if not self.validate_tracking_number(tracking_number):
            logger.warning(f"Invalid tracking number skipped: '{tracking_number}'")
            return TrackingResult(
                tracking_number = tracking_number,
                location        = "N/A",
                status          = STATUS_FAILED,
                success         = False,
                error_message   = "Invalid tracking number format"
            )

        # Step 2 — Route to the appropriate implementation
        if DEMO_MODE:
            return self._demo_response(tracking_number)
        else:
            return self._live_response(tracking_number)

    # ── Demo Implementation ───────────────────────────────────────────────────

    def _demo_response(self, tracking_number: str) -> TrackingResult:
        """
        Simulates a real API call:
          • Pauses to mimic network latency
          • Returns deterministic fake data based on the tracking number
          • Simulates failure for numbers starting with "INVALID"
        """
        # Mimic network round-trip time
        time.sleep(DEMO_API_DELAY)

        # Simulate a "not found" scenario for obviously bad numbers
        upper = tracking_number.upper()
        if upper.startswith("INVALID") or upper.startswith("BAD"):
            logger.warning(f"[DEMO] Simulating not-found for: {tracking_number}")
            return TrackingResult(
                tracking_number = tracking_number,
                location        = "N/A",
                status          = STATUS_FAILED,
                success         = False,
                error_message   = "Tracking number not found in courier system"
            )

        # Deterministic scenario selection:
        # Sum the ASCII values of all characters, mod by number of scenarios.
        # Same tracking number → same index → same result every time.
        index    = sum(ord(c) for c in tracking_number) % len(_DEMO_SCENARIOS)
        scenario = _DEMO_SCENARIOS[index]

        logger.info(
            f"[DEMO] {tracking_number} → "
            f"{scenario['status']} @ {scenario['location']}"
        )

        return TrackingResult(
            tracking_number = tracking_number,
            location        = scenario["location"],
            status          = scenario["status"],
            success         = True
        )

    # ── Live / Production Implementation ─────────────────────────────────────

    def _live_response(self, tracking_number: str) -> TrackingResult:
        """
        Makes a real HTTP GET request to the AfterShip API.

        Error handling covers:
          • No internet connection (ConnectionError)
          • Server too slow (Timeout)
          • Bad HTTP status codes (HTTPError from raise_for_status)
          • Unexpected JSON structure (KeyError, IndexError)
          • Any other unexpected error (broad Exception catch)

        Professional rule: every network call must be wrapped in try/except.
        A crashed app due to a dropped WiFi connection is unacceptable.
        """
        url     = f"{self.BASE_URL}/{tracking_number}"
        headers = {
            "aftership-api-key" : self.api_key,
            "Content-Type"      : "application/json",
        }

        try:
            response = requests.get(
                url,
                headers = headers,
                timeout = API_TIMEOUT_SECONDS
            )
            # Raise an HTTPError for 4xx and 5xx status codes
            response.raise_for_status()

            data          = response.json()
            tracking_data = data["data"]["tracking"]
            checkpoints   = tracking_data.get("checkpoints", [])

            if checkpoints:
                latest   = checkpoints[-1]
                location = latest.get("city") or latest.get("location") or "Unknown"
                status   = latest.get("subtag_message") or STATUS_IN_TRANSIT
            else:
                location = "No checkpoints yet"
                status   = STATUS_PENDING

            logger.info(f"[LIVE] {tracking_number} → {status} @ {location}")
            return TrackingResult(
                tracking_number = tracking_number,
                location        = location,
                status          = status,
                success         = True
            )

        except requests.exceptions.ConnectionError:
            msg = "No internet connection"
            logger.error(f"{tracking_number}: {msg}")
            return TrackingResult(tracking_number, "N/A", STATUS_API_ERROR, False, msg)

        except requests.exceptions.Timeout:
            msg = f"Request timed out after {API_TIMEOUT_SECONDS}s"
            logger.error(f"{tracking_number}: {msg}")
            return TrackingResult(tracking_number, "N/A", STATUS_API_ERROR, False, msg)

        except requests.exceptions.HTTPError as e:
            msg = f"HTTP {e.response.status_code}: {e.response.reason}"
            logger.error(f"{tracking_number}: {msg}")
            return TrackingResult(tracking_number, "N/A", STATUS_API_ERROR, False, msg)

        except (KeyError, IndexError) as e:
            msg = f"Unexpected API response structure: {e}"
            logger.error(f"{tracking_number}: {msg}")
            return TrackingResult(tracking_number, "N/A", STATUS_API_ERROR, False, msg)

        except Exception as e:
            msg = f"Unexpected error: {e}"
            logger.exception(f"Unhandled error for {tracking_number}")
            return TrackingResult(tracking_number, "N/A", STATUS_API_ERROR, False, msg)
