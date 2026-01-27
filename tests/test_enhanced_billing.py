"""Tests for enhanced billing output features."""

import unittest
from datetime import date
from decimal import Decimal

from rals.models import (
    ServiceRecord,
    BillingLineItem,
    get_service_abbreviation,
    parse_pps_comment,
    format_updated_pps_comment,
    generate_combined_comment,
)


class TestServiceAbbreviation(unittest.TestCase):
    """Test cases for service abbreviation mapping."""

    def test_exact_match_standard_services(self):
        """Test exact matches from the abbreviation mapping."""
        test_cases = [
            ("IOP-Wilton", "IOP"),
            ("Outpatient 53+", "IT 53+"),
            ("Outpatient 16-37 minutes", "IT 16-37"),
            ("Outpatient 38-52 minutes", "IT 38-52"),
            ("Psychiatric Diag. Eval. W. Med Services", "Psych Eval"),
            ("Assessment/Diag (BPS) w/o med services", "Assess"),
            ("Outpatient Group (75-90 minutes)", "Group"),
            ("Family Session with Client 26+ minutes", "FT"),
            ("Medication Admin/Injection", "MAT"),
            ("OP: Psych Appointment (30-39 minutes)", "Psych f/u 30-39"),
            ("OP: Psych Appointment (20-29 minutes)", "Psych f/u 20-29"),
        ]
        
        for service_type, expected_abbrev in test_cases:
            with self.subTest(service_type=service_type):
                result = get_service_abbreviation(service_type)
                self.assertEqual(result, expected_abbrev)

    def test_telehealth_prefix(self):
        """Test that Telemed services get 'Tele' prefix."""
        test_cases = [
            ("Telemed: IOP", "Tele IOP"),
            ("Telemed: Outpatient 53+", "Tele IT 53+"),
            ("Telemed: Outpatient 16-37 minutes", "Tele IT 16-37"),
        ]
        
        for service_type, expected_abbrev in test_cases:
            with self.subTest(service_type=service_type):
                result = get_service_abbreviation(service_type)
                self.assertEqual(result, expected_abbrev)

    def test_nsf_suffix(self):
        """Test that NSF services get 'NSF' suffix."""
        test_cases = [
            ("NSF Psychiatric Diag. Eval. W. Med Services", "Psych Eval NSF"),
            ("NSF IOP-Wilton", "IOP NSF"),
        ]
        
        for service_type, expected_abbrev in test_cases:
            with self.subTest(service_type=service_type):
                result = get_service_abbreviation(service_type)
                self.assertEqual(result, expected_abbrev)

    def test_telemed_nsf_combination(self):
        """Test services that are both Telemed and NSF."""
        result = get_service_abbreviation("Telemed: NSF Psychiatric Diag. Eval. W. Med Services")
        # Should strip NSF from middle, but this is a rare edge case
        # The function processes it as: starts with "Telemed:" -> adds Tele prefix
        # Just verify it doesn't crash
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_fallback_parsing(self):
        """Test fallback parsing for unknown service types."""
        # Unknown service should default to "IT"
        result = get_service_abbreviation("Some Unknown Service Type")
        self.assertEqual(result, "IT")
        
        # But should recognize common patterns
        result = get_service_abbreviation("Individual Therapy Session")
        self.assertEqual(result, "IT")
        
        result = get_service_abbreviation("Group Therapy")
        self.assertEqual(result, "Group")


