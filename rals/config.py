"""
Centralized domain knowledge configuration for RALS billing system.

This file contains all the terminology mappings, parsing rules, and special case
definitions that encode "biller knowledge" - the institutional understanding of
how spreadsheet data maps to billing logic.

To add new terms or rules, update the appropriate dictionary below.
No code changes should be needed for most terminology additions.
"""

import re
from decimal import Decimal
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field


# =============================================================================
# SERVICE TYPE MAPPINGS
# =============================================================================
# Maps service names (Column D) to their rate key in PPS Comment
# The rate key is what appears before the $ amount (e.g., "IT $260" -> rate_key = "IT")

SERVICE_TO_RATE_KEY: Dict[str, str] = {
    # Individual Therapy (IT) services - map to "IT" rate
    "Outpatient 53+": "IT",
    "Outpatient 38-52 minutes": "IT",
    "Outpatient 16-37 minutes": "IT",  # Half-rate applies
    "Outpatient EMDR 53+": "IT",
    "Outpatient EMDR 53+ minutes": "IT",
    "Individual Therapy": "IT",
    "IT": "IT",

    # Telemed IT variants
    "Telemed: Outpatient 53+": "IT",
    "Telemed: Outpatient 38-52 minutes": "IT",
    "Telemed: Outpatient 16-37 minutes": "IT",
    "Telemed: Outpatient EMDR 53+": "IT",

    # IOP services - map to "IOP" rate
    "IOP-Wilton": "IOP",
    "IOP Huntington": "IOP",
    "IOP": "IOP",
    "Telemed: IOP": "IOP",
    "Telemed: IOP-Wilton": "IOP",

    # Group services - map to "Group" rate
    "Outpatient Group (75-90 minutes)": "Group",
    "Outpatient Group (75-90 r": "Group",  # Truncated version
    "Group": "Group",
    "Group Therapy": "Group",

    # Family Therapy (FT) services - map to "FT" rate
    "Family Session with Client 26+ minutes": "FT",
    "Family Session 26+ minutes": "FT",
    "Family Therapy": "FT",
    "FT": "FT",
    "Telemed: Family Session with Client 26+ minutes": "FT",

    # Psychiatric services
    "Psychiatric Diag. Eval. W. Med Services": "Psych Eval",
    "Psychiatric Diag. Eval.": "Psych Eval",
    "Psych Eval": "Psych Eval",
    "OP: Psych Appointment (30-39 minutes)": "Psych f/u",
    "OP: Psych Appointment (20-29 minutes)": "Psych f/u",  # Half-rate applies
    "Telemed OP: Psych Appointment (30-39 minutes)": "Psych f/u",
    "Telemed OP: Psych Appointment (20-29 minutes)": "Psych f/u",  # Half-rate

    # Assessment services - map to "Assessment" rate
    "Assessment/Diag (BPS) w/o med services": "Assessment",
    "Assessment": "Assessment",
    "Telemed: Assessment/Diag (BPS) w/o med services": "Assessment",
    "Telemed: Assessment/D": "Assessment",  # Truncated

    # MAT services
    "Medication Admin/Injection": "MAT",
    "MAT": "MAT",
    "MATS": "MAT",

    # Drug screens - typically non-billable or special handling
    "Drug Screen 13 Panel OF": "Drug Screen",
    "Drug Screen": "Drug Screen",
}

# Rate key to attribute name mapping (for RateSchedule)
RATE_KEY_TO_ATTRIBUTE: Dict[str, str] = {
    "IT": "it_rate",
    "IOP": "iop_rate",
    "Group": "group_rate",
    "FT": "ft_rate",
    "Psych Eval": "psych_eval_rate",
    "Psych f/u": "psych_followup_rate",
    "Psych flu": "psych_followup_rate",  # Alternative spelling
    "Assessment": "assessment_rate",
    "MAT": "mat_rate",
    "MATS": "mat_rate",
    "Telemed": "telemed_rate",
    "EMDR": "emdr_rate",
    "OP/IT": "it_rate",  # Alias
    "Intake": "assessment_rate",  # Alias
    "Fam": "ft_rate",  # Alias
}


