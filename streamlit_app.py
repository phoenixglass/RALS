"""
RALS - Streamlit Web Application
Insurance rate calculator web interface
"""

import streamlit as st
from pathlib import Path
import tempfile
from decimal import Decimal

from rals.parser import SpreadsheetParser
from rals.calculator import RateCalculator
from rals.output import BillingOutputGenerator
from rals.models import Client, InsurancePlan


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
    st.markdown("Insurance rate calculator for service appointment billing")
    
    st.divider()
    
    # File upload section
    st.header("1️⃣ Upload Service Data")
    uploaded_file = st.file_uploader(
        "Choose an Excel file (.xlsx or .xls)",
        type=["xlsx", "xls"],
        help="Upload your service appointment data spreadsheet"
    )
    
    st.divider()
    
    # Client information section
    st.header("2️⃣ Client Information")
    client_name = st.text_input(
        "Client Name (Optional)",
        placeholder="Enter client name",
        help="This will appear in the billing summary"
    )
    
    st.divider()
    
    # Insurance parameters section
    st.header("3️⃣ Insurance Parameters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        deductible = st.number_input(
            "Annual Deductible ($)",
            min_value=0.0,
            value=3272.0,
            step=100.0,
            format="%.2f",
            help="Annual deductible amount"
        )
    
    with col2:
        coinsurance = st.number_input(
            "Coinsurance Rate",
            min_value=0.0,
            max_value=1.0,
            value=0.40,
            step=0.05,
            format="%.2f",
            help="Coinsurance rate (e.g., 0.40 = 40%)"
        )
    
    with col3:
        oop_max = st.number_input(
            "Out-of-Pocket Maximum ($)",
            min_value=0.0,
            value=6500.0,
            step=100.0,
            format="%.2f",
            help="Annual out-of-pocket maximum"
        )
    
    # Advanced options (collapsible)
    with st.expander("⚙️ Advanced Options"):
        st.markdown("### Prior Accumulations")
        adv_col1, adv_col2 = st.columns(2)
        
        with adv_col1:
            deductible_met = st.number_input(
                "Deductible Already Met ($)",
                min_value=0.0,
                value=0.0,
                step=100.0,
                format="%.2f",
                help="Amount of deductible already accumulated"
            )
        
        with adv_col2:
            oop_accumulated = st.number_input(
                "OOP Already Accumulated ($)",
                min_value=0.0,
                value=0.0,
                step=100.0,
                format="%.2f",
                help="Amount of OOP already accumulated"
            )
        
        include_details = st.checkbox(
            "Include calculation details in output",
            value=False,
            help="Add columns showing deductible and coinsurance breakdown"
        )
    
    st.divider()
    
    # Calculate button
    st.header("4️⃣ Process Billing")
    
    if st.button("🔢 Calculate Billing", type="primary", use_container_width=True):
        if uploaded_file is None:
            st.error("⚠️ Please upload an Excel file first")
        else:
            try:
                # Process the file
                with st.spinner("Processing service data..."):
                    # Save uploaded file to temporary location
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        input_path = tmp_file.name
                    
                    # Parse the input file
                    parser = SpreadsheetParser()
                    services = parser.parse_file(input_path)
                    
                    if not services:
                        st.error("⚠️ No valid service records found in the uploaded file")
                        return
                    
                    # Extract rate schedule from the first service record
                    rate_schedule = parser.extract_rate_schedule(services)
                    
                    # Create insurance plan
                    insurance_plan = InsurancePlan(
                        name="Client Insurance Plan",
                        deductible=Decimal(str(deductible)),
                        coinsurance_rate=Decimal(str(coinsurance)),
                        oop_max=Decimal(str(oop_max)),
                        deductible_met=Decimal(str(deductible_met)),
                        oop_accumulated=Decimal(str(oop_accumulated))
                    )
                    
                    # Create client
                    # Get MRN from first service record
                    mrn = services[0].mrn if services and hasattr(services[0], 'mrn') and services[0].mrn else "UNKNOWN"
                    client = Client(
                        name=client_name if client_name else "Client",
                        mrn=mrn,
                        insurance_plan=insurance_plan
                    )
                    
                    # Calculate billing
                    calculator = RateCalculator(client, rate_schedule)
                    billing_items = calculator.calculate_all_services_combined(services)
                    
                    if not billing_items:
                        st.error("⚠️ No billable items generated from the service records")
                        return
                    
                    # Generate output file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as output_tmp:
                        output_path = output_tmp.name
                    
                    generator = BillingOutputGenerator()
                    result_path = generator.generate(
                        billing_items,
                        output_path,
                        include_details=include_details
                    )
                    
                    # Read the generated file
                    with open(result_path, "rb") as f:
                        output_data = f.read()
                
                # Display success message
                st.success("✅ Billing calculation completed successfully!")
                
                # Display summary statistics
                st.header("📈 Summary Statistics")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Services Processed", len(services))
                
                with col2:
                    st.metric("Billable Items", len(billing_items))
                
                with col3:
                    total_charges = sum(item.charge_amount for item in billing_items)
                    st.metric("Total Patient Responsibility", f"${total_charges:,.2f}")
                
                # Show additional details
                with st.expander("📋 Billing Details"):
                    st.markdown("### Billing Breakdown")
                    for i, item in enumerate(billing_items[:10], 1):  # Show first 10 items
                        st.text(f"{i}. {item.service_date} - {item.service_type}: ${item.charge_amount:.2f}")
                    
                    if len(billing_items) > 10:
                        st.text(f"... and {len(billing_items) - 10} more items")
                
                st.divider()
                
                # Download button
                st.header("5️⃣ Download Results")
                
                output_filename = f"billing_summary_{client_name.replace(' ', '_') if client_name else 'output'}.xlsx"
                
                st.download_button(
                    label="⬇️ Download Billing Summary",
                    data=output_data,
                    file_name=output_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                st.success("Click the button above to download your billing summary")
                
            except Exception as e:
                st.error(f"❌ Error processing file: {str(e)}")
                st.exception(e)
    
    # Footer
    st.divider()
    st.markdown("""
    ---
    **RALS - Rate and Ledger System** | 
    [GitHub Repository](https://github.com/phoenixglass/RALS) | 
    Version 1.0.0
    """)


if __name__ == "__main__":
    main()
