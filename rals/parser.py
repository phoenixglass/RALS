"""Spreadsheet parser for input service data."""

from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Optional
import re
import pandas as pd
from collections import defaultdict

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from .models import ServiceRecord, RateSchedule, InsurancePlan, Client
from .calculator import (
    parse_rates_from_pps_comment, 
    parse_oop_from_pps_comment,
    parse_deductible_from_pps_comment
)


# Default column mappings (0-indexed) based on spreadsheet structure
DEFAULT_INPUT_COLUMNS = {
    "group_id": 0,       # A - GROUPFLD1
    "mrn": 1,            # B - MRN
    "date": 2,           # C - Date
    "service": 3,        # D - Service
    "from_time": 4,      # E - From
    "to_time": 5,        # F - To
    "duration": 6,       # G - Duration
    "location": 7,       # H - Location
    "pps_comment": 8,    # I - PPS Comment
    "provider": 9,       # J - Provider
    "supervisor": 10,    # K - Supervisor
    "status": 11,        # L - Status
    "note_status": 12,   # M - Note Status
    "physical_proc": 13, # N - Physical Proc
    "financial_div": 14, # O - Financial Div
    "funding": 15,       # P - Funding
    "comments": 16,      # Q - Comments
}


class SpreadsheetParser:
    """Parser for input service data spreadsheets."""

    def __init__(
        self,
        column_mapping: Optional[dict] = None,
        start_row: int = 2,
        end_row: Optional[int] = None
    ):
        """
        Initialize parser with column configuration.

        Args:
            column_mapping: Dict mapping field names to column indices (0-indexed)
            start_row: First row of data (1-indexed, default 2 for header in row 1)
            end_row: Last row of data (1-indexed, None for auto-detect)
        """
        self.columns = column_mapping or DEFAULT_INPUT_COLUMNS
        self.start_row = start_row
        self.end_row = end_row

    def parse_file(self, filepath: str | Path) -> list[ServiceRecord]:
        """
        Parse a spreadsheet file and return service records.
        Supports both Excel (.xlsx, .xls) and CSV (.csv) files.

        Args:
            filepath: Path to Excel or CSV file

        Returns:
            List of ServiceRecord objects
        """
        filepath = Path(filepath)
        
        # Check file extension and route to appropriate parser
        if filepath.suffix.lower() == '.csv':
            return self._parse_csv_file(filepath)
        else:
            return self._parse_excel_file(filepath)
    
    def _parse_excel_file(self, filepath: Path) -> list[ServiceRecord]:
        """Parse an Excel file and return service records."""
        wb = load_workbook(filepath, data_only=True)
        ws = wb.active

        records = []
        end = self.end_row or ws.max_row

        for row_num in range(self.start_row, end + 1):
            record = self._parse_row(ws, row_num)
            if record:
                records.append(record)

        wb.close()
        return records
    
    def _parse_csv_file(self, filepath: Path) -> list[ServiceRecord]:
        """Parse a CSV file and return service records."""
        # Read CSV file with pandas
        df = pd.read_csv(filepath)
        
        records = []
        for idx, row in df.iterrows():
            record = self._parse_csv_row(row)
            if record:
                records.append(record)
        
        return records
    
    def _parse_csv_row(self, row: pd.Series) -> Optional[ServiceRecord]:
        """Parse a single CSV row (pandas Series) into a ServiceRecord."""
        # Get values from the row using column names
        # Expected columns: GROUPFLD1, MRN, Date, Service, From, Location, 
        # PPS Comment, Provider, Supervisor, Status, Note Status, 
        # Physical Program, Financial Division, Funding, Comments
        
        try:
            mrn = row.get('MRN', '')
            service_date_raw = row.get('Date', '')
            service_type = row.get('Service', '')
            
            # Skip empty rows
            if pd.isna(mrn) or mrn == '' or pd.isna(service_date_raw) or service_date_raw == '':
                return None
            
            # Parse date
            if isinstance(service_date_raw, str):
                service_date = self._parse_date(service_date_raw)
            elif pd.isna(service_date_raw):
                return None
            else:
                # Pandas might have already parsed it as a datetime
                service_date = pd.to_datetime(service_date_raw).date()
            
            # Get other fields with defaults for missing values
            location = row.get('Location', '')
            pps_comment = row.get('PPS Comment', '')
            provider = row.get('Provider', '')
            supervisor = row.get('Supervisor', None)
            status = row.get('Status', '')
            note_status = row.get('Note Status', '')
            physical_proc = row.get('Physical Program', '')
            financial_div = row.get('Financial Division', '')
            funding = row.get('Funding', '')
            comments = row.get('Comments', '')
            group_id = row.get('GROUPFLD1', None)
            start_time = row.get('From', None)
            
            # Handle NaN values from pandas
            def clean_value(val):
                if pd.isna(val):
                    return ''
                return str(val)
            
            return ServiceRecord(
                mrn=str(mrn),
                service_date=service_date,
                service_type=clean_value(service_type),
                duration_mins=0,  # CSV format doesn't have duration column
                location=clean_value(location),
                pps_comment=clean_value(pps_comment),
                provider=clean_value(provider),
                supervisor=clean_value(supervisor) if not pd.isna(supervisor) else None,
                status=clean_value(status),
                note_status=clean_value(note_status),
                physical_proc=clean_value(physical_proc),
                financial_div=clean_value(financial_div),
                funding=clean_value(funding),
                comments=clean_value(comments),
                group_id=clean_value(group_id) if not pd.isna(group_id) else None,
                start_time=clean_value(start_time) if not pd.isna(start_time) else None,
                end_time=None,
            )
        except Exception as e:
            # Skip malformed rows
            return None

    def _parse_row(self, ws: Worksheet, row_num: int) -> Optional[ServiceRecord]:
        """Parse a single row into a ServiceRecord."""
        # Get cell values (column indices are 0-based, openpyxl is 1-based)
        def get_cell(col_name: str):
            col_idx = self.columns.get(col_name)
            if col_idx is None:
                return None
            return ws.cell(row=row_num, column=col_idx + 1).value

        mrn = get_cell("mrn")
        service_date = get_cell("date")
        service_type = get_cell("service")

        # Skip empty rows
        if not mrn or not service_date:
            return None

        # Parse duration
        duration_raw = get_cell("duration")
        duration_mins = self._parse_duration(duration_raw)

        # Parse date
        if isinstance(service_date, datetime):
            service_date = service_date.date()
        elif isinstance(service_date, str):
            service_date = self._parse_date(service_date)

        return ServiceRecord(
            mrn=str(mrn),
            service_date=service_date,
            service_type=str(service_type) if service_type else "",
            duration_mins=duration_mins,
            location=str(get_cell("location") or ""),
            pps_comment=str(get_cell("pps_comment") or ""),
            provider=str(get_cell("provider") or ""),
            supervisor=str(get_cell("supervisor") or "") if get_cell("supervisor") else None,
            status=str(get_cell("status") or ""),
            note_status=str(get_cell("note_status") or ""),
            physical_proc=str(get_cell("physical_proc") or ""),
            financial_div=str(get_cell("financial_div") or ""),
            funding=str(get_cell("funding") or ""),
            comments=str(get_cell("comments") or ""),
            group_id=str(get_cell("group_id") or "") if get_cell("group_id") else None,
            start_time=str(get_cell("from_time") or "") if get_cell("from_time") else None,
            end_time=str(get_cell("to_time") or "") if get_cell("to_time") else None,
        )

    def _parse_duration(self, duration_raw) -> int:
        """Parse duration string like '180 mins' to integer minutes."""
        if duration_raw is None:
            return 0
        if isinstance(duration_raw, (int, float)):
            return int(duration_raw)

        duration_str = str(duration_raw)
        match = re.search(r'(\d+)', duration_str)
        if match:
            return int(match.group(1))
        return 0

    def _parse_date(self, date_str: str) -> date:
        """Parse date string in various formats."""
        for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%Y"]:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Could not parse date: {date_str}")

    def extract_rate_schedule(self, records: list[ServiceRecord]) -> RateSchedule:
        """
        Extract rate schedule from the PPS Comment field of service records.

        Args:
            records: List of service records

        Returns:
            RateSchedule with parsed rates
        """
        # Use the first record with a valid PPS comment
        for record in records:
            if record.pps_comment:
                schedule = parse_rates_from_pps_comment(record.pps_comment)
                # Check if we got any rates
                if any([
                    schedule.iop_rate > 0,
                    schedule.it_rate > 0,
                    schedule.group_rate > 0,
                    schedule.psych_eval_rate > 0
                ]):
                    return schedule

        # Return empty schedule if no rates found
        return RateSchedule()
    
    def group_by_mrn(self, records: list[ServiceRecord]) -> dict[str, list[ServiceRecord]]:
        """
        Group service records by MRN (Medical Record Number).
        
        Args:
            records: List of service records
            
        Returns:
            Dictionary mapping MRN to list of service records
        """
        grouped = defaultdict(list)
        for record in records:
            grouped[record.mrn].append(record)
        return dict(grouped)
    
    def extract_insurance_params_from_pps(self, pps_comment: str) -> tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        """
        Extract insurance parameters from PPS comment.
        
        Args:
            pps_comment: PPS Comment string
            
        Returns:
            Tuple of (deductible_total, deductible_met, oop_max, oop_used, coinsurance_rate)
            Returns None for any values that cannot be parsed
        """
        # Parse deductible
        ded_met, ded_total, _ = parse_deductible_from_pps_comment(pps_comment)
        
        # Parse OOP
        oop_used, oop_max, _ = parse_oop_from_pps_comment(pps_comment)
        
        # Parse coinsurance rate
        coinsurance_rate = None
        coins_pattern = r'(\d+)%\s*coinsurance'
        coins_match = re.search(coins_pattern, pps_comment, re.IGNORECASE)
        if coins_match:
            # Convert percentage to decimal (e.g., 50% -> 0.50)
            coinsurance_rate = Decimal(coins_match.group(1)) / Decimal('100')
        
        return ded_total, ded_met, oop_max, oop_used, coinsurance_rate


def extract_deductible_from_comment(comment: str) -> Optional[Decimal]:
    """
    Extract deductible amount from a comment string.

    Looks for patterns like "$3,272.00" at the start of a comment.

    Args:
        comment: Comment string that may contain deductible info

    Returns:
        Decimal deductible amount if found, None otherwise
    """
    pattern = r'\$\s*([\d,]+(?:\.\d{2})?)'
    match = re.search(pattern, comment)
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return None


def extract_prior_payment_from_comment(comment: str) -> Optional[Decimal]:
    """
    Extract prior payment amount from comments like "already paid $298.00 toward this appointment".

    Args:
        comment: Comment string that may contain prior payment info

    Returns:
        Decimal amount if found, None otherwise
    """
    pattern = r'already paid \$\s*([\d,]+(?:\.\d{2})?)'
    match = re.search(pattern, comment.lower())
    if match:
        return Decimal(match.group(1).replace(",", ""))
    return None