# =============================================================================
# SERVICE ABBREVIATIONS FOR OUTPUT
# =============================================================================
# Maps full service names to abbreviated versions for billing comments
# Used when generating payment comments like "$200.00 1/26 Tele IOP"

SERVICE_ABBREVIATIONS: Dict[str, str] = {
    # IOP
    "Telemed: IOP": "IOP",
    "Telemed: IOP-Wilton": "IOP",
    "IOP-Wilton": "IOP",
    "IOP Huntington": "IOP",
    "IOP": "IOP",

    # IT/Outpatient
    "Telemed: Outpatient 53+": "IT 53+",
    "Outpatient 53+": "IT 53+",
    "Outpatient 16-37 minutes": "IT 16-37",
    "Outpatient 38-52 minutes": "IT 38-52",
    "Telemed: Outpatient 16-37 minutes": "IT 16-37",
    "Telemed: Outpatient 38-52 minutes": "IT 38-52",
    "Outpatient EMDR 53+": "EMDR 53+",
    "Outpatient EMDR 53+ minutes": "EMDR 53+",
    "Telemed: Outpatient EMDR 53+": "EMDR 53+",

    # Psych
    "Psychiatric Diag. Eval. W. Med Services": "Psych Eval",
    "Psychiatric Diag. Eval.": "Psych Eval",
    "OP: Psych Appointment (30-39 minutes)": "Psych f/u",
    "OP: Psych Appointment (20-29 minutes)": "Psych f/u",
    "Telemed OP: Psych Appointment (30-39 minutes)": "Psych f/u",
    "Telemed OP: Psych Appointment (20-29 minutes)": "Psych f/u",

    # Assessment
    "Assessment/Diag (BPS) w/o med services": "Assess",
    "Telemed: Assessment/Diag (BPS) w/o med services": "Assess",

    # Group
    "Outpatient Group (75-90 minutes)": "Group",
    "Outpatient Group (75-90 r": "Group",

    # Family
    "Family Session with Client 26+ minutes": "FT",
    "Family Session 26+ minutes": "FT",
    "Telemed: Family Session with Client 26+ minutes": "FT",

    # MAT
    "Medication Admin/Injection": "MAT",

    # Non-billable (for reference)
    "RC Client Call": "RC Call",
    "Drug Screen 13 Panel OF": "Drug Screen",
}


# =============================================================================
# NON-BILLABLE SERVICES
# =============================================================================
# Services that should always be $0 charge
# Can be exact matches or patterns (regex)
# NOTE: No Shows (NSF) are NOT non-billable - they are billed at self-pay rates

NON_BILLABLE_SERVICES_EXACT: List[str] = [
    "RC Client Call",
    "Cancelled",
    "Late Cancel",
]

NON_BILLABLE_SERVICES_PATTERNS: List[str] = [
    r"^RC\s+",  # Anything starting with "RC "
    r"Cancel",
    r"Late\s+Cancel",
    r"Drug\s+Screen",  # Drug screens typically non-billable to client
    r"\*PP\s+Unsigned\*",  # Unsigned paperwork
    r"\*Unsigned\s+PP\*",
]


# =============================================================================
# NO SHOW FEE (NSF) RATES
# =============================================================================
# No Shows are always billed at self-pay rates, regardless of insurance status.
# NSF services are identified by "NSF" prefix in service type.

NSF_RATES: Dict[str, Decimal] = {
    # IOP and Group NSF: Always $25.00 flat fee
    "iop_rate": Decimal("25.00"),
    "group_rate": Decimal("25.00"),

    # All psych appointments (including evals): $200 flat
    "psych_eval_rate": Decimal("200.00"),
    "psych_followup_rate": Decimal("200.00"),

    # Assessment/Intake: $200
    "assessment_rate": Decimal("200.00"),

    # IT full length (38+ minutes): $175
    "it_rate": Decimal("175.00"),

    # IT short (16-37 minutes): $87.50
    "it_rate_short": Decimal("87.50"),

    # FT: Use standard self-pay rate
    "ft_rate": Decimal("275.00"),

    # MAT: Use standard self-pay rate
    "mat_rate": Decimal("200.00"),

    # EMDR: Same as IT
    "emdr_rate": Decimal("175.00"),
}


