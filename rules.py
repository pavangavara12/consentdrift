import re
from typing import List, Dict, Any, Set

SIGNAL_PATTERNS: Dict[str, List[str]] = {
    "SALE_OR_BROKER": [
        r"\b(?:sell(?:ing)?|sale of (?:your )?data|sold to)\b",
        r"\bdata brokers?\b",
        r"\b(?:monetis|monetiz)(?:e|ing|ation)\b",
    ],
    "THIRD_PARTY_SHARING": [
        r"\bshare[a-z]*\s+(?:[^.?!;,]{0,80}\s+)?with\s+(?:[^.?!;,]{0,40}\s+)?(?:advertising partners|advertisers|sponsors|corporate sponsors|commercial partners|data brokers|marketing vendors|affiliates for commercial)\b",
        r"\bdisclose[a-z]*\s+to\s+(?:[^.?!;,]{0,40}\s+)?(?:advertising(?: agencies| networks)?|commercial sponsors|advertisers|marketing partners)\b",
        r"\badvertising\s+partners\b",
        r"\bcommercial\s+sponsors\b",
        r"\bcorporate\s+sponsors\b",
        r"\badvertising\s+agencies\b",
        r"\badvertising\s+networks\b",
    ],
    "VAGUE_PARTNER_SHARING": [
        r"\b(?:trusted|selected)\s+(?:third[- ]parties|partners)\b",
        r"\bshare[a-z]*\s+(?:[^.?!;,]{0,80}\s+)?with\s+(?:[^.?!;,]{0,40}\s+)?(?:trusted partners|selected partners|third[- ]parties|affiliates|service providers)\b",
        r"\bdisclose[a-z]*\s+to\s+(?:[^.?!;,]{0,40}\s+)?(?:third[- ]parties|partners|affiliates|contractors|vendors)\b",
        r"\bselected\s+third[- ]parties\b",
        r"\btechnical\s+contractors\b",
    ],
    "MARKETING": [
        r"\bmarketing(?:\s+campaigns?|\s+initiatives?|\s+offers|\s+updates|\s+vendors)?\b",
        r"\bpromotional(?:\s+communication|\s+offers|\s+material|\s+emails|\s+messages|\s+content|\s+campaigns?|\s+initiatives?)?\b",
        r"\bpromotions\b",
        r"\badvertis(?:e|ing|ement|ements|er|ers)\b",
        r"\bnewsletter\b",
        r"\b(?:commercial|special|promotional|partner)\s+offers\b",
        r"\b(?:marketing|promotional)\s+campaigns?\b",
        r"\bspecial deals\b",
    ],
    "PROFILING": [
        r"\bprofiling\b",
        r"\bbehavio(?:u)?ral(?:\s+tracking|\s+targeting|\s+data|\s+advertising|\s+profiling)?\b",
        r"\bpersonali[sz]ed\s+ads?\b",
        r"\btargeted\s+ads?\b",
        r"\binterests\s+and\s+preferences\b",
        r"\buser\s+profiles?\b",
    ],
    "ANALYTICS_RESEARCH": [
        r"\banalytics\b",
        r"\bresearch(?:\s+purposes)?\b",
        r"\bimprove\s+(?:our\s+)?(?:services?|products?|platform|experience)\b",
        r"\bproduct\s+development\b",
        r"\busage\s+statistics\b",
        r"\bstatistical\s+analysis\b",
        r"\binfrastructure\s+optimization\b",
        r"\bplatform\s+enhancement\b",
    ],
    "RETENTION_CHANGE": [
        r"\bretain(?:ing)?\b",
        r"\bretention(?:\s+policy)?\b",
        r"\bkeep\s+(?:your\s+)?data\s+(?:for\s+)?(?:indefinitely|\d+\s+years?)\b",
        r"\bindefinitely\b",
    ],
    "CONSENT_WITHDRAWAL_LIMIT": [
        r"\bcannot\s+opt[- ]out\b",
        r"\bno\s+option\s+to\s+opt[- ]out\b",
        r"\bdeemed\s+consent\b",
        r"\bmandatory\s+consent\b",
    ],
    "OPT_IN_OPTIONAL": [
        r"\bopt(?:ional|ionally)?\b",
        r"\bif you (?:choose|opt|wish) to receive\b",
        r"\byou may opt[- ]in\b",
        r"\boptional\s+marketing\b",
    ],
    "BENIGN_STATUS": [
        r"\bapplication\s+status\b",
        r"\b(?:under\s+review|shortlisted|application\s+received)\b",
        r"\binterview(?:\s+scheduled|\s+invitation|\s+details)?\b",
        r"\bscheduled\b",
        r"\bverification\b",
        r"\bverified\b",
        r"\beligibility\b",
        r"\byour\s+application\b",
        r"\breset\s+(?:your\s+)?password\b",
        r"\bone[- ]time\s+password\b",
        r"\bOTP\b",
        r"\breceipt\b",
        r"\bconfirmation\b",
        r"\bconfirmed\b",
        r"\benrollment\b",
        r"\baccount\s+verification\b",
        r"\bcredentials\b",
    ]
}

