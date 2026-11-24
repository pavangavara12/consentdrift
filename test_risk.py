from app.engine.risk import determine_risk

def test_insufficient_evidence_short_text():
    # Under 15 words
    evidence = "Hello applicant, check status."
    risk, reasons, warnings = determine_risk(
        rule_signals=[],
        valid_quotes=[],
        evidence_text=evidence,
        original_purpose="Verify scholarship eligibility and communicate updates."
    )
    assert risk == "INSUFFICIENT_EVIDENCE"
    assert "too short" in reasons[0]

def test_low_risk_benign():
    evidence = (
        "Dear applicant, your documents have been successfully verified and your application status "
        "is now Under Review. We will email you about the next steps and interview scheduled shortly."
    )
    signals = [{"signal": "BENIGN_STATUS", "matched_text": "application status"}]
    risk, reasons, warnings = determine_risk(
        rule_signals=signals,
        valid_quotes=["your documents have been successfully verified"],
        evidence_text=evidence,
        original_purpose="Verify scholarship eligibility and communicate application updates."
    )
    assert risk == "LOW"

def test_medium_risk_vague_or_analytics():
    evidence = (
        "To improve our services, we may use your profile information for analytics "
        "and share insights with trusted partners to develop new portal features."
    )
    signals = [
        {"signal": "ANALYTICS_RESEARCH", "matched_text": "improve our services"},
        {"signal": "THIRD_PARTY_SHARING", "matched_text": "trusted partners"}
    ]
    # If opt-in or secondary analytics
    risk, reasons, warnings = determine_risk(
        rule_signals=[{"signal": "ANALYTICS_RESEARCH", "matched_text": "improve our services"}],
        valid_quotes=["To improve our services, we may use your profile information for analytics"],
        evidence_text=evidence,
        original_purpose="Evaluate job application resume and contact details."
    )
    assert risk == "MEDIUM"

def test_high_risk_uncovered_sharing_or_marketing():
    evidence = (
        "We may share your registered email address with selected advertising partners "
        "for promotional communication and special deals across affiliated platforms."
    )
    signals = [
        {"signal": "THIRD_PARTY_SHARING", "matched_text": "share your registered email address with selected advertising partners"},
        {"signal": "MARKETING", "matched_text": "promotional communication"}
    ]
    quotes = ["We may share your registered email address with selected advertising partners"]
    risk, reasons, warnings = determine_risk(
        rule_signals=signals,
        valid_quotes=quotes,
        evidence_text=evidence,
        original_purpose="Verify scholarship eligibility and communicate application updates."
    )
    assert risk == "HIGH"
    assert any("THIRD_PARTY_SHARING" in r or "High-impact" in r for r in reasons)

def test_downgrade_rule_when_quotes_are_missing():
    # If high signals exist but 0 valid quotes remain
    evidence = (
        "This is an administrative email update regarding your account security settings. "
        "Please visit our customer portal to review your account details and profile information."
    )
    # Suppose high signal is passed but valid_quotes is empty
    signals = [{"signal": "MARKETING", "matched_text": "promotional"}]
    risk, reasons, warnings = determine_risk(
        rule_signals=signals,
        valid_quotes=[],  # Zero valid quotes!
        evidence_text=evidence,
        original_purpose="Verify scholarship eligibility and communicate updates."
    )
    assert risk == "MEDIUM"
    assert any("downgraded to MEDIUM" in w for w in warnings)

def test_covered_purpose_does_not_trigger_high():
    evidence = (
        "We are sending you our monthly promotional marketing newsletter with offers "
        "and updates on our educational services as agreed during your sign up."
    )
    signals = [{"signal": "MARKETING", "matched_text": "promotional marketing"}]
    quotes = ["We are sending you our monthly promotional marketing newsletter"]
    # Original purpose explicitly mentions promotional marketing!
    original_purpose = "Provide educational services and send promotional marketing offers and newsletters."
    risk, reasons, warnings = determine_risk(
        rule_signals=signals,
        valid_quotes=quotes,
        evidence_text=evidence,
        original_purpose=original_purpose
    )
    assert risk == "LOW"