def is_nsf_service(service_type: str) -> bool:
    """Check if this is a No Show Fee (NSF) service."""
    if not service_type:
        return False
    return service_type.upper().startswith("NSF") or " NSF" in service_type.upper()


def get_nsf_rate(service_type: str) -> Decimal:
    """
    Get the NSF rate for a service type.

    NSF services are always billed at self-pay rates:
    - IOP/Group: $25.00
    - Psych (any): $200.00
    - Assessment: $200.00
    - IT full (38+): $175.00
    - IT short (16-37): $87.50

    Args:
        service_type: The service type (with or without NSF prefix)

    Returns:
        The NSF rate for this service
    """
    service_lower = service_type.lower()

    # Remove NSF prefix for matching
    clean_service = re.sub(r'^nsf\s*', '', service_lower, flags=re.IGNORECASE).strip()

    # IOP and Group: Always $25
    if "iop" in clean_service:
        return NSF_RATES["iop_rate"]
    if "group" in clean_service:
        return NSF_RATES["group_rate"]

    # All psych appointments (including evals): $200
    if "psych" in clean_service:
        return NSF_RATES["psych_eval_rate"]  # Same rate for eval and f/u

    # Assessment/Intake: $200
    if "assessment" in clean_service or "intake" in clean_service:
        return NSF_RATES["assessment_rate"]

    # IT short (16-37 minutes): $87.50
    if "16-37" in clean_service:
        return NSF_RATES["it_rate_short"]

    # IT/Outpatient full length: $175
    if "outpatient" in clean_service or "individual" in clean_service or clean_service.startswith("it"):
        return NSF_RATES["it_rate"]

    # Family therapy
    if "family" in clean_service or clean_service.startswith("ft"):
        return NSF_RATES["ft_rate"]

    # MAT
    if "medication" in clean_service or "mat" in clean_service:
        return NSF_RATES["mat_rate"]

    # EMDR
    if "emdr" in clean_service:
        return NSF_RATES["emdr_rate"]

    # Default to IT rate
    return NSF_RATES["it_rate"]


# =============================================================================
# HALF-RATE RULES
# =============================================================================
# Services that should be charged at half the normal rate
# Based on shorter appointment durations

HALF_RATE_PATTERNS: List[Tuple[str, str]] = [
    # (pattern to match in service type, rate_key affected)
    (r"16-37", "IT"),  # IT 16-37 minutes = half IT rate
    (r"20-29.*[Pp]sych", "Psych f/u"),  # Psych 20-29 min = half psych f/u rate
    (r"[Pp]sych.*20-29", "Psych f/u"),  # Alternative order
]


# =============================================================================
# SPECIAL CASE INDICATORS
# =============================================================================
# Patterns in PPS Comment that indicate special billing scenarios

@dataclass
class SpecialCasePattern:
    """Definition of a special case pattern to detect in PPS Comment."""
    name: str
    patterns: List[str]  # Regex patterns (case-insensitive)
    description: str
    billing_impact: str  # What happens to billing