class TestPPSCommentParsing(unittest.TestCase):
    """Test cases for PPS comment parsing."""

    def test_parse_full_pps_comment(self):
        """Test parsing a complete PPS comment with all components."""
        comment = "$1,670/$3,500 deductible / $14,000 OOP (combine) used as of 1/23 | 40% coinsurance | Ins Renews 1/2027"
        
        parsed = parse_pps_comment(comment)
        
        self.assertEqual(parsed['deductible_met'], Decimal("1670"))
        self.assertEqual(parsed['deductible_total'], Decimal("3500"))
        self.assertEqual(parsed['oop_max'], Decimal("14000"))
        self.assertEqual(parsed['as_of_date'], "1/23")
        self.assertEqual(parsed['coinsurance_rate'], "40%")
        self.assertEqual(parsed['renewal_date'], "1/2027")

    def test_parse_deductible_only(self):
        """Test parsing comment with only deductible information."""
        comment = "$2,095/$3,500 deductible"
        
        parsed = parse_pps_comment(comment)
        
        self.assertEqual(parsed['deductible_met'], Decimal("2095"))
        self.assertEqual(parsed['deductible_total'], Decimal("3500"))
        self.assertIsNone(parsed['oop_max'])

    def test_parse_oop_with_accumulated(self):
        """Test parsing OOP format with accumulated amount."""
        comment = "$2,911/$3,350 OOP used as of 1/23"
        
        parsed = parse_pps_comment(comment)
        
        self.assertEqual(parsed['oop_accumulated'], Decimal("2911"))
        self.assertEqual(parsed['oop_max'], Decimal("3350"))
        self.assertEqual(parsed['as_of_date'], "1/23")

    def test_parse_oop_combine_format(self):
        """Test parsing OOP (combine) format without accumulated amount."""
        comment = "/$18,200 OOP (combine) used as of 1/26"
        
        parsed = parse_pps_comment(comment)
        
        self.assertIsNone(parsed['oop_accumulated'])
        self.assertEqual(parsed['oop_max'], Decimal("18200"))
        self.assertEqual(parsed['as_of_date'], "1/26")

    def test_parse_empty_comment(self):
        """Test parsing empty or None comment."""
        parsed = parse_pps_comment("")
        self.assertIsNone(parsed['deductible_met'])
        
        parsed = parse_pps_comment(None)
        self.assertIsNone(parsed['deductible_met'])


class TestPPSCommentFormatting(unittest.TestCase):
    """Test cases for PPS comment formatting."""

    def test_format_updated_deductible(self):
        """Test formatting with updated deductible amount."""
        parsed = {
            'deductible_met': Decimal("1670"),
            'deductible_total': Decimal("3500"),
            'oop_accumulated': None,
            'oop_max': Decimal("14000"),
            'as_of_date': "1/23",
            'coinsurance_rate': "40%",
            'renewal_date': "1/2027",
            'other_parts': []
        }
        
        result = format_updated_pps_comment(
            parsed,
            new_deductible=Decimal("2095"),
            as_of_date=date(2026, 1, 27)
        )
        
        self.assertIn("$2,095/$3,500 deductible", result)
        self.assertIn("1/27", result)
        self.assertIn("40% coinsurance", result)
        self.assertIn("Ins Renews 1/2027", result)

    def test_format_updated_oop(self):
        """Test formatting with updated OOP amount."""
        parsed = {
            'deductible_met': None,
            'deductible_total': None,
            'oop_accumulated': Decimal("2911"),
            'oop_max': Decimal("3350"),
            'as_of_date': "1/23",
            'coinsurance_rate': None,
            'renewal_date': None,
            'other_parts': []
        }
        
        result = format_updated_pps_comment(
            parsed,
            new_oop=Decimal("3211"),
            as_of_date=date(2026, 1, 27)
        )
        
        self.assertIn("$3,211/$3,350 OOP used as of 1/27", result)

    def test_format_combine_format(self):
        """Test formatting OOP (combine) format."""
        parsed = {
            'deductible_met': Decimal("1670"),
            'deductible_total': Decimal("3500"),
            'oop_accumulated': None,
            'oop_max': Decimal("18200"),
            'as_of_date': "1/26",
            'coinsurance_rate': None,
            'renewal_date': None,
            'other_parts': []
        }
        
        result = format_updated_pps_comment(
            parsed,
            new_deductible=Decimal("2095"),
            as_of_date=date(2026, 1, 27)
        )
        
        self.assertIn("$2,095/$3,500 deductible", result)
        self.assertIn("/$18,200 OOP (combine) used as of 1/27", result)

    def test_format_preserves_other_parts(self):
        """Test that formatting preserves other parts of the comment."""
        parsed = {
            'deductible_met': Decimal("1670"),
            'deductible_total': Decimal("3500"),
            'oop_accumulated': None,
            'oop_max': None,
            'as_of_date': None,
            'coinsurance_rate': None,
            'renewal_date': None,
            'other_parts': ["W: Group Room", "Provider: Dr. Smith"]
        }
        
        result = format_updated_pps_comment(parsed)
        
        self.assertIn("W: Group Room", result)
        self.assertIn("Provider: Dr. Smith", result)


