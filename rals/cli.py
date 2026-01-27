"""Command-line interface for RALS."""

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from .models import InsurancePlan, Client, RateSchedule
from .parser import SpreadsheetParser
from .calculator import RateCalculator, parse_rates_from_pps_comment
from .output import generate_billing_report, print_billing_summary


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="RALS - Insurance Rate and Ledger System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with default insurance parameters
  python -m rals.cli input.xlsx -o billing_output.xlsx

  # Specify custom insurance plan parameters
  python -m rals.cli input.xlsx -o billing.xlsx --deductible 3272 --coinsurance 0.40 --oop-max 6500

  # Include calculation details in output
  python -m rals.cli input.xlsx -o billing.xlsx --details

  # Specify client name
  python -m rals.cli input.xlsx -o billing.xlsx --client-name "John Doe"

  # Process specific rows
  python -m rals.cli input.xlsx -o billing.xlsx --start-row 2 --end-row 14
        """
    )

    parser.add_argument(
        "input_file",
        help="Input Excel file with service data"
    )

    parser.add_argument(
        "-o", "--output",
        default="billing_summary.xlsx",
        help="Output Excel file path (default: billing_summary.xlsx)"
    )

    parser.add_argument(
        "--client-name",
        default="",
        help="Client name to use in output"
    )

    parser.add_argument(
        "--deductible",
        type=Decimal,
        default=Decimal("3272.00"),
        help="Annual deductible amount (default: 3272.00)"
    )

    parser.add_argument(
        "--coinsurance",
        type=Decimal,
        default=Decimal("0.40"),
        help="Coinsurance rate as decimal (default: 0.40 = 40%%)"
    )

    parser.add_argument(
        "--oop-max",
        type=Decimal,
        default=Decimal("6500.00"),
        help="Out-of-pocket maximum (default: 6500.00)"
    )

    parser.add_argument(
        "--deductible-met",
        type=Decimal,
        default=Decimal("0.00"),
        help="Amount already applied to deductible (default: 0.00)"
    )

    parser.add_argument(
        "--oop-accumulated",
        type=Decimal,
        default=Decimal("0.00"),
        help="Amount already accumulated toward OOP max (default: 0.00)"
    )

    parser.add_argument(
        "--start-row",
        type=int,
        default=2,
        help="First row of data in input file (default: 2)"
    )

    parser.add_argument(
        "--end-row",
        type=int,
        default=None,
        help="Last row of data in input file (default: auto-detect)"
    )

    parser.add_argument(
        "--details",
        action="store_true",
        help="Include calculation details in output"
    )

    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print summary to console"
    )

    # Rate overrides
    parser.add_argument("--iop-rate", type=Decimal, help="Override IOP rate")
    parser.add_argument("--it-rate", type=Decimal, help="Override Individual Therapy rate")
    parser.add_argument("--ft-rate", type=Decimal, help="Override Family Therapy rate")
    parser.add_argument("--group-rate", type=Decimal, help="Override Group rate")
    parser.add_argument("--psych-eval-rate", type=Decimal, help="Override Psych Eval rate")
    parser.add_argument("--psych-followup-rate", type=Decimal, help="Override Psych Follow-up rate")

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Parse input data
    print(f"Parsing input file: {input_path}")
    spreadsheet_parser = SpreadsheetParser(
        start_row=args.start_row,
        end_row=args.end_row
    )

    try:
        services = spreadsheet_parser.parse_file(input_path)
    except Exception as e:
        print(f"Error parsing input file: {e}", file=sys.stderr)
        sys.exit(1)

    if not services:
        print("No service records found in input file.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(services)} service records")

    # Get MRN from first record if client name not provided
    mrn = services[0].mrn
    client_name = args.client_name or f"Client {mrn}"

    # Extract rate schedule from PPS comments
    rate_schedule = spreadsheet_parser.extract_rate_schedule(services)

    # Apply rate overrides from CLI
    if args.iop_rate:
        rate_schedule.iop_rate = args.iop_rate
    if args.it_rate:
        rate_schedule.it_rate = args.it_rate
    if args.ft_rate:
        rate_schedule.ft_rate = args.ft_rate
    if args.group_rate:
        rate_schedule.group_rate = args.group_rate
    if args.psych_eval_rate:
        rate_schedule.psych_eval_rate = args.psych_eval_rate
    if args.psych_followup_rate:
        rate_schedule.psych_followup_rate = args.psych_followup_rate

    print(f"Rate schedule extracted:")
    print(f"  IOP: ${rate_schedule.iop_rate:,.2f}")
    print(f"  IT: ${rate_schedule.it_rate:,.2f}")
    print(f"  FT: ${rate_schedule.ft_rate:,.2f}")
    print(f"  Group: ${rate_schedule.group_rate:,.2f}")
    print(f"  Psych Eval: ${rate_schedule.psych_eval_rate:,.2f}")
    print(f"  Psych Follow-up: ${rate_schedule.psych_followup_rate:,.2f}")

    # Create insurance plan
    insurance_plan = InsurancePlan(
        name="Client Insurance",
        deductible=args.deductible,
        coinsurance_rate=args.coinsurance,
        oop_max=args.oop_max,
        deductible_met=args.deductible_met,
        oop_accumulated=args.oop_accumulated
    )

    print(f"\nInsurance plan:")
    print(f"  Deductible: ${insurance_plan.deductible:,.2f}")
    print(f"  Already met: ${insurance_plan.deductible_met:,.2f}")
    print(f"  Remaining: ${insurance_plan.remaining_deductible:,.2f}")
    print(f"  Coinsurance: {insurance_plan.coinsurance_rate * 100:.0f}%")
    print(f"  OOP Max: ${insurance_plan.oop_max:,.2f}")

    # Create client
    client = Client(
        name=client_name,
        mrn=mrn,
        insurance_plan=insurance_plan
    )

    # Calculate billing
    print(f"\nCalculating billing...")
    calculator = RateCalculator(client, rate_schedule)
    billing_items = calculator.calculate_all_services(services)

    # Generate output
    output_path = Path(args.output)
    generate_billing_report(billing_items, output_path, include_details=args.details)
    print(f"\nBilling summary written to: {output_path}")

    # Print summary if requested
    if args.print_summary:
        print_billing_summary(billing_items)

    # Print totals
    total_charges = sum(item.charge_amount for item in billing_items)
    print(f"\nTotal patient responsibility: ${total_charges:,.2f}")
    print(f"Final deductible remaining: ${insurance_plan.remaining_deductible:,.2f}")
    print(f"Final OOP remaining: ${insurance_plan.remaining_oop:,.2f}")


if __name__ == "__main__":
    main()
