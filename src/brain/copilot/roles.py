"""Role-aware framing and PII access control.

The same fact is framed differently for a technician, an engineer, a safety
officer, and an auditor — and sensitive personal data (who did what) is only
shown to roles allowed to see it.
"""
from __future__ import annotations

from typing import Dict

DEFAULT_ROLE = "engineer"

# How each role wants the answer framed (goes into the system prompt).
ROLE_FRAMING: Dict[str, str] = {
    "technician": (
        "You are advising a field technician. Be practical and concise, put "
        "safety first, and give clear step-by-step actions where relevant."
    ),
    "engineer": (
        "You are advising a plant/reliability engineer. Be technically precise "
        "and root-cause oriented; reference equipment behaviour and history."
    ),
    "safety_officer": (
        "You are advising a safety officer. Frame the answer around risk, "
        "relief protection, and regulatory compliance."
    ),
    "auditor": (
        "You are advising an auditor. Emphasise evidence, traceability, dates, "
        "and whether records substantiate each statement."
    ),
    "operator": (
        "You are advising a control-room operator. Be clear and plain, focused "
        "on current status and safe operating limits."
    ),
    "plant_manager": (
        "You are advising a plant manager. Lead with operational risk and "
        "impact (downtime, compliance exposure), then what needs a decision "
        "and by when. Keep detail brief; point to the records that matter."
    ),
}

# Roles permitted to see personal data (names of people). Others get it redacted.
PII_ALLOWED = {"safety_officer", "auditor"}


def framing(role: str) -> str:
    return ROLE_FRAMING.get(role, ROLE_FRAMING[DEFAULT_ROLE])


def can_see_pii(role: str) -> bool:
    return role in PII_ALLOWED
