from app.engine.validator import validate_quotes, get_rule_quotes

def test_exact_quote_passes():
    evidence = "We may share your registered email address with selected advertising partners for promotional communication."
    quotes = ["share your registered email address with selected advertising partners"]
    valid, spans, warnings = validate_quotes(quotes, evidence)
    assert len(valid) == 1
    assert valid[0] == "share your registered email address with selected advertising partners"
    assert len(warnings) == 0
    assert len(spans) == 1
    assert spans[0]["start"] == evidence.find(quotes[0])

def test_case_and_whitespace_normalized_quote_passes():
    evidence = "We may share your registered email address\n  with selected  advertising partners."
    # Quote has different whitespace and different casing
    quotes = ["SHARE YOUR REGISTERED EMAIL ADDRESS WITH SELECTED ADVERTISING PARTNERS"]
    valid, spans, warnings = validate_quotes(quotes, evidence)
    assert len(valid) == 1
    assert len(warnings) == 0
    assert len(spans) == 1
    assert spans[0]["start"] >= 0

def test_fabricated_quote_dropped_and_warning_generated():
    evidence = "Dear applicant, your documents have been verified and your application status is now Under Review."
    quotes = [
        "your documents have been verified",  # genuine quote
        "We will sell your credit card information on the dark web"  # fabricated quote
    ]
    valid, spans, warnings = validate_quotes(quotes, evidence)
    assert len(valid) == 1
    assert valid[0] == "your documents have been verified"
    assert len(warnings) == 1
    assert "1 AI quote removed: not found in evidence" in warnings[0]

def test_rules_based_quote_generation():
    evidence = "Welcome to our portal. We may share personal data with trusted partners. Have a nice day."
    rule_signals = [{"signal": "THIRD_PARTY_SHARING", "matched_text": "share personal data with trusted partners", "start": 23, "end": 64}]
    quotes, spans = get_rule_quotes(evidence, rule_signals)
    assert len(quotes) == 1
    assert "We may share personal data with trusted partners." in quotes[0]
