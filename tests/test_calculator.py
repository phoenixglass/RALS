"""Tests for the rate calculator."""

import unittest
from datetime import date
from decimal import Decimal

from rals.models import InsurancePlan, Client, RateSchedule, ServiceRecord
from rals.calculator import RateCalculator, parse_rates_from_pps_comment


class TestRateCalculator(unittest.TestCase):
    """Test cases for RateCalculator."""

    def setUp(self):
        """Set up test fixtures."""
        self.rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
            group_rate=Decimal("125.00"),
            it_rate=Decimal("260.00"),
            ft_rate=Decimal("200.00"),
            psych_eval_rate=Decimal("350.00"),
            psych_followup_rate=Decimal("275.00"),
        )

        self.insurance_plan = InsurancePlan(
            name="Test Insurance",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("2000.00"),
        )

        self.client = Client(
            name="Test Client",
            mrn="12345",
            insurance_plan=self.insurance_plan
        )

    def test_full_rate_applied_to_deductible(self):
        """Test that full rate is charged when under deductible."""
        calculator = RateCalculator(self.client, self.rate_schedule)

        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="Test",
            pps_comment="",
            provider="Test"
        )

        result = calculator.calculate_patient_responsibility(service)

        # Full $575 should apply to deductible since it's under $1000
        self.assertEqual(result.charge_amount, Decimal("575.00"))
        self.assertEqual(result.applied_to_deductible, Decimal("575.00"))
        self.assertEqual(result.coinsurance_amount, Decimal("0.00"))

    def test_partial_deductible_then_coinsurance(self):
        """Test split between deductible and coinsurance."""
        # Pre-set deductible to $800 met
        self.insurance_plan.deductible_met = Decimal("800.00")

        calculator = RateCalculator(self.client, self.rate_schedule)

        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="IOP-Wilton",  # $575 rate
            duration_mins=180,
            location="Test",
            pps_comment="",
            provider="Test"
        )

        result = calculator.calculate_patient_responsibility(service)

        # $200 should go to deductible (remaining), $375 subject to 20% coinsurance = $75
        self.assertEqual(result.applied_to_deductible, Decimal("200.00"))
        self.assertEqual(result.coinsurance_amount, Decimal("75.00"))
        self.assertEqual(result.charge_amount, Decimal("275.00"))

    def test_coinsurance_only_after_deductible_met(self):
        """Test coinsurance when deductible already met."""
        # Deductible fully met
        self.insurance_plan.deductible_met = Decimal("1000.00")

        calculator = RateCalculator(self.client, self.rate_schedule)

        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="IOP-Wilton",  # $575 rate
            duration_mins=180,
            location="Test",
            pps_comment="",
            provider="Test"
        )

        result = calculator.calculate_patient_responsibility(service)

        # 20% of $575 = $115
        self.assertEqual(result.applied_to_deductible, Decimal("0.00"))
        self.assertEqual(result.coinsurance_amount, Decimal("115.00"))
        self.assertEqual(result.charge_amount, Decimal("115.00"))

    def test_oop_max_caps_charges(self):
        """Test that OOP max caps patient charges."""
        # Deductible met, OOP near max
        self.insurance_plan.deductible_met = Decimal("1000.00")
        self.insurance_plan.oop_accumulated = Decimal("1950.00")  # Only $50 remaining

        calculator = RateCalculator(self.client, self.rate_schedule)

        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="IOP-Wilton",  # $575 rate, 20% = $115 normally
            duration_mins=180,
            location="Test",
            pps_comment="",
            provider="Test"
        )

        result = calculator.calculate_patient_responsibility(service)

        # Should be capped at $50 (remaining OOP)
        self.assertEqual(result.charge_amount, Decimal("50.00"))

    def test_zero_charge_after_oop_max(self):
        """Test zero charge when OOP max already reached."""
        self.insurance_plan.deductible_met = Decimal("1000.00")
        self.insurance_plan.oop_accumulated = Decimal("2000.00")  # Max reached

        calculator = RateCalculator(self.client, self.rate_schedule)

        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="Test",
            pps_comment="",
            provider="Test"
        )

        result = calculator.calculate_patient_responsibility(service)

        self.assertEqual(result.charge_amount, Decimal("0.00"))

    def test_service_type_rate_mapping(self):
        """Test correct rate is selected for different service types."""
        calculator = RateCalculator(self.client, self.rate_schedule)

        test_cases = [
            ("IOP-Wilton", Decimal("575.00")),
            ("Outpatient 53+", Decimal("260.00")),  # Maps to IT
            ("Telemed: Psych", Decimal("275.00")),  # Maps to psych followup
            ("Group Therapy", Decimal("125.00")),
        ]

        for service_type, expected_rate in test_cases:
            # Reset plan
            self.insurance_plan.reset()
            self.client = Client(
                name="Test Client",
                mrn="12345",
                insurance_plan=self.insurance_plan
            )
            calculator = RateCalculator(self.client, self.rate_schedule)

            service = ServiceRecord(
                mrn="12345",
                service_date=date(2026, 1, 1),
                service_type=service_type,
                duration_mins=60,
                location="Test",
                pps_comment="",
                provider="Test"
            )

            result = calculator.calculate_patient_responsibility(service)
            self.assertEqual(
                result.full_rate,
                expected_rate,
                f"Expected {expected_rate} for {service_type}, got {result.full_rate}"
            )


