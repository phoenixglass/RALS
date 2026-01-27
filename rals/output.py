"""Output generator for billing summary spreadsheets."""

import re
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .models import BillingLineItem, generate_combined_comment, get_service_abbreviation


# Output column configuration
OUTPUT_COLUMNS = [
    ("Client Name", 15),
    ("MRN", 10),
    ("DOS", 12),
    ("Service Type", 20),
    ("Payment Date", 12),
    ("Charge Amt", 12),
    ("Payment Type", 12),
    ("Receipt Saved", 12),
    ("Comment", 60),
]

OUTPUT_COLUMNS_NO_NAME = [
    ("MRN", 10),
    ("DOS", 12),
    ("Service Type", 20),
    ("Payment Date", 12),
    ("Charge Amt", 12),
    ("Payment Type", 12),
    ("Receipt Saved", 12),
    ("Comment", 60),
]


class BillingOutputGenerator:
    """Generates billing summary spreadsheets."""

    def __init__(self, include_client_names: bool = True):
        """
        Initialize the output generator.
        
        Args:
            include_client_names: Whether to include client names in output (default True)
                                 Set to False for HIPAA-compliant web deployments
        """
        self.include_client_names = include_client_names
        self.header_font = Font(bold=True, color="FFFFFF")
        self.header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
        self.data_fill_odd = PatternFill(start_color="D6DCE4", end_color="D6DCE4", fill_type="solid")
        self.data_fill_even = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        self.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        self.currency_format = '$#,##0.00'

    def generate(
        self,
        billing_items: list[BillingLineItem],
        output_path: str | Path,
        include_details: bool = False,
        payment_date: Optional[date] = None
    ) -> Path:
        """
        Generate enhanced billing summary spreadsheet with combined comments and PPS updates.

        Args:
            billing_items: List of billing line items
            output_path: Path for output file
            include_details: If True, add extra columns for calculation details
            payment_date: Payment date to use (defaults to today)

        Returns:
            Path to generated file
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Billing Summary"
        
        # Use today's date if payment_date not provided
        if payment_date is None:
            payment_date = date.today()

        # Choose columns based on client name privacy setting
        columns = list(OUTPUT_COLUMNS if self.include_client_names else OUTPUT_COLUMNS_NO_NAME)
        if include_details:
            columns.extend([
                ("Full Rate", 12),
                ("Applied to Ded", 15),
                ("Coinsurance", 12),
                ("Ded Remaining", 15),
                ("OOP Remaining", 15),
            ])

        # Write header row (row 17 in the spec, but we start at row 1 for simplicity)
        current_row = 1
        self._write_header(ws, current_row, columns)
        current_row += 1

        # Group billing items by MRN and date for combined comments
        grouped_items = self._group_items_by_mrn_date(billing_items)
        
        # Write billing data rows with combined comments
        for (mrn, service_date), items in sorted(grouped_items.items()):
            # Generate combined comment for same-day services
            total_charge = sum(item.charge_amount for item in items)
            
            # Get unique service abbreviations, preserving Tele/NSF markers per service
            seen_abbrevs = set()
            service_abbrevs = []
            for item in items:
                abbrev = get_service_abbreviation(item.service_type)
                # Keep the full abbreviation with Tele/NSF if present
                if abbrev not in seen_abbrevs:
                    service_abbrevs.append(abbrev)
                    seen_abbrevs.add(abbrev)
            
            # Build combined comment
            parts = [f"${total_charge:,.2f}", f"{service_date.month}/{service_date.day}"]
            parts.append(" & ".join(service_abbrevs))
            
            combined_comment = " ".join(parts)
            
            # Write one row per service, all with the same combined comment
            for item in items:
                self._write_billing_row(ws, current_row, item, payment_date, combined_comment, include_details)
                current_row += 1
        
        # Add blank row
        current_row += 1
        
        # Write PPS comment summary section
        current_row = self._write_pps_summary_section(ws, current_row, billing_items, payment_date)

        # Set column widths
        for col_idx, (_, width) in enumerate(columns, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        # Save file
        output_path = Path(output_path)
        wb.save(output_path)
        wb.close()

        return output_path

    def _group_items_by_mrn_date(self, billing_items: list[BillingLineItem]) -> dict:
        """Group billing items by (MRN, date) for combined comment generation."""
        grouped = defaultdict(list)
        for item in billing_items:
            key = (item.mrn, item.date_of_service)
            grouped[key].append(item)
        return grouped

    def _write_header(self, ws, row_num: int, columns: list):
        """Write the header row with styling."""
        for col_idx, (name, _) in enumerate(columns, start=1):
            cell = ws.cell(row=row_num, column=col_idx, value=name)
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = self.border

    def _write_billing_row(
        self, 
        ws, 
        row_num: int, 
        item: BillingLineItem, 
        payment_date: date,
        combined_comment: str,
        include_details: bool
    ):
        """Write a single billing data row."""
        fill = self.data_fill_odd if row_num % 2 == 0 else self.data_fill_even

        # Basic columns
        values = []
        if self.include_client_names:
            values.append(item.client_name)
        
        values.extend([
            item.mrn,
            item.date_of_service,
            item.service_type,
            payment_date,
            float(item.charge_amount),
            item.payment_type,
            item.receipt_saved,
            combined_comment,
        ])

        # Detail columns
        if include_details:
            values.extend([
                float(item.full_rate),
                float(item.applied_to_deductible),
                float(item.coinsurance_amount),
                float(item.deductible_remaining_after),
                float(item.oop_remaining_after),
            ])

        for col_idx, value in enumerate(values, start=1):
            cell = ws.cell(row=row_num, column=col_idx, value=value)
            cell.fill = fill
            cell.border = self.border

            # Determine currency column position based on whether client name is included
            charge_col = 6 if self.include_client_names else 5
            detail_start_col = 10 if self.include_client_names else 9
            
            # Format currency columns
            if col_idx == charge_col or (include_details and col_idx >= detail_start_col):
                cell.number_format = self.currency_format

            # Format date columns
            dos_col = 3 if self.include_client_names else 2
            payment_col = 5 if self.include_client_names else 4
            if col_idx in [dos_col, payment_col] and value:
                cell.number_format = 'MM/DD/YYYY'

    def _write_pps_summary_section(
        self, 
        ws, 
        start_row: int, 
        billing_items: list[BillingLineItem],
        payment_date: date
    ) -> int:
        """
        Write the Updated PPS Comments summary section.
        
        Returns:
            Next available row number
        """
        current_row = start_row
        
        # Write section header
        cell = ws.cell(row=current_row, column=1, value="Updated PPS Comments by MRN")
        cell.font = Font(bold=True, size=12)
        current_row += 1
        
        # Write column headers
        header_cols = ["Client Name", "MRN", "Updated PPS Comment"] if self.include_client_names else ["MRN", "Updated PPS Comment"]
        for col_idx, header_text in enumerate(header_cols, start=1):
            cell = ws.cell(row=current_row, column=col_idx, value=header_text)
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = self.border
        current_row += 1
        
        # Group by MRN and get the latest updated PPS comment for each
        mrn_pps_map = {}
        for item in billing_items:
            if item.updated_pps_comment:
                # Use the most recent updated PPS comment for each MRN
                if item.mrn not in mrn_pps_map:
                    mrn_pps_map[item.mrn] = {
                        'client_name': item.client_name,
                        'pps_comment': item.updated_pps_comment,
                        'date': item.date_of_service
                    }
                elif item.date_of_service > mrn_pps_map[item.mrn]['date']:
                    mrn_pps_map[item.mrn] = {
                        'client_name': item.client_name,
                        'pps_comment': item.updated_pps_comment,
                        'date': item.date_of_service
                    }
        
        # Write PPS comment rows
        for mrn in sorted(mrn_pps_map.keys()):
            info = mrn_pps_map[mrn]
            fill = self.data_fill_odd if current_row % 2 == 0 else self.data_fill_even
            
            col_idx = 1
            if self.include_client_names:
                cell = ws.cell(row=current_row, column=col_idx, value=info['client_name'])
                cell.fill = fill
                cell.border = self.border
                col_idx += 1
            
            cell = ws.cell(row=current_row, column=col_idx, value=mrn)
            cell.fill = fill
            cell.border = self.border
            col_idx += 1
            
            cell = ws.cell(row=current_row, column=col_idx, value=info['pps_comment'])
            cell.fill = fill
            cell.border = self.border
            
            current_row += 1
        
        return current_row

    def _write_data_row(self, ws, row_num: int, item: BillingLineItem, include_details: bool):
        """Write a single data row (legacy method - kept for compatibility)."""
        fill = self.data_fill_odd if row_num % 2 == 0 else self.data_fill_even

        # Basic columns
        values = []
        if self.include_client_names:
            values.append(item.client_name)
        
        values.extend([
            item.mrn,
            item.date_of_service,
            item.service_type,
            item.payment_date,
            float(item.charge_amount),
            item.payment_type,
            item.receipt_saved,
            item.comment,
        ])

        # Detail columns
        if include_details:
            values.extend([
                float(item.full_rate),
                float(item.applied_to_deductible),
                float(item.coinsurance_amount),
                float(item.deductible_remaining_after),
                float(item.oop_remaining_after),
            ])

        for col_idx, value in enumerate(values, start=1):
            cell = ws.cell(row=row_num, column=col_idx, value=value)
            cell.fill = fill
            cell.border = self.border

            # Determine currency column position
            charge_col = 6 if self.include_client_names else 5
            detail_start_col = 10 if self.include_client_names else 9
            
            # Format currency columns
            if col_idx == charge_col or (include_details and col_idx >= detail_start_col):
                cell.number_format = self.currency_format

            # Format date columns
            dos_col = 3 if self.include_client_names else 2
            payment_col = 5 if self.include_client_names else 4
            if col_idx in [dos_col, payment_col] and value:
                cell.number_format = 'MM/DD/YYYY'


def generate_billing_report(
    billing_items: list[BillingLineItem],
    output_path: str | Path,
    include_details: bool = False,
    include_client_names: bool = True,
    payment_date: Optional[date] = None
) -> Path:
    """
    Convenience function to generate a billing report.

    Args:
        billing_items: List of billing line items
        output_path: Path for output file
        include_details: If True, include calculation details
        include_client_names: If True, include client names (default True for HIPAA safety)
        payment_date: Payment date to use (defaults to today)

    Returns:
        Path to generated file
    """
    generator = BillingOutputGenerator(include_client_names=include_client_names)
    return generator.generate(billing_items, output_path, include_details, payment_date)


def print_billing_summary(billing_items: list[BillingLineItem]):
    """
    Print a text summary of billing items to console.

    Args:
        billing_items: List of billing line items
    """
    print("\n" + "=" * 80)
    print("BILLING SUMMARY")
    print("=" * 80)

    total_charges = Decimal("0.00")

    for item in billing_items:
        print(f"\n{item.date_of_service.strftime('%m/%d/%Y')} - {item.service_type}")
        print(f"  Full Rate:     ${item.full_rate:,.2f}")
        print(f"  Charge Amount: ${item.charge_amount:,.2f}")

        if item.applied_to_deductible > 0:
            print(f"  → Applied to Deductible: ${item.applied_to_deductible:,.2f}")

        if item.coinsurance_amount > 0:
            print(f"  → Coinsurance: ${item.coinsurance_amount:,.2f}")

        print(f"  Deductible Remaining: ${item.deductible_remaining_after:,.2f}")
        print(f"  OOP Remaining: ${item.oop_remaining_after:,.2f}")

        total_charges += item.charge_amount

    print("\n" + "-" * 80)
    print(f"TOTAL PATIENT RESPONSIBILITY: ${total_charges:,.2f}")
    print("=" * 80 + "\n")
