"""Insurance rate calculation engine."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple

from .models import InsurancePlan, BillingLineItem, ServiceRecord, RateSchedule, Client


class RateCalculator:
    """Calculates patient responsibility based on insurance parameters."""

    def __init__(self, client: Client, rate_schedule: RateSchedule):
        """
        Initialize calculator with client and rate schedule.

        Args:
            client: Client with insurance plan information
            rate_schedule: Rate schedule for services
        """
        self.client = client
        self.rate_schedule = rate_schedule
        self.plan = client.insurance_plan

    def calculate_patient_responsibility(
        self,
        service: ServiceRecord
    ) -> BillingLineItem:
        """
        Calculate patient responsibility for a service.

        The calculation follows these rules:
        1. If deductible not met: patient pays full rate up to remaining deductible
        2. Once deductible met: patient pays coinsurance (e.g., 20% of rate)
        3. If OOP max reached: patient pays $0

        Args:
            service: The service record to calculate billing for

        Returns:
            BillingLineItem with calculated amounts
        """
        # Get the full rate for this service
        full_rate = self.rate_schedule.get_rate_for_service(service.service_type)

        # Calculate the breakdown
        charge_amount, applied_to_ded, coinsurance_amt = self._calculate_breakdown(full_rate)

        # Update plan accumulators
        self.plan.deductible_met += applied_to_ded
        self.plan.oop_accumulated += charge_amount

        # Track for comment generation
        if charge_amount > 0:
            self.client.add_service_to_tracking(service.service_date, service.service_type)

        # Create billing line item with telehealth and duration info
        billing_item = BillingLineItem(
            client_name=self.client.name,
            mrn=self.client.mrn,
            date_of_service=service.service_date,
            service_type=service.service_type,
            payment_date=None,  # Set by user later
            charge_amount=charge_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            full_rate=full_rate,
            applied_to_deductible=applied_to_ded.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            coinsurance_amount=coinsurance_amt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            deductible_remaining_after=self.plan.remaining_deductible,
            oop_remaining_after=self.plan.remaining_oop,
            comment=self.client.generate_tracking_comment(),
            is_telehealth=service.is_telehealth,
            duration_code=service.duration_code,
            short_service_type=service.short_service_type
        )

        # Generate the payment comment automatically
        billing_item.comment = billing_item.generate_payment_comment()

        return billing_item

    def _calculate_breakdown(
        self,
        full_rate: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate the breakdown of patient responsibility.

        Args:
            full_rate: The full rate for the service

        Returns:
            Tuple of (total_patient_owes, applied_to_deductible, coinsurance_amount)
        """
        # If OOP max already reached, patient owes nothing
        if self.plan.oop_max_reached:
            return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")

        remaining_oop = self.plan.remaining_oop
        remaining_ded = self.plan.remaining_deductible

        applied_to_deductible = Decimal("0.00")
        coinsurance_amount = Decimal("0.00")
        total_patient_owes = Decimal("0.00")

        if not self.plan.deductible_satisfied:
            # Deductible not yet met
            if full_rate <= remaining_ded:
                # Full rate goes to deductible
                applied_to_deductible = full_rate
                total_patient_owes = full_rate
            else:
                # Part goes to deductible, rest subject to coinsurance
                applied_to_deductible = remaining_ded
                remaining_after_ded = full_rate - remaining_ded
                coinsurance_amount = remaining_after_ded * self.plan.coinsurance_rate
                total_patient_owes = applied_to_deductible + coinsurance_amount
        else:
            # Deductible already satisfied, just coinsurance
            coinsurance_amount = full_rate * self.plan.coinsurance_rate
            total_patient_owes = coinsurance_amount

        # Cap at remaining OOP
        if total_patient_owes > remaining_oop:
            # Adjust amounts proportionally
            ratio = remaining_oop / total_patient_owes if total_patient_owes > 0 else Decimal("0")
            applied_to_deductible = applied_to_deductible * ratio
            coinsurance_amount = coinsurance_amount * ratio
            total_patient_owes = remaining_oop

        return total_patient_owes, applied_to_deductible, coinsurance_amount

    def calculate_all_services(
        self,
        services: list[ServiceRecord]
    ) -> list[BillingLineItem]:
        """
        Calculate billing for multiple services in date order.

        Args:
            services: List of service records

        Returns:
            List of billing line items
        """
        # Sort by date to ensure proper deductible/OOP accumulation
        sorted_services = sorted(services, key=lambda s: s.service_date)

        billing_items = []
        for service in sorted_services:
            item = self.calculate_patient_responsibility(service)
            billing_items.append(item)

        return billing_items


def parse_rates_from_pps_comment(pps_comment: str) -> RateSchedule:
    """
    Parse rate schedule from PPS Comment field.

    Expected format examples:
    - "W: Group Room IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275 | MAT $1: Provider"
    - "IOP $575 | Group $125 | IT $260"

    Args:
        pps_comment: The PPS Comment string containing rate info

    Returns:
        RateSchedule with parsed rates
    """
    import re

    schedule = RateSchedule()

    if not pps_comment:
        return schedule

    # Known rate type patterns (case-insensitive)
    # Maps pattern -> (attribute_name, is_exact_match)
    rate_type_patterns = [
        (r'\bAssessment\b', 'assessment_rate'),
        (r'\bIOP\b', 'iop_rate'),
        (r'\bGroup\b', 'group_rate'),
        (r'\bIT\b', 'it_rate'),
        (r'\bFT\b', 'ft_rate'),
        (r'\bPsych\s*Eval\b', 'psych_eval_rate'),
        (r'\bPsych\s*flu\b', 'psych_followup_rate'),
        (r'\bPsych\s*f/u\b', 'psych_followup_rate'),
        (r'\bPsych\s*Follow\s*-?\s*up\b', 'psych_followup_rate'),
        (r'\bTelemed\b', 'telemed_rate'),
        (r'\bEMDR\b', 'emdr_rate'),
    ]

    # Split by pipe delimiter to get individual rate entries
    segments = pps_comment.split('|')

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        # Look for a dollar amount in this segment
        # Pattern: $XXX or $X,XXX or $XXX.XX
        amount_match = re.search(r'\$\s*([\d,]+(?:\.\d{2})?)', segment)
        if not amount_match:
            continue

        amount_str = amount_match.group(1).replace(",", "")
        try:
            amount = Decimal(amount_str)
        except:
            continue

        # Skip very small amounts (likely not service rates, e.g., "MAT $1")
        if amount < Decimal("10"):
            continue

        # Determine which rate type this is
        segment_before_dollar = segment[:amount_match.start()].strip()

        for pattern, attr_name in rate_type_patterns:
            if re.search(pattern, segment_before_dollar, re.IGNORECASE):
                setattr(schedule, attr_name, amount)
                break

    # If pipe-delimited parsing didn't find rates, try full string matching
    # This handles cases where the format might be different
    if not any([
        schedule.iop_rate > 0,
        schedule.it_rate > 0,
        schedule.group_rate > 0,
        schedule.psych_eval_rate > 0
    ]):
        # Fallback: look for patterns anywhere in the string
        for pattern, attr_name in rate_type_patterns:
            # Match pattern followed by dollar amount
            full_pattern = pattern + r'\s*\$\s*([\d,]+(?:\.\d{2})?)'
            match = re.search(full_pattern, pps_comment, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    amount = Decimal(amount_str)
                    if amount >= Decimal("10"):  # Skip small amounts
                        setattr(schedule, attr_name, amount)
                except:
                    continue

    return schedule
