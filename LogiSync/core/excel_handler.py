"""
LogiSync — Excel Handler
=========================
Owns ALL Excel read/write operations.
No other module touches Excel files directly.

This separation means:
  • Switching from .xlsx to a database = change only this file.
  • The Tracker doesn't know or care what format the data is in.
  • The GUI doesn't know or care how data is stored.
"""

import os
from datetime import datetime
from typing import List, Optional

import pandas as pd
from pandas import col

from config.settings import (
    COL_TRACKING_NUMBER, COL_LOCATION, COL_STATUS, COL_LAST_UPDATED
)
from utils.logger import get_logger

logger = get_logger(__name__)


class ExcelHandler:
    """
    Handles loading, querying, updating, and saving of the Excel workbook.

    Lifecycle:
        handler = ExcelHandler("shipments.xlsx")
        handler.load()                              # Read from disk
        numbers = handler.get_tracking_numbers()   # Extract column
        handler.update_row("TRK001", "Mumbai", "In Transit")
        handler.save()                              # Write back to disk
    """

    def __init__(self, file_path: str):
        """
        Args:
            file_path: Absolute or relative path to the .xlsx file.
        """
        self.file_path              = file_path
        self.dataframe: Optional[pd.DataFrame] = None
        logger.info(f"ExcelHandler created for: {file_path}")

    # ── Loading ───────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Reads the Excel file into a pandas DataFrame and validates its structure.

        Raises:
            FileNotFoundError : The file path does not exist.
            ValueError        : File is not .xlsx/.xls, or required column missing.
            Exception         : Any other pandas/openpyxl error propagates up.
        """
        # ── Guard Clauses — fail early with clear messages ─────────────────
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")

        ext = os.path.splitext(self.file_path)[1].lower()
        if ext not in (".xlsx", ".xls"):
            raise ValueError(
                f"Unsupported file type '{ext}'. "
                "LogiSync only supports .xlsx and .xls files."
            )

        # ── Read the File ──────────────────────────────────────────────────
        logger.info(f"Reading Excel file: {self.file_path}")
        self.dataframe = pd.read_excel(self.file_path, engine="openpyxl")

        # ── Validate Required Column ───────────────────────────────────────
        if COL_TRACKING_NUMBER not in self.dataframe.columns:
            found = list(self.dataframe.columns)
            raise ValueError(
                f"Required column '{COL_TRACKING_NUMBER}' not found.\n"
                f"Columns found in file: {found}\n"
                f"Check config/settings.py → COL_TRACKING_NUMBER"
            )

        # ── Add Missing Optional Columns ───────────────────────────────────
        # If the file has only "Tracking No", we add the other columns automatically.
        for col in [COL_LOCATION, COL_STATUS, COL_LAST_UPDATED]:
            if col not in self.dataframe.columns:
                self.dataframe[col] = ""
                logger.info(f"Column '{col}' not found — added automatically.")
                
            self.dataframe[col] = (
               self.dataframe[col]
             .fillna("")
             .astype(object)
            )

        # ── Clean Tracking Number Column ───────────────────────────────────
        # Excel may store numbers as floats (e.g. 12345.0) or mixed types.
        # Convert everything to string first, then strip whitespace.
        self.dataframe[COL_TRACKING_NUMBER] = (
            self.dataframe[COL_TRACKING_NUMBER]
            .astype(str)
            .str.strip()
        )

        # Remove rows where tracking number is empty, "nan", or whitespace
        before = len(self.dataframe)
        self.dataframe = self.dataframe[
            self.dataframe[COL_TRACKING_NUMBER].str.lower().ne("nan") &
            self.dataframe[COL_TRACKING_NUMBER].str.len().gt(0)
        ].reset_index(drop=True)
        dropped = before - len(self.dataframe)

        if dropped > 0:
            logger.warning(f"Dropped {dropped} row(s) with empty tracking numbers.")

        logger.info(f"Loaded {len(self.dataframe)} valid tracking rows.")

    # ── Reading ───────────────────────────────────────────────────────────────

    def get_tracking_numbers(self) -> List[str]:
        """
        Returns all tracking numbers as a clean list of strings.

        Returns:
            e.g. ["TRK-001", "TRK-002", "TRK-003"]

        Raises:
            RuntimeError: If load() was not called first.
        """
        self._require_loaded()
        numbers = self.dataframe[COL_TRACKING_NUMBER].tolist()
        logger.debug(f"get_tracking_numbers() → {len(numbers)} items")
        return numbers

    # ── Writing ───────────────────────────────────────────────────────────────

    def update_row(self, tracking_number: str, location: str, status: str) -> bool:
        """
        Finds the row with the given tracking number and updates its
        Location, Status, and Last Updated columns.

        Args:
            tracking_number : The tracking ID to look up (must match exactly)
            location        : New location string to write
            status          : New status string to write

        Returns:
            True  if the row was found and updated.
            False if no matching row was found (logged as a warning).
        """
        self._require_loaded()

        # Build a boolean mask: True for rows that match the tracking number
        mask = (
            self.dataframe[COL_TRACKING_NUMBER].str.strip()
            == tracking_number.strip()
        )

        if not mask.any():
            logger.warning(f"Row not found for tracking number: '{tracking_number}'")
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        self.dataframe.loc[mask, COL_LOCATION]     = location
        self.dataframe.loc[mask, COL_STATUS]       = status
        self.dataframe.loc[mask, COL_LAST_UPDATED] = timestamp

        logger.debug(f"Updated '{tracking_number}' → {status} @ {location}")
        return True

    # ── Saving ────────────────────────────────────────────────────────────────

    def save(self, output_path: Optional[str] = None) -> str:
        """
        Writes the updated DataFrame back to an Excel file.

        Args:
            output_path: Optional alternative save path (Save As behaviour).
                         If None, overwrites the original file.

        Returns:
            The path where the file was saved.

        Raises:
            RuntimeError: If load() was not called first.
        """
        self._require_loaded()

        target = output_path or self.file_path

        # index=False means pandas won't write the row numbers (0, 1, 2…) to Excel
        self.dataframe.to_excel(target, index=False, engine="openpyxl")
        logger.info(f"Saved {len(self.dataframe)} rows to: {target}")

        return target

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def row_count(self) -> int:
        """Number of data rows currently loaded (0 if not yet loaded)."""
        return len(self.dataframe) if self.dataframe is not None else 0

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _require_loaded(self) -> None:
        """
        Raises RuntimeError if load() has not been called.
        A guard that prevents confusing NoneType errors later.
        """
        if self.dataframe is None:
            raise RuntimeError(
                "ExcelHandler: data not loaded. Call load() before using this method."
            )