SPECIAL_CASES: List[SpecialCasePattern] = [
    # Self-Pay for Virtual
    SpecialCasePattern(
        name="self_pay_virtual",
        patterns=[
            r"SP\s+rates?\s+for\s+virtual",
            r"Self[- ]?Pay\s+rates?\s+for\s+virtual",
            r"\(SP\s+for\s+virtual\)",
            r"Telemed:\s*Self[- ]?Pay",
        ],
        description="Client has no virtual/telehealth benefits",
        billing_impact="Use self-pay rates for telehealth services; does NOT count toward deductible/OOP"
    ),

    # Paid in Full (PIF)
    SpecialCasePattern(
        name="paid_in_full",
        patterns=[
            r"\b\d{4}\s+PIF\b",  # e.g., "2026 PIF"
            r"\bPIF\b",
            r"Paid\s+[Ii]n\s+[Ff]ull",
        ],
        description="Client has paid in full for the year",
        billing_impact="No charges for services; $0 for all"
    ),

    # In Network
    SpecialCasePattern(
        name="in_network",
        patterns=[
            r"^In\s+Network:",
            r"\bIn\s+Network:",
        ],
        description="In-network insurance rates apply",
        billing_impact="Use in-network rates from PPS Comment"
    ),

    # Self-Pay (general)
    SpecialCasePattern(
        name="self_pay",
        patterns=[
            r"\|\s*Self[- ]?Pay\s*$",
            r"Telemed:\s*Self[- ]?Pay\s*$",
            r":\s*Self[- ]?Pay\s*$",
        ],
        description="Client is self-pay (no insurance)",
        billing_impact="Use self-pay rate schedule"
    ),

    # Payment Plan
    SpecialCasePattern(
        name="payment_plan",
        patterns=[
            r"Payment\s+plan\s+\$[\d,]+/month",
            r"\$[\d,]+/month\s+for\s+\d+\s+months",
        ],
        description="Client has a payment plan arrangement",
        billing_impact="Fixed monthly payment; may affect per-service billing"
    ),

    # Fixed Per-Session Rate
    SpecialCasePattern(
        name="fixed_session_rate",
        patterns=[
            r"\$\d+\s+per\s+session",
            r"per\s+session\s*[:\|]\s*\$\d+",
        ],
        description="Client pays fixed amount per session",
        billing_impact="Use fixed rate instead of calculated amount"
    ),

    # Copay Plan
    SpecialCasePattern(
        name="copay",
        patterns=[
            r"OP\s+LOC\s+\$\d+\s+copay",
            r"\$\d+\s+copay",
            r"copay\s*[:\|]\s*\$\d+",
        ],
        description="Client has copay (fixed amount per visit)",
        billing_impact="Charge copay amount; counts toward OOP but NOT deductible"
    ),

    # Deductible then Covered 100%
    SpecialCasePattern(
        name="deductible_then_covered",
        patterns=[
            r"deductible,?\s+then\s+covered\s+100%",
            r"after\s+deductible\s+covered\s+100%",
        ],
        description="After deductible met, insurance covers 100%",
        billing_impact="0% coinsurance after deductible"
    ),

    # IOP LOC Covered 100%
    SpecialCasePattern(
        name="iop_covered_100",
        patterns=[
            r"IOP\s+LOC\s+covered\s+100%",
            r"IOP.*covered\s+100%",
        ],
        description="IOP level of care is fully covered",
        billing_impact="$0 for IOP services"
    ),

    # Unsigned Paperwork
    SpecialCasePattern(
        name="unsigned_paperwork",
        patterns=[
            r"\*PP\s+Unsigned\*",
            r"\*Unsigned\s+PP\*",
            r"PP\s+Unsigned",
        ],
        description="Client paperwork not yet signed",
        billing_impact="May need to hold billing"
    ),

    # Bundled with IOP (In Network + IOP program)
    SpecialCasePattern(
        name="bundled_iop",
        patterns=[
            r"In\s+Network:.*IOP",
        ],
        description="IT/FT services bundled with IOP (no separate charge)",
        billing_impact="$0 for IT/FT when in IOP program"
    ),
]


def detect_special_cases(pps_comment: str) -> Dict[str, bool]:
    """
    Detect which special cases apply based on PPS Comment.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        Dictionary mapping special case names to True/False
    """
    if not pps_comment:
        return {case.name: False for case in SPECIAL_CASES}

    results = {}
    for case in SPECIAL_CASES:
        detected = False
        for pattern in case.patterns:
            if re.search(pattern, pps_comment, re.IGNORECASE):
                detected = True
                break
        results[case.name] = detected

    return results


# =============================================================================
# PPS COMMENT PARSING PATTERNS
# =============================================================================
# Regex patterns for extracting data from PPS Comment