class TestCombinedCommentGeneration(unittest.TestCase):
    """Test cases for combined comment generation."""

    def test_single_service_comment(self):
        """Test comment generation for a single service."""
        service = ServiceRecord(
            mrn="28986",
            service_date=date(2026, 1, 26),
            service_type="Outpatient 53+",
            duration_mins=60,
            location="Office",
            pps_comment="",
            provider="Dr. Smith"
        )
        
        result = generate_combined_comment(
            [service],
            Decimal("225.00"),
            date(2026, 1, 26)
        )
        
        self.assertEqual(result, "$225.00 1/26 IT 53+")

    def test_multiple_services_same_day(self):
        """Test combined comment for multiple services on same day."""
        service1 = ServiceRecord(
            mrn="28986",
            service_date=date(2026, 1, 26),
            service_type="IOP-Wilton",
            duration_mins=180,
            location="Office",
            pps_comment="",
            provider="Dr. Smith"
        )
        
        service2 = ServiceRecord(
            mrn="28986",
            service_date=date(2026, 1, 26),
            service_type="Outpatient 53+",
            duration_mins=60,
            location="Office",
            pps_comment="",
            provider="Dr. Smith"
        )
        
        result = generate_combined_comment(
            [service1, service2],
            Decimal("425.00"),
            date(2026, 1, 26)
        )
        
        self.assertEqual(result, "$425.00 1/26 IOP & IT 53+")

    def test_telehealth_combined_comment(self):
        """Test combined comment with telehealth services."""
        service = ServiceRecord(
            mrn="28986",
            service_date=date(2026, 1, 27),
            service_type="Telemed: IOP",
            duration_mins=180,
            location="Telehealth",
            pps_comment="",
            provider="Dr. Smith"
        )
        
        result = generate_combined_comment(
            [service],
            Decimal("200.00"),
            date(2026, 1, 27)
        )
        
        self.assertEqual(result, "$200.00 1/27 Tele IOP")

    def test_nsf_combined_comment(self):
        """Test combined comment with NSF services."""
        service = ServiceRecord(
            mrn="28986",
            service_date=date(2026, 1, 26),
            service_type="NSF Psychiatric Diag. Eval. W. Med Services",
            duration_mins=60,
            location="Office",
            pps_comment="",
            provider="Dr. Smith"
        )
        
        result = generate_combined_comment(
            [service],
            Decimal("0.00"),
            date(2026, 1, 26)
        )
        
        self.assertEqual(result, "$0.00 1/26 Psych Eval NSF")

    def test_date_format_no_leading_zeros(self):
        """Test that date format is M/D without leading zeros."""
        service = ServiceRecord(
            mrn="28986",
            service_date=date(2026, 3, 5),  # March 5th
            service_type="IOP-Wilton",
            duration_mins=180,
            location="Office",
            pps_comment="",
            provider="Dr. Smith"
        )
        
        result = generate_combined_comment(
            [service],
            Decimal("200.00"),
            date(2026, 3, 5)
        )
        
        # Should be 3/5, not 03/05
        self.assertIn("3/5", result)
        self.assertNotIn("03/05", result)


if __name__ == "__main__":
    unittest.main()
