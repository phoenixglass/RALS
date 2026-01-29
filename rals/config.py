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

    # EMDR variants (use IT rate)
    "Outpatient - EMDR 38-52 minutes": "IT",
    "Outpatient EMDR 38-52 minutes": "IT",

    # Crisis Psychotherapy (use IT rate)
    "Crisis Psychotherapy 30-60min": "IT",
    "Crisis Psychotherapy additional 30 minutes": "IT",
    "Telemed: Crisis Psychotherapy 30-60min": "IT",
    "Telemed: Crisis Psychotherapy Addt. 30min": "IT",

    # Telemed IT variants
    "Telemed: Outpatient 53+": "IT",
    "Telemed: Outpatient 53+ minutes": "IT",
    "Telemed: Outpatient 38-52 minutes": "IT",
    "Telemed: Outpatient 16-37 minutes": "IT",
    "Telemed: Outpatient EMDR 53+": "IT",
    "Telemed: Outpatient EMDR 38-52 minutes": "IT",

    # IOP services - map to "IOP" rate
    "IOP-Wilton": "IOP",
    "IOP Huntington": "IOP",
    "IOP Canaan": "IOP",
    "IOP Chappaqua": "IOP",
    "IOP NYC": "IOP",
    "IOP Ramsey": "IOP",
    "IOP": "IOP",
    "Telemed: IOP": "IOP",
    "Telemed: IOP-Wilton": "IOP",

    # Group services - map to "Group" rate
    "Outpatient Group (75-90 minutes)": "Group",
    "Outpatient Group (75-90 r": "Group",  # Truncated version
    "Outpatient Group (45-60 Minutes)": "Group",
    "Outpatient Group (45-60 minutes)": "Group",
    "Telemed: Outpatient Group (75-90 minutes)": "Group",
    "Telemed: Outpatient Group (45-60 Minutes)": "Group",
    "Telemed: Outpatient Group (45-60 minutes))": "Group",  # Note: has extra paren in source
    "Group": "Group",
    "Group Therapy": "Group",

    # Family Therapy (FT) services - map to "FT" rate
    "Family Session with Client 26+ minutes": "FT",
    "Family Session w/out the Client 26+ minutes": "FT",
    "Family Session 26+ minutes": "FT",
    "Outpatient Family Therapy w/ Client": "FT",
    "Family Therapy": "FT",
    "FT": "FT",
    "Telemed: Family Session with Client 26+ minutes": "FT",
    "Telemed: Family Session with client 26+ minutes": "FT",  # Lowercase variant
    "Telemed: Family Session w/o Client 26+ minutes": "FT",

    # Psychiatric services
    "Psychiatric Diag. Eval. W. Med Services": "Psych Eval",
    "Psychiatric Diag. Eval.": "Psych Eval",
    "Psych Eval": "Psych Eval",
    "Telemed: Psych Diag. Eval. W. Med Services": "Psych Eval",
    "OP: Psych Appointment (10-19 minutes)": "Psych f/u",  # Half-rate applies
    "OP: Psych Appointment (20-29 minutes)": "Psych f/u",  # Half-rate applies
    "OP: Psych Appointment (30-39 minutes)": "Psych f/u",
    "OP: Psych Appointment (40+ minutes)": "Psych f/u",
    "OP: Psych 40+ with Medication Admin/Injection": "Psych f/u",
    "OP: Psych w. Medication Induction": "Psych f/u",
    "OP: Psych with Medication Admin/Injection": "Psych f/u",
    "Telemed OP: Psych Appointment (10-19 minutes)": "Psych f/u",  # Half-rate
    "Telemed OP: Psych Appointment (20-29 minutes)": "Psych f/u",  # Half-rate
    "Telemed OP: Psych Appointment (30-39 minutes)": "Psych f/u",
    "Telemed OP: Psych Appointment (40+ minutes)": "Psych f/u",

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
    # IOP (all locations)
    "Telemed: IOP": "IOP",
    "Telemed: IOP-Wilton": "IOP",
    "IOP-Wilton": "IOP",
    "IOP Huntington": "IOP",
    "IOP Canaan": "IOP",
    "IOP Chappaqua": "IOP",
    "IOP NYC": "IOP",
    "IOP Ramsey": "IOP",
    "IOP": "IOP",

    # IT/Outpatient
    "Telemed: Outpatient 53+": "IT 53+",
    "Telemed: Outpatient 53+ minutes": "IT 53+",
    "Outpatient 53+": "IT 53+",
    "Outpatient 16-37 minutes": "IT 16-37",
    "Outpatient 38-52 minutes": "IT 38-52",
    "Telemed: Outpatient 16-37 minutes": "IT 16-37",
    "Telemed: Outpatient 38-52 minutes": "IT 38-52",

    # EMDR
    "Outpatient EMDR 53+": "EMDR 53+",
    "Outpatient EMDR 53+ minutes": "EMDR 53+",
    "Telemed: Outpatient EMDR 53+": "EMDR 53+",
    "Outpatient - EMDR 38-52 minutes": "EMDR 38-52",
    "Outpatient EMDR 38-52 minutes": "EMDR 38-52",
    "Telemed: Outpatient EMDR 38-52 minutes": "EMDR 38-52",

    # Crisis Psychotherapy
    "Crisis Psychotherapy 30-60min": "Crisis IT",
    "Crisis Psychotherapy additional 30 minutes": "Crisis IT Addt",
    "Telemed: Crisis Psychotherapy 30-60min": "Crisis IT",
    "Telemed: Crisis Psychotherapy Addt. 30min": "Crisis IT Addt",

    # Psych Eval
    "Psychiatric Diag. Eval. W. Med Services": "Psych Eval",
    "Psychiatric Diag. Eval.": "Psych Eval",
    "Telemed: Psych Diag. Eval. W. Med Services": "Psych Eval",

    # Psych Follow-up
    "OP: Psych Appointment (10-19 minutes)": "Psych f/u",
    "OP: Psych Appointment (20-29 minutes)": "Psych f/u",
    "OP: Psych Appointment (30-39 minutes)": "Psych f/u",
    "OP: Psych Appointment (40+ minutes)": "Psych f/u",
    "OP: Psych 40+ with Medication Admin/Injection": "Psych f/u + MAT",
    "OP: Psych w. Medication Induction": "Psych f/u + MAT",
    "OP: Psych with Medication Admin/Injection": "Psych f/u + MAT",
    "Telemed OP: Psych Appointment (10-19 minutes)": "Psych f/u",
    "Telemed OP: Psych Appointment (20-29 minutes)": "Psych f/u",
    "Telemed OP: Psych Appointment (30-39 minutes)": "Psych f/u",
    "Telemed OP: Psych Appointment (40+ minutes)": "Psych f/u",

    # Assessment
    "Assessment/Diag (BPS) w/o med services": "Assess",
    "Telemed: Assessment/Diag (BPS) w/o med services": "Assess",

    # Group
    "Outpatient Group (75-90 minutes)": "Group",
    "Outpatient Group (75-90 r": "Group",
    "Outpatient Group (45-60 Minutes)": "Group 45-60",
    "Outpatient Group (45-60 minutes)": "Group 45-60",
    "Telemed: Outpatient Group (75-90 minutes)": "Group",
    "Telemed: Outpatient Group (45-60 Minutes)": "Group 45-60",
    "Telemed: Outpatient Group (45-60 minutes))": "Group 45-60",

    # Family
    "Family Session with Client 26+ minutes": "FT",
    "Family Session w/out the Client 26+ minutes": "FT w/o Client",
    "Family Session 26+ minutes": "FT",
    "Outpatient Family Therapy w/ Client": "FT",
    "Telemed: Family Session with Client 26+ minutes": "FT",
    "Telemed: Family Session with client 26+ minutes": "FT",
    "Telemed: Family Session w/o Client 26+ minutes": "FT w/o Client",

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