class PPSPatterns:
    """Centralized regex patterns for PPS Comment parsing."""

    # Rate extraction: "ServiceType $XXX" or "ServiceType $X,XXX.XX"
    RATE_AMOUNT = r'\$\s*([\d,]+(?:\.\d{1,2})?)'

    # Deductible: "$X,XXX/$X,XXX deductible"
    DEDUCTIBLE = r'\$\s*([\d,]+(?:\.\d{1,2})?)\s*/\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*deductible'

    # OOP with used amount: "$X,XXX/$X,XXX OOP used as of M/D"
    OOP_USED = r'\$\s*([\d,]+(?:\.\d{1,2})?)\s*/\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*OOP(?:\s*\(combine\))?\s+used\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'

    # OOP combine format: "/$X,XXX OOP (combine) used as of M/D"
    OOP_COMBINE = r'/\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*OOP\s*\(combine\)\s+used\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'

    # OOPM format: "OOPM $X,XXX" or "OOPM $X,XXX: $XXX met as of M/D"
    OOPM = r'OOPM?\s*\$\s*([\d,]+(?:\.\d{1,2})?)'
    OOPM_WITH_MET = r'OOPM?\s*\$\s*([\d,]+(?:\.\d{1,2})?)\s*:\s*\$\s*([\d,]+(?:\.\d{1,2})?)\s*met\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'

    # Coinsurance: "XX% coinsurance"
    COINSURANCE = r'(\d+)%\s*coinsurance'

    # Insurance renewal: "Ins Renews M/YYYY"
    RENEWAL = r'Ins(?:urance)?\s+Renews?\s+(\d{1,2}/\d{4})'

    # Telehealth indicator: "Telemed: Y" or "Telemed: N"
    TELEMED_INDICATOR = r'Telemed:\s*([YN])'

    # Fixed per-session rate: "$XX per session"
    PER_SESSION = r'\$\s*(\d+(?:\.\d{2})?)\s+per\s+session'

    # Copay amount: "OP LOC $XX copay" or "$XX copay"
    COPAY = r'(?:OP\s+LOC\s+)?\$\s*(\d+(?:\.\d{2})?)\s*copay'

    # Payment plan: "Payment plan $X,XXX/month"
    PAYMENT_PLAN = r'Payment\s+plan\s+\$\s*([\d,]+(?:\.\d{2})?)/month(?:\s+for\s+(\d+)\s+months)?'

    # Service rates in PPS Comment (for parsing rate schedule)
    # Format: "ServiceType $XXX" where ServiceType is one of the known types
    RATE_TYPES = [
        (r'\bAssessment\b', 'assessment_rate'),
        (r'\bIntake\b', 'assessment_rate'),
        (r'\bIOP\b', 'iop_rate'),
        (r'\bGroup\b', 'group_rate'),
        (r'\bIT\b', 'it_rate'),
        (r'\bOP/IT\b', 'it_rate'),
        (r'\bFT\b', 'ft_rate'),
        (r'\bFam\b', 'ft_rate'),
        (r'\bPsych\s*Eval\b', 'psych_eval_rate'),
        (r'\bPsych\s*E\b', 'psych_eval_rate'),
        (r'\bPsych\s*flu\b', 'psych_followup_rate'),
        (r'\bPsych\s*f/u\b', 'psych_followup_rate'),
        (r'\bPsych\s*Follow\s*-?\s*up\b', 'psych_followup_rate'),
        (r'\bTelemed\b', 'telemed_rate'),
        (r'\bEMDR\b', 'emdr_rate'),
        (r'\bMATS?\b', 'mat_rate'),
    ]


# =============================================================================
# SELF-PAY RATE SCHEDULES
# =============================================================================
# Default rates for self-pay clients (same for virtual and in-person)

SELF_PAY_RATES: Dict[str, Decimal] = {
    "assessment_rate": Decimal("450.00"),
    "iop_rate": Decimal("295.00"),
    "group_rate": Decimal("175.00"),
    "it_rate": Decimal("175.00"),
    "ft_rate": Decimal("275.00"),
    "psych_eval_rate": Decimal("675.00"),
    "psych_followup_rate": Decimal("200.00"),
    "mat_rate": Decimal("200.00"),
    "emdr_rate": Decimal("175.00"),
    "telemed_rate": Decimal("175.00"),
}

