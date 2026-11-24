from unittest.mock import patch
from app.engine.pipeline import analyze

class DummyConsent:
    def __init__(self, original_purpose, service_name="TestApp", data_categories=None):
        self.original_purpose = original_purpose
        self.service_name = service_name
        self.data_categories = data_categories or []

class DummyEvidence:
    def __init__(self, content, evidence_type="email"):
        self.content = content
        self.evidence_type = evidence_type

def test_pipeline_rules_only_mode():
    consent = DummyConsent("Verify scholarship eligibility and communicate application updates.")
    evidence = DummyEvidence(
        "We may share your registered email address with selected advertising partners for promotional communication and special partner offers."
    )
    result = analyze(consent, evidence, force_rules_only=True)
    assert result["mode"] == "rules-only"
    assert result["risk"] == "HIGH"
    assert len(result["evidence_quotes"]) > 0
    assert result["third_party_sharing"] == "yes"

def test_pipeline_llm_invalid_json_fallback():
    consent = DummyConsent("Verify scholarship eligibility and communicate application updates.")
    evidence = DummyEvidence(
        "Dear applicant, your documents have been verified and your application status is now Under Review. We will contact you soon."
    )

    with patch("app.engine.llm.LLM_API_KEY", "test-key-123"):
        with patch("app.engine.llm.call_chat_completions", return_value="Invalid JSON response not conforming to schema"):
            result = analyze(consent, evidence)
            assert result["mode"] == "rules-only"
            assert any("fell back to rules-only mode" in w for w in result["warnings"])
            assert result["risk"] == "LOW"

def test_pipeline_llm_hallucinated_quote_downgrade():
    consent = DummyConsent("Provide online learning services and track course progress.")
    # Genuine evidence text has no mention of selling data or credit cards (>= 15 words)
    evidence = DummyEvidence(
        "Dear student, welcome to your online courses. We look forward to helping you track your progress throughout the semester with our tools."
    )

    # LLM hallucinates HIGH risk and a fake quote that does not appear in evidence
    mock_llm_payload = {
        "insufficient_evidence": False,
        "original_purposes": ["Provide online learning services and track course progress."],
        "new_purposes": ["Selling personal data to third parties"],
        "data_categories_affected": ["financial", "email"],
        "third_party_sharing": "yes",
        "covered_by_original_purpose": False,
        "additional_purposes_not_covered": ["Selling personal data to third parties"],
        "evidence_quotes": ["We sell your credit card information on data broker marketplaces."],
        "explanation": "The provider appears to sell data.",
        "confidence": 0.95
    }

    with patch("app.engine.llm.extract_with_llm", return_value=(mock_llm_payload, None)):
        result = analyze(consent, evidence)
        assert result["mode"] == "hybrid"
        # The hallucinated quote must be dropped by validator
        assert "We sell your credit card information on data broker marketplaces." not in result["evidence_quotes"]
        # Warning about removed quote must be present
        assert any("AI quote removed" in w for w in result["warnings"])
        # Risk should be downgraded from HIGH because 0 valid quotes supported the claim
        assert result["risk"] in ("MEDIUM", "LOW")
