#!/usr/bin/env python3
"""
Test script for enhanced billing output features.

Demonstrates:
1. Combined comments for same-day services
2. Updated PPS comment summary section
3. Service abbreviations with Tele/NSF prefixes
4. Client name privacy option
"""

from datetime import date
from decimal import Decimal

from rals.models import InsurancePlan, Client, RateSchedule, ServiceRecord
from rals.calculator import RateCalculator
from rals.output import generate_billing_report


def main():
    """Run enhanced billing test."""

    # Define the rate schedule
    rate_schedule = RateSchedule(
        iop_rate=Decimal("200.00"),
        group_rate=Decimal("125.00"),
        it_rate=Decimal("225.00"),
        ft_rate=Decimal("200.00"),
        psych_eval_rate=Decimal("350.00"),
        psych_followup_rate=Decimal("275.00"),
    )

    # Define the insurance plan with PPS-style comment tracking
    insurance_plan = InsurancePlan(
        name="Test Insurance",
        deductible=Decimal("3500.00"),
        coinsurance_rate=Decimal("0.40"),  # 40% coinsurance
        oop_max=Decimal("18200.00"),
        deductible_met=Decimal("1670.00"),  # Already have some met
        oop_accumulated=Decimal("14000.00"),  # Already have some accumulated
    )

    # Create the client
    client = Client(
        name="John Doe",
        mrn="28986",
        insurance_plan=insurance_plan
    )

    # Test case 1: Multiple services on same day (should get combined comment)
    # Test case 2: Telehealth service (should get Tele prefix)
    # Test case 3: NSF service (should get NSF suffix)
    services = [
        # Day 1: Two services on same day (1/26) - should combine
        ServiceRecord(
            mrn="28986",
            service_date=date(2026, 1, 26),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="Office",
            pps_comment="$1,670/$3,500 deductible / $14,000 OOP (combine) used as of 1/23 | 40% coinsurance | Ins Renews 1/2027",
            provider="Dr. Smith",
        ),
        ServiceRecord(
            mrn="28986",
            service_date=date(2026, 1, 26),
            service_type="Outpatient 53+",
            duration_mins=60,
            location="Office",
            pps_comment="$1,670/$3,500 deductible / $14,000 OOP (combine) used as of 1/23 | 40% coinsurance | Ins Renews 1/2027",
            provider="Dr. Smith",
        ),
        # Day 2: Single telehealth service (1/27)
        ServiceRecord(
            mrn="28986",
            service_date=date(2026, 1, 27),
            service_type="Telemed: IOP",
            duration_mins=180,
            location="Telehealth",
            pps_comment="$1,670/$3,500 deductible / $14,000 OOP (combine) used as of 1/23 | 40% coinsurance | Ins Renews 1/2027",
            provider="Dr. Jones",
        ),
        # Day 3: NSF service (1/28)
        ServiceRecord(
            mrn="28986",
            service_date=date(2026, 1, 28),
            service_type="NSF Psychiatric Diag. Eval. W. Med Services",
            duration_mins=60,
            location="Office",
            pps_comment="$1,670/$3,500 deductible / $14,000 OOP (combine) used as of 1/23 | 40% coinsurance | Ins Renews 1/2027",
            provider="Dr. Smith",
        ),
        # Day 4: Psych follow-up (1/29)
        ServiceRecord(
            mrn="28986",
            service_date=date(2026, 1, 29),
            service_type="OP: Psych Appointment (30-39 minutes)",
            duration_mins=35,
            location="Office",
            pps_comment="$1,670/$3,500 deductible / $14,000 OOP (combine) used as of 1/23 | 40% coinsurance | Ins Renews 1/2027",
            provider="Dr. Jones",
        ),
    ]

    # Create calculator and process all services
    print("=" * 80)
    print("ENHANCED BILLING OUTPUT TEST")
    print("=" * 80)
    print(f"\nProcessing {len(services)} services for MRN: {client.mrn}")
    print(f"Client: {client.name}")
    print(f"\nInitial Insurance Status:")
    print(f"  Deductible: ${insurance_plan.deductible_met:,.2f}/${insurance_plan.deductible:,.2f}")
    print(f"  OOP: ${insurance_plan.oop_accumulated:,.2f}/${insurance_plan.oop_max:,.2f}")
    print()

    calculator = RateCalculator(client, rate_schedule)
    billing_items = calculator.calculate_all_services(services)

    # Generate Excel outputs with and without client names
    print("\nGenerating output files...")
    
    # Output WITH client names (desktop version)
    output_path_with_names = generate_billing_report(
        billing_items,
        "/tmp/test_billing_with_names.xlsx",
        include_details=True,
        include_client_names=True,
        payment_date=date(2026, 1, 27)
    )
    print(f"  ✓ Output WITH client names: {output_path_with_names}")

    # Output WITHOUT client names (web version for HIPAA)
    output_path_no_names = generate_billing_report(
        billing_items,
        "/tmp/test_billing_no_names.xlsx",
        include_details=True,
        include_client_names=False,
        payment_date=date(2026, 1, 27)
    )
    print(f"  ✓ Output WITHOUT client names: {output_path_no_names}")

    # Show billing summary
    print("\n" + "=" * 80)
    print("BILLING SUMMARY")
    print("=" * 80)
    
    for item in billing_items:
        print(f"\n{item.date_of_service.strftime('%m/%d/%Y')} - {item.service_type}")
        print(f"  Charge Amount: ${item.charge_amount:,.2f}")
        print(f"  Comment: {item.comment}")
        if item.updated_pps_comment:
            print(f"  Updated PPS: {item.updated_pps_comment[:80]}...")

    # Show final status
    total_charges = sum(item.charge_amount for item in billing_items)
    print("\n" + "=" * 80)
    print(f"Total Patient Responsibility: ${total_charges:,.2f}")
    print(f"\nFinal Insurance Status:")
    print(f"  Deductible met: ${insurance_plan.deductible_met:,.2f} of ${insurance_plan.deductible:,.2f}")
    print(f"  OOP accumulated: ${insurance_plan.oop_accumulated:,.2f} of ${insurance_plan.oop_max:,.2f}")
    print("=" * 80)

    # Show what to expect in output
    print("\n" + "=" * 80)
    print("EXPECTED OUTPUT FILE STRUCTURE:")
    print("=" * 80)
    print("""
Row 1:  Header (Client Name | MRN | Date of Service | Service Type | ...)
Row 2:  1/26/2026 IOP-Wilton         $200.00  [Comment: $425.00 1/26 IOP & IT 53+]
Row 3:  1/26/2026 Outpatient 53+     $225.00  [Comment: $425.00 1/26 IOP & IT 53+]
Row 4:  1/27/2026 Telemed: IOP       $200.00  [Comment: $200.00 1/27 Tele IOP]
Row 5:  1/28/2026 NSF Psych Eval     $XXX.XX  [Comment: $XXX.XX 1/28 Psych Eval NSF]
Row 6:  1/29/2026 Psych f/u 30-39    $XXX.XX  [Comment: $XXX.XX 1/29 Psych f/u 30-39]
Row 7:  [Blank]
Row 8:  "Updated PPS Comments by MRN"
Row 9:  Header (Client Name | MRN | Updated PPS Comment)
Row 10: John Doe | 28986 | $X,XXX/$3,500 deductible / $XX,XXX OOP (combine) used as of 1/27 | ...
    """)

    print("\n✅ Test completed successfully!")
    print(f"   Review the generated Excel files at:")
    print(f"   - {output_path_with_names}")
    print(f"   - {output_path_no_names}")


if __name__ == "__main__":
    main()
