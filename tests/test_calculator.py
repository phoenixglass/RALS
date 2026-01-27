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


class TestCopayHandling(unittest.TestCase):
    """Test cases for copay handling.

    Copay rules:
    - Copay does NOT count toward deductible
    - Copay DOES count toward OOP
    """

    def test_copay_does_not_count_toward_deductible(self):
        """Test that copay payments do not reduce the deductible."""
        rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
            it_rate=Decimal("260.00"),
        )

        insurance_plan = InsurancePlan(
            name="Copay Plan",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),  # Ignored when copay is set
            oop_max=Decimal("5000.00"),
            copay=Decimal("50.00")  # $50 copay per visit
        )

        client = Client(
            name="Test Client",
            mrn="12345",
            insurance_plan=insurance_plan
        )

        calculator = RateCalculator(client, rate_schedule)

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

        # Patient should pay copay amount, NOT the full rate
        self.assertEqual(result.charge_amount, Decimal("50.00"))
        # Deductible should NOT be affected by copay
        self.assertEqual(result.applied_to_deductible, Decimal("0.00"))
        # The deductible remaining should be unchanged (still full $1000)
        self.assertEqual(insurance_plan.remaining_deductible, Decimal("1000.00"))

    def test_copay_counts_toward_oop(self):
        """Test that copay payments DO count toward OOP max."""
        rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
        )

        insurance_plan = InsurancePlan(
            name="Copay Plan",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("200.00"),  # Low OOP max for testing
            copay=Decimal("50.00")
        )

        client = Client(
            name="Test Client",
            mrn="12345",
            insurance_plan=insurance_plan
        )

        calculator = RateCalculator(client, rate_schedule)

        # First service - should pay full copay
        service1 = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="Test",
            pps_comment="",
            provider="Test"
        )
        result1 = calculator.calculate_patient_responsibility(service1)
        self.assertEqual(result1.charge_amount, Decimal("50.00"))
        self.assertEqual(insurance_plan.oop_accumulated, Decimal("50.00"))

        # After 4 services at $50 each, OOP should be $200 (max)
        for i in range(3):
            service = ServiceRecord(
                mrn="12345",
                service_date=date(2026, 1, 2 + i),
                service_type="IOP-Wilton",
                duration_mins=180,
                location="Test",
                pps_comment="",
                provider="Test"
            )
            calculator.calculate_patient_responsibility(service)

        self.assertEqual(insurance_plan.oop_accumulated, Decimal("200.00"))
        self.assertTrue(insurance_plan.oop_max_reached)

        # Next service should be $0 (OOP max reached)
        service5 = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 10),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="Test",
            pps_comment="",
            provider="Test"
        )
        result5 = calculator.calculate_patient_responsibility(service5)
        self.assertEqual(result5.charge_amount, Decimal("0.00"))

    def test_copay_capped_at_remaining_oop(self):
        """Test that copay is capped at remaining OOP when near max."""
        rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
        )

        insurance_plan = InsurancePlan(
            name="Copay Plan",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("100.00"),
            oop_accumulated=Decimal("75.00"),  # Only $25 remaining
            copay=Decimal("50.00")
        )

        client = Client(
            name="Test Client",
            mrn="12345",
            insurance_plan=insurance_plan
        )

        calculator = RateCalculator(client, rate_schedule)

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

        # Copay should be capped at $25 (remaining OOP), not full $50
        self.assertEqual(result.charge_amount, Decimal("25.00"))


