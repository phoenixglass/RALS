#!/usr/bin/env python3
"""
RALS Streamlit Web Application - Batch Insurance Rate Calculator

Provides a web-based interface for batch processing of multiple clients
from CSV or Excel files. Insurance parameters are automatically extracted
from PPS comment fields.
"""

import streamlit as st
import tempfile
from pathlib import Path
from decimal import Decimal
import traceback
from collections import defaultdict

from rals import __version__
from rals.models import InsurancePlan, Client, RateSchedule
from rals.parser import SpreadsheetParser
from rals.calculator import RateCalculator
from rals.output import generate_billing_report


def main():
    """Main Streamlit application."""
    
    # Page configuration
    st.set_page_config(
        page_title="RALS - Batch Insurance Rate Calculator",
        page_icon="📊",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # Header
    st.title("📊 RALS Batch Insurance Rate Calculator")
    st.markdown(f"*Version {__version__}*")
    st.markdown("---")
    
    # File uploader
    st.subheader("📁 Upload Input File")
    uploaded_file = st.file_uploader(
        "Select CSV or Excel file with service data for multiple clients",
        type=["csv", "xlsx", "xls"],
        help="Upload a file containing service appointment data with PPS comments for multiple clients"
    )
    
    # Client name privacy toggle for HIPAA compliance
    include_client_names = st.checkbox(
        "Include client names in output",
        value=False,  # Default unchecked for web app (HIPAA safety)
        help="⚠️ IMPORTANT: For HIPAA compliance in web deployments, leave this UNCHECKED. "
             "Client names should only be included when processing files locally on a secure desktop."
    )
    
    if include_client_names:
        st.warning("⚠️ **HIPAA Warning**: You have enabled client names in the output. "
                  "Ensure you are processing this file on a secure, local device and not uploading "
                  "it to any cloud or shared services.")
    
    st.markdown("---")
    
    # Calculate button
    if st.button("🔄 Calculate Billing", type="primary", use_container_width=True):
        if uploaded_file is None:
            st.error("❌ Please upload a file first.")
        else:
            try:
                # Show progress
                with st.spinner("Processing data..."):
                    # Save uploaded file to temporary location
                    tmp_file_path = None
                    output_path = None
                    
                    try:
                        # Create and save uploaded file to temporary location
                        suffix = Path(uploaded_file.name).suffix
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_file_path = tmp_file.name
                        
                        # Parse input data
                        st.info("📖 Parsing input file...")
                        spreadsheet_parser = SpreadsheetParser()
                        all_services = spreadsheet_parser.parse_file(tmp_file_path)
                        
                        if not all_services:
                            st.error("❌ No service records found in input file.")
                            return
                        
                        # Group services by MRN
                        st.info("👥 Grouping services by client (MRN)...")
                        services_by_mrn = spreadsheet_parser.group_by_mrn(all_services)
                        
                        st.success(f"✅ Found {len(services_by_mrn)} clients with {len(all_services)} total service records")
                        
                        # Process each client
                        all_billing_items = []
                        client_summaries = []
                        
                        for mrn, services in services_by_mrn.items():
                            st.info(f"💵 Processing client MRN {mrn}...")
                            
                            # Extract rate schedule from first service with PPS comment
                            rate_schedule = spreadsheet_parser.extract_rate_schedule(services)
                            
                            # Extract insurance parameters from PPS comment
                            # Find the first service with a PPS comment
                            pps_comment = next((s.pps_comment for s in services if s.pps_comment), "")
                            
                            if not pps_comment:
                                st.warning(f"⚠️ No PPS comment found for MRN {mrn}, using defaults")
                                ded_total = Decimal("0.00")
                                ded_met = Decimal("0.00")
                                oop_max = Decimal("999999.00")
                                oop_used = Decimal("0.00")
                                coinsurance_rate = Decimal("0.00")
                            else:
                                # Parse insurance parameters from PPS comment
                                ded_total, ded_met, oop_max, oop_used, coinsurance_rate = \
                                    spreadsheet_parser.extract_insurance_params_from_pps(pps_comment)
                                
                                # Use defaults for any missing values
                                if ded_total is None:
                                    ded_total = Decimal("0.00")
                                if ded_met is None:
                                    ded_met = Decimal("0.00")
                                if oop_max is None:
                                    oop_max = Decimal("999999.00")
                                if oop_used is None:
                                    # If we have deductible met, use that as OOP starting point
                                    oop_used = ded_met if ded_met else Decimal("0.00")
                                if coinsurance_rate is None:
                                    coinsurance_rate = Decimal("0.00")
                            
                            # Create insurance plan with parsed parameters
                            insurance_plan = InsurancePlan(
                                name=f"Insurance for {mrn}",
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
                            
                            # Calculate billing
                            calculator = RateCalculator(client, rate_schedule)
                            billing_items = calculator.calculate_all_services(services)
                            
                            all_billing_items.extend(billing_items)
                            
                            # Track summary for this client
                            total_charges = sum(item.charge_amount for item in billing_items)
                            client_summaries.append({
                                'mrn': mrn,
                                'services': len(services),
                                'billable': len(billing_items),
                                'total_charges': total_charges
                            })
                        
                        # Generate output file
                        st.info("📄 Generating output file...")
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as output_tmp:
                            output_path = output_tmp.name
                        
                        try:
                            generate_billing_report(
                                all_billing_items, 
                                output_path, 
                                include_details=False,
                                include_client_names=include_client_names
                            )
                            
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
                        
                        # Calculate overall summary statistics
                        total_services = len(all_services)
                        total_clients = len(services_by_mrn)
                        total_billable = sum(s['billable'] for s in client_summaries)
                        total_charges = sum(s['total_charges'] for s in client_summaries)
                        
                        # Display overall metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Clients Processed", total_clients)
                        with col2:
                            st.metric("Total Services", total_services)
                        with col3:
                            st.metric("Billable Items", total_billable)
                        with col4:
                            st.metric("Total Charges", f"${total_charges:,.2f}")
                        
                        st.success("✅ Batch billing calculation completed successfully!")
                        
                        # Download button
                        st.download_button(
                            label="📥 Download Billing Summary",
                            data=output_data,
                            file_name=f"billing_summary_batch.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
                        # Per-client details
                        with st.expander("📊 View Per-Client Details"):
                            for summary in client_summaries:
                                st.markdown(f"""
                                **MRN {summary['mrn']}:**  
                                - Total Services: {summary['services']}  
                                - Billable Items: {summary['billable']}  
                                - Total Charges: ${summary['total_charges']:,.2f}
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
