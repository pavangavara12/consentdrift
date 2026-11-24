import re
from typing import List, Tuple, Dict, Any, Optional

def normalize_text(text: str) -> str:
    """Normalize whitespace and strip text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()

def find_quote_span(quote: str, evidence_text: str) -> Optional[Tuple[int, int, str]]:
    """
    Attempt to find the quote in evidence_text.
    Returns (start, end, exact_matched_text) or None if not found.
    """
    if not quote or not evidence_text:
        return None
    
    quote_clean = quote.strip().strip('"\'')
    if not quote_clean:
        return None

    # 1. Exact case-sensitive search
    idx = evidence_text.find(quote_clean)
    if idx != -1:
        return (idx, idx + len(quote_clean), evidence_text[idx : idx + len(quote_clean)])

    # 2. Case-insensitive exact search
    lower_evidence = evidence_text.lower()
    lower_quote = quote_clean.lower()
    idx = lower_evidence.find(lower_quote)
    if idx != -1:
        return (idx, idx + len(quote_clean), evidence_text[idx : idx + len(quote_clean)])

    # 3. Flexible whitespace search (handles multiple spaces, newlines, tabs)
    words = quote_clean.split()
    if words:
        pattern = r"\s+".join(re.escape(w) for w in words)
        try:
            match = re.search(pattern, evidence_text, flags=re.IGNORECASE)
            if match:
                return (match.start(), match.end(), evidence_text[match.start() : match.end()])
        except re.error:
            pass

    return None

def validate_quotes(
    quotes: List[str],
    evidence_text: str
) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
    """
    Validate LLM evidence quotes against original evidence text.
    Returns:
        (valid_quotes, quote_spans, warnings)
    """
    valid_quotes: List[str] = []
    quote_spans: List[Dict[str, Any]] = []
    dropped_count = 0
    warnings: List[str] = []

    seen_spans = set()

    for q in quotes:
        span_info = find_quote_span(q, evidence_text)
        if span_info:
            start, end, exact_text = span_info
            span_key = (start, end)
            if span_key not in seen_spans:
                seen_spans.add(span_key)
                valid_quotes.append(exact_text)
                quote_spans.append({
                    "start": start,
                    "end": end,
                    "quote": exact_text
                })
        else:
            dropped_count += 1

    if dropped_count > 0:
        plural = "quote" if dropped_count == 1 else "quotes"
        warnings.append(f"{dropped_count} AI {plural} removed: not found in evidence")

    return valid_quotes, quote_spans, warnings

def extract_sentence_for_match(evidence_text: str, start_pos: int, end_pos: int) -> Tuple[int, int, str]:
    """
    Given a match position in evidence_text, expand to the full containing sentence.
    """
    # Look backwards for sentence start (. ! ? or start of string)
    sentence_start = 0
    for i in range(start_pos - 1, -1, -1):
        if evidence_text[i] in ".!?\n":
            sentence_start = i + 1
            break
    
    # Look forwards for sentence end (. ! ? or end of string)
    sentence_end = len(evidence_text)
    for i in range(end_pos, len(evidence_text)):
        if evidence_text[i] in ".!?\n":
            sentence_end = i + 1
            break
            
    sentence = evidence_text[sentence_start:sentence_end].strip()
    # Adjust start and end to stripped bounds
    if sentence:
        s_idx = evidence_text.find(sentence, sentence_start)
        if s_idx != -1:
            return (s_idx, s_idx + len(sentence), sentence)
            
    return (start_pos, end_pos, evidence_text[start_pos:end_pos])

def get_rule_quotes(
    evidence_text: str,
    rule_signals: List[Dict[str, Any]]
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Generate evidence quotes and spans directly from rule signals.
    Excludes pure benign status unless no other signals exist.
    """
    if not rule_signals or not evidence_text:
        return [], []

    # Prioritize purpose and control signals over benign signals
    purpose_signals = [s for s in rule_signals if s.get("signal") != "BENIGN_STATUS"]
    target_signals = purpose_signals if purpose_signals else rule_signals

    valid_quotes: List[str] = []
    quote_spans: List[Dict[str, Any]] = []
    seen_spans = set()

    for sig in target_signals:
        start = sig.get("start")
        end = sig.get("end")
        if start is not None and end is not None:
            s_start, s_end, sentence = extract_sentence_for_match(evidence_text, start, end)
        else:
            span_info = find_quote_span(sig.get("matched_text", ""), evidence_text)
            if span_info:
                s_start, s_end, sentence = extract_sentence_for_match(evidence_text, span_info[0], span_info[1])
            else:
                continue

        span_key = (s_start, s_end)
        if span_key not in seen_spans:
            seen_spans.add(span_key)
            valid_quotes.append(sentence)
            quote_spans.append({
                "start": s_start,
                "end": s_end,
                "quote": sentence
            })

    return valid_quotes, quote_spans
