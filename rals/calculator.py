"""Insurance rate calculation engine."""

import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple, Optional

from .models import (
    InsurancePlan, BillingLineItem, ServiceRecord, RateSchedule, Client,
    is_self_pay_virtual, SELF_PAY_VIRTUAL_RATES, SELF_PAY_RATES, is_bundled_with_iop,
    is_non_billable, is_paid_in_full, is_self_pay, get_fixed_session_rate,
    get_copay_amount, get_special_cases
)
from . import config
from .config import is_nsf_service, get_nsf_rate


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
        1. Non-billable services: $0 (RC Client Call, Drug Screen, etc.)
        2. No Show Fee (NSF): Charged even for PIF clients!
           - IOP/Group NSF: ALWAYS $25 (no exceptions)
           - In-Network NSF: Full contracted rate from PPS Comment
           - Out-of-Network/Self-Pay NSF: Self-pay rates
        3. Paid in Full (PIF): $0 (but NOT for NSF - see rule 2)
        4. Fixed session rate: Use that rate instead of calculated
        5. Bundled with IOP: $0 for IT/FT services
        6. Self-pay virtual: Use self-pay rates, doesn't count toward deductible/OOP
        7. Self-pay: Use self-pay rates
        8. Copay: Use copay amount instead of coinsurance
        9. Normal insurance:
           - If deductible not met: patient pays full rate up to remaining deductible
           - Once deductible met: patient pays coinsurance (e.g., 20% of rate)
           - If OOP max reached: patient pays $0

        Args:
            service: The service record to calculate billing for

        Returns:
            BillingLineItem with calculated amounts
        """
        # Detect all special cases from PPS Comment
        special_cases = get_special_cases(service.pps_comment)

        # Check if this is a non-billable service
        is_service_non_billable = is_non_billable(service.service_type, service.pps_comment)

        # Check if this is a No Show Fee (NSF) service
        # NSF is charged regardless of PIF status - must check BEFORE PIF
        is_nsf = is_nsf_service(service.service_type)

        # Check if Paid in Full (but NSF overrides PIF)
        is_pif = special_cases.get("paid_in_full", False)

        # Check for fixed session rate
        fixed_rate = get_fixed_session_rate(service.pps_comment)

        # Check if this is a self-pay virtual service (no virtual benefits)
        is_sp_virtual = (
            service.is_telehealth and
            is_self_pay_virtual(service.pps_comment)
        )

        # Check if this is a general self-pay client
        is_sp = special_cases.get("self_pay", False)

        # Check if this service is bundled with IOP (no separate charge)
        is_bundled = service.is_bundled

        # Check for copay
        copay_amount = get_copay_amount(service.pps_comment)

        # Check for "deductible then covered 100%"
        deductible_then_covered = special_cases.get("deductible_then_covered", False)

        # Check for "IOP covered 100%"
        iop_covered_100 = special_cases.get("iop_covered_100", False) and "iop" in service.service_type.lower()

        # Track if deductible becomes met with this charge
        deductible_now_met = False

        # Initialize variables
        full_rate = Decimal("0.00")
        charge_amount = Decimal("0.00")
        applied_to_ded = Decimal("0.00")
        coinsurance_amt = Decimal("0.00")
        is_self_pay_flag = False

        # Priority 1: Non-billable services (but NOT NSF - NSF is billable)
        if is_service_non_billable and not is_nsf:
            full_rate = self.rate_schedule.get_rate_for_service(service.service_type)
            charge_amount = Decimal("0.00")

        # Priority 2: No Show Fee (NSF) - charged even for PIF clients
        # IOP/Group = $25 always; In-Network = contracted rate; Others = self-pay rate
        elif is_nsf:
            full_rate = get_nsf_rate(service.service_type, service.pps_comment, self.rate_schedule)
            charge_amount = full_rate
            is_self_pay_flag = True
            # NSF does NOT count toward deductible/OOP

        # Priority 3: Paid in Full (but NSF still gets charged above)
        elif is_pif:
            full_rate = self.rate_schedule.get_rate_for_service(service.service_type)
            charge_amount = Decimal("0.00")

        # Priority 4: IOP covered 100%
        elif iop_covered_100:
            full_rate = self.rate_schedule.get_rate_for_service(service.service_type)
            charge_amount = Decimal("0.00")

        # Priority 5: Fixed session rate
        elif fixed_rate is not None:
            full_rate = fixed_rate
            charge_amount = fixed_rate
            is_self_pay_flag = True
            # Fixed rates don't count toward deductible/OOP

        # Priority 6: Bundled with IOP
        elif is_bundled:
            full_rate = self.rate_schedule.get_rate_for_service(service.service_type)
            charge_amount = Decimal("0.00")

        # Priority 7: Self-pay virtual
        elif is_sp_virtual:
            full_rate = SELF_PAY_VIRTUAL_RATES.get_rate_for_service(service.service_type)
            charge_amount = full_rate
            is_self_pay_flag = True

        # Priority 8: General self-pay
        elif is_sp:
            full_rate = SELF_PAY_RATES.get_rate_for_service(service.service_type)
            charge_amount = full_rate
            is_self_pay_flag = True

        # Priority 9: Copay plan
        elif copay_amount is not None:
            full_rate = self.rate_schedule.get_rate_for_service(service.service_type)
            # Cap copay at remaining OOP
            charge_amount = min(copay_amount, self.plan.remaining_oop)
            coinsurance_amt = charge_amount
            # Copay counts toward OOP but NOT deductible
            self.plan.oop_accumulated += charge_amount

        # Priority 9: Normal insurance calculation
        else:
            full_rate = self.rate_schedule.get_rate_for_service(service.service_type)

            # Check if deductible was NOT met before this charge
            deductible_was_not_met = not self.plan.deductible_satisfied

            # Check for special coinsurance rules
            effective_coinsurance = self.plan.coinsurance_rate
            if deductible_then_covered and self.plan.deductible_satisfied:
                effective_coinsurance = Decimal("0.00")  # 0% after deductible

            charge_amount, applied_to_ded, coinsurance_amt = self._calculate_breakdown(
                full_rate, effective_coinsurance
            )

            # Update plan accumulators (only for insurance, not self-pay or bundled)
            self.plan.deductible_met += applied_to_ded
            self.plan.oop_accumulated += charge_amount

            # Check if deductible IS met after this charge (transition happened)
            deductible_now_met = deductible_was_not_met and self.plan.deductible_satisfied

        # Track for comment generation
        if charge_amount > 0:
            self.client.add_service_to_tracking(service.service_date, service.service_type)

        # Calculate final charge amount (rounded)
        final_charge = charge_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Create billing line item with telehealth and duration info
        billing_item = BillingLineItem(
            client_name=self.client.name,
            mrn=self.client.mrn,
            date_of_service=service.service_date,
            service_type=service.service_type,
            payment_date=None,  # Set by user later
            charge_amount=final_charge,
            full_rate=full_rate,
            applied_to_deductible=applied_to_ded.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            coinsurance_amount=coinsurance_amt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            deductible_remaining_after=self.plan.remaining_deductible,
            oop_remaining_after=self.plan.remaining_oop,
            comment=self.client.generate_tracking_comment(),
            is_telehealth=service.is_telehealth,
            duration_code=service.duration_code,
            short_service_type=service.short_service_type,
            is_self_pay=is_self_pay_flag or is_sp_virtual or is_sp,
            is_bundled=is_bundled
        )

        # Generate the payment comment automatically
        billing_item.comment = billing_item.generate_payment_comment()

        # Generate the updated PPS comment with new OOP/deductible values
        # Only for insurance charges, NOT for self-pay or bundled (these don't affect OOP/deductible)
        # Note: The "as of" date is set to today (when the billing report is generated),
        # not the service date, as per user requirements.
        if service.pps_comment and final_charge > 0 and not is_self_pay_flag and not is_bundled:
            billing_item.updated_pps_comment = generate_updated_pps_comment(
                service.pps_comment,
                final_charge,
                None,  # Use today's date for "as of" date
                self.plan.coinsurance_rate,
                deductible_now_met
            )

        return billing_item

    def _calculate_breakdown(
        self,
        full_rate: Decimal,
        effective_coinsurance: Optional[Decimal] = None
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate the breakdown of patient responsibility.

        Args:
            full_rate: The full rate for the service
            effective_coinsurance: Optional override for coinsurance rate
                                   (used for "deductible then covered 100%" cases)

        Returns:
            Tuple of (total_patient_owes, applied_to_deductible, coinsurance_amount)
            Note: For copay plans, coinsurance_amount contains the copay amount
        """
        # If OOP max already reached, patient owes nothing
        if self.plan.oop_max_reached:
            return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")

        remaining_oop = self.plan.remaining_oop

        # Handle copay plans
        if self.plan.has_copay:
            # Copay: fixed amount, does NOT count toward deductible, DOES count toward OOP
            copay_amount = min(self.plan.copay, remaining_oop)  # Cap at remaining OOP
            # Return copay as "coinsurance_amount" for tracking (applied_to_deductible is always 0)
            return copay_amount, Decimal("0.00"), copay_amount

        # Use effective coinsurance rate (allows override for special cases)
        coinsurance_rate = effective_coinsurance if effective_coinsurance is not None else self.plan.coinsurance_rate

        # Standard deductible + coinsurance calculation
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
                coinsurance_amount = remaining_after_ded * coinsurance_rate
                total_patient_owes = applied_to_deductible + coinsurance_amount
        else:
            # Deductible already satisfied, just coinsurance
            coinsurance_amount = full_rate * coinsurance_rate
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
        services: list[ServiceRecord],
        include_zero_charges: bool = False
    ) -> list[BillingLineItem]:
        """
        Calculate billing for multiple services in date order.

        Args:
            services: List of service records
            include_zero_charges: If False (default), excludes unbillable ($0) appointments

        Returns:
            List of billing line items
        """
        # Sort by date to ensure proper deductible/OOP accumulation
        sorted_services = sorted(services, key=lambda s: s.service_date)

        billing_items = []
        for service in sorted_services:
            item = self.calculate_patient_responsibility(service)
            # Only include items with charges > $0 (unless include_zero_charges is True)
            if include_zero_charges or item.charge_amount > 0:
                billing_items.append(item)

        return billing_items

    def calculate_all_services_combined(
        self,
        services: list[ServiceRecord],
        combine_same_day: bool = True,
        include_zero_charges: bool = False
    ) -> list[BillingLineItem]:
        """
        Calculate billing for multiple services, optionally combining same-day services.

        When combine_same_day is True, services on the same date get a combined comment
        showing the total amount and all service types (e.g., "$300.00 1/26 IT & IOP").

        Args:
            services: List of service records
            combine_same_day: If True, combine same-day service comments
            include_zero_charges: If False (default), excludes unbillable ($0) appointments

        Returns:
            List of billing line items (with combined comments for same-day items)
        """
        # First calculate all services individually (excluding $0 by default)
        billing_items = self.calculate_all_services(services, include_zero_charges)

        if not combine_same_day:
            return billing_items

        # Combine same-day self-pay items
        return combine_same_day_billing_items(billing_items)


