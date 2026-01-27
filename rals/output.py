"""Output generator for billing summary spreadsheets."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .models import BillingLineItem


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


class BillingOutputGenerator:
    """Generates billing summary spreadsheets."""

    def __init__(self):
        """Initialize the output generator."""
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
        include_details: bool = False
    ) -> Path:
        """
        Generate billing summary spreadsheet.

        Args:
            billing_items: List of billing line items
            output_path: Path for output file
            include_details: If True, add extra columns for calculation details

        Returns:
            Path to generated file
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Billing Summary"

        # Add columns for details if requested
        columns = list(OUTPUT_COLUMNS)
        if include_details:
            columns.extend([
                ("Full Rate", 12),
                ("Applied to Ded", 15),
                ("Coinsurance", 12),
                ("Ded Remaining", 15),
                ("OOP Remaining", 15),
            ])

        # Write header row
        self._write_header(ws, columns)

        # Write data rows
        for idx, item in enumerate(billing_items, start=2):
            self._write_data_row(ws, idx, item, include_details)

        # Set column widths
        for col_idx, (_, width) in enumerate(columns, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        # Save file
        output_path = Path(output_path)
        wb.save(output_path)
        wb.close()

        return output_path

    def _write_header(self, ws, columns: list):
        """Write the header row with styling."""
        for col_idx, (name, _) in enumerate(columns, start=1):
            cell = ws.cell(row=1, column=col_idx, value=name)
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = self.border

    def _write_data_row(self, ws, row_num: int, item: BillingLineItem, include_details: bool):
        """Write a single data row."""
        fill = self.data_fill_odd if row_num % 2 == 0 else self.data_fill_even

        # Basic columns
        values = [
            item.client_name,
            item.mrn,
            item.date_of_service,
            item.service_type,
            item.payment_date,
            float(item.charge_amount),
            item.payment_type,
            item.receipt_saved,
            item.comment,
        ]

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

            # Format currency columns
            if col_idx in [6] or (include_details and col_idx in [10, 11, 12, 13, 14]):
                cell.number_format = self.currency_format

            # Format date columns
            if col_idx in [3, 5] and value:
                cell.number_format = 'MM/DD/YYYY'


def generate_billing_report(
    billing_items: list[BillingLineItem],
    output_path: str | Path,
    include_details: bool = False
) -> Path:
    """
    Convenience function to generate a billing report.

    Args:
        billing_items: List of billing line items
        output_path: Path for output file
        include_details: If True, include calculation details

    Returns:
        Path to generated file
    """
    generator = BillingOutputGenerator()
    return generator.generate(billing_items, output_path, include_details)


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