def is_in_network(pps_comment: str) -> bool:
    """Check if this client is in-network based on PPS Comment."""
    if not pps_comment:
        return False
    return "in network:" in pps_comment.lower()


def get_nsf_rate(service_type: str, pps_comment: str = "", rate_schedule: Any = None) -> Decimal:
    """
    Get the NSF rate for a service type.

    NSF Rules:
    1. IOP/Group: ALWAYS $25.00 - no exceptions (in-network, out-of-network, self-pay, PIF)
    2. In-Network: Use full contracted rate from PPS Comment (before deductible rate)
    3. Out-of-Network/Self-Pay: Use self-pay rates

    Args:
        service_type: The service type (with or without NSF prefix)
        pps_comment: The PPS Comment string (to check in-network status and get contracted rates)
        rate_schedule: Optional RateSchedule with parsed in-network rates

    Returns:
        The NSF rate for this service
    """
    service_lower = service_type.lower()

    # Remove NSF prefix for matching
    clean_service = re.sub(r'^nsf\s*', '', service_lower, flags=re.IGNORECASE).strip()

    # =======================================================================
    # RULE 1: IOP and Group NSF are ALWAYS $25 - no exceptions
    # =======================================================================
    if "iop" in clean_service:
        return NSF_RATES["iop_rate"]  # Always $25
    if "group" in clean_service:
        return NSF_RATES["group_rate"]  # Always $25

    # =======================================================================
    # RULE 2: In-Network clients - use full contracted rate from PPS Comment
    # =======================================================================
    if is_in_network(pps_comment) and rate_schedule is not None:
        # Get the rate key for this service
        rate_key = get_rate_key_for_service(service_type)
        attr_name = RATE_KEY_TO_ATTRIBUTE.get(rate_key, "it_rate")

        # Get the contracted rate (full rate, not coinsurance rate)
        contracted_rate = getattr(rate_schedule, attr_name, Decimal("0.00"))

        if contracted_rate > Decimal("0.00"):
            return contracted_rate

    # =======================================================================
    # RULE 3: Out-of-Network / Self-Pay - use self-pay NSF rates
    # =======================================================================

    # All psych appointments (including evals): $200
    if "psych" in clean_service:
        return NSF_RATES["psych_eval_rate"]  # $200 for all psych NSF

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
    (r"10-19.*[Pp]sych", "Psych f/u"),  # Psych 10-19 min = half psych f/u rate
    (r"[Pp]sych.*10-19", "Psych f/u"),  # Alternative order
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
    "specialty_group_rate": Decimal("100.00"),  # 45-60 min groups
    "it_rate": Decimal("175.00"),
    "ft_rate": Decimal("275.00"),
    "psych_eval_rate": Decimal("675.00"),
    "psych_followup_rate": Decimal("200.00"),
    "mat_rate": Decimal("200.00"),
    "emdr_rate": Decimal("175.00"),
    "telemed_rate": Decimal("175.00"),
}