# Virtual and in-person self-pay rates are identical
SELF_PAY_VIRTUAL_RATES: Dict[str, Decimal] = SELF_PAY_RATES.copy()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_rate_key_for_service(service_type: str) -> str:
    """
    Get the rate key (e.g., "IT", "IOP") for a service type.

    Args:
        service_type: The full service type name from Column D

    Returns:
        The rate key to look up in PPS Comment rates
    """
    if not service_type:
        return "IT"  # Default

    # Check exact match first
    if service_type in SERVICE_TO_RATE_KEY:
        return SERVICE_TO_RATE_KEY[service_type]

    # Strip common prefixes and check again
    clean_service = service_type
    for prefix in ["Telemed: ", "Telemed:", "NSF ", "NSF"]:
        if clean_service.startswith(prefix):
            clean_service = clean_service[len(prefix):].strip()

    if clean_service in SERVICE_TO_RATE_KEY:
        return SERVICE_TO_RATE_KEY[clean_service]

    # Fuzzy match based on keywords
    service_lower = service_type.lower()

    if "iop" in service_lower:
        return "IOP"
    if "group" in service_lower:
        return "Group"
    if "psych eval" in service_lower or ("psychiatric" in service_lower and "eval" in service_lower):
        return "Psych Eval"
    if "psych" in service_lower and any(x in service_lower for x in ["appointment", "f/u", "follow"]):
        return "Psych f/u"
    if "family" in service_lower or service_lower.startswith("ft"):
        return "FT"
    if "assessment" in service_lower or "intake" in service_lower:
        return "Assessment"
    if "medication" in service_lower or "mat" in service_lower or "injection" in service_lower:
        return "MAT"
    if "emdr" in service_lower:
        return "IT"  # EMDR uses IT rate
    if "outpatient" in service_lower or "individual" in service_lower:
        return "IT"

    # Default to IT
    return "IT"


def is_non_billable_service(service_type: str, pps_comment: str = "") -> bool:
    """
    Check if a service is non-billable.

    Args:
        service_type: The service type from Column D
        pps_comment: The PPS Comment (for additional context)

    Returns:
        True if the service should be $0
    """
    if not service_type:
        return False

    # Check exact matches
    if service_type in NON_BILLABLE_SERVICES_EXACT:
        return True

    # Check patterns
    for pattern in NON_BILLABLE_SERVICES_PATTERNS:
        if re.search(pattern, service_type, re.IGNORECASE):
            return True

    # Check PPS Comment for special indicators
    if pps_comment:
        special_cases = detect_special_cases(pps_comment)
        if special_cases.get("paid_in_full"):
            return True
        if special_cases.get("unsigned_paperwork"):
            # May want to flag but not necessarily non-billable
            pass

    return False


def should_apply_half_rate(service_type: str) -> bool:
    """
    Check if half-rate should be applied for this service.

    Args:
        service_type: The service type from Column D

    Returns:
        True if half-rate should be applied
    """
    if not service_type:
        return False

    for pattern, _ in HALF_RATE_PATTERNS:
        if re.search(pattern, service_type, re.IGNORECASE):
            return True

    return False


def extract_fixed_session_rate(pps_comment: str) -> Optional[Decimal]:
    """
    Extract fixed per-session rate from PPS Comment if present.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        The fixed rate as Decimal, or None if not found
    """
    if not pps_comment:
        return None

    match = re.search(PPSPatterns.PER_SESSION, pps_comment, re.IGNORECASE)
    if match:
        try:
            return Decimal(match.group(1).replace(",", ""))
        except:
            pass

    return None


def extract_copay_amount(pps_comment: str) -> Optional[Decimal]:
    """
    Extract copay amount from PPS Comment if present.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        The copay amount as Decimal, or None if not found
    """
    if not pps_comment:
        return None

    match = re.search(PPSPatterns.COPAY, pps_comment, re.IGNORECASE)
    if match:
        try:
            return Decimal(match.group(1).replace(",", ""))
        except:
            pass

    return None


def extract_coinsurance_rate(pps_comment: str) -> Optional[Decimal]:
    """
    Extract coinsurance rate from PPS Comment.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        Coinsurance rate as Decimal (e.g., 0.40 for 40%), or None if not found
    """
    if not pps_comment:
        return None

    match = re.search(PPSPatterns.COINSURANCE, pps_comment, re.IGNORECASE)
    if match:
        try:
            return Decimal(match.group(1)) / Decimal("100")
        except:
            pass

    return None