class TestSelfPayVirtualServices(unittest.TestCase):
    """Test cases for self-pay virtual services (no virtual benefits).

    When PPS comment indicates "SP rates for virtual" or similar,
    the client pays self-pay rates and these do NOT count toward
    deductible or OOP.
    """

    def test_self_pay_virtual_does_not_count_toward_deductible(self):
        """Test that self-pay virtual charges don't reduce deductible."""
        rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
        )

        insurance_plan = InsurancePlan(
            name="Test Plan",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("5000.00"),
        )

        client = Client(
            name="Test Client",
            mrn="12345",
            insurance_plan=insurance_plan
        )

        calculator = RateCalculator(client, rate_schedule)

        # Telehealth service with "SP rates for virtual" in PPS comment
        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="Telemed: IOP",  # Telehealth service
            duration_mins=180,
            location="Telehealth",
            pps_comment="IOP $575 | (SP rates for virtual) | IT $260",  # Self-pay for virtual
            provider="Test"
        )

        result = calculator.calculate_patient_responsibility(service)

        # Should use self-pay rate for IOP ($295), not insurance rate ($575)
        self.assertEqual(result.charge_amount, Decimal("295.00"))
        self.assertTrue(result.is_self_pay)
        # Deductible should NOT be affected
        self.assertEqual(result.applied_to_deductible, Decimal("0.00"))
        self.assertEqual(insurance_plan.deductible_met, Decimal("0.00"))

    def test_self_pay_virtual_does_not_count_toward_oop(self):
        """Test that self-pay virtual charges don't count toward OOP."""
        rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
        )

        insurance_plan = InsurancePlan(
            name="Test Plan",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("5000.00"),
        )

        client = Client(
            name="Test Client",
            mrn="12345",
            insurance_plan=insurance_plan
        )

        calculator = RateCalculator(client, rate_schedule)

        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="Telemed: IOP",
            duration_mins=180,
            location="Telehealth",
            pps_comment="(Self Pay for virtual)",
            provider="Test"
        )

        result = calculator.calculate_patient_responsibility(service)

        # OOP should NOT be affected
        self.assertEqual(insurance_plan.oop_accumulated, Decimal("0.00"))

    def test_self_pay_virtual_uses_correct_rates(self):
        """Test that self-pay virtual uses the defined self-pay rates."""
        rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
            it_rate=Decimal("260.00"),
            ft_rate=Decimal("200.00"),
            group_rate=Decimal("125.00"),
            psych_eval_rate=Decimal("350.00"),
            psych_followup_rate=Decimal("275.00"),
        )

        insurance_plan = InsurancePlan(
            name="Test Plan",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("5000.00"),
        )

        # Expected self-pay rates from requirements:
        # Assessment $450 | IOP $295 | Group $175 | IT $175 | FT $275 |
        # Psych Eval $675 | Psych f/u $200 | MAT $200
        test_cases = [
            ("Telemed: IOP", Decimal("295.00")),  # IOP SP rate
            ("Telemed: Outpatient 53+", Decimal("175.00")),  # IT SP rate
            ("Telemed: Group Therapy", Decimal("175.00")),  # Group SP rate
            ("Telemed: Family Session", Decimal("275.00")),  # FT SP rate
        ]

        for service_type, expected_rate in test_cases:
            client = Client(
                name="Test Client",
                mrn="12345",
                insurance_plan=InsurancePlan(
                    name="Test Plan",
                    deductible=Decimal("1000.00"),
                    coinsurance_rate=Decimal("0.20"),
                    oop_max=Decimal("5000.00"),
                )
            )

            calculator = RateCalculator(client, rate_schedule)

            service = ServiceRecord(
                mrn="12345",
                service_date=date(2026, 1, 1),
                service_type=service_type,
                duration_mins=60,
                location="Telehealth",
                pps_comment="(SP rates for virtual)",
                provider="Test"
            )

            result = calculator.calculate_patient_responsibility(service)
            self.assertEqual(
                result.charge_amount,
                expected_rate,
                f"Expected {expected_rate} for {service_type}, got {result.charge_amount}"
            )