def combine_same_day_billing_items(billing_items: list[BillingLineItem]) -> list[BillingLineItem]:
    """
    Update billing items to show combined totals for same-day services.

    When a client has multiple services on the same day, each row keeps its
    individual service type, but all rows get the same combined comment
    showing the total amount and all service types.

    Example:
        Row 1: IOP service, Comment: "$470.00 1/26 IT & IOP"
        Row 2: IT service, Comment: "$470.00 1/26 IT & IOP"

    Args:
        billing_items: List of billing line items

    Returns:
        List of billing line items with combined comments for same-day items
    """
    from collections import defaultdict

    if not billing_items:
        return billing_items

    # Group by (client_mrn, date)
    grouped = defaultdict(list)
    for item in billing_items:
        key = (item.mrn, item.date_of_service)
        grouped[key].append(item)

    # Update comments for groups with multiple items
    for (mrn, service_date), items in grouped.items():
        if len(items) > 1:
            # Calculate combined totals
            total_charge = sum(item.charge_amount for item in items)

            # Collect unique service types
            service_types = []
            for item in items:
                short_type = item.short_service_type or item._derive_short_service_type()
                if short_type not in service_types:
                    service_types.append(short_type)

            # Determine flags for the combined comment
            is_telehealth = any(item.is_telehealth for item in items)
            is_self_pay = any(item.is_self_pay for item in items)

            # Generate combined comment
            date_str = f"{service_date.month}/{service_date.day}"
            parts = [f"${total_charge:,.2f}", date_str]

            if is_telehealth:
                parts.append("Tele")

            parts.append(" & ".join(service_types))

            if is_self_pay:
                parts.append("SP")

            combined_comment = " ".join(parts)

            # Update all items in this group with the combined comment
            for item in items:
                item.comment = combined_comment

    # Return items in original order (sorted by date)
    billing_items.sort(key=lambda x: x.date_of_service)
    return billing_items


