#!/usr/bin/env python3
"""
Example usage of the RALS insurance rate calculator.

This demonstrates how to use the library programmatically
without going through the CLI.
"""

from datetime import date
from decimal import Decimal

from rals.models import InsurancePlan, Client, RateSchedule, ServiceRecord
from rals.calculator import RateCalculator
from rals.output import print_billing_summary, generate_billing_report


def main():
    """Run example billing calculation."""

    # Define the rate schedule (extracted from PPS Comment)
    rate_schedule = RateSchedule(
        iop_rate=Decimal("575.00"),
        group_rate=Decimal("125.00"),
        it_rate=Decimal("260.00"),
        ft_rate=Decimal("200.00"),
        psych_eval_rate=Decimal("350.00"),
        psych_followup_rate=Decimal("275.00"),
    )

    # Define the insurance plan
    insurance_plan = InsurancePlan(
        name="Example Insurance",
        deductible=Decimal("3272.00"),
        coinsurance_rate=Decimal("0.20"),  # Patient pays 20% after deductible
        oop_max=Decimal("6500.00"),
    )

    # Create the client
    client = Client(
        name="Example Client",
        mrn="28829",
        insurance_plan=insurance_plan
    )

    # Define service records (simulating rows 2-14 from spreadsheet)
    services = [
        ServiceRecord(
            mrn="28829",
            service_date=date(2026, 1, 5),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="W: Group Room",
            pps_comment="IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275",
            provider="MAT $1",
        ),
        ServiceRecord(
            mrn="28829",
            service_date=date(2026, 1, 7),
            service_type="Outpatient 53+",
            duration_mins=60,
            location="W: Cindy's Office",
            pps_comment="IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275",
            provider="MAT $1",
        ),
        ServiceRecord(
            mrn="28829",
            service_date=date(2026, 1, 8),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="W: Group Room",
            pps_comment="IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275",
            provider="MAT $1",
        ),
        ServiceRecord(
            mrn="28829",
            service_date=date(2026, 1, 12),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="W: Group Room",
            pps_comment="IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275",
            provider="MAT $1",
        ),
        ServiceRecord(
            mrn="28829",
            service_date=date(2026, 1, 13),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="W: Group Room",
            pps_comment="IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275",
            provider="MAT $1",
        ),
        ServiceRecord(
            mrn="28829",
            service_date=date(2026, 1, 14),
            service_type="Telemed: Psych",
            duration_mins=70,
            location="W: Telehealth",
            pps_comment="IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275",
            provider="MAT $1",
        ),
        ServiceRecord(
            mrn="28829",
            service_date=date(2026, 1, 19),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="W: Group Room",
            pps_comment="IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275",
            provider="MAT $1",
        ),
        ServiceRecord(
            mrn="28829",
            service_date=date(2026, 1, 19),
            service_type="Outpatient EMDR",
            duration_mins=60,
            location="W: Cindy's Office",
            pps_comment="IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275",
            provider="MAT $1",
        ),
        ServiceRecord(
            mrn="28829",
            service_date=date(2026, 1, 20),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="W: Group Room",
            pps_comment="IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275",
            provider="MAT $1",
        ),
        ServiceRecord(
            mrn="28829",
            service_date=date(2026, 1, 22),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="W: Group Room",
            pps_comment="IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275",
            provider="MAT $1",
        ),
        ServiceRecord(
            mrn="28829",
            service_date=date(2026, 1, 26),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="W: Group Room",
            pps_comment="IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275",
            provider="MAT $1",
        ),
    ]

    # Create calculator and process all services
    calculator = RateCalculator(client, rate_schedule)
    billing_items = calculator.calculate_all_services(services)

    # Print summary to console
    print_billing_summary(billing_items)

    # Generate Excel output
    output_path = generate_billing_report(
        billing_items,
        "example_billing_output.xlsx",
        include_details=True
    )
    print(f"Excel output saved to: {output_path}")

    # Show final insurance status
    print(f"\nFinal Insurance Status:")
    print(f"  Deductible met: ${insurance_plan.deductible_met:,.2f} of ${insurance_plan.deductible:,.2f}")
    print(f"  Deductible satisfied: {insurance_plan.deductible_satisfied}")
    print(f"  OOP accumulated: ${insurance_plan.oop_accumulated:,.2f} of ${insurance_plan.oop_max:,.2f}")
    print(f"  OOP max reached: {insurance_plan.oop_max_reached}")


if __name__ == "__main__":
    main()