SELF_PAY_VIRTUAL_RATES: Dict[str, Decimal] = {
    "assessment_rate": Decimal("450.00"),
    "iop_rate": Decimal("295.00"),
    "group_rate": Decimal("175.00"),
    "specialty_group_rate": Decimal("100.00"),  # 45-60 min groups (same as in-person)
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
# SCHOLARSHIP CONFIGURATION
# =============================================================================
# Scholarships reduce or eliminate client payment for services.
# Tracking is done in PPS Comment using STANDARDIZED FORMATS.
#
# STANDARDIZED SCHOLARSHIP FORMATS:
# =================================
# All scholarship info should start with "SCHOLARSHIP:" prefix for clarity.
#
# 1. Full Scholarship:
#    SCHOLARSHIP: Full
#
# 2. Partial Scholarship (session-based):
#    SCHOLARSHIP: Partial | 8/17 IOP paid as of 1/27
#    (Client pays for 17 IOP sessions, sessions 18-24 are free)
#
# 3. Dollar Cap:
#    SCHOLARSHIP: Cap $1,500/$3,000 collected as of 1/27
#    (Client pays until $3,000 collected, then scholarship kicks in)
#
# 4. Program Total:
#    SCHOLARSHIP: Program $7,160 | Includes: 1 Intake + 24 IOP + 3 IT + 2 Psych
#    (Fixed total for entire program - any overage is scholarshipped)
#
# 5. Balance Due:
#    SCHOLARSHIP: Balance $885 due | 3 IOP remaining
#
# 6. After Threshold:
#    SCHOLARSHIP: After $2,775 | $2,500/$2,775 collected as of 1/27
#    (Scholarship kicks in after threshold collected)
#
# 7. Payment Plan (can combine with any above):
#    Payment Plan $150/week
#    Payment Plan $500/month
#
# 8. Self-Pay Rates (always include for scholarship clients):
#    RATES: Assessment $450 | IOP $295 | Group $175 | IT $175 | FT $275 | Psych Eval $675 | Psych f/u $200 | MAT $200
#
# FULL EXAMPLE (IOP Program):
#    SCHOLARSHIP: Partial | 8/17 IOP paid as of 1/27 | Includes: 1 Intake + 24 IOP + 3 IT + 2 Psych | Payment Plan $150/week | RATES: IOP $295 | IT $175 | Telemed: Self-Pay

# Program session limits
# Note: Psych appointments vary by client type:
#   - New clients: 1 Psych Eval + 1 Psych f/u = 2 total
#   - Transfer clients: 2 Psych f/u = 2 total
PROGRAM_LIMITS: Dict[str, int] = {
    "IOP": 24,           # IOP program is 24 IOP Group sessions
    "Group": 10,         # OP program is 10 Group sessions
    "IT_IOP": 3,         # IT sessions included in IOP program
    "IT_OP": 10,         # IT sessions in OP program
    "Psych": 2,          # 2 Psych appointments in both programs
}

# Program definitions for validation
# Psych appointments (2 total) are:
#   - New clients: 1 Psych Eval + 1 Psych f/u
#   - Transfer clients: 2 Psych f/u
PROGRAM_DEFINITIONS: Dict[str, Dict[str, int]] = {
    "IOP": {
        "Intake": 1,
        "IOP": 24,           # 24 IOP Group Sessions
        "IT": 3,             # 3 IT Sessions
        "Psych": 2,          # 2 Psych Appointments (see note above)
    },
    "OP": {
        "Intake": 1,
        "Group": 10,         # 10 OP Group Sessions
        "IT": 10,            # 10 IT Sessions
        "Psych": 2,          # 2 Psych Appointments (see note above)
    },
}


@dataclass
class ScholarshipInfo:
    """Parsed scholarship information from PPS Comment."""
    scholarship_type: str  # "full", "partial", "dollar_cap", "program", "balance", "after_threshold", "blended", "none"

    # For partial scholarships (X/Y service paid)
    sessions_paid: int = 0           # X - sessions already paid
    total_paid_sessions: int = 0     # Y - total sessions client pays for
    service_type: str = ""           # Which service (IOP, IT, Group, etc.)
    as_of_date: str = ""             # Date of last update

    # For dollar cap and program scholarships
    amount_used: Decimal = Decimal("0.00")   # Amount client has paid
    cap_amount: Decimal = Decimal("0.00")    # Total cap/program amount

    # For after-threshold scholarships
    threshold_amount: Decimal = Decimal("0.00")  # Amount after which scholarship kicks in

    # For balance due
    balance_due: Decimal = Decimal("0.00")

    # For blended rate
    blended_rate: Optional[Decimal] = None   # Fixed rate per session

    # Program includes (what services are covered)
    program_includes: Dict[str, int] = field(default_factory=dict)

    # Payment plan
    payment_plan_amount: Optional[Decimal] = None
    payment_plan_frequency: str = ""  # "week" or "month"

    @property
    def is_scholarshipped(self) -> bool:
        """Check if any scholarship applies."""
        return self.scholarship_type != "none"

    @property
    def sessions_remaining_paid(self) -> int:
        """For partial scholarships, how many paid sessions remain."""
        if self.scholarship_type == "partial":
            return max(0, self.total_paid_sessions - self.sessions_paid)
        return 0

    @property
    def is_in_scholarship_phase(self) -> bool:
        """For partial scholarships, check if we're past paid sessions."""
        if self.scholarship_type == "partial":
            return self.sessions_paid >= self.total_paid_sessions
        if self.scholarship_type in ("dollar_cap", "program"):
            return self.amount_used >= self.cap_amount
        if self.scholarship_type == "after_threshold":
            return self.amount_used >= self.threshold_amount
        if self.scholarship_type == "balance":
            return self.balance_due <= Decimal("0.00")
        if self.scholarship_type == "full":
            return True
        return False

    @property
    def amount_remaining(self) -> Decimal:
        """Amount remaining before scholarship phase (for cap/program/threshold)."""
        if self.scholarship_type in ("dollar_cap", "program"):
            return max(Decimal("0.00"), self.cap_amount - self.amount_used)
        if self.scholarship_type == "after_threshold":
            return max(Decimal("0.00"), self.threshold_amount - self.amount_used)
        if self.scholarship_type == "balance":
            return max(Decimal("0.00"), self.balance_due)
        return Decimal("0.00")


class ScholarshipPatterns:
    """Regex patterns for parsing scholarship info from PPS Comment.

    STANDARDIZED FORMATS (preferred):
    - SCHOLARSHIP: Full
    - SCHOLARSHIP: Partial | X/Y SERVICE paid as of M/D
    - SCHOLARSHIP: Cap $X/$Y collected as of M/D
    - SCHOLARSHIP: Program $X | Includes: ...
    - SCHOLARSHIP: Balance $X due
    - SCHOLARSHIP: After $X | $Y/$X collected as of M/D
    - Payment Plan $X/week or $X/month
    """

    # ==========================================================================
    # STANDARDIZED FORMATS (with SCHOLARSHIP: prefix)
    # ==========================================================================

    # SCHOLARSHIP: Full
    FULL_STANDARD = r'SCHOLARSHIP:\s*Full\b'

    # SCHOLARSHIP: Partial | 8/17 IOP paid as of 1/27
    PARTIAL_STANDARD = r'SCHOLARSHIP:\s*Partial\s*\|\s*(\d+)/(\d+)\s+(IOP|IT|Group|FT|Psych(?:\s*(?:Eval|f/u))?)\s+paid\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'

    # SCHOLARSHIP: Cap $1,500/$3,000 collected as of 1/27
    CAP_STANDARD = r'SCHOLARSHIP:\s*Cap\s+\$\s*([\d,]+(?:\.\d{2})?)\s*/\s*\$?\s*([\d,]+(?:\.\d{2})?)\s+collected\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'

    # SCHOLARSHIP: Program $7,160 | Includes: 1 Intake + 24 IOP + 3 IT + 2 Psych
    PROGRAM_STANDARD = r'SCHOLARSHIP:\s*Program\s+\$\s*([\d,]+(?:\.\d{2})?)'

    # SCHOLARSHIP: Balance $885 due
    BALANCE_STANDARD = r'SCHOLARSHIP:\s*Balance\s+\$\s*([\d,]+(?:\.\d{2})?)\s+due'

    # SCHOLARSHIP: After $2,775 | $2,500/$2,775 collected as of 1/27
    AFTER_THRESHOLD_STANDARD = r'SCHOLARSHIP:\s*After\s+\$\s*([\d,]+(?:\.\d{2})?)\s*\|\s*\$\s*([\d,]+(?:\.\d{2})?)\s*/\s*\$?\s*([\d,]+(?:\.\d{2})?)\s+collected\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'

    # Includes: 1 Intake + 24 IOP + 3 IT + 2 Psych (can appear with any type)
    INCLUDES = r'Includes:\s*([^|]+)'

    # Payment Plan $150/week or Payment Plan $500/month
    PAYMENT_PLAN = r'Payment\s+Plan\s+\$\s*([\d,]+(?:\.\d{2})?)\s*/\s*(week|month)'

    # ==========================================================================
    # LEGACY FORMATS (for backwards compatibility)
    # ==========================================================================

    # Full scholarship: "Full scholarship"
    FULL_LEGACY = r'\bFull\s+[Ss]cholarship\b'

    # Partial scholarship: "8/17 IOP paid as of 1/27" (without SCHOLARSHIP: prefix)
    PARTIAL_LEGACY = r'(\d+)/(\d+)\s+(IOP|IT|Group|FT|Psych(?:\s*(?:Eval|f/u))?)\s+paid\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'

    # Dollar cap legacy: "$1,500/$3,000 scholarship cap used as of 1/27"
    CAP_LEGACY = r'\$\s*([\d,]+(?:\.\d{2})?)\s*/\s*\$?\s*([\d,]+(?:\.\d{2})?)\s+scholarship\s+cap\s+(?:used|collected)\s+as\s+of\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'

    # Blended rate: "$150 per session"
    BLENDED_RATE = r'\$\s*(\d+(?:\.\d{2})?)\s+per\s+session'

    # Legacy payment plan: "payment plan of $150 per week"
    PAYMENT_PLAN_LEGACY = r'payment\s+plan\s+(?:of\s+)?\$\s*([\d,]+(?:\.\d{2})?)\s+per\s+(week|month)'


def parse_includes(pps_comment: str) -> Dict[str, int]:
    """Parse the 'Includes:' section of a scholarship PPS Comment.

    Example: "Includes: 1 Intake + 24 IOP + 3 IT + 2 Psych"
    Returns: {"Intake": 1, "IOP": 24, "IT": 3, "Psych": 2}
    """
    result = {}

    match = re.search(ScholarshipPatterns.INCLUDES, pps_comment, re.IGNORECASE)
    if not match:
        return result

    includes_str = match.group(1)

    # Parse "N ServiceType" patterns
    # Note: Order matters - more specific patterns (Psych Eval, Psych f/u) must come before generic "Psych"
    service_patterns = [
        (r'(\d+)\s*Intake', 'Intake'),
        (r'(\d+)\s*IOP', 'IOP'),
        (r'(\d+)\s*IT', 'IT'),
        (r'(\d+)\s*(?:OP\s+)?Group', 'Group'),  # "Group" or "OP Group"
        (r'(\d+)\s*FT', 'FT'),
        (r'(\d+)\s*Psych\s*Eval', 'Psych Eval'),
        (r'(\d+)\s*Psych\s*f/u', 'Psych f/u'),
        (r'(\d+)\s*Psych(?!\s*(?:Eval|f/u))', 'Psych'),  # Generic "Psych" (not Eval or f/u)
        (r'(\d+)\s*MAT', 'MAT'),
    ]

    for pattern, service in service_patterns:
        match = re.search(pattern, includes_str, re.IGNORECASE)
        if match:
            result[service] = int(match.group(1))

    return result


def parse_payment_plan(pps_comment: str) -> Tuple[Optional[Decimal], str]:
    """Parse payment plan info from PPS Comment.

    Returns: (amount, frequency) or (None, "")
    """
    if not pps_comment:
        return None, ""

    # Try standard format first
    match = re.search(ScholarshipPatterns.PAYMENT_PLAN, pps_comment, re.IGNORECASE)
    if match:
        return Decimal(match.group(1).replace(",", "")), match.group(2).lower()

    # Try legacy format
    match = re.search(ScholarshipPatterns.PAYMENT_PLAN_LEGACY, pps_comment, re.IGNORECASE)
    if match:
        return Decimal(match.group(1).replace(",", "")), match.group(2).lower()

    return None, ""


def parse_scholarship_info(pps_comment: str) -> ScholarshipInfo:
    """
    Parse scholarship information from PPS Comment.

    Supports both STANDARDIZED and LEGACY formats.

    STANDARDIZED FORMATS (preferred):
    - SCHOLARSHIP: Full
    - SCHOLARSHIP: Partial | 8/17 IOP paid as of 1/27
    - SCHOLARSHIP: Cap $1,500/$3,000 collected as of 1/27
    - SCHOLARSHIP: Program $7,160 | Includes: 1 Intake + 24 IOP + 3 IT + 2 Psych
    - SCHOLARSHIP: Balance $885 due
    - SCHOLARSHIP: After $2,775 | $2,500/$2,775 collected as of 1/27

    LEGACY FORMATS (still supported):
    - Full scholarship
    - 8/17 IOP paid as of 1/27
    - $1,500/$3,000 scholarship cap used as of 1/27
    - $150 per session

    Args:
        pps_comment: The PPS Comment string

    Returns:
        ScholarshipInfo with parsed values
    """
    if not pps_comment:
        return ScholarshipInfo(scholarship_type="none")

    # Parse payment plan (can accompany any scholarship type)
    payment_amount, payment_freq = parse_payment_plan(pps_comment)

    # Parse includes (can accompany any scholarship type)
    includes = parse_includes(pps_comment)

    # ==========================================================================
    # TRY STANDARDIZED FORMATS FIRST
    # ==========================================================================

    # SCHOLARSHIP: Full
    if re.search(ScholarshipPatterns.FULL_STANDARD, pps_comment, re.IGNORECASE):
        return ScholarshipInfo(
            scholarship_type="full",
            payment_plan_amount=payment_amount,
            payment_plan_frequency=payment_freq,
            program_includes=includes
        )

    # SCHOLARSHIP: Partial | X/Y SERVICE paid as of M/D
    match = re.search(ScholarshipPatterns.PARTIAL_STANDARD, pps_comment, re.IGNORECASE)
    if match:
        return ScholarshipInfo(
            scholarship_type="partial",
            sessions_paid=int(match.group(1)),
            total_paid_sessions=int(match.group(2)),
            service_type=match.group(3),
            as_of_date=match.group(4),
            payment_plan_amount=payment_amount,
            payment_plan_frequency=payment_freq,
            program_includes=includes
        )

    # SCHOLARSHIP: Cap $X/$Y collected as of M/D
    match = re.search(ScholarshipPatterns.CAP_STANDARD, pps_comment, re.IGNORECASE)
    if match:
        return ScholarshipInfo(
            scholarship_type="dollar_cap",
            amount_used=Decimal(match.group(1).replace(",", "")),
            cap_amount=Decimal(match.group(2).replace(",", "")),
            as_of_date=match.group(3),
            payment_plan_amount=payment_amount,
            payment_plan_frequency=payment_freq,
            program_includes=includes
        )

    # SCHOLARSHIP: Program $X | Includes: ...
    match = re.search(ScholarshipPatterns.PROGRAM_STANDARD, pps_comment, re.IGNORECASE)
    if match:
        return ScholarshipInfo(
            scholarship_type="program",
            cap_amount=Decimal(match.group(1).replace(",", "")),
            payment_plan_amount=payment_amount,
            payment_plan_frequency=payment_freq,
            program_includes=includes
        )

    # SCHOLARSHIP: Balance $X due
    match = re.search(ScholarshipPatterns.BALANCE_STANDARD, pps_comment, re.IGNORECASE)
    if match:
        return ScholarshipInfo(
            scholarship_type="balance",
            balance_due=Decimal(match.group(1).replace(",", "")),
            payment_plan_amount=payment_amount,
            payment_plan_frequency=payment_freq,
            program_includes=includes
        )

    # SCHOLARSHIP: After $X | $Y/$X collected as of M/D
    match = re.search(ScholarshipPatterns.AFTER_THRESHOLD_STANDARD, pps_comment, re.IGNORECASE)
    if match:
        return ScholarshipInfo(
            scholarship_type="after_threshold",
            threshold_amount=Decimal(match.group(1).replace(",", "")),
            amount_used=Decimal(match.group(2).replace(",", "")),
            cap_amount=Decimal(match.group(3).replace(",", "")),
            as_of_date=match.group(4),
            payment_plan_amount=payment_amount,
            payment_plan_frequency=payment_freq,
            program_includes=includes
        )

    # ==========================================================================
    # TRY LEGACY FORMATS
    # ==========================================================================

    # Full scholarship (legacy)
    if re.search(ScholarshipPatterns.FULL_LEGACY, pps_comment, re.IGNORECASE):
        return ScholarshipInfo(
            scholarship_type="full",
            payment_plan_amount=payment_amount,
            payment_plan_frequency=payment_freq,
            program_includes=includes
        )

    # Partial scholarship (legacy): X/Y SERVICE paid as of M/D
    match = re.search(ScholarshipPatterns.PARTIAL_LEGACY, pps_comment, re.IGNORECASE)
    if match:
        return ScholarshipInfo(
            scholarship_type="partial",
            sessions_paid=int(match.group(1)),
            total_paid_sessions=int(match.group(2)),
            service_type=match.group(3),
            as_of_date=match.group(4),
            payment_plan_amount=payment_amount,
            payment_plan_frequency=payment_freq,
            program_includes=includes
        )

    # Dollar cap (legacy)
    match = re.search(ScholarshipPatterns.CAP_LEGACY, pps_comment, re.IGNORECASE)
    if match:
        return ScholarshipInfo(
            scholarship_type="dollar_cap",
            amount_used=Decimal(match.group(1).replace(",", "")),
            cap_amount=Decimal(match.group(2).replace(",", "")),
            as_of_date=match.group(3),
            payment_plan_amount=payment_amount,
            payment_plan_frequency=payment_freq,
            program_includes=includes
        )

    # Blended rate: $X per session
    match = re.search(ScholarshipPatterns.BLENDED_RATE, pps_comment, re.IGNORECASE)
    if match:
        return ScholarshipInfo(
            scholarship_type="blended",
            blended_rate=Decimal(match.group(1)),
            payment_plan_amount=payment_amount,
            payment_plan_frequency=payment_freq,
            program_includes=includes
        )

    return ScholarshipInfo(scholarship_type="none")


def get_scholarship_charge(
    service_type: str,
    scholarship: ScholarshipInfo,
    default_rate: Decimal
) -> Tuple[Decimal, bool]:
    """
    Determine the charge amount based on scholarship status.

    Args:
        service_type: The service type being charged
        scholarship: Parsed scholarship info
        default_rate: The rate that would apply without scholarship

    Returns:
        Tuple of (charge_amount, is_scholarshipped)
        - charge_amount: What to charge (may be $0 if scholarshipped)
        - is_scholarshipped: True if this service is covered by scholarship
    """
    if scholarship.scholarship_type == "none":
        return default_rate, False

    if scholarship.scholarship_type == "full":
        return Decimal("0.00"), True

    if scholarship.scholarship_type == "blended":
        # Blended rate applies to all services
        return scholarship.blended_rate or default_rate, False

    if scholarship.scholarship_type == "partial":
        # Check if this service type matches the scholarship service
        service_lower = service_type.lower()
        scholarship_service_lower = scholarship.service_type.lower()

        # Normalize service types for comparison
        service_matches = False
        if "iop" in scholarship_service_lower and "iop" in service_lower:
            service_matches = True
        elif "it" in scholarship_service_lower and ("outpatient" in service_lower or "it" in service_lower) and "iop" not in service_lower and "group" not in service_lower:
            service_matches = True
        elif "group" in scholarship_service_lower and "group" in service_lower:
            service_matches = True
        elif "ft" in scholarship_service_lower and ("family" in service_lower or "ft" in service_lower):
            service_matches = True
        elif "psych" in scholarship_service_lower and "psych" in service_lower:
            service_matches = True

        if service_matches:
            # Check if we're still in the paid phase
            if scholarship.sessions_paid < scholarship.total_paid_sessions:
                # Still paying - charge the default rate
                return default_rate, False
            else:
                # In scholarship phase - $0
                return Decimal("0.00"), True
        else:
            # Different service type - not affected by this scholarship
            return default_rate, False

    if scholarship.scholarship_type == "dollar_cap":
        # Check if cap has been reached
        if scholarship.amount_used >= scholarship.cap_amount:
            return Decimal("0.00"), True
        else:
            # Still under cap - charge normally
            return default_rate, False

    if scholarship.scholarship_type == "program":
        # Program total - check if total paid equals program amount
        if scholarship.amount_used >= scholarship.cap_amount:
            return Decimal("0.00"), True
        else:
            return default_rate, False

    if scholarship.scholarship_type == "balance":
        # Balance due - if balance is 0 or less, scholarship phase
        if scholarship.balance_due <= Decimal("0.00"):
            return Decimal("0.00"), True
        else:
            return default_rate, False

    if scholarship.scholarship_type == "after_threshold":
        # Scholarship kicks in after threshold reached
        if scholarship.amount_used >= scholarship.threshold_amount:
            return Decimal("0.00"), True
        else:
            return default_rate, False

    return default_rate, False


def _format_currency(amount: Decimal) -> str:
    """Format a decimal as currency string."""
    if amount == amount.to_integral_value():
        return f"${int(amount):,}"
    else:
        return f"${amount:,.2f}"


def format_updated_scholarship(
    scholarship: ScholarshipInfo,
    increment_sessions: bool = False,
    add_amount: Decimal = Decimal("0.00"),
    subtract_balance: Decimal = Decimal("0.00"),
    new_date: Optional[str] = None
) -> str:
    """
    Generate updated scholarship tracking string for PPS Comment.

    Uses STANDARDIZED format with SCHOLARSHIP: prefix.

    Args:
        scholarship: Current scholarship info
        increment_sessions: Whether to increment session count (for partial)
        add_amount: Amount to add to used amount (for dollar cap/program/threshold)
        subtract_balance: Amount to subtract from balance due
        new_date: New as-of date (defaults to keeping existing)

    Returns:
        Updated scholarship string for PPS Comment (standardized format)
    """
    if scholarship.scholarship_type == "none":
        return ""

    date_str = new_date or scholarship.as_of_date
    parts = []

    if scholarship.scholarship_type == "full":
        parts.append("SCHOLARSHIP: Full")

    elif scholarship.scholarship_type == "blended":
        parts.append(f"${scholarship.blended_rate} per session")

    elif scholarship.scholarship_type == "partial":
        new_sessions = scholarship.sessions_paid + (1 if increment_sessions else 0)
        parts.append(f"SCHOLARSHIP: Partial | {new_sessions}/{scholarship.total_paid_sessions} {scholarship.service_type} paid as of {date_str}")

    elif scholarship.scholarship_type == "dollar_cap":
        new_amount = scholarship.amount_used + add_amount
        parts.append(f"SCHOLARSHIP: Cap {_format_currency(new_amount)}/{_format_currency(scholarship.cap_amount)} collected as of {date_str}")

    elif scholarship.scholarship_type == "program":
        new_amount = scholarship.amount_used + add_amount
        parts.append(f"SCHOLARSHIP: Program {_format_currency(scholarship.cap_amount)} | {_format_currency(new_amount)}/{_format_currency(scholarship.cap_amount)} collected as of {date_str}")

    elif scholarship.scholarship_type == "balance":
        new_balance = max(Decimal("0.00"), scholarship.balance_due - subtract_balance)
        parts.append(f"SCHOLARSHIP: Balance {_format_currency(new_balance)} due")

    elif scholarship.scholarship_type == "after_threshold":
        new_amount = scholarship.amount_used + add_amount
        parts.append(f"SCHOLARSHIP: After {_format_currency(scholarship.threshold_amount)} | {_format_currency(new_amount)}/{_format_currency(scholarship.threshold_amount)} collected as of {date_str}")

    # Add Includes if present
    if scholarship.program_includes:
        includes_parts = []
        for service, count in scholarship.program_includes.items():
            includes_parts.append(f"{count} {service}")
        parts.append(f"Includes: {' + '.join(includes_parts)}")

    # Add payment plan if present
    if scholarship.payment_plan_amount:
        parts.append(f"Payment Plan {_format_currency(scholarship.payment_plan_amount)}/{scholarship.payment_plan_frequency}")

    return " | ".join(parts)


# Specialty group patterns (45-60 min groups - different self-pay rate)
SPECIALTY_GROUP_PATTERNS: List[str] = [
    r"45-60",  # Matches "45-60 Minutes" or "45-60 minutes"
]


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


def is_specialty_group(service_type: str) -> bool:
    """
    Check if this is a specialty group (45-60 min).

    Specialty groups have different self-pay pricing ($100) but same
    insurance rate as regular groups.

    Args:
        service_type: The service type from Column D

    Returns:
        True if this is a specialty group
    """
    if not service_type:
        return False

    for pattern in SPECIALTY_GROUP_PATTERNS:
        if re.search(pattern, service_type, re.IGNORECASE):
            return True

    return False


def is_psych_with_mat(service_type: str) -> bool:
    """
    Check if this is a combined Psych + MAT service.

    These services have special pricing:
    - Self-pay: flat $200
    - Insurance: Psych f/u rate + MAT rate combined

    Args:
        service_type: The service type from Column D

    Returns:
        True if this is a combined Psych + MAT service
    """
    if not service_type:
        return False

    psych_mat_patterns = [
        r"Psych.*Medication\s*Admin",
        r"Psych.*Medication\s*Induction",
        r"Psych.*MAT",
    ]

    for pattern in psych_mat_patterns:
        if re.search(pattern, service_type, re.IGNORECASE):
            return True

    return False


# Self-pay rate for combined Psych + MAT appointments
PSYCH_MAT_SELF_PAY_RATE = Decimal("200.00")


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


def parse_pps_payment_plan(pps_comment: str) -> Optional[Dict[str, Any]]:
    """
    Extract payment plan details from PPS Comment using PPSPatterns format.

    This is for the insurance/PPS format: "Payment plan $500/month for 12 months"

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