DATA_CATEGORY_PATTERNS: Dict[str, List[str]] = {
    "email": [r"\bemail(?:\s+address)?\b"],
    "phone": [r"\b(?:phone|mobile|cell)(?:\s+number)?\b"],
    "address": [r"\b(?:postal\s+)?address\b", r"\bresidence\b"],
    "location": [r"\blocation(?:\s+data)?\b", r"\bGPS\b", r"\bgeolocation\b"],
    "income": [r"\b(?:family\s+)?income\b", r"\bsalary\b", r"\bearnings\b"],
    "resume": [r"\bresume\b", r"\bCV\b", r"\bcurriculum\s+vitae\b"],
    "id_number": [r"\b(?:national\s+)?id\s+number\b", r"\bssn\b", r"\bpassport\s+number\b"],
    "date_of_birth": [r"\bdate\s+of\s+birth\b", r"\bdob\b", r"\bbirthday\b"],
    "academic_records": [r"\bacademic\s+records?\b", r"\btranscripts?\b", r"\bgrades?\b", r"\bcredentials\b"],
    "financial": [r"\bfinancial(?:\s+data|\s+information|\s+details)?\b", r"\bbank\s+account\b", r"\bcredit\s+card\b"],
    "learning_activity": [r"\blearning\s+activity\b", r"\bcourse\s+progress\b", r"\bstudy\s+habits\b"],
}

def detect_signals(text: str) -> List[Dict[str, Any]]:
    """Detect purpose and risk signals from evidence text."""
    if not text:
        return []
    
    signals: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for signal_name, patterns in SIGNAL_PATTERNS.items():
        category = "benign" if signal_name == "BENIGN_STATUS" else ("control" if signal_name in ("CONSENT_WITHDRAWAL_LIMIT", "OPT_IN_OPTIONAL") else "purpose")
        for pat in patterns:
            for match in re.finditer(pat, text, flags=re.IGNORECASE):
                matched = match.group(0)
                # Deduplicate identical signal & matched_text
                key = f"{signal_name}:{matched.lower()}"
                if key not in seen:
                    seen.add(key)
                    signals.append({
                        "signal": signal_name,
                        "matched_text": matched,
                        "category": category,
                        "start": match.start(),
                        "end": match.end()
                    })
    return signals

def detect_data_categories(text: str) -> List[str]:
    """Detect mentioned personal data categories in text."""
    if not text:
        return []
    
    found: List[str] = []
    for cat, patterns in DATA_CATEGORY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, flags=re.IGNORECASE):
                found.append(cat)
                break
    return found

def is_signal_covered(signal: str, original_purpose: str) -> bool:
    """
    Check if a signal detected in evidence was already covered in original purpose text.
    """
    if not original_purpose:
        return False
    
    purpose_signals = detect_signals(original_purpose)
    for ps in purpose_signals:
        if ps["signal"] == signal:
            return True
        if signal in ("MARKETING", "PROMOTIONS") and ps["signal"] in ("MARKETING", "PROMOTIONS"):
            return True
        if signal in ("THIRD_PARTY_SHARING", "VAGUE_PARTNER_SHARING") and ps["signal"] in ("THIRD_PARTY_SHARING", "VAGUE_PARTNER_SHARING", "SALE_OR_BROKER"):
            return True
        if signal == "ANALYTICS_RESEARCH" and ps["signal"] in ("ANALYTICS_RESEARCH",):
            return True
    
    # Direct keyword check as extra coverage fallback
    op_lower = original_purpose.lower()
    if signal == "MARKETING" and any(k in op_lower for k in ["market", "promot", "newsletter", "offers"]):
        return True
    if signal in ("THIRD_PARTY_SHARING", "VAGUE_PARTNER_SHARING") and any(k in op_lower for k in ["partner", "third part", "affiliate", "disclose"]):
        return True
    if signal == "ANALYTICS_RESEARCH" and any(k in op_lower for k in ["analytic", "research", "improve service"]):
        return True
    if signal == "PROFILING" and any(k in op_lower for k in ["profil", "personali", "targeted"]):
        return True

    return False
