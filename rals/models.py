"""Data models for insurance billing calculations."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from enum import Enum
import decimal  # For InvalidOperation exception

# Import from centralized config
from . import config


class ServiceCategory(Enum):
    """Categories of services for rate mapping."""
    IOP = "IOP"
    OUTPATIENT = "Outpatient"
    TELEMED = "Telemed"
    PSYCH_EVAL = "Psych Eval"
    GROUP = "Group"
    IT = "IT"  # Individual Therapy
    FT = "FT"  # Family Therapy
    EMDR = "EMDR"
    OTHER = "Other"


# Re-export SERVICE_ABBREVIATIONS for backward compatibility
SERVICE_ABBREVIATIONS = config.SERVICE_ABBREVIATIONS


def get_service_abbreviation(service_type: str) -> str:
    """
    Get abbreviated service name for billing comments.

    Delegates to config module for centralized mapping.

    Args:
        service_type: Full service type name

    Returns:
        Abbreviated service name for use in billing comments
    """
    return config.get_service_abbreviation(service_type)


@dataclass
class InsurancePlan:
    """Insurance plan parameters for billing calculations."""
    name: str
    deductible: Decimal
    coinsurance_rate: Decimal  # Patient responsibility after deductible (e.g., 0.20 = 20%)
    oop_max: Decimal  # Out-of-pocket maximum

    # Track accumulation
    deductible_met: Decimal = Decimal("0.00")
    oop_accumulated: Decimal = Decimal("0.00")

    # Copay (if set, used instead of coinsurance; does NOT count toward deductible, DOES count toward OOP)
    copay: Optional[Decimal] = None

    def __post_init__(self):
        """Ensure all monetary values are Decimal."""
        if not isinstance(self.deductible, Decimal):
            self.deductible = Decimal(str(self.deductible))
        if not isinstance(self.coinsurance_rate, Decimal):
            self.coinsurance_rate = Decimal(str(self.coinsurance_rate))
        if not isinstance(self.oop_max, Decimal):
            self.oop_max = Decimal(str(self.oop_max))
        if not isinstance(self.deductible_met, Decimal):
            self.deductible_met = Decimal(str(self.deductible_met))
        if not isinstance(self.oop_accumulated, Decimal):
            self.oop_accumulated = Decimal(str(self.oop_accumulated))
        if self.copay is not None and not isinstance(self.copay, Decimal):
            self.copay = Decimal(str(self.copay))

    @property
    def has_copay(self) -> bool:
        """Whether this plan uses copay instead of coinsurance."""
        return self.copay is not None and self.copay > 0

    @property
    def remaining_deductible(self) -> Decimal:
        """Amount remaining until deductible is met."""
        return max(Decimal("0.00"), self.deductible - self.deductible_met)

    @property
    def remaining_oop(self) -> Decimal:
        """Amount remaining until OOP max is reached."""
        return max(Decimal("0.00"), self.oop_max - self.oop_accumulated)

    @property
    def deductible_satisfied(self) -> bool:
        """Whether the deductible has been fully met."""
        return self.deductible_met >= self.deductible

    @property
    def oop_max_reached(self) -> bool:
        """Whether the OOP maximum has been reached."""
        return self.oop_accumulated >= self.oop_max

    def reset(self):
        """Reset accumulators for new plan year."""
        self.deductible_met = Decimal("0.00")
        self.oop_accumulated = Decimal("0.00")


@dataclass
class RateSchedule:
    """Rate schedule extracted from PPS Comment."""
    assessment_rate: Decimal = Decimal("0.00")  # Initial assessment
    iop_rate: Decimal = Decimal("0.00")
    group_rate: Decimal = Decimal("0.00")
    it_rate: Decimal = Decimal("0.00")  # Individual Therapy
    ft_rate: Decimal = Decimal("0.00")  # Family Therapy
    psych_eval_rate: Decimal = Decimal("0.00")
    psych_followup_rate: Decimal = Decimal("0.00")  # "Psych flu" = Psych follow-up
    emdr_rate: Decimal = Decimal("0.00")
    telemed_rate: Decimal = Decimal("0.00")
    mat_rate: Decimal = Decimal("0.00")  # Medication Assisted Treatment

    def get_rate_for_service(self, service_type: str) -> Decimal:
        """Get the appropriate rate for a service type.

        Uses centralized config for service-to-rate mapping.
        Applies half-rate rules for shorter appointments.
        """
        # Get the rate key from config
        rate_key = config.get_rate_key_for_service(service_type)

        # Map rate key to attribute
        attr_name = config.RATE_KEY_TO_ATTRIBUTE.get(rate_key, "it_rate")
        base_rate = getattr(self, attr_name, self.it_rate)

        # Handle fallbacks for zero rates
        if base_rate == Decimal("0.00"):
            if attr_name == "assessment_rate":
                base_rate = self.it_rate
            elif attr_name == "emdr_rate":
                base_rate = self.it_rate

        # Apply half-rate if applicable
        if config.should_apply_half_rate(service_type):
            return (base_rate / 2).quantize(Decimal("0.01"))

        return base_rate


# Default self-pay rates for virtual services (when client has no virtual benefits)
# Uses rates from centralized config
SELF_PAY_VIRTUAL_RATES = RateSchedule(
    assessment_rate=config.SELF_PAY_VIRTUAL_RATES["assessment_rate"],
    iop_rate=config.SELF_PAY_VIRTUAL_RATES["iop_rate"],
    group_rate=config.SELF_PAY_VIRTUAL_RATES["group_rate"],
    it_rate=config.SELF_PAY_VIRTUAL_RATES["it_rate"],
    ft_rate=config.SELF_PAY_VIRTUAL_RATES["ft_rate"],
    psych_eval_rate=config.SELF_PAY_VIRTUAL_RATES["psych_eval_rate"],
    psych_followup_rate=config.SELF_PAY_VIRTUAL_RATES["psych_followup_rate"],
    mat_rate=config.SELF_PAY_VIRTUAL_RATES["mat_rate"],
)

# Default self-pay rates (non-virtual)
SELF_PAY_RATES = RateSchedule(
    assessment_rate=config.SELF_PAY_RATES["assessment_rate"],
    iop_rate=config.SELF_PAY_RATES["iop_rate"],
    group_rate=config.SELF_PAY_RATES["group_rate"],
    it_rate=config.SELF_PAY_RATES["it_rate"],
    ft_rate=config.SELF_PAY_RATES["ft_rate"],
    psych_eval_rate=config.SELF_PAY_RATES["psych_eval_rate"],
    psych_followup_rate=config.SELF_PAY_RATES["psych_followup_rate"],
    mat_rate=config.SELF_PAY_RATES["mat_rate"],
)


def is_self_pay_virtual(pps_comment: str) -> bool:
    """
    Check if the PPS comment indicates self-pay rates for virtual services.

    Delegates to config module for pattern matching.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        True if self-pay rates apply for virtual services
    """
    special_cases = config.detect_special_cases(pps_comment)
    return special_cases.get("self_pay_virtual", False)


def is_bundled_with_iop(pps_comment: str, physical_proc: str, service_type: str) -> bool:
    """
    Check if a service is bundled with IOP and should not be charged separately.

    When the PPS comment includes "In Network:" and the Physical Program column
    includes "IOP", then IT and FT services are bundled with the IOP program
    and should not be charged separately.

    Args:
        pps_comment: The PPS Comment string
        physical_proc: The Physical Program column value
        service_type: The service type being checked

    Returns:
        True if this service is bundled with IOP (no separate charge)
    """
    if not pps_comment or not physical_proc:
        return False

    pps_lower = pps_comment.lower()
    physical_lower = physical_proc.lower()
    service_lower = service_type.lower()

    # Check if "In Network:" is in PPS comment and "IOP" is in Physical Program
    is_in_network_iop = "in network:" in pps_lower and "iop" in physical_lower

    if not is_in_network_iop:
        return False

    # IT and FT services are bundled with IOP
    # Group therapy is NOT bundled - it's a different level of care (outpatient vs intensive outpatient)
    is_group_service = "group" in service_lower

    is_it_service = (
        "individual" in service_lower or
        ("it" in service_lower and "outpatient" not in service_lower) or
        ("outpatient" in service_lower and not is_group_service)  # Exclude "Outpatient Group"
    )
    is_ft_service = "family" in service_lower or "ft" in service_lower

    # Only IT and FT are bundled; Group is NOT bundled (different LOC)
    return (is_it_service or is_ft_service) and not is_group_service


def is_non_billable(service_type: str, pps_comment: str = "") -> bool:
    """
    Check if a service is non-billable (should be $0).

    Delegates to config module for pattern matching.

    Args:
        service_type: The service type from Column D
        pps_comment: The PPS Comment (for additional context)

    Returns:
        True if the service should be $0
    """
    return config.is_non_billable_service(service_type, pps_comment)


def is_paid_in_full(pps_comment: str) -> bool:
    """
    Check if the client has paid in full for the year.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        True if PIF indicator found
    """
    special_cases = config.detect_special_cases(pps_comment)
    return special_cases.get("paid_in_full", False)


def is_self_pay(pps_comment: str) -> bool:
    """
    Check if this is a self-pay client (no insurance).

    Args:
        pps_comment: The PPS Comment string

    Returns:
        True if self-pay indicator found
    """
    special_cases = config.detect_special_cases(pps_comment)
    return special_cases.get("self_pay", False)


def get_fixed_session_rate(pps_comment: str) -> Optional[Decimal]:
    """
    Get fixed per-session rate if specified in PPS Comment.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        Fixed rate as Decimal, or None if not specified
    """
    return config.extract_fixed_session_rate(pps_comment)


def get_copay_amount(pps_comment: str) -> Optional[Decimal]:
    """
    Get copay amount if specified in PPS Comment.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        Copay amount as Decimal, or None if not specified
    """
    return config.extract_copay_amount(pps_comment)


def get_special_cases(pps_comment: str) -> dict:
    """
    Detect all special cases in PPS Comment.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        Dictionary mapping special case names to True/False
    """
    return config.detect_special_cases(pps_comment)


@dataclass
class ServiceRecord:
    """A single service/appointment record from input data."""
    mrn: str
    service_date: date
    service_type: str
    duration_mins: int
    location: str
    pps_comment: str
    provider: str
    supervisor: Optional[str] = None
    status: str = ""
    note_status: str = ""
    physical_proc: str = ""
    financial_div: str = ""
    funding: str = ""
    comments: str = ""
    group_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    def __post_init__(self):
        """Parse date if string."""
        if isinstance(self.service_date, str):
            # Try multiple date formats
            for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"]:
                try:
                    self.service_date = datetime.strptime(self.service_date, fmt).date()
                    break
                except ValueError:
                    continue

    @property
    def is_telehealth(self) -> bool:
        """Check if this is a telehealth service.

        Telehealth is determined by:
        1. Service type starting with "Telemed:" (e.g., "Telemed: IOP")
        2. Location containing "telehealth"

        Note: "Telemed: Y" in PPS comment indicates telehealth availability,
        not that this specific service was telehealth.
        """
        service_lower = self.service_type.lower()
        location_lower = self.location.lower() if self.location else ""

        # Check if service type explicitly indicates telehealth
        # e.g., "Telemed: IOP", "Telemed: Outpatient 16-37 minute"
        return (
            service_lower.startswith("telemed") or
            "telehealth" in location_lower
        )

    @property
    def duration_code(self) -> str:
        """Get duration code based on service duration (e.g., '53+', '16-37').

        Duration codes only apply to IT/Outpatient services, not IOP, Group, etc.
        """
        service_lower = self.service_type.lower()

        # Duration codes only apply to IT/Outpatient services
        if not ("outpatient" in service_lower or "it" in service_lower or "individual" in service_lower):
            # Check if it's not IOP, Group, Assessment, etc.
            if any(x in service_lower for x in ["iop", "group", "assessment", "psych", "emdr", "family", "ft"]):
                return ""

        # Check if duration code is in service type already
        service_type = self.service_type
        if "53+" in service_type or "53-" in service_type:
            return "53+"
        if "16-37" in service_type:
            return "16-37"
        if "38-52" in service_type:
            return "38-52"

        # Determine from duration_mins for IT/Outpatient services
        if "outpatient" in service_lower or "it" in service_lower or "individual" in service_lower:
            if self.duration_mins >= 53:
                return "53+"
            elif self.duration_mins >= 38:
                return ""  # Standard session, no suffix needed
            elif self.duration_mins >= 16:
                return "16-37"

        return ""

    @property
    def short_service_type(self) -> str:
        """Get abbreviated service type for payment comments."""
        service_lower = self.service_type.lower()

        if "iop" in service_lower:
            return "IOP"
        elif "assessment" in service_lower:
            return "Assessment"
        elif "psych eval" in service_lower:
            return "Psych Eval"
        elif "emdr" in service_lower:
            return "EMDR"
        elif "group" in service_lower:
            return "Group"
        elif "family" in service_lower or ("ft" in service_lower and "outpatient" not in service_lower):
            return "FT"
        elif "outpatient" in service_lower or "individual" in service_lower or "it" in service_lower:
            return "IT"
        else:
            return "IT"

    @property
    def is_bundled(self) -> bool:
        """Check if this service is bundled with IOP (no separate charge).

        When PPS comment has "In Network:" and Physical Program has "IOP",
        IT and FT services are bundled with IOP and not charged separately.
        """
        return is_bundled_with_iop(self.pps_comment, self.physical_proc, self.service_type)


@dataclass
class BillingLineItem:
    """A single line item in the billing output."""
    client_name: str
    mrn: str
    date_of_service: date
    service_type: str
    payment_date: Optional[date]
    charge_amount: Decimal
    payment_type: str = ""
    receipt_saved: str = ""
    comment: str = ""

    # Calculation details
    full_rate: Decimal = Decimal("0.00")
    applied_to_deductible: Decimal = Decimal("0.00")
    coinsurance_amount: Decimal = Decimal("0.00")
    deductible_remaining_after: Decimal = Decimal("0.00")
    oop_remaining_after: Decimal = Decimal("0.00")

    # Service details for payment comment generation
    is_telehealth: bool = False
    duration_code: str = ""
    short_service_type: str = ""

    # Self-pay indicator (for virtual services with no virtual benefits)
    is_self_pay: bool = False

    # Bundled indicator (IT/FT bundled with IOP when In Network)
    is_bundled: bool = False

    # Updated PPS comment (with new OOP/deductible values after this charge)
    # Empty if self-pay or bundled (these don't affect OOP/deductible)
    updated_pps_comment: str = ""

    def generate_payment_comment(self, payment_date: Optional[date] = None) -> str:
        """
        Generate a payment comment in the format: $amount date [Tele] service [duration] [SP|Bundled]

        Examples:
            - "$200.00 1/26 Tele IOP"
            - "$173.00 1/26 IOP"
            - "$330.00 1/26 IT 53+"
            - "$25.00 1/26 Tele IT 16-37"
            - "$295.00 1/26 Tele IOP SP" (self-pay, no virtual benefits)
            - "$0.00 1/26 IT Bundled" (IT bundled with IOP, no charge)

        Args:
            payment_date: Optional payment date to use (defaults to date_of_service)

        Returns:
            Formatted payment comment string
        """
        # Use provided payment date or fall back to service date
        comment_date = payment_date or self.payment_date or self.date_of_service

        # Format date as M/DD (no leading zero on month)
        date_str = f"{comment_date.month}/{comment_date.day}"

        # Build the comment parts
        parts = [f"${self.charge_amount:,.2f}", date_str]

        # Add Tele prefix if telehealth
        if self.is_telehealth:
            parts.append("Tele")

        # Add service type
        service = self.short_service_type or self._derive_short_service_type()
        parts.append(service)

        # Add duration code if present (for IT/Outpatient services)
        if self.duration_code:
            parts.append(self.duration_code)

        # Add SP suffix for self-pay (no virtual benefits)
        if self.is_self_pay:
            parts.append("SP")

        # Add Bundled suffix for services bundled with IOP
        if self.is_bundled:
            parts.append("Bundled")

        return " ".join(parts)

    def _derive_short_service_type(self) -> str:
        """Derive short service type from full service type."""
        service_lower = self.service_type.lower()

        if "iop" in service_lower:
            return "IOP"
        elif "assessment" in service_lower:
            return "Assessment"
        elif "psych eval" in service_lower:
            return "Psych Eval"
        elif "emdr" in service_lower:
            return "EMDR"
        elif "group" in service_lower:
            return "Group"
        elif "family" in service_lower or ("ft" in service_lower and "outpatient" not in service_lower):
            return "FT"
        elif "outpatient" in service_lower or "individual" in service_lower or "it" in service_lower:
            return "IT"
        else:
            return "IT"


@dataclass
class Client:
    """Client information with insurance details."""
    name: str
    mrn: str
    insurance_plan: InsurancePlan

    # Service tracking for comment generation
    services_applied: list = field(default_factory=list)

    def add_service_to_tracking(self, dos: date, service_type: str):
        """Track services applied to deductible for comment generation."""
        self.services_applied.append({
            "date": dos,
            "service_type": service_type
        })

    def generate_tracking_comment(self) -> str:
        """Generate the tracking comment showing deductible progress."""
        if not self.services_applied:
            return ""

        # Group by service type
        service_groups = {}
        for svc in self.services_applied:
            stype = self._categorize_service(svc["service_type"])
            if stype not in service_groups:
                service_groups[stype] = []
            service_groups[stype].append(svc["date"])

        # Build comment
        parts = [f"${self.insurance_plan.deductible_met:,.2f}"]

        for stype, dates in service_groups.items():
            date_strs = [d.strftime("%-m/%-d") for d in sorted(dates)]
            parts.append(f"{', '.join(date_strs)} {stype}")

        return " ".join(parts)

    def _categorize_service(self, service_type: str) -> str:
        """Categorize service type for tracking comment."""
        service_lower = service_type.lower()
        if "iop" in service_lower:
            return "IOP"
        elif "psych eval" in service_lower:
            return "Psych Eval"
        elif "emdr" in service_lower:
            return "EMDR"
        elif "telemed" in service_lower:
            return "Telemed"
        elif "outpatient" in service_lower:
            return "IT"
        elif "group" in service_lower:
            return "Group"
        elif "family" in service_lower:
            return "FT"
        else:
            return "IT"


def parse_pps_comment(comment: str) -> dict:
    """
    Parse PPS comment into structured components.
    
    Expected format example:
    "$1,670/$3,500 deductible / $14,000 OOP (combine) used as of 1/23 | 40% coinsurance | Ins Renews 1/2027"
    
    Args:
        comment: PPS comment string
        
    Returns:
        Dictionary with parsed components:
        - deductible_met: Decimal
        - deductible_total: Decimal
        - oop_accumulated: Decimal
        - oop_max: Decimal
        - as_of_date: str (M/D format)
        - coinsurance_rate: str (e.g., "40%")
        - renewal_date: str
        - other_parts: list of str (any other pipe-separated parts)
    """
    result = {
        'deductible_met': None,
        'deductible_total': None,
        'oop_accumulated': None,
        'oop_max': None,
        'as_of_date': None,
        'coinsurance_rate': None,
        'renewal_date': None,
        'other_parts': []
    }
    
    if not comment:
        return result
    
    # Parse deductible: $X,XXX/$X,XXX deductible
    ded_pattern = r'\$\s*([\d,]+(?:\.\d{2})?)\s*/\s*\$?\s*([\d,]+(?:\.\d{2})?)\s*deductible'
    ded_match = re.search(ded_pattern, comment, re.IGNORECASE)
    if ded_match:
        try:
            result['deductible_met'] = Decimal(ded_match.group(1).replace(',', ''))
            result['deductible_total'] = Decimal(ded_match.group(2).replace(',', ''))
        except (ValueError, decimal.InvalidOperation):
            pass
    
    # Parse OOP: $X,XXX OOP (combine) used as of M/D
    # or: $X,XXX/$X,XXX OOP used as of M/D
    oop_pattern1 = r'\$\s*([\d,]+(?:\.\d{2})?)\s*/\s*\$?\s*([\d,]+(?:\.\d{2})?)\s*OOP(?:\s*\(combine\))?\s+used\s+as\s+of\s+(\d{1,2}/\d{1,2})'
    oop_match1 = re.search(oop_pattern1, comment, re.IGNORECASE)
    if oop_match1:
        try:
            result['oop_accumulated'] = Decimal(oop_match1.group(1).replace(',', ''))
            result['oop_max'] = Decimal(oop_match1.group(2).replace(',', ''))
            result['as_of_date'] = oop_match1.group(3)
        except (ValueError, decimal.InvalidOperation):
            pass
    else:
        # Try format without accumulated amount: /$X,XXX OOP (combine) used as of M/D
        oop_pattern2 = r'/\s*\$?\s*([\d,]+(?:\.\d{2})?)\s*OOP\s*\(combine\)\s+used\s+as\s+of\s+(\d{1,2}/\d{1,2})'
        oop_match2 = re.search(oop_pattern2, comment, re.IGNORECASE)
        if oop_match2:
            try:
                result['oop_max'] = Decimal(oop_match2.group(1).replace(',', ''))
                result['as_of_date'] = oop_match2.group(2)
            except (ValueError, decimal.InvalidOperation):
                pass
    
    # Parse coinsurance rate: XX% coinsurance
    coins_pattern = r'(\d+)%\s*coinsurance'
    coins_match = re.search(coins_pattern, comment, re.IGNORECASE)
    if coins_match:
        result['coinsurance_rate'] = f"{coins_match.group(1)}%"
    
    # Parse renewal date: Ins Renews M/YYYY or similar
    renewal_pattern = r'Ins(?:urance)?\s+Renews?\s+(\d{1,2}/\d{4})'
    renewal_match = re.search(renewal_pattern, comment, re.IGNORECASE)
    if renewal_match:
        result['renewal_date'] = renewal_match.group(1)
    
    # Extract other pipe-separated parts that aren't the main components
    parts = [p.strip() for p in comment.split('|')]
    for part in parts:
        # Skip parts we've already parsed
        if any([
            'deductible' in part.lower(),
            'oop' in part.lower() and 'used as of' in part.lower(),
            'coinsurance' in part.lower(),
            'renew' in part.lower()
        ]):
            continue
        if part:
            result['other_parts'].append(part)
    
    return result


def format_updated_pps_comment(
    parsed: dict,
    new_deductible: Optional[Decimal] = None,
    new_oop: Optional[Decimal] = None,
    as_of_date: Optional[date] = None
) -> str:
    """
    Format an updated PPS comment with new deductible and OOP values.
    
    Args:
        parsed: Dictionary from parse_pps_comment()
        new_deductible: New deductible met amount (or None to keep existing)
        new_oop: New OOP accumulated amount (or None to keep existing)
        as_of_date: New as-of date (or None to keep existing)
        
    Returns:
        Formatted PPS comment string
    """
    parts = []
    
    # Add deductible section if present
    if parsed['deductible_met'] is not None and parsed['deductible_total'] is not None:
        ded_met = new_deductible if new_deductible is not None else parsed['deductible_met']
        ded_total = parsed['deductible_total']
        
        # Format with commas but no decimals if whole number
        if ded_met == ded_met.to_integral_value():
            ded_met_str = f"${int(ded_met):,}"
        else:
            ded_met_str = f"${ded_met:,.2f}"
        
        if ded_total == ded_total.to_integral_value():
            ded_total_str = f"${int(ded_total):,}"
        else:
            ded_total_str = f"${ded_total:,.2f}"
        
        parts.append(f"{ded_met_str}/{ded_total_str} deductible")
    
    # Add OOP section if present
    if parsed['oop_max'] is not None:
        oop_max = parsed['oop_max']
        # Format date - use provided date or fall back to parsed date
        if as_of_date:
            date_str = f"{as_of_date.month}/{as_of_date.day}"
        else:
            date_str = parsed['as_of_date'] if parsed['as_of_date'] else "unknown"
        
        if parsed['oop_accumulated'] is not None:
            oop_acc = new_oop if new_oop is not None else parsed['oop_accumulated']
            
            # Format with commas
            if oop_acc == oop_acc.to_integral_value():
                oop_acc_str = f"${int(oop_acc):,}"
            else:
                oop_acc_str = f"${oop_acc:,.2f}"
            
            if oop_max == oop_max.to_integral_value():
                oop_max_str = f"${int(oop_max):,}"
            else:
                oop_max_str = f"${oop_max:,.2f}"
            
            parts.append(f"{oop_acc_str}/{oop_max_str} OOP used as of {date_str}")
        else:
            # Format without accumulated (combine format)
            if oop_max == oop_max.to_integral_value():
                oop_max_str = f"${int(oop_max):,}"
            else:
                oop_max_str = f"${oop_max:,.2f}"
            
            parts.append(f"/{oop_max_str} OOP (combine) used as of {date_str}")
    
    # Add coinsurance if present
    if parsed['coinsurance_rate']:
        parts.append(f"{parsed['coinsurance_rate']} coinsurance")
    
    # Add renewal date if present
    if parsed['renewal_date']:
        parts.append(f"Ins Renews {parsed['renewal_date']}")
    
    # Add any other parts
    parts.extend(parsed['other_parts'])
    
    return " | ".join(parts)


def generate_combined_comment(
    services: list,
    total_charge: Decimal,
    service_date: date
) -> str:
    """
    Generate a combined comment for multiple services on the same date.
    
    Format: ${total} {month}/{day} {service1} & {service2} & ...
    
    Args:
        services: List of ServiceRecord objects
        total_charge: Total charge amount for all services
        service_date: Date of service
        
    Returns:
        Combined comment string
    """
    # Get abbreviated service names
    service_abbrevs = []
    is_telehealth = False
    is_nsf = False
    
    for service in services:
        abbrev = get_service_abbreviation(service.service_type)
        
        # Check if any service is telehealth or NSF
        if service.service_type.startswith("Telemed:") or service.is_telehealth:
            is_telehealth = True
        if service.service_type.startswith("NSF"):
            is_nsf = True
        
        # Remove "Tele" and "NSF" from individual abbreviations
        # We'll add them once at the beginning/end
        abbrev = abbrev.replace("Tele ", "").replace(" NSF", "")
        
        if abbrev not in service_abbrevs:
            service_abbrevs.append(abbrev)
    
    # Build comment parts
    parts = [f"${total_charge:,.2f}", f"{service_date.month}/{service_date.day}"]
    
    if is_telehealth:
        parts.append("Tele")
    
    parts.append(" & ".join(service_abbrevs))
    
    if is_nsf:
        parts.append("NSF")
    
    return " ".join(parts)
