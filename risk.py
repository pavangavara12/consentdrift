from typing import List, Dict, Any, Optional, Tuple
from app.engine.rules import is_signal_covered

HIGH_SIGNALS = {"SALE_OR_BROKER", "THIRD_PARTY_SHARING", "MARKETING", "PROFILING"}
MEDIUM_SIGNALS = {"ANALYTICS_RESEARCH", "RETENTION_CHANGE", "CONSENT_WITHDRAWAL_LIMIT", "VAGUE_PARTNER_SHARING"}

RECOMMENDED_ACTIONS = {
    "LOW": "No action needed. Keep this record for reference.",
    "MEDIUM": "Review the full privacy policy and consider asking the organisation for clarification.",
    "HIGH": "Review the privacy policy and send a clarification request. Check available opt-out options.",
    "INSUFFICIENT_EVIDENCE": "Submit more complete text, such as the full email or policy section."
}

def count_words(text: str) -> int:
    if not text:
        return 0
    return len(text.split())

def determine_risk(
    rule_signals: List[Dict[str, Any]],
    valid_quotes: List[str],
    evidence_text: str,
    original_purpose: str,
    llm_output: Optional[Dict[str, Any]] = None,
) -> Tuple[str, List[str], List[str]]:
    """
    Determine final deterministic risk classification.
    Returns:
        (risk_level, triggered_reasons, warnings)
    """
    warnings: List[str] = []
    triggered_reasons: List[str] = []
    
    word_count = count_words(evidence_text)

    # 1. INSUFFICIENT_EVIDENCE check for length
    if word_count < 15:
        return "INSUFFICIENT_EVIDENCE", [f"Evidence text is too short ({word_count} words; minimum 15 words required)."], warnings

    if llm_output and llm_output.get("insufficient_evidence"):
        return "INSUFFICIENT_EVIDENCE", ["AI assessment indicated insufficient evidence of data processing purposes."], warnings

    active_signals = [s["signal"] for s in rule_signals]
    is_optional_opt_in = "OPT_IN_OPTIONAL" in active_signals

    high_detected = [s for s in active_signals if s in HIGH_SIGNALS]
    medium_detected = [s for s in active_signals if s in MEDIUM_SIGNALS]
    benign_detected = [s for s in active_signals if s == "BENIGN_STATUS"]

    # Filter out signals covered by original purpose
    uncovered_high = [s for s in high_detected if not is_signal_covered(s, original_purpose)]
    uncovered_medium = [s for s in medium_detected if not is_signal_covered(s, original_purpose)]

    # Check LLM inputs if in hybrid mode
    llm_says_uncovered = False
    llm_third_party = "unclear"
    if llm_output:
        llm_third_party = llm_output.get("third_party_sharing", "unclear")
        covered = llm_output.get("covered_by_original_purpose", True)
        add_purposes = llm_output.get("additional_purposes_not_covered", [])
        if not covered or (add_purposes and len(add_purposes) > 0) or llm_third_party == "yes":
            llm_says_uncovered = True

    # Check Downgrade rule: LLM says HIGH-type findings or uncovered_high exists, but 0 valid quotes remain
    if (uncovered_high or (llm_output and llm_says_uncovered)) and not valid_quotes:
        warnings.append("High-impact findings indicated but zero valid quotes substantiated them; downgraded to MEDIUM.")
        triggered_reasons.append("Unverified potential high-impact findings detected without supporting verbatim quotes.")
        return "MEDIUM", triggered_reasons, warnings

    # Check if there are no purpose or risk signals and no benign signals either
    if not active_signals and not valid_quotes and not (llm_output and llm_output.get("new_purposes")):
        return "INSUFFICIENT_EVIDENCE", ["No identifiable data usage purposes or signals found in the evidence."], warnings

    # Check if all detected signals are covered by baseline purpose
    if (high_detected or medium_detected) and not uncovered_high and not uncovered_medium:
        triggered_reasons.append("Signals detected match the original purpose baseline and appear covered.")
        return "LOW", triggered_reasons, warnings

    # Check for HIGH risk
    if uncovered_high:
        if is_optional_opt_in:
            triggered_reasons.append(
                f"Potentially sensitive activities detected ({', '.join(uncovered_high)}), but appears to be optional or opt-in."
            )
            return "MEDIUM", triggered_reasons, warnings

        if valid_quotes:
            for s in uncovered_high:
                triggered_reasons.append(f"High-impact data practice detected: {s} (not covered by original baseline).")
            return "HIGH", triggered_reasons, warnings

    if llm_output and llm_says_uncovered and (llm_output.get("new_purposes") or llm_third_party == "yes"):
        if is_optional_opt_in:
            triggered_reasons.append("Additional data use detected, but indicated as optional.")
            return "MEDIUM", triggered_reasons, warnings

        if valid_quotes:
            triggered_reasons.append("AI extraction identified additional purposes outside original consent, supported by verified quotes.")
            return "HIGH", triggered_reasons, warnings

    # Check for MEDIUM risk
    if uncovered_medium:
        for s in uncovered_medium:
            triggered_reasons.append(f"Additional secondary data processing detected: {s}.")
        return "MEDIUM", triggered_reasons, warnings

    if llm_output and llm_third_party == "unclear" and not benign_detected and active_signals:
        triggered_reasons.append("Third-party sharing terms appear ambiguous or unclear.")
        return "MEDIUM", triggered_reasons, warnings

    # Check for LOW risk
    if benign_detected and not uncovered_high and not uncovered_medium:
        triggered_reasons.append("Evidence content reflects routine administrative or status communications consistent with original purpose.")
        return "LOW", triggered_reasons, warnings

    if not uncovered_high and not uncovered_medium:
        triggered_reasons.append("Evidence content appears consistent with the original stated purpose.")
        return "LOW", triggered_reasons, warnings

    return "MEDIUM", ["Indeterminate secondary usage signals identified."], warnings