def extract_telemed_benefit(pps_comment: str) -> Optional[bool]:
    """
    Check if telehealth benefits are available based on PPS Comment.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        True if telehealth covered, False if not, None if not specified
    """
    if not pps_comment:
        return None

    match = re.search(PPSPatterns.TELEMED_INDICATOR, pps_comment, re.IGNORECASE)
    if match:
        return match.group(1).upper() == "Y"

    # Check for self-pay virtual indicator
    special_cases = detect_special_cases(pps_comment)
    if special_cases.get("self_pay_virtual"):
        return False

    return None


def parse_payment_plan(pps_comment: str) -> Optional[Dict[str, Any]]:
    """
    Extract payment plan details from PPS Comment.

    Args:
        pps_comment: The PPS Comment string

    Returns:
        Dictionary with 'monthly_amount' and optionally 'months', or None
    """
    if not pps_comment:
        return None

    match = re.search(PPSPatterns.PAYMENT_PLAN, pps_comment, re.IGNORECASE)
    if match:
        result = {
            "monthly_amount": Decimal(match.group(1).replace(",", ""))
        }
        if match.group(2):
            result["months"] = int(match.group(2))
        return result

    return None


def get_service_abbreviation(service_type: str) -> str:
    """
    Get abbreviated service name for billing comments.

    Handles special rules:
    - Services starting with "Telemed:" get "Tele" prefix
    - Services starting with "NSF" get "NSF" suffix

    Args:
        service_type: Full service type name

    Returns:
        Abbreviated service name for use in billing comments
    """
    if not service_type:
        return "IT"

    # Check exact match first
    if service_type in SERVICE_ABBREVIATIONS:
        abbrev = SERVICE_ABBREVIATIONS[service_type]

        # Add Tele prefix if original starts with "Telemed:"
        if service_type.startswith("Telemed:") and not abbrev.startswith("Tele"):
            return f"Tele {abbrev}"

        return abbrev

    # Handle NSF prefix/suffix
    has_nsf = service_type.startswith("NSF")
    clean_service = service_type.replace("NSF ", "").strip() if has_nsf else service_type

    # Handle Telemed prefix
    is_telemed = clean_service.startswith("Telemed:")
    if is_telemed:
        clean_service = clean_service.replace("Telemed:", "").strip()

    # Check cleaned service in mapping
    if clean_service in SERVICE_ABBREVIATIONS:
        abbrev = SERVICE_ABBREVIATIONS[clean_service]

        if is_telemed and not abbrev.startswith("Tele"):
            abbrev = f"Tele {abbrev}"
        if has_nsf:
            abbrev = f"{abbrev} NSF"

        return abbrev

    # Fallback: derive from keywords
    service_lower = clean_service.lower()

    if "iop" in service_lower:
        abbrev = "IOP"
    elif "psych eval" in service_lower or ("psychiatric" in service_lower and "eval" in service_lower):
        abbrev = "Psych Eval"
    elif "psych" in service_lower and ("appointment" in service_lower or "f/u" in service_lower or "follow" in service_lower):
        abbrev = "Psych f/u"
    elif "53+" in service_lower:
        abbrev = "IT 53+"
    elif "16-37" in service_lower:
        abbrev = "IT 16-37"
    elif "38-52" in service_lower:
        abbrev = "IT 38-52"
    elif "outpatient" in service_lower or "individual" in service_lower:
        abbrev = "IT"
    elif "assessment" in service_lower or "diag" in service_lower:
        abbrev = "Assess"
    elif "group" in service_lower:
        abbrev = "Group"
    elif "family" in service_lower:
        abbrev = "FT"
    elif "medication" in service_lower or "injection" in service_lower:
        abbrev = "MAT"
    elif "emdr" in service_lower:
        abbrev = "EMDR"
    else:
        abbrev = "IT"

    # Add prefixes/suffixes
    if is_telemed and not abbrev.startswith("Tele"):
        abbrev = f"Tele {abbrev}"
    if has_nsf:
        abbrev = f"{abbrev} NSF"

    return abbrev
