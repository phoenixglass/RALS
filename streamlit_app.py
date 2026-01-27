#!/usr/bin/env python3
"""
RALS Streamlit Web Application - Insurance Rate Calculator

Provides a web-based interface for processing service appointment data
and calculating client billing based on insurance plan parameters.
"""

import streamlit as st
import tempfile
from pathlib import Path
from decimal import Decimal
import traceback

from rals import __version__
from rals.models import InsurancePlan, Client, RateSchedule
from rals.parser import SpreadsheetParser
from rals.calculator import RateCalculator
from rals.output import generate_billing_report


def main():
    """Main Streamlit application."""
    
    # Page configuration
    st.set_page_config(
        page_title="RALS - Insurance Rate Calculator",
        page_icon="📊",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # Header
    st.title("📊 RALS Insurance Rate Calculator")
    st.markdown(f"*Version {__version__}*")
    st.markdown("---")
    
    # Description
    st.markdown("""
    ### Welcome to RALS
    
    This application calculates insurance billing based on service appointment data 
    and insurance plan parameters including deductibles, coinsurance, and out-of-pocket maximums.
    
    **Instructions:**
    1. Upload your Excel file containing service data
    2. Optionally enter a client name
    3. Configure insurance parameters (or use defaults)
    4. Click "Calculate Billing" to process
    5. Download the generated billing summary
    """)
    
    st.markdown("---")
    
    # File uploader
    st.subheader("📁 Upload Input File")
    uploaded_file = st.file_uploader(
        "Select Excel file with service data",
        type=["xlsx", "xls"],
        help="Upload an Excel spreadsheet containing service appointment data"
    )
    
    # Client name (optional)
    st.subheader("👤 Client Information")
    client_name = st.text_input(
        "Client Name (optional)",
        value="",
        help="Enter the client name. If left empty, it will default to 'Client [MRN]'"
    )
    
    # Insurance parameters
    st.subheader("💰 Insurance Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        deductible = st.number_input(
            "Deductible ($)",
            min_value=0.0,
            value=3272.00,
            step=100.0,
            format="%.2f",
            help="Annual deductible amount"
        )
        
        coinsurance = st.number_input(
            "Coinsurance Rate",
            min_value=0.0,
            max_value=1.0,
            value=0.40,
            step=0.05,
            format="%.2f",
            help="Patient responsibility after deductible (e.g., 0.40 = 40%)"
        )
    
    with col2:
        oop_max = st.number_input(
            "Out-of-Pocket Maximum ($)",
            min_value=0.0,
            value=6500.00,
            step=100.0,
            format="%.2f",
            help="Maximum out-of-pocket amount"
        )
    
    st.markdown("---")
    
    # Calculate button
    if st.button("🔄 Calculate Billing", type="primary", use_container_width=True):
        if uploaded_file is None:
            st.error("❌ Please upload an Excel file first.")
        else:
            try:
                # Show progress
                with st.spinner("Processing data..."):
                    # Save uploaded file to temporary location
                    tmp_file_path = None
                    output_path = None
                    
                    try:
                        # Create and save uploaded file to temporary location
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_file_path = tmp_file.name
                        
                        # Parse input data
                        st.info("📖 Parsing input file...")
                        spreadsheet_parser = SpreadsheetParser()
                        services = spreadsheet_parser.parse_file(tmp_file_path)
                        
                        if not services:
                            st.error("❌ No service records found in input file.")
                            return
                        
                        st.success(f"✅ Found {len(services)} service records")
                        
                        # Get MRN from first record
                        mrn = services[0].mrn
                        client_display_name = client_name or f"Client {mrn}"
                        
                        # Extract rate schedule from PPS comments
                        st.info("💵 Extracting rate schedule...")
                        rate_schedule = spreadsheet_parser.extract_rate_schedule(services)
                        
                        # Create insurance plan
                        insurance_plan = InsurancePlan(
                            name="Client Insurance",
                            deductible=Decimal(str(deductible)),
                            coinsurance_rate=Decimal(str(coinsurance)),
                            oop_max=Decimal(str(oop_max)),
                            deductible_met=Decimal("0.00"),
                            oop_accumulated=Decimal("0.00")
                        )
                        
                        # Create client
                        client = Client(
                            name=client_display_name,
                            mrn=mrn,
                            insurance_plan=insurance_plan
                        )
                        
                        # Calculate billing
                        st.info("🔢 Calculating billing...")
                        calculator = RateCalculator(client, rate_schedule)
                        billing_items = calculator.calculate_all_services(services)
                        
                        # Generate output file
                        st.info("📄 Generating output file...")
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as output_tmp:
                            output_path = output_tmp.name
                        
                        try:
                            generate_billing_report(billing_items, output_path, include_details=False)
                            
                            # Read the output file for download
                            with open(output_path, 'rb') as f:
                                output_data = f.read()
                        finally:
                            # Clean up output file
                            if output_path:
                                Path(output_path).unlink(missing_ok=True)
                        
                        # Display results
                        st.markdown("---")
                        st.subheader("✨ Results")
                        
                        # Calculate summary statistics
                        total_charges = sum(item.charge_amount for item in billing_items)
                        billable_items = sum(1 for item in billing_items if item.charge_amount > 0)
                        
                        # Display metrics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Services Processed", len(billing_items))
                        with col2:
                            st.metric("Billable Items", billable_items)
                        with col3:
                            st.metric("Total Patient Responsibility", f"${total_charges:,.2f}")
                        
                        st.success("✅ Billing calculation completed successfully!")
                        
                        # Download button
                        st.download_button(
                            label="📥 Download Billing Summary",
                            data=output_data,
                            file_name=f"billing_summary_{mrn}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
                        # Additional details
                        with st.expander("📊 View Calculation Details"):
                            st.markdown(f"""
                            **Client:** {client_display_name}  
                            **MRN:** {mrn}  
                            **Total Services:** {len(services)}  
                            **Billable Items:** {billable_items}  
                            **Total Charges:** ${total_charges:,.2f}
                            
                            **Insurance Plan:**
                            - Deductible: ${insurance_plan.deductible:,.2f}
                            - Coinsurance: {insurance_plan.coinsurance_rate * 100:.0f}%
                            - Out-of-Pocket Max: ${insurance_plan.oop_max:,.2f}
                            
                            **Rate Schedule:**
                            - IOP: ${rate_schedule.iop_rate:,.2f}
                            - Individual Therapy: ${rate_schedule.it_rate:,.2f}
                            - Family Therapy: ${rate_schedule.ft_rate:,.2f}
                            - Group: ${rate_schedule.group_rate:,.2f}
                            - Psych Eval: ${rate_schedule.psych_eval_rate:,.2f}
                            - Psych Follow-up: ${rate_schedule.psych_followup_rate:,.2f}
                            """)
                    
                    finally:
                        # Clean up temporary input file
                        if tmp_file_path:
                            Path(tmp_file_path).unlink(missing_ok=True)
                        
            except Exception as e:
                st.error(f"❌ Error processing file: {str(e)}")
                with st.expander("🔍 View Error Details"):
                    st.code(traceback.format_exc())
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: gray; font-size: 0.9em;'>
        <p>RALS - Rate and Ledger System</p>
        <p>For more information, visit the <a href='https://github.com/phoenixglass/RALS' target='_blank'>GitHub repository</a></p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