class TestIOPBundling(unittest.TestCase):
    """Test cases for IOP bundling rules.

    When PPS comment includes "In Network:" and Physical Program includes "IOP",
    IT and FT services are bundled with IOP and should not be charged separately.
    Group therapy is NOT bundled (different level of care).
    """

    def test_it_bundled_with_iop_when_in_network(self):
        """Test that IT is bundled (no charge) when In Network + IOP."""
        rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
            it_rate=Decimal("260.00"),
        )

        insurance_plan = InsurancePlan(
            name="Test Plan",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("5000.00"),
        )

        client = Client(
            name="Test Client",
            mrn="12345",
            insurance_plan=insurance_plan
        )

        calculator = RateCalculator(client, rate_schedule)

        # IT service with "In Network:" in PPS and "IOP" in physical_proc
        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="Outpatient 53+",  # IT service
            duration_mins=60,
            location="Test",
            pps_comment="In Network: IOP $575 | IT $260",
            provider="Test",
            physical_proc="IOP"  # Client is in IOP program
        )

        result = calculator.calculate_patient_responsibility(service)

        # IT should be bundled - $0 charge
        self.assertEqual(result.charge_amount, Decimal("0.00"))
        self.assertTrue(result.is_bundled)

    def test_ft_bundled_with_iop_when_in_network(self):
        """Test that FT is bundled (no charge) when In Network + IOP."""
        rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
            ft_rate=Decimal("200.00"),
        )

        insurance_plan = InsurancePlan(
            name="Test Plan",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("5000.00"),
        )

        client = Client(
            name="Test Client",
            mrn="12345",
            insurance_plan=insurance_plan
        )

        calculator = RateCalculator(client, rate_schedule)

        # FT service with "In Network:" in PPS and "IOP" in physical_proc
        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="Family Session with Client 26+ minutes",
            duration_mins=60,
            location="Test",
            pps_comment="In Network: IOP $575 | FT $200",
            provider="Test",
            physical_proc="IOP"
        )

        result = calculator.calculate_patient_responsibility(service)

        # FT should be bundled - $0 charge
        self.assertEqual(result.charge_amount, Decimal("0.00"))
        self.assertTrue(result.is_bundled)

    def test_group_not_bundled_with_iop(self):
        """Test that Group therapy is NOT bundled with IOP (different LOC)."""
        rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
            group_rate=Decimal("125.00"),
        )

        insurance_plan = InsurancePlan(
            name="Test Plan",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("5000.00"),
        )

        client = Client(
            name="Test Client",
            mrn="12345",
            insurance_plan=insurance_plan
        )

        calculator = RateCalculator(client, rate_schedule)

        # Group service with "In Network:" in PPS and "IOP" in physical_proc
        # Group is OUTPATIENT level of care, IOP is INTENSIVE OUTPATIENT (higher LOC)
        # Therefore, Group should NOT be bundled
        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="Outpatient Group (75-90 minutes)",
            duration_mins=90,
            location="Test",
            pps_comment="In Network: IOP $575 | Group $125",
            provider="Test",
            physical_proc="IOP"
        )

        result = calculator.calculate_patient_responsibility(service)

        # Group should NOT be bundled - should be charged
        self.assertFalse(result.is_bundled)
        self.assertGreater(result.charge_amount, Decimal("0.00"))
        # Under $1000 deductible, full rate applies = $125
        self.assertEqual(result.charge_amount, Decimal("125.00"))

    def test_it_not_bundled_when_not_in_network(self):
        """Test that IT is NOT bundled when not In Network."""
        rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
            it_rate=Decimal("260.00"),
        )

        insurance_plan = InsurancePlan(
            name="Test Plan",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("5000.00"),
        )

        client = Client(
            name="Test Client",
            mrn="12345",
            insurance_plan=insurance_plan
        )

        calculator = RateCalculator(client, rate_schedule)

        # IT service WITHOUT "In Network:" in PPS comment
        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="Outpatient 53+",
            duration_mins=60,
            location="Test",
            pps_comment="IOP $575 | IT $260",  # No "In Network:"
            provider="Test",
            physical_proc="IOP"
        )

        result = calculator.calculate_patient_responsibility(service)

        # IT should NOT be bundled
        self.assertFalse(result.is_bundled)
        self.assertEqual(result.charge_amount, Decimal("260.00"))

    def test_it_not_bundled_when_not_iop_program(self):
        """Test that IT is NOT bundled when client is not in IOP program."""
        rate_schedule = RateSchedule(
            iop_rate=Decimal("575.00"),
            it_rate=Decimal("260.00"),
        )

        insurance_plan = InsurancePlan(
            name="Test Plan",
            deductible=Decimal("1000.00"),
            coinsurance_rate=Decimal("0.20"),
            oop_max=Decimal("5000.00"),
        )

        client = Client(
            name="Test Client",
            mrn="12345",
            insurance_plan=insurance_plan
        )

        calculator = RateCalculator(client, rate_schedule)

        # IT service with "In Network:" but physical_proc is NOT "IOP"
        service = ServiceRecord(
            mrn="12345",
            service_date=date(2026, 1, 1),
            service_type="Outpatient 53+",
            duration_mins=60,
            location="Test",
            pps_comment="In Network: IT $260",
            provider="Test",
            physical_proc="Outpatient"  # NOT IOP
        )

        result = calculator.calculate_patient_responsibility(service)

        # IT should NOT be bundled
        self.assertFalse(result.is_bundled)
        self.assertEqual(result.charge_amount, Decimal("260.00"))


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
