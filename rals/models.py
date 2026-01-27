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
    iop_rate: Decimal = Decimal("0.00")
    group_rate: Decimal = Decimal("0.00")
    it_rate: Decimal = Decimal("0.00")  # Individual Therapy
    ft_rate: Decimal = Decimal("0.00")  # Family Therapy
    psych_eval_rate: Decimal = Decimal("0.00")
    psych_followup_rate: Decimal = Decimal("0.00")  # "Psych flu" = Psych follow-up
    emdr_rate: Decimal = Decimal("0.00")
    telemed_rate: Decimal = Decimal("0.00")

    def get_rate_for_service(self, service_type: str) -> Decimal:
        """Get the appropriate rate for a service type."""
        service_lower = service_type.lower()

        if "iop" in service_lower:
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
