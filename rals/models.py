"""Data models for insurance billing calculations."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from enum import Enum


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
        """Get the appropriate rate for a service type."""
        service_lower = service_type.lower()

        if "assessment" in service_lower:
            return self.assessment_rate if self.assessment_rate > 0 else self.it_rate
        elif "iop" in service_lower:
            return self.iop_rate
        elif "emdr" in service_lower:
            return self.emdr_rate if self.emdr_rate > 0 else self.it_rate
        elif "telemed" in service_lower and "psych" in service_lower:
            return self.psych_followup_rate if self.psych_followup_rate > 0 else self.telemed_rate
        elif "outpatient" in service_lower and "53" in service_lower:
            return self.it_rate  # Outpatient 53+ maps to IT rate
        elif "outpatient" in service_lower:
            return self.it_rate
        elif "psych eval" in service_lower:
            return self.psych_eval_rate
        elif "group" in service_lower:
            return self.group_rate
        elif "family" in service_lower or "ft" in service_lower:
            return self.ft_rate
        elif "individual" in service_lower or "it" in service_lower:
            return self.it_rate
        else:
            # Default to IT rate
            return self.it_rate


# Default self-pay rates for virtual services (when client has no virtual benefits)
# Used when PPS comment indicates "SP rates for virtual", "SP for virtual", etc.
SELF_PAY_VIRTUAL_RATES = RateSchedule(
    assessment_rate=Decimal("450.00"),
    iop_rate=Decimal("295.00"),
    group_rate=Decimal("175.00"),
    it_rate=Decimal("175.00"),
    ft_rate=Decimal("275.00"),
    psych_eval_rate=Decimal("675.00"),
    psych_followup_rate=Decimal("200.00"),
    mat_rate=Decimal("200.00"),
)


def is_self_pay_virtual(pps_comment: str) -> bool:
    """
    Check if the PPS comment indicates self-pay rates for virtual services.

    This occurs when the client has no virtual/telehealth benefits.
    Patterns: "SP rates for virtual", "SP for virtual", "Self Pay rates for virtual", etc.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        True if self-pay rates apply for virtual services
    """
    if not pps_comment:
        return False

    pps_lower = pps_comment.lower()

    # Check for various patterns indicating self-pay for virtual
    sp_patterns = [
        "sp rates for virtual",
        "sp for virtual",
        "self pay rates for virtual",
        "self pay for virtual",
        "self-pay rates for virtual",
        "self-pay for virtual",
        "(sp rates for virtual)",
        "(sp for virtual)",
        "(self pay rates for virtual)",
        "(self pay for virtual)",
    ]

    return any(pattern in pps_lower for pattern in sp_patterns)


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

    # Updated PPS comment (with new OOP/deductible values after this charge)
    # Empty if self-pay (self-pay charges don't affect OOP/deductible)
    updated_pps_comment: str = ""

    def generate_payment_comment(self, payment_date: Optional[date] = None) -> str:
        """
        Generate a payment comment in the format: $amount date [Tele] service [duration] [SP]

        Examples:
            - "$200.00 1/26 Tele IOP"
            - "$173.00 1/26 IOP"
            - "$330.00 1/26 IT 53+"
            - "$25.00 1/26 Tele IT 16-37"
            - "$295.00 1/26 Tele IOP SP" (self-pay, no virtual benefits)

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
