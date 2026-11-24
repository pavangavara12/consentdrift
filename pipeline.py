from typing import Dict, Any, List, Optional
from app.engine.rules import detect_signals, detect_data_categories, is_signal_covered
from app.engine.validator import validate_quotes, get_rule_quotes
from app.engine.risk import determine_risk, generate_explanation, calculate_score, RECOMMENDED_ACTIONS
from app.engine import llm

def analyze(consent: Any, evidence: Any, force_rules_only: bool = False) -> Dict[str, Any]:
    """
    Run multi-stage purpose drift analysis on the provided consent and evidence.
    Pipeline: rules -> LLM (optional) -> validator -> risk -> explanation.
    """
    evidence_text = evidence.content
    original_purpose = consent.original_purpose
    service_name = consent.service_name
    evidence_type = evidence.evidence_type or "evidence"

    # STAGE 1: Rules signal detector
    rule_signals = detect_signals(evidence_text)
    data_cats_detected = detect_data_categories(evidence_text)
    
    # Merge detected data categories with existing categories in consent if relevant
    affected_categories = list(dict.fromkeys(data_cats_detected + (consent.data_categories or [])))

    # STAGE 2: LLM extraction (optional)
    llm_output = None
    mode = "rules-only"
    pipeline_warnings: List[str] = []

    if not force_rules_only:
        llm_res, llm_warning = llm.extract_with_llm(
            original_purpose=original_purpose,
            data_categories=consent.data_categories or [],
            evidence_type=evidence_type,
            evidence_text=evidence_text
        )
        if llm_warning:
            pipeline_warnings.append(llm_warning)
        if llm_res:
            llm_output = llm_res
            mode = "hybrid"

    # STAGE 3: Quote validation
    valid_quotes: List[str] = []
    quote_spans: List[Dict[str, Any]] = []

    if mode == "hybrid" and llm_output:
        raw_quotes = llm_output.get("evidence_quotes", [])
        v_quotes, v_spans, v_warns = validate_quotes(raw_quotes, evidence_text)
        valid_quotes = v_quotes
        quote_spans = v_spans
        pipeline_warnings.extend(v_warns)
        # If all LLM quotes were invalid or dropped, fallback to rule-derived quotes
        if not valid_quotes and rule_signals:
            r_quotes, r_spans = get_rule_quotes(evidence_text, rule_signals)
            if r_quotes:
                valid_quotes = r_quotes
                quote_spans = r_spans
    else:
        # Rules-only quote extraction
        r_quotes, r_spans = get_rule_quotes(evidence_text, rule_signals)
        valid_quotes = r_quotes
        quote_spans = r_spans

    # STAGE 4: Risk determination
    risk, triggered_reasons, risk_warns = determine_risk(
        rule_signals=rule_signals,
        valid_quotes=valid_quotes,
        evidence_text=evidence_text,
        original_purpose=original_purpose,
        llm_output=llm_output
    )
    pipeline_warnings.extend(risk_warns)

    # Determine third-party sharing status
    if mode == "hybrid" and llm_output and "third_party_sharing" in llm_output:
        third_party_sharing = llm_output["third_party_sharing"]
    else:
        has_tp_signal = any(s["signal"] in ("THIRD_PARTY_SHARING", "SALE_OR_BROKER") for s in rule_signals)
        third_party_sharing = "yes" if has_tp_signal else "no" if risk == "LOW" else "unclear"

    # Identify new purposes
    new_purposes: List[str] = []
    if mode == "hybrid" and llm_output:
        new_purposes = llm_output.get("new_purposes", [])
    else:
        for s in rule_signals:
            sig = s["signal"]
            if sig not in ("BENIGN_STATUS", "OPT_IN_OPTIONAL"):
                new_purposes.append(f"{sig.replace('_', ' ').title()}: \"{s['matched_text']}\"")
        new_purposes = list(dict.fromkeys(new_purposes))

    original_purposes = [original_purpose]

    # STAGE 5: Explanation & Labels
    explanation = generate_explanation(
        risk=risk,
        original_purpose=original_purpose,
        service_name=service_name,
        evidence_type=evidence_type,
        detected_purposes=new_purposes,
        rule_signals=rule_signals,
        third_party=third_party_sharing
    )

    recommended_action = RECOMMENDED_ACTIONS.get(
        risk,
        "Review the submitted evidence and consult with your privacy officer."
    )

    # Score calculation
    score, score_breakdown = calculate_score(
        risk=risk,
        rule_signals=rule_signals,
        original_purpose=original_purpose,
        valid_quotes=valid_quotes
    )

    # Highlight spans as [start, end]
    highlight_spans = [[span["start"], span["end"]] for span in quote_spans if "start" in span and "end" in span]

    # Directly stated vs AI interpretation
    if mode == "hybrid" and llm_output:
        ai_interpretations = [explanation]
        if llm_output.get("additional_purposes_not_covered"):
            ai_interpretations.extend([f"Additional purpose not covered: {p}" for p in llm_output["additional_purposes_not_covered"]])
    else:
        ai_interpretations = [explanation] + [f"Rule signal detected: {r}" for r in triggered_reasons]

    statement_labels = {
        "directly_stated": valid_quotes,
        "ai_interpretation": ai_interpretations
    }

    return {
        "mode": mode,
        "risk": risk,
        "score": score,
        "score_breakdown": score_breakdown,
        "highlight_spans": highlight_spans,
        "original_purposes": original_purposes,
        "new_purposes": new_purposes,
        "data_categories_affected": affected_categories,
        "third_party_sharing": third_party_sharing,
        "evidence_quotes": valid_quotes,
        "rule_signals": rule_signals,
        "explanation": explanation,
        "recommended_action": recommended_action,
        "statement_labels": statement_labels,
        "warnings": pipeline_warnings,
        "quote_spans": quote_spans
    }

class MockObject:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def analyze_playground(original_purpose: str, evidence_text: str) -> Dict[str, Any]:
    """
    Run lightweight, in-memory analysis for the public interactive playground.
    Stores nothing, requires no auth.
    """
    mock_consent = MockObject(
        original_purpose=original_purpose,
        service_name="Interactive Simulator",
        data_categories=[]
    )
    mock_evidence = MockObject(
        content=evidence_text,
        evidence_type="policy"
    )
    return analyze(mock_consent, mock_evidence, force_rules_only=False)