def _combine_billing_items(items: list[BillingLineItem]) -> BillingLineItem:
    """
    Combine multiple billing items into a single combined item.

    Args:
        items: List of billing items to combine (must be same client/date)

    Returns:
        Combined billing item
    """
    if len(items) == 1:
        return items[0]

    # Use first item as base
    base = items[0]

    # Sum up charges and amounts
    total_charge = sum(item.charge_amount for item in items)
    total_full_rate = sum(item.full_rate for item in items)
    total_applied_to_ded = sum(item.applied_to_deductible for item in items)
    total_coinsurance = sum(item.coinsurance_amount for item in items)

    # Collect unique service types for the comment
    service_types = []
    for item in items:
        short_type = item.short_service_type or item._derive_short_service_type()
        if short_type not in service_types:
            service_types.append(short_type)

    # Determine flags
    is_telehealth = any(item.is_telehealth for item in items)
    is_self_pay = any(item.is_self_pay for item in items)
    is_bundled = all(item.is_bundled for item in items)  # Only bundled if ALL are bundled

    # Use the last item's remaining values (most up-to-date)
    last_item = items[-1]

    # Create combined item
    combined = BillingLineItem(
        client_name=base.client_name,
        mrn=base.mrn,
        date_of_service=base.date_of_service,
        service_type=" & ".join(service_types),  # Combined service types
        payment_date=base.payment_date,
        charge_amount=total_charge,
        full_rate=total_full_rate,
        applied_to_deductible=total_applied_to_ded,
        coinsurance_amount=total_coinsurance,
        deductible_remaining_after=last_item.deductible_remaining_after,
        oop_remaining_after=last_item.oop_remaining_after,
        is_telehealth=is_telehealth,
        duration_code="",  # No duration code for combined
        short_service_type=" & ".join(service_types),
        is_self_pay=is_self_pay,
        is_bundled=is_bundled,
        updated_pps_comment=last_item.updated_pps_comment  # Use last update
    )

    # Generate combined payment comment
    combined.comment = combined.generate_payment_comment()

    return combined


