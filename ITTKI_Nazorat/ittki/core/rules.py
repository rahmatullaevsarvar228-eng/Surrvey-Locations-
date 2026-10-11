"""Standard references for decision rules R1–R8 (table M5 of the TZ), shown next to each cost."""

RULE_REF = {
    "R1": {"IAS38": "IAS 38.67", "NAS11": "BHMS 11, 8-9-band"},
    "R2": {"IAS38": "IAS 38.53", "NAS11": "BHMS 11 da tartibga solinmagan (ehtiyotkorlik)"},
    "R3": {"IAS38": "IAS 38.54", "NAS11": "BHMS 11, 10-band"},
    "R4": {"IAS38": "—", "NAS11": "—"},
    "R5": {"IAS38": "IAS 38.66, 38.20", "NAS11": "—"},
    "R6": {"IAS38": "IAS 38.65, 38.71", "NAS11": "BHMS 11, 11-band"},
    "R7": {"IAS38": "IAS 38.57", "NAS11": "BHMS 11, 12-band"},
    "R8": {"IAS38": "—", "NAS11": "BHMS 11, 13-band"},
}


def rule_code(reason: str) -> str:
    """'R6: ...' -> 'R6'."""
    return reason.split(":", 1)[0].strip()


def rule_ref(reason: str, fw: str) -> str:
    return RULE_REF.get(rule_code(reason), {}).get(fw, "")


def reason_text(reason: str) -> str:
    """Reason without the 'Rn:' prefix."""
    return reason.split(":", 1)[1].strip() if ":" in reason else reason
