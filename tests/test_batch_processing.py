"""Tests for batch processing functionality."""

import tempfile
from pathlib import Path
from decimal import Decimal
from datetime import date

from rals.parser import SpreadsheetParser
from rals.models import InsurancePlan, Client
from rals.calculator import RateCalculator
from rals.output import generate_billing_report


def test_csv_parsing():
    """Test that CSV files can be parsed correctly."""
    # Create a test CSV file
    csv_content = """GROUPFLD1,MRN,Date,Service,From,Location,PPS Comment,Provider,Supervisor,Status,Note Status,Physical Program,Financial Division,Funding,Comments
,12345,01/15/2026,Telemed: IOP,06:00 PM,W: Telehealth Group Room,"IOP $200 | IT $225 | $1000/$3000 deductible / $5000 OOP (combine) used as of 1/15 | 40% coinsurance",Provider A,Supervisor B,Pending,Missing Note,W-IOP,OP Wilton,Insurance Co,
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        csv_path = f.name
    
    try:
        parser = SpreadsheetParser()
        records = parser.parse_file(csv_path)
        
        assert len(records) == 1
        assert records[0].mrn == "12345"
        assert records[0].service_type == "Telemed: IOP"
        assert "IOP $200" in records[0].pps_comment
    finally:
        Path(csv_path).unlink()


def test_group_by_mrn():
    """Test grouping services by MRN."""
    csv_content = """GROUPFLD1,MRN,Date,Service,From,Location,PPS Comment,Provider,Supervisor,Status,Note Status,Physical Program,Financial Division,Funding,Comments
,12345,01/15/2026,Telemed: IOP,06:00 PM,Room A,"IOP $200",Provider A,Supervisor B,Pending,Missing Note,W-IOP,OP,Insurance Co,
,12345,01/16/2026,Outpatient 53+,02:00 PM,Room B,"IT $225",Provider A,Supervisor B,Pending,Missing Note,W-IOP,OP,Insurance Co,
,67890,01/15/2026,Telemed: IOP,06:00 PM,Room A,"IOP $214",Provider C,Supervisor D,Pending,Missing Note,W-IOP,OP,Insurance Co,
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        csv_path = f.name
    
    try:
        parser = SpreadsheetParser()
        records = parser.parse_file(csv_path)
        grouped = parser.group_by_mrn(records)
        
        assert len(grouped) == 2
        assert len(grouped["12345"]) == 2
        assert len(grouped["67890"]) == 1
    finally:
        Path(csv_path).unlink()


def test_insurance_param_extraction():
    """Test extraction of insurance parameters from PPS comments."""
    parser = SpreadsheetParser()
    
    # Test with deductible and OOP
    pps1 = "$1,732.50/$3,500 deductible / $18,200 OOP (combine) used as of 1/26 | 50% coinsurance"
    ded_total, ded_met, oop_max, oop_used, coins_rate = parser.extract_insurance_params_from_pps(pps1)
    
    assert ded_total == Decimal("3500")
    assert ded_met == Decimal("1732.50")
    assert oop_max == Decimal("18200")
    assert oop_used is None  # (combine) format doesn't show used amount
    assert coins_rate == Decimal("0.50")
    
    # Test with OOP only (no deductible)
    pps2 = "$4,053.5/$17,000 OOP used as of 1/23"
    ded_total, ded_met, oop_max, oop_used, coins_rate = parser.extract_insurance_params_from_pps(pps2)
    
    assert ded_total is None
    assert ded_met is None
    assert oop_max == Decimal("17000")
    assert oop_used == Decimal("4053.5")
    assert coins_rate is None


def test_batch_processing():
    """Test complete batch processing workflow."""
    csv_content = """GROUPFLD1,MRN,Date,Service,From,Location,PPS Comment,Provider,Supervisor,Status,Note Status,Physical Program,Financial Division,Funding,Comments
,12345,01/15/2026,Telemed: IOP,06:00 PM,Room A,"IOP $200 | IT $225 | $1000/$3000 deductible / $5000 OOP (combine) used as of 1/15 | 40% coinsurance",Provider A,Supervisor B,Pending,Missing Note,W-IOP,OP,Insurance Co,
,12345,01/16/2026,Outpatient 53+,02:00 PM,Room B,"IOP $200 | IT $225 | $1000/$3000 deductible / $5000 OOP (combine) used as of 1/15 | 40% coinsurance",Provider A,Supervisor B,Pending,Missing Note,W-IOP,OP,Insurance Co,
,67890,01/15/2026,Telemed: IOP,06:00 PM,Room A,"IOP $214 | IT $158 | $2000/$5000 deductible / $8000 OOP (combine) used as of 1/15 | 30% coinsurance",Provider C,Supervisor D,Pending,Missing Note,W-IOP,OP,Insurance Co,
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        csv_path = f.name
    
    try:
        # Parse and group
        parser = SpreadsheetParser()
        all_services = parser.parse_file(csv_path)
        services_by_mrn = parser.group_by_mrn(all_services)
        
        assert len(services_by_mrn) == 2
        
        # Process each client
        all_billing_items = []
        for mrn, services in services_by_mrn.items():
            rate_schedule = parser.extract_rate_schedule(services)
            pps_comment = next((s.pps_comment for s in services if s.pps_comment), "")
            
            ded_total, ded_met, oop_max, oop_used, coinsurance_rate = \
                parser.extract_insurance_params_from_pps(pps_comment)
            
            # Use defaults for missing values
            if ded_total is None:
                ded_total = Decimal("0.00")
            if ded_met is None:
                ded_met = Decimal("0.00")
            if oop_max is None:
                oop_max = Decimal("999999.00")
            if oop_used is None:
                oop_used = ded_met
            if coinsurance_rate is None:
                coinsurance_rate = Decimal("0.00")
            
            insurance_plan = InsurancePlan(
                name=f"Insurance for {mrn}",
                deductible=ded_total,
                coinsurance_rate=coinsurance_rate,
                oop_max=oop_max,
                deductible_met=ded_met,
                oop_accumulated=oop_used
            )
            
            client = Client(
                name=f"Client {mrn}",
                mrn=mrn,
                insurance_plan=insurance_plan
            )
            
            calculator = RateCalculator(client, rate_schedule)
            billing_items = calculator.calculate_all_services(services)
            all_billing_items.extend(billing_items)
        
        # Should have billing items from both clients
        assert len(all_billing_items) > 0
        
        # Generate output file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as output_f:
            output_path = output_f.name
        
        try:
            result_path = generate_billing_report(
                all_billing_items,
                output_path,
                include_details=False,
                include_client_names=False
            )
            
            assert Path(result_path).exists()
        finally:
            Path(output_path).unlink(missing_ok=True)
    
    finally:
        Path(csv_path).unlink()


if __name__ == "__main__":
    test_csv_parsing()
    test_group_by_mrn()
    test_insurance_param_extraction()
    test_batch_processing()
    print("All batch processing tests passed!")