def parse_rates_from_pps_comment(pps_comment: str) -> RateSchedule:
    """
    Parse rate schedule from PPS Comment field.

    Expected format examples:
    - "W: Group Room IOP $575 | Group $125 | IT $260 | FT $200 | Psych Eval $350 | Psych flu $275 | MAT $1: Provider"
    - "IOP $575 | Group $125 | IT $260"
    - "In Network: IOP $298 | Group $40 | Psych Eval $176.3"

    Uses centralized config patterns for rate type recognition.

    Args:
        pps_comment: The PPS Comment string containing rate info

    Returns:
        RateSchedule with parsed rates
    """
    schedule = RateSchedule()

    if not pps_comment:
        return schedule

    # Use patterns from config
    rate_type_patterns = config.PPSPatterns.RATE_TYPES

    # Split by pipe delimiter to get individual rate entries
    segments = pps_comment.split('|')

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        # Look for a dollar amount in this segment
        amount_match = re.search(config.PPSPatterns.RATE_AMOUNT, segment)
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
            full_pattern = pattern + r'\s*\$\s*([\d,]+(?:\.\d{1,2})?)'
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


def parse_oop_from_pps_comment(pps_comment: str) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[str]]:
    """
    Parse OOP (Out of Pocket) information from PPS Comment.

    Supported formats:
    - "$2,911/ $3,350 OOP used as of 1/23"
    - "$2,911/$3,350 OOP used as of 1/23"
    - "/$18,200 OOP (combine) used as of 1/26"
    - "OOPM $3750" (just max, no used amount)
    - "OOPM $2,252.89: $240 met as of 11/28" (max with amount met)

    Args:
        pps_comment: The PPS Comment string

    Returns:
        Tuple of (oop_used, oop_max, as_of_date_str) or (None, None, None) if not found
    """
    if not pps_comment:
        return None, None, None

    # Pattern 1: $amount/ $amount OOP used as of date
    pattern = r'\$\s*([\d,]+(?:\.\d{1,2})?)\s*/\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*OOP(?:\s*\(combine\))?\s+used\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'
    match = re.search(pattern, pps_comment, re.IGNORECASE)
    if match:
        try:
            oop_used = Decimal(match.group(1).replace(",", ""))
            oop_max = Decimal(match.group(2).replace(",", ""))
            return oop_used, oop_max, match.group(3)
        except:
            pass

    # Pattern 2: /$amount OOP (combine) used as of date
    pattern2 = r'/\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*OOP\s*\(combine\)\s+used\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'
    match2 = re.search(pattern2, pps_comment, re.IGNORECASE)
    if match2:
        try:
            oop_max = Decimal(match2.group(1).replace(",", ""))
            return None, oop_max, match2.group(2)
        except:
            pass

    # Pattern 3: OOPM $amount: $amount met as of date (e.g., "OOPM $2,252.89: $240 met as of 11/28")
    pattern3 = r'OOPM?\s*\$\s*([\d,]+(?:\.\d{1,2})?)\s*:\s*\$\s*([\d,]+(?:\.\d{1,2})?)\s*met\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'
    match3 = re.search(pattern3, pps_comment, re.IGNORECASE)
    if match3:
        try:
            oop_max = Decimal(match3.group(1).replace(",", ""))
            oop_used = Decimal(match3.group(2).replace(",", ""))
            return oop_used, oop_max, match3.group(3)
        except:
            pass

    # Pattern 4: OOPM $amount (just max, no used amount, e.g., "OOPM $3750")
    pattern4 = r'OOPM?\s*\$\s*([\d,]+(?:\.\d{1,2})?)'
    match4 = re.search(pattern4, pps_comment, re.IGNORECASE)
    if match4:
        try:
            oop_max = Decimal(match4.group(1).replace(",", ""))
            return Decimal("0"), oop_max, None
        except:
            pass

    return None, None, None


