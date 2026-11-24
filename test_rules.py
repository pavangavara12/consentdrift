from app.engine.rules import detect_signals, detect_data_categories, is_signal_covered

def test_signal_patterns_fire():
    # Test marketing pattern
    s1 = detect_signals("We will send promotional communication and special deals.")
    sig_names1 = [s["signal"] for s in s1]
    assert "MARKETING" in sig_names1

    # Test third party sharing pattern
    s2 = detect_signals("We may share your registered email address with advertising partners and third parties.")
    sig_names2 = [s["signal"] for s in s2]
    assert "THIRD_PARTY_SHARING" in sig_names2

    # Test vague partner sharing pattern
    s2_vague = detect_signals("We share information with selected partners and trusted partners.")
    sig_names2_vague = [s["signal"] for s in s2_vague]
    assert "VAGUE_PARTNER_SHARING" in sig_names2_vague

    # Test sale or broker pattern
    s3 = detect_signals("We do not sell your personal data or provide it to any data broker.")
    sig_names3 = [s["signal"] for s in s3]
    assert "SALE_OR_BROKER" in sig_names3

    # Test profiling pattern
    s4 = detect_signals("We use behavioural tracking and targeted ads based on your interests and preferences.")
    sig_names4 = [s["signal"] for s in s4]
    assert "PROFILING" in sig_names4

    # Test analytics research pattern
    s5 = detect_signals("To improve our services, we conduct analytics and research purposes.")
    sig_names5 = [s["signal"] for s in s5]
    assert "ANALYTICS_RESEARCH" in sig_names5

    # Test retention change pattern
    s6 = detect_signals("We retain your account data indefinitely.")
    sig_names6 = [s["signal"] for s in s6]
    assert "RETENTION_CHANGE" in sig_names6

    # Test consent withdrawal limit
    s7 = detect_signals("Users cannot opt out of this system under deemed consent.")
    sig_names7 = [s["signal"] for s in s7]
    assert "CONSENT_WITHDRAWAL_LIMIT" in sig_names7

def test_benign_text_fires_only_benign_status():
    benign_text = "Dear applicant, your documents have been verified and your application status is now Under Review. We will email you regarding interview scheduled."
    signals = detect_signals(benign_text)
    sig_names = [s["signal"] for s in signals]
    assert "BENIGN_STATUS" in sig_names
    assert "MARKETING" not in sig_names
    assert "THIRD_PARTY_SHARING" not in sig_names
    assert "SALE_OR_BROKER" not in sig_names

def test_detect_data_categories():
    text = "Please submit your resume, email, phone number, and family income details."
    cats = detect_data_categories(text)
    assert "resume" in cats
    assert "email" in cats
    assert "phone" in cats
    assert "income" in cats

def test_covered_signal_check():
    baseline_with_marketing = "Use email to send newsletters and promotional marketing updates."
    assert is_signal_covered("MARKETING", baseline_with_marketing) is True
    assert is_signal_covered("SALE_OR_BROKER", baseline_with_marketing) is False
