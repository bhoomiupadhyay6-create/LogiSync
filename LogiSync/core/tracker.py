"""
LogiSync — Tracker (Orchestrator)
===================================
The Tracker coordinates the entire update workflow.
It knows ABOUT ExcelHandler and BaseCourierAPI, but doesn't
depend on their concrete implementations.

Flow:
  1. Load Excel file
  2. Extract all tracking numbers
  3. For each number: call API, update the DataFrame
  4. Save the Excel file
  5. Report progress throughout via callbacks

The GUI passes callback functions into run().
The Tracker calls those callbacks to push updates into the GUI.
This keeps the Tracker completely independent of Tkinter.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional

from core.api.base_api import BaseCourierAPI, TrackingResult
from core.excel_handler import ExcelHandler
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Type Aliases ──────────────────────────────────────────────────────────────
# These make function signatures more readable:
#   ProgressFn = a function that takes (current, total, result)
#   LogFn      = a function that takes a string message
ProgressFn = Callable[[int, int, TrackingResult], None]
LogFn      = Callable[[str], None]


@dataclass
class TrackingSession:
    """
    Holds a summary of one complete tracking run.

    Using a dataclass to group related data keeps things clean.
    Returned to the GUI when the run is complete.
    """
    total      : int   = 0
    succeeded  : int   = 0
    failed     : int   = 0
    results    : List[TrackingResult] = field(default_factory=list)
    start_time : datetime = field(default_factory=datetime.now)
    end_time   : Optional[datetime] = None

    def finish(self) -> None:
        """Call this when the session ends to record the finish time."""
        self.end_time = datetime.now()

    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def __str__(self) -> str:
        return (
            f"Session: {self.succeeded}/{self.total} succeeded, "
            f"{self.failed} failed in {self.duration_seconds:.1f}s"
        )


class Tracker:
    """
    Orchestrates reading, API calling, and writing.

    The GUI creates a Tracker, passes it a file path and callbacks,
    and calls run(). The Tracker handles everything else.

    Designed to run in a background thread — it never touches the GUI directly.
    All GUI updates go through the callback functions.
    """

    def __init__(self, api_client: BaseCourierAPI):
        """
        Args:
            api_client: Any concrete implementation of BaseCourierAPI.
                        Could be AfterShipAPI, DHLApi, FedExAPI, etc.
                        The Tracker doesn't know which one it is — and that's the point.
        """
        self.api_client = api_client
        logger.info(f"Tracker ready — courier: {api_client.courier_name}")

    def run(
        self,
        file_path         : str,
        progress_callback : Optional[ProgressFn] = None,
        log_callback      : Optional[LogFn]      = None,
    ) -> TrackingSession:
        """
        Executes the full tracking update workflow.

        Args:
            file_path         : Path to the Excel file to process.
            progress_callback : Called after each tracking number.
                                Signature: callback(current_index, total, result)
            log_callback      : Called with each log message for the GUI log panel.
                                Signature: callback(message_string)

        Returns:
            A TrackingSession with statistics about this run.

        Raises:
            Any exception from ExcelHandler.load() or .save() propagates up.
            (API errors are caught inside AfterShipAPI and returned as TrackingResult.)
        """
        session = TrackingSession()

        def emit(message: str) -> None:
            """Send a message to both file logger and GUI log panel."""
            logger.info(message)
            if log_callback:
                log_callback(message)

        try:
            # ── Phase 1: Load Excel ────────────────────────────────────────────
            emit(f"📂  Loading file: {file_path}")
            handler = ExcelHandler(file_path)
            handler.load()

            tracking_numbers = handler.get_tracking_numbers()
            session.total    = len(tracking_numbers)

            if session.total == 0:
                emit("⚠️   No tracking numbers found. Is the file empty?")
                return session

            emit(f"✅  Found {session.total} tracking number(s).")
            emit(f"🌐  Fetching data via {self.api_client.courier_name}...\n")

            # ── Phase 2: Process Each Tracking Number ──────────────────────────
            for index, tracking_number in enumerate(tracking_numbers, start=1):

                emit(f"  [{index}/{session.total}]  Checking: {tracking_number}")

                # This is the only line that knows about the courier API.
                # Change the API client and this line works with any courier.
                result: TrackingResult = self.api_client.get_tracking_info(
                    tracking_number
                )

                # Write the result into the DataFrame (not to disk yet)
                handler.update_row(
                    tracking_number = result.tracking_number,
                    location        = result.location,
                    status          = result.status,
                )

                # Accumulate session stats
                if result.success:
                    session.succeeded += 1
                    emit(f"        ✅  {result.status}  @  {result.location}")
                else:
                    session.failed += 1
                    emit(f"        ❌  Failed — {result.error_message}")

                session.results.append(result)

                # Notify the GUI to advance its progress bar
                if progress_callback:
                    progress_callback(index, session.total, result)

            # ── Phase 3: Save Results ──────────────────────────────────────────
            emit(f"\n💾  Saving updated file...")
            saved_path = handler.save()
            emit(f"✅  Saved to: {saved_path}")

        except Exception as e:
            emit(f"❌  Critical error: {e}")
            logger.exception("Unhandled exception in Tracker.run()")
            raise   # Re-raise so the GUI can catch and show an error dialog

        finally:
            # finish() is always called, even if an exception occurred
            session.finish()

        emit(f"\n{'─' * 48}")
        emit(str(session))

        return session