SIGNAL_WEIGHTS = {
    "SALE_OR_BROKER": 35,
    "THIRD_PARTY_SHARING": 30,
    "PROFILING": 25,
    "MARKETING": 20,
    "VAGUE_PARTNER_SHARING": 15,
    "RETENTION_CHANGE": 15,
    "CONSENT_WITHDRAWAL_LIMIT": 15,
    "ANALYTICS_RESEARCH": 10,
    "OPT_IN_OPTIONAL": -10,
    "BENIGN_STATUS": -15
}

def calculate_score(
    risk: str,
    rule_signals: List[Dict[str, Any]],
    original_purpose: str,
    valid_quotes: List[str]
) -> Tuple[int, Dict[str, Any]]:
    """
    Calculate deterministic discrepancy score (0-100) and structured breakdown.
    Score ranges:
      INSUFFICIENT_EVIDENCE: 0
      LOW: 5 - 25
      MEDIUM: 40 - 65
      HIGH: 75 - 98
    """
    if risk == "INSUFFICIENT_EVIDENCE":
        return 0, {
            "final_score": 0,
            "risk": risk,
            "base_score": 0,
            "formula": "Score = 0 (Evidence text is insufficient or lacks actionable purpose statements).",
            "signals": []
        }

    # Base score per tier
    base_scores = {
        "LOW": 10,
        "MEDIUM": 45,
        "HIGH": 75
    }
    base = base_scores.get(risk, 50)
    
    signals_breakdown: List[Dict[str, Any]] = []
    added_weight = 0

    seen_signals = set()
    for s in rule_signals:
        sig = s.get("signal", "")
        if sig in seen_signals:
            continue
        seen_signals.add(sig)

        weight = SIGNAL_WEIGHTS.get(sig, 5)
        is_covered = is_signal_covered(sig, original_purpose)
        
        # Covered signals contribute 0 to the discrepancy score
        contribution = 0 if is_covered else weight
        if sig == "BENIGN_STATUS":
            contribution = -5 if risk == "LOW" else 0
        elif sig == "OPT_IN_OPTIONAL":
            contribution = -10

        added_weight += contribution
        signals_breakdown.append({
            "signal": sig,
            "matched_text": s.get("matched_text", ""),
            "weight": weight,
            "covered_by_baseline": is_covered,
            "score_contribution": contribution
        })

    # Quote verification confidence boost
    quote_bonus = min(len(valid_quotes) * 2, 6) if valid_quotes else 0

    raw_score = base + added_weight + quote_bonus

    # Clamp by risk tier
    if risk == "LOW":
        final_score = max(5, min(raw_score, 25))
        formula = f"Base ({base}) + Purpose Alignment ({added_weight:+d}) + Quote Validation (+{quote_bonus}) = {final_score}/100"
    elif risk == "MEDIUM":
        final_score = max(35, min(raw_score, 68))
        formula = f"Base ({base}) + Uncovered Secondary Signals ({added_weight:+d}) + Quote Validation (+{quote_bonus}) = {final_score}/100"
    else:  # HIGH
        final_score = max(75, min(raw_score, 98))
        formula = f"Base ({base}) + Uncovered High-Impact Discrepancies ({added_weight:+d}) + Quote Validation (+{quote_bonus}) = {final_score}/100"

    return final_score, {
        "final_score": final_score,
        "risk": risk,
        "base_score": base,
        "quote_bonus": quote_bonus,
        "formula": formula,
        "signals": signals_breakdown
    }

def generate_explanation(
    risk: str,
    original_purpose: str,
    service_name: str,
    evidence_type: str,
    detected_purposes: List[str],
    rule_signals: List[Dict[str, Any]],
    third_party: str
) -> str:
    """
    Generate 2-3 plain-language sentences.
    Always uses cautious terms: 'potential', 'may', 'appears'.
    Never uses words like 'violation', 'illegal', 'breach'.
    """
    baseline_snippet = original_purpose[:120].strip()
    if len(original_purpose) > 120:
        baseline_snippet += "..."

    sig_names = [s["signal"] for s in rule_signals if s.get("signal") != "BENIGN_STATUS"]

    if risk == "HIGH":
        signals_str = ", ".join(sig_names) if sig_names else "secondary processing"
        sharing_str = "including third-party sharing" if third_party == "yes" else "for additional activities"
        return (
            f"The original consent for {service_name} covered: \"{baseline_snippet}\". "
            f"The newly received {evidence_type} appears to disclose {signals_str} {sharing_str} not explicitly mentioned in the original baseline. "
            f"This may represent potential purpose drift affecting how your personal information is utilized."
        )
    elif risk == "MEDIUM":
        details = ", ".join(sig_names) if sig_names else "analytics, retention, or service improvements"
        return (
            f"The original consent for {service_name} was established for: \"{baseline_snippet}\". "
            f"The newly submitted {evidence_type} introduces broader terms relating to {details}. "
            f"While these practices may be auxiliary, they appear less specific than the original baseline and warrant clarification."
        )
    elif risk == "LOW":
        return (
            f"The original purpose for {service_name} was recorded as: \"{baseline_snippet}\". "
            f"The submitted {evidence_type} appears fully aligned with routine communications and expected service operations. "
            f"No unexpected data-handling or potential drift was identified from the provided text."
        )
    else:  # INSUFFICIENT_EVIDENCE
        return (
            f"The submitted text does not appear to contain sufficient detail regarding data processing practices for {service_name}. "
            f"No conclusive comparison against the original purpose (\"{baseline_snippet}\") could be established. "
            f"Please submit more complete text, such as the full email body or privacy policy snippet."
        )