def parse_deductible_from_pps_comment(pps_comment: str) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[str]]:
    """
    Parse deductible information from PPS Comment.

    Supported formats:
    - "$1,732.50/$3,500 deductible"
    - "$1,732.50/$3,500 deductible| /$18,200 OOP (combine) used as of 1/26"
    - "Ded $1,721.27" (just amount met, no total)

    Args:
        pps_comment: The PPS Comment string

    Returns:
        Tuple of (deductible_met, deductible_total, as_of_date_str) or (None, None, None) if not found
    """
    if not pps_comment:
        return None, None, None

    # Pattern 1: $amount/$amount deductible
    pattern = r'\$\s*([\d,]+(?:\.\d{1,2})?)\s*/\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*deductible'
    match = re.search(pattern, pps_comment, re.IGNORECASE)
    if match:
        try:
            ded_met = Decimal(match.group(1).replace(",", ""))
            ded_total = Decimal(match.group(2).replace(",", ""))

            # Try to find associated date
            date_pattern = r'used\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'
            date_match = re.search(date_pattern, pps_comment, re.IGNORECASE)
            date_str = date_match.group(1) if date_match else None

            return ded_met, ded_total, date_str
        except:
            pass

    # Pattern 2: "Ded $amount" (just amount met, assume deductible is fully met)
    pattern2 = r'\bDed\s*\$\s*([\d,]+(?:\.\d{1,2})?)'
    match2 = re.search(pattern2, pps_comment, re.IGNORECASE)
    if match2:
        try:
            ded_met = Decimal(match2.group(1).replace(",", ""))
            # Assume deductible is fully met (total = met)
            return ded_met, ded_met, None
        except:
            pass

    return None, None, None