class TestParseRatesFromPPSComment(unittest.TestCase):
    """Test cases for parsing rates from PPS Comment."""

    def test_parse_standard_format(self):
        """Test parsing standard PPS comment format."""
        comment = "IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275"

        schedule = parse_rates_from_pps_comment(comment)

        self.assertEqual(schedule.iop_rate, Decimal("575"))
        self.assertEqual(schedule.group_rate, Decimal("125"))
        self.assertEqual(schedule.it_rate, Decimal("260"))
        self.assertEqual(schedule.ft_rate, Decimal("200"))
        self.assertEqual(schedule.psych_eval_rate, Decimal("350"))
        self.assertEqual(schedule.psych_followup_rate, Decimal("275"))

    def test_parse_full_pps_comment_with_location_and_provider(self):
        """Test parsing full PPS comment format with location prefix and provider suffix."""
        comment = "W: Group Room IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275 | MAT $1: Silfen, Jane"

        schedule = parse_rates_from_pps_comment(comment)

        self.assertEqual(schedule.iop_rate, Decimal("575"))
        self.assertEqual(schedule.group_rate, Decimal("125"))
        self.assertEqual(schedule.it_rate, Decimal("260"))
        self.assertEqual(schedule.ft_rate, Decimal("200"))
        self.assertEqual(schedule.psych_eval_rate, Decimal("350"))
        self.assertEqual(schedule.psych_followup_rate, Decimal("275"))

    def test_parse_ignores_small_amounts(self):
        """Test that small amounts like MAT $1 are ignored."""
        comment = "IOP $575 | MAT $1 | IT $260"

        schedule = parse_rates_from_pps_comment(comment)

        self.assertEqual(schedule.iop_rate, Decimal("575"))
        self.assertEqual(schedule.it_rate, Decimal("260"))

    def test_parse_with_commas(self):
        """Test parsing amounts with comma separators."""
        comment = "IOP $1,575 | IT $1,260"

        schedule = parse_rates_from_pps_comment(comment)

        self.assertEqual(schedule.iop_rate, Decimal("1575"))
        self.assertEqual(schedule.it_rate, Decimal("1260"))

    def test_parse_partial_comment(self):
        """Test parsing comment with only some rates."""
        comment = "IOP $575 | IT $260"

        schedule = parse_rates_from_pps_comment(comment)

        self.assertEqual(schedule.iop_rate, Decimal("575"))
        self.assertEqual(schedule.it_rate, Decimal("260"))
        self.assertEqual(schedule.group_rate, Decimal("0"))  # Not specified

    def test_parse_with_decimals(self):
        """Test parsing amounts with decimal places."""
        comment = "IOP $575.00 | IT $260.50"

        schedule = parse_rates_from_pps_comment(comment)

        self.assertEqual(schedule.iop_rate, Decimal("575.00"))
        self.assertEqual(schedule.it_rate, Decimal("260.50"))

    def test_parse_psych_followup_variations(self):
        """Test parsing various psych follow-up formats."""
        # Test "Psych flu"
        comment1 = "Psych flu $275"
        schedule1 = parse_rates_from_pps_comment(comment1)
        self.assertEqual(schedule1.psych_followup_rate, Decimal("275"))

        # Test "Psych f/u"
        comment2 = "Psych f/u $275"
        schedule2 = parse_rates_from_pps_comment(comment2)
        self.assertEqual(schedule2.psych_followup_rate, Decimal("275"))

    def test_parse_empty_comment(self):
        """Test parsing empty or None comment."""
        schedule = parse_rates_from_pps_comment("")
        self.assertEqual(schedule.iop_rate, Decimal("0"))

        schedule2 = parse_rates_from_pps_comment(None)
        self.assertEqual(schedule2.iop_rate, Decimal("0"))

    def test_parse_real_world_example(self):
        """Test parsing a real-world PPS comment from the spreadsheet."""
        comment = "W: Group Room IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275 | MAT $1: Tamburri, Cindy  Wu, Jana"

        schedule = parse_rates_from_pps_comment(comment)

        # Should correctly extract all rates
        self.assertEqual(schedule.iop_rate, Decimal("575"))
        self.assertEqual(schedule.group_rate, Decimal("125"))
        self.assertEqual(schedule.it_rate, Decimal("260"))
        self.assertEqual(schedule.ft_rate, Decimal("200"))
        self.assertEqual(schedule.psych_eval_rate, Decimal("350"))
        self.assertEqual(schedule.psych_followup_rate, Decimal("275"))


class TestInsurancePlan(unittest.TestCase):
    """Test cases for InsurancePlan model."""

    def test_remaining_deductible(self):
        """Test remaining deductible calculation."""
        plan = InsurancePlan(
            name="Test",
            deductible=Decimal("1000"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("5000"),
            deductible_met=Decimal("750")
        )

        self.assertEqual(plan.remaining_deductible, Decimal("250"))

    def test_deductible_satisfied(self):
        """Test deductible satisfied flag."""
        plan = InsurancePlan(
            name="Test",
            deductible=Decimal("1000"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("5000"),
            deductible_met=Decimal("1000")
        )

        self.assertTrue(plan.deductible_satisfied)

    def test_reset(self):
        """Test plan reset for new year."""
        plan = InsurancePlan(
            name="Test",
            deductible=Decimal("1000"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("5000"),
            deductible_met=Decimal("800"),
            oop_accumulated=Decimal("1200")
        )

        plan.reset()

        self.assertEqual(plan.deductible_met, Decimal("0"))
        self.assertEqual(plan.oop_accumulated, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
