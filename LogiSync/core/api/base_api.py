"""
LogiSync — Abstract Base API
==============================
Defines the contract (interface) every courier API client must follow.

WHY THIS EXISTS — The "Strategy Pattern":
  The Tracker orchestrator calls api.get_tracking_info(number).
  It does NOT know or care whether it's talking to AfterShip, DHL,
  FedEx, or any other courier. They all look identical to the Tracker.

  This means:
    • Adding a new courier = create one new file, change zero existing ones.
    • Switching couriers = change one line in main.py.
    • Testing = swap the real API for a mock with zero refactoring.

  This is called "programming to an interface, not an implementation"
  and is a foundational principle of professional software design.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrackingResult:
    """
    A structured data object representing the result of one tracking lookup.

    We use a dataclass instead of a plain dictionary because:
      • result.location  is safer than result["locaiton"] (typo caught at runtime)
      • It's self-documenting — the fields are declared explicitly
      • It's easily serialisable to JSON if needed later
      • IDE autocomplete works on attributes, not on string keys

    Fields:
        tracking_number : The tracking ID that was looked up
        location        : Latest known location of the shipment
        status          : Current status string (e.g. "In Transit")
        success         : True if the lookup succeeded, False on any error
        error_message   : Human-readable error description (only set on failure)
    """
    tracking_number : str
    location        : str
    status          : str
    success         : bool
    error_message   : Optional[str] = field(default=None)

    def __str__(self) -> str:
        if self.success:
            return f"[{self.tracking_number}] {self.status} @ {self.location}"
        return f"[{self.tracking_number}] FAILED — {self.error_message}"


class BaseCourierAPI(ABC):
    """
    Abstract Base Class for all courier API integrations.

    ABC (Abstract Base Class) is a Python mechanism that enforces a contract.
    Any class that inherits from BaseCourierAPI MUST implement every method
    decorated with @abstractmethod. If it doesn't, Python raises a TypeError
    the moment you try to create an instance of the incomplete class.

    Think of this as a job description:
      "Every courier API we hire must be able to do these three things."
    """

    def __init__(self, api_key: str = ""):
        """
        Args:
            api_key: Authentication credential for the courier's API.
                     Empty by default for demo/mock implementations.
        """
        self.api_key = api_key

    # ── Abstract Methods (MUST be implemented by subclasses) ─────────────────

    @abstractmethod
    def get_tracking_info(self, tracking_number: str) -> TrackingResult:
        """
        Fetch location and status for a single shipment.

        This is the core method the Tracker calls for every row in Excel.

        Args:
            tracking_number: The shipment ID to look up.

        Returns:
            A TrackingResult with location, status, and success flag.
            Must NEVER raise an exception — errors go in TrackingResult.
        """
        ...

    @abstractmethod
    def validate_tracking_number(self, tracking_number: str) -> bool:
        """
        Check if a tracking number looks valid BEFORE making an API call.

        Different couriers have different formats:
          FedEx : 12 or 15 digits
          UPS   : starts with "1Z", 18 characters total
          DHL   : 10 digits
          DTDC  : starts with letters, followed by digits

        Catching invalid numbers early avoids wasting API quota.

        Returns:
            True if the format looks valid, False otherwise.
        """
        ...

    @property
    @abstractmethod
    def courier_name(self) -> str:
        """
        Human-readable name of this courier integration.
        Used in log messages and the GUI.
        Example return values: "AfterShip", "DHL Express", "FedEx"
        """
        ...