def generate_updated_pps_comment(
    original_pps: str,
    charge_amount: Decimal,
    new_date: Optional[date] = None,
    coinsurance_rate: Optional[Decimal] = None,
    deductible_now_met: bool = False
) -> str:
    """
    Generate an updated PPS Comment with new OOP and/or deductible values.

    For combined deductible/OOP tracking:
    - While deductible not met: Update deductible amount, keep full rates
    - When deductible becomes met: Remove deductible section, update rates to
      coinsurance amounts, convert OOP from (combine) to standard format

    Example (deductible not yet met):
        Original: "IOP $600 | $440/$3,400 deductible /$17,000 OOP (combine) used as of 1/28"
        After $110 charge:
        Updated:  "IOP $600 | $550/$3,400 deductible /$17,000 OOP (combine) used as of 1/28"

    Example (deductible now met):
        Original: "IOP $600 | $3,290/$3,400 deductible /$17,000 OOP (combine) used as of 1/28 | 40% coinsurance"
        After $200 charge (110 to ded + 36 coinsurance):
        Updated:  "IOP $240 | $3,446/$17,000 OOP used as of 1/28 | Ins Renews..."

    Args:
        original_pps: The original PPS Comment string
        charge_amount: The amount charged to the patient
        new_date: The date to use for "as of" (defaults to today)
        coinsurance_rate: Coinsurance rate for updating rates (e.g., 0.40 for 40%)
        deductible_now_met: If True, deductible was met with this charge - transform PPS

    Returns:
        Updated PPS Comment string
    """
    if not original_pps:
        return original_pps

    if new_date is None:
        new_date = date.today()

    new_date_str = f"{new_date.month}/{new_date.day}"
    updated_pps = original_pps

    # Check if this is a combined deductible/OOP format
    is_combined = '(combine)' in original_pps.lower()

    # Parse current values
    ded_met, ded_total, _ = parse_deductible_from_pps_comment(original_pps)
    oop_used, oop_max, _ = parse_oop_from_pps_comment(original_pps)

    # Get coinsurance rate from PPS if not provided
    if coinsurance_rate is None:
        coins_match = re.search(r'(\d+)%\s*coinsurance', original_pps, re.IGNORECASE)
        if coins_match:
            coinsurance_rate = Decimal(coins_match.group(1)) / Decimal('100')
        else:
            coinsurance_rate = Decimal('0.40')  # Default 40%

    # Case 1: Deductible is now fully met - transform the PPS comment
    if deductible_now_met and ded_total is not None and coinsurance_rate is not None:
        # Update all rates to coinsurance amounts
        updated_pps = _update_rates_to_coinsurance(updated_pps, coinsurance_rate)

        # Calculate new OOP used (deductible total + any coinsurance from this charge)
        new_oop_used = ded_total + charge_amount
        if oop_max is None:
            oop_max = Decimal("10000")  # Default

        # Remove deductible section and coinsurance mention
        updated_pps = re.sub(
            r'\$\s*[\d,]+(?:\.\d{1,2})?\s*/\s*\$?\s*[\d,]+(?:\.\d{1,2})?\s*deductible\s*',
            '',
            updated_pps,
            flags=re.IGNORECASE
        )
        updated_pps = re.sub(r'\|\s*\d+%\s*coinsurance\s*', '', updated_pps, flags=re.IGNORECASE)

        # Replace OOP (combine) format with standard OOP format
        oop_combine_pattern = r'/\s*\$?\s*[\d,]+(?:\.\d{1,2})?\s*OOP\s*\(combine\)\s+used\s+as\s+of\s+\d{1,2}/\d{1,2}(?:/\d{2,4})?'

        if new_oop_used == new_oop_used.to_integral_value():
            new_oop_used_str = f"${int(new_oop_used):,}"
        else:
            new_oop_used_str = f"${new_oop_used:,.2f}"

        if oop_max == oop_max.to_integral_value():
            oop_max_str = f"${int(oop_max):,}"
        else:
            oop_max_str = f"${oop_max:,.2f}"

        new_oop_section = f"{new_oop_used_str}/{oop_max_str} OOP used as of {new_date_str}"
        updated_pps = re.sub(oop_combine_pattern, new_oop_section, updated_pps, flags=re.IGNORECASE)

        # Clean up multiple pipes
        updated_pps = re.sub(r'\|\s*\|', '|', updated_pps)
        updated_pps = re.sub(r'\s+\|', ' |', updated_pps)

        return updated_pps.strip()

    # Case 2: Standard update - deductible not yet met
    if ded_met is not None and ded_total is not None and ded_met < ded_total:
        remaining_ded = ded_total - ded_met
        applied_to_ded = min(charge_amount, remaining_ded)
        new_ded_met = ded_met + applied_to_ded

        ded_pattern = r'\$\s*[\d,]+(?:\.\d{1,2})?\s*/\s*\$?\s*[\d,]+(?:\.\d{1,2})?\s*deductible'

        if new_ded_met == new_ded_met.to_integral_value():
            new_ded_met_str = f"${int(new_ded_met):,}"
        else:
            new_ded_met_str = f"${new_ded_met:,.2f}"

        if ded_total == ded_total.to_integral_value():
            ded_total_str = f"${int(ded_total):,}"
        else:
            ded_total_str = f"${ded_total:,.2f}"

        new_ded_section = f"{new_ded_met_str}/{ded_total_str} deductible"
        updated_pps = re.sub(ded_pattern, new_ded_section, updated_pps, flags=re.IGNORECASE)

        # For combined format, also update the date
        if is_combined:
            date_pattern = r'used\s+as\s+of\s+\d{1,2}/\d{1,2}(?:/\d{2,4})?'
            updated_pps = re.sub(date_pattern, f"used as of {new_date_str}", updated_pps, flags=re.IGNORECASE)

    # Case 3: Deductible already met, just update OOP
    elif oop_used is not None and oop_max is not None:
        new_oop_used = oop_used + charge_amount

        oop_pattern = r'\$\s*[\d,]+(?:\.\d{1,2})?\s*/\s*\$?\s*[\d,]+(?:\.\d{1,2})?\s*OOP(?:\s*\(combine\))?\s+used\s+as\s+of\s+\d{1,2}/\d{1,2}(?:/\d{2,4})?'

        if new_oop_used == new_oop_used.to_integral_value():
            new_oop_used_str = f"${int(new_oop_used):,}"
        else:
            new_oop_used_str = f"${new_oop_used:,.2f}"

        if oop_max == oop_max.to_integral_value():
            oop_max_str = f"${int(oop_max):,}"
        else:
            oop_max_str = f"${oop_max:,.2f}"

        new_oop_section = f"{new_oop_used_str}/{oop_max_str} OOP used as of {new_date_str}"
        updated_pps = re.sub(oop_pattern, new_oop_section, updated_pps, flags=re.IGNORECASE)

    return updated_pps


