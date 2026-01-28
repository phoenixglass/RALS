"""
RALS - Streamlit Web Application
Insurance rate calculator web interface with batch processing support.

This app processes spreadsheets with multiple clients, extracting insurance
parameters from PPS Comments automatically.
"""

import streamlit as st
import tempfile
import os
from datetime import date
from decimal import Decimal
import re

from rals.parser import SpreadsheetParser
from rals.calculator import RateCalculator
from rals.output import BillingOutputGenerator
from rals.models import Client, InsurancePlan


def sanitize_filename(name):
    """Sanitize a string to be safe for use in a filename."""
    safe_name = name.replace(' ', '_')
    safe_name = re.sub(r'[^\w\-.]', '', safe_name)
    safe_name = safe_name[:100]
    return safe_name if safe_name else "output"


def process_batch(services, parser):
    """
    Process multiple clients from a single spreadsheet.

    Groups services by MRN, extracts insurance params from PPS Comments,
    and calculates billing for each client.

    Returns:
        Tuple of (all_billing_items, client_count, errors)
    """
    # Group services by MRN (client)
    grouped = parser.group_by_mrn(services)

    all_billing_items = []
    errors = []

    for mrn, client_services in grouped.items():
        try:
            # Get the first service record with a PPS comment for this client
            pps_comment = None
            for svc in client_services:
                if svc.pps_comment:
                    pps_comment = svc.pps_comment
                    break

            if not pps_comment:
                errors.append(f"MRN {mrn}: No PPS Comment found, skipping")
                continue

            # Check if self-pay client
            is_self_pay = 'self-pay' in pps_comment.lower() or 'self pay' in pps_comment.lower()

            # Extract rate schedule from PPS comment
            rate_schedule = parser.extract_rate_schedule(client_services)

            # Extract insurance parameters from PPS comment
            ded_total, ded_met, oop_max, oop_used, coinsurance_rate = parser.extract_insurance_params_from_pps(pps_comment)

            # For self-pay clients, patient pays full rate (no deductible/coinsurance)
            if is_self_pay:
                ded_total = Decimal("0")
                ded_met = Decimal("0")
                oop_max = Decimal("999999")
                oop_used = Decimal("0")
                coinsurance_rate = Decimal("1.0")  # 100% patient responsibility
            else:
                # Use defaults if not found in PPS comment
                if ded_total is None:
                    ded_total = Decimal("0")
                if ded_met is None:
                    ded_met = Decimal("0")
                if oop_max is None:
                    oop_max = Decimal("10000")  # Reasonable default
                if oop_used is None:
                    oop_used = Decimal("0")
                if coinsurance_rate is None:
                    coinsurance_rate = Decimal("0.40")  # Default 40%

            # Create insurance plan with extracted parameters
            insurance_plan = InsurancePlan(
                name="Insurance",
                deductible=ded_total,
                coinsurance_rate=coinsurance_rate,
                oop_max=oop_max,
                deductible_met=ded_met,
                oop_accumulated=oop_used
            )

            # Create client
            client = Client(
                name=f"Client {mrn}",
                mrn=mrn,
                insurance_plan=insurance_plan
            )

            # Calculate billing for this client
            calculator = RateCalculator(client, rate_schedule)
            billing_items = calculator.calculate_all_services_combined(client_services)

            all_billing_items.extend(billing_items)

        except Exception as e:
            errors.append(f"MRN {mrn}: {str(e)}")

    return all_billing_items, len(grouped), errors