def _update_rates_to_coinsurance(pps_comment: str, coinsurance_rate: Decimal) -> str:
    """
    Update all rates in a PPS comment to coinsurance amounts.

    Example: "IOP $600 | Group $110 | IT $330" with 40% coinsurance becomes
             "IOP $240 | Group $44 | IT $132"

    Args:
        pps_comment: Original PPS comment
        coinsurance_rate: Coinsurance rate (e.g., 0.40 for 40%)

    Returns:
        PPS comment with updated rates
    """
    # Rate patterns to find and update
    rate_patterns = [
        (r'Assessment\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'Assessment'),
        (r'IOP\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'IOP'),
        (r'Group\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'Group'),
        (r'\bIT\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'IT'),
        (r'\bFT\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'FT'),
        (r'Psych\s*Eval\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'Psych Eval'),
        (r'Psych\s*f/u\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'Psych f/u'),
        (r'MAT\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'MAT'),
        (r'Fam\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'Fam'),
        (r'OP/IT\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'OP/IT'),
        (r'Intake\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'Intake'),
        (r'Psych\s*E\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'Psych E'),
        (r'MATS\s*\$\s*([\d,]+(?:\.\d{1,2})?)', 'MATS'),
    ]

    updated = pps_comment

    for pattern, label in rate_patterns:
        match = re.search(pattern, updated, re.IGNORECASE)
        if match:
            original_rate_str = match.group(1).replace(',', '')
            try:
                original_rate = Decimal(original_rate_str)
                new_rate = (original_rate * coinsurance_rate).quantize(Decimal('1'))

                # Format new rate
                new_rate_str = f"${int(new_rate):,}" if new_rate == new_rate.to_integral_value() else f"${new_rate:,.2f}"

                # Replace in string
                old_text = match.group(0)
                new_text = f"{label} {new_rate_str}"
                updated = updated.replace(old_text, new_text, 1)
            except:
                pass

    return updated