def main():
    """Main Streamlit application"""

    # Page configuration
    st.set_page_config(
        page_title="RALS - Rate and Ledger System",
        page_icon="📊",
        layout="wide"
    )

    # Header
    st.title("📊 RALS - Rate and Ledger System")
    st.markdown("**Batch processing** for multiple clients - insurance parameters are extracted from PPS Comments automatically")

    st.divider()

    # File upload section
    st.header("1️⃣ Upload Service Data")
    st.markdown("""
    Upload an Excel file containing service records. The file should have:
    - **MRN** column - Medical Record Number for each client
    - **Date** column - Service date
    - **Service** column - Service type (IOP, IT, FT, Group, etc.)
    - **PPS Comment** column - Contains insurance info like:
      - Rates: `IOP $200 | Group $75 | IT $225`
      - Deductible: `$1,732.50/$3,500 deductible`
      - OOP: `$2,911/$3,350 OOP used as of 1/23`
      - Coinsurance: `50% coinsurance`
    """)

    uploaded_file = st.file_uploader(
        "Choose an Excel file (.xlsx or .xls)",
        type=["xlsx", "xls"],
        help="Upload your service appointment data spreadsheet with PPS Comments containing insurance info"
    )

    st.divider()

    # Options section
    st.header("2️⃣ Output Options")

    col1, col2 = st.columns(2)

    with col1:
        include_details = st.checkbox(
            "Include calculation details",
            value=False,
            help="Add columns showing deductible and coinsurance breakdown"
        )

    with col2:
        include_client_names = st.checkbox(
            "Include client names in output",
            value=True,
            help="Uncheck for HIPAA-compliant output (MRN only)"
        )

    st.divider()

    # Calculate button
    st.header("3️⃣ Process Billing")

    if st.button("🔢 Calculate Billing for All Clients", type="primary", use_container_width=True):
        if uploaded_file is None:
            st.error("Please upload an Excel file first")
        else:
            try:
                with st.spinner("Processing service data..."):
                    # Save uploaded file to temporary location
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        input_path = tmp_file.name

                    try:
                        # Parse the input file
                        parser = SpreadsheetParser()
                        services = parser.parse_file(input_path)

                        # Debug: Show detected columns
                        st.info(f"Detected columns: {parser.columns}")

                        # Debug: Show first few PPS comments found
                        pps_samples = [s.pps_comment[:100] for s in services[:3] if s.pps_comment]
                        if pps_samples:
                            st.info(f"Sample PPS Comments found: {pps_samples}")
                        else:
                            st.warning("No PPS Comments found in any records")
                    finally:
                        if os.path.exists(input_path):
                            os.unlink(input_path)

                    if not services:
                        st.error("No valid service records found in the uploaded file")
                        return

                    # Process all clients in batch
                    billing_items, client_count, errors = process_batch(services, parser)

                    if not billing_items:
                        st.error("No billable items generated. Check that PPS Comments contain valid insurance information.")
                        if errors:
                            st.warning("Errors encountered:")
                            for err in errors:
                                st.text(f"  - {err}")
                        return

                    # Generate output file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as output_tmp:
                        output_path = output_tmp.name

                    try:
                        generator = BillingOutputGenerator(include_client_names=include_client_names)
                        result_path = generator.generate(
                            billing_items,
                            output_path,
                            include_details=include_details,
                            payment_date=date.today()
                        )

                        with open(result_path, "rb") as f:
                            output_data = f.read()
                    finally:
                        if os.path.exists(output_path):
                            os.unlink(output_path)

                # Display success message
                st.success("Billing calculation completed successfully!")

                # Show errors if any
                if errors:
                    with st.expander(f"⚠️ {len(errors)} Warning(s)", expanded=False):
                        for err in errors:
                            st.text(f"  - {err}")

                # Display summary statistics
                st.header("📈 Summary Statistics")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("Clients Processed", client_count)

                with col2:
                    st.metric("Services Processed", len(services))

                with col3:
                    st.metric("Billable Items", len(billing_items))

                with col4:
                    total_charges = sum(item.charge_amount for item in billing_items)
                    st.metric("Total Charges", f"${total_charges:,.2f}")

                # Show billing details by client
                with st.expander("📋 Billing Details by Client"):
                    # Group by MRN for display
                    from collections import defaultdict
                    by_mrn = defaultdict(list)
                    for item in billing_items:
                        by_mrn[item.mrn].append(item)

                    for mrn, items in sorted(by_mrn.items()):
                        client_total = sum(item.charge_amount for item in items)
                        st.markdown(f"**MRN {mrn}** - {len(items)} items - Total: ${client_total:,.2f}")
                        for item in items[:5]:
                            st.text(f"  {item.date_of_service} - {item.service_type}: ${item.charge_amount:.2f}")
                        if len(items) > 5:
                            st.text(f"  ... and {len(items) - 5} more items")
                        st.markdown("---")

                st.divider()

                # Download button
                st.header("4️⃣ Download Results")

                output_filename = f"billing_summary_{date.today().strftime('%Y%m%d')}.xlsx"

                st.download_button(
                    label="⬇️ Download Billing Summary",
                    data=output_data,
                    file_name=output_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

                st.info("The output includes:\n- Billing rows with Payment Date, Charge Amount, and Comment\n- Updated PPS Comments section with new deductible/OOP values")

            except Exception as e:
                st.error(f"Error processing file: {str(e)}")
                st.exception(e)

    # Footer
    st.divider()
    st.markdown("""
    **RALS - Rate and Ledger System** |
    [GitHub Repository](https://github.com/phoenixglass/RALS) |
    Version 2.0.0 - Batch Processing
    """)


if __name__ == "__main__":
    main()
