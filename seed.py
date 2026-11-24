import hashlib
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from app.db import SessionLocal, Base, engine
from app.models import User, ConsentRecord, Evidence, Analysis, Alert, AlertEvent, ComplaintDraft, Notification
from app.auth import hash_password
from app.engine.pipeline import analyze
from app.engine.clarification import generate_clarification_email

DEMO_USER_EMAIL = "demo@consentdrift.app"
DEMO_USER_PASSWORD = "Demo@1234"
DEMO_USER_NAME = "Demo User"

DEMO_DATA = [
    {
        "organisation": "ABC Education Foundation",
        "service_name": "ABC Scholarship Portal",
        "original_purpose": "Verify scholarship eligibility and communicate application updates.",
        "original_consent_text": "By applying for the ABC Scholarship, you consent to the collection and processing of your academic details, contact information, and eligibility verification solely for administering your scholarship application.",
        "data_categories": ["name", "email", "phone", "family income"],
        "source_type": "official_text",
        "consent_date": date(2026, 1, 15),
        "evidence_items": [
            {
                "title": "Application Status Update Email",
                "evidence_type": "email",
                "source": "scholarships@abcfoundation.org",
                "content": "Dear applicant, your documents have been verified and your application status is now Under Review. We will email you about the next steps and interview scheduled shortly."
            },
            {
                "title": "Partner Marketing Notice",
                "evidence_type": "email",
                "source": "updates@abcfoundation.org",
                "content": "We may share your registered email address with selected advertising partners for promotional communication and exclusive partner offers."
            }
        ]
    },
    {
        "organisation": "TechHire Inc.",
        "service_name": "TechHire Jobs Portal",
        "original_purpose": "Use my resume and contact details to evaluate my job application.",
        "original_consent_text": "TechHire uses submitted resumes, candidate credentials, and contact records to evaluate applicants for open engineering and technology roles.",
        "data_categories": ["name", "email", "phone", "resume"],
        "source_type": "user_summary",
        "consent_date": date(2026, 2, 1),
        "evidence_items": [
            {
                "title": "Platform Analytics Notification",
                "evidence_type": "notification",
                "source": "System Notification",
                "content": "To improve our services, we may use your profile information for analytics and share insights with trusted partners to enhance platform performance."
            },
            {
                "title": "Commercial Partner Course Email",
                "evidence_type": "email",
                "source": "promotions@techhire.jobs",
                "content": "Candidate contact details will be used to send promotional offers about partner courses and products directly to your registered email address."
            }
        ]
    },
    {
        "organisation": "LearnFast Education Ltd.",
        "service_name": "LearnFast Edtech",
        "original_purpose": "Provide online learning services and track course progress.",
        "original_consent_text": "Student profile information and course progress telemetry are processed to deliver interactive modules and issue certificates of completion.",
        "data_categories": ["name", "email", "learning activity"],
        "source_type": "official_text",
        "consent_date": date(2026, 3, 10),
        "evidence_items": [
            {
                "title": "Terms of Service Section 4",
                "evidence_type": "policy",
                "source": "https://learnfast.io/terms",
                "content": "Your learning activity may be shared with selected third parties for additional purposes including external academic research and platform enhancement."
            },
            {
                "title": "Short Push Notification",
                "evidence_type": "notification",
                "source": "Mobile App Alert",
                "content": "Hello, please check the app."
            }
        ]
    }
]

def get_or_create_demo_user(db: Session) -> User:
    demo_user = db.query(User).filter(User.email == DEMO_USER_EMAIL).first()
    if not demo_user:
        demo_user = User(
            full_name=DEMO_USER_NAME,
            email=DEMO_USER_EMAIL,
            password_hash=hash_password(DEMO_USER_PASSWORD),
            phone="+1-555-0199",
            is_active=True
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
    return demo_user

def seed_database(db: Optional[Session] = None, target_user: Optional[User] = None) -> dict:
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        Base.metadata.create_all(bind=engine)

        user = target_user or get_or_create_demo_user(db)

        created_consents = 0
        created_evidence = 0
        created_analyses = 0
        created_alerts = 0
        created_drafts = 0

        sample_high_analysis = None
        sample_high_consent = None
        sample_high_evidence = None

        for item in DEMO_DATA:
            existing = db.query(ConsentRecord).filter(
                ConsentRecord.user_id == user.id,
                ConsentRecord.organisation == item["organisation"],
                ConsentRecord.service_name == item["service_name"]
            ).first()

            if existing:
                consent = existing
            else:
                consent = ConsentRecord(
                    user_id=user.id,
                    organisation=item["organisation"],
                    service_name=item["service_name"],
                    original_purpose=item["original_purpose"],
                    original_consent_text=item.get("original_consent_text"),
                    data_categories=item["data_categories"],
                    source_type=item["source_type"],
                    consent_date=item["consent_date"]
                )
                db.add(consent)
                db.commit()
                db.refresh(consent)
                created_consents += 1

            for ev_data in item["evidence_items"]:
                existing_ev = db.query(Evidence).filter(
                    Evidence.consent_id == consent.id,
                    Evidence.title == ev_data["title"],
                    Evidence.user_id == user.id
                ).first()

                if existing_ev:
                    evidence = existing_ev
                else:
                    content_hash = hashlib.sha256(ev_data["content"].encode("utf-8")).hexdigest()
                    evidence = Evidence(
                        user_id=user.id,
                        consent_id=consent.id,
                        title=ev_data["title"],
                        evidence_type=ev_data["evidence_type"],
                        content=ev_data["content"],
                        source=ev_data.get("source"),
                        content_hash=content_hash
                    )
                    db.add(evidence)
                    db.commit()
                    db.refresh(evidence)
                    created_evidence += 1

                existing_an = db.query(Analysis).filter(
                    Analysis.evidence_id == evidence.id,
                    Analysis.user_id == user.id
                ).first()

                if not existing_an:
                    analysis_res = analyze(consent, evidence, force_rules_only=False)
                    analysis = Analysis(
                        user_id=user.id,
                        evidence_id=evidence.id,
                        consent_id=consent.id,
                        mode=analysis_res["mode"],
                        risk=analysis_res["risk"],
                        score=analysis_res.get("score", 0),
                        score_breakdown=analysis_res.get("score_breakdown", {}),
                        highlight_spans=analysis_res.get("highlight_spans", []),
                        original_purposes=analysis_res["original_purposes"],
                        new_purposes=analysis_res["new_purposes"],
                        data_categories_affected=analysis_res["data_categories_affected"],
                        third_party_sharing=analysis_res["third_party_sharing"],
                        evidence_quotes=analysis_res["evidence_quotes"],
                        rule_signals=analysis_res["rule_signals"],
                        explanation=analysis_res["explanation"],
                        recommended_action=analysis_res["recommended_action"],
                        statement_labels=analysis_res["statement_labels"],
                        warnings=analysis_res["warnings"]
                    )
                    db.add(analysis)
                    db.commit()
                    db.refresh(analysis)
                    created_analyses += 1

                    # Auto-create alert for MEDIUM or HIGH
                    if analysis.risk in ("MEDIUM", "HIGH"):
                        alert = Alert(
                            user_id=user.id,
                            analysis_id=analysis.id,
                            consent_id=consent.id,
                            risk=analysis.risk,
                            status="new",
                            notes=f"Discrepancy detected with {analysis.risk} risk rating."
                        )
                        db.add(alert)
                        db.commit()
                        db.refresh(alert)
                        created_alerts += 1

                        ev_log = AlertEvent(
                            alert_id=alert.id,
                            event=f"Initial alert generated ({analysis.risk} risk, Score {analysis.score}/100)."
                        )
                        db.add(ev_log)

                        notif = Notification(
                            user_id=user.id,
                            message=f"{analysis.risk} alert flagged for {consent.service_name}.",
                            link="/alerts",
                            is_read=False
                        )
                        db.add(notif)
                        db.commit()

                        if analysis.risk == "HIGH" and sample_high_analysis is None:
                            sample_high_analysis = analysis
                            sample_high_consent = consent
                            sample_high_evidence = evidence

        # Add one sample complaint draft for the user if none exists
        existing_draft = db.query(ComplaintDraft).filter(ComplaintDraft.user_id == user.id).first()
        if not existing_draft and sample_high_analysis and sample_high_consent:
            draft_content = generate_clarification_email(
                service_name=sample_high_consent.service_name,
                organisation=sample_high_consent.organisation,
                original_purpose=sample_high_consent.original_purpose,
                evidence_type=sample_high_evidence.evidence_type,
                evidence_source=sample_high_evidence.source,
                evidence_date=sample_high_evidence.submitted_at.strftime("%Y-%m-%d"),
                evidence_quotes=sample_high_analysis.evidence_quotes,
                data_categories=sample_high_analysis.data_categories_affected,
                template="general"
            )
            sample_draft = ComplaintDraft(
                user_id=user.id,
                consent_id=sample_high_consent.id,
                analysis_id=sample_high_analysis.id,
                template="general",
                subject=draft_content["subject"],
                body=draft_content["body"],
                status="draft"
            )
            db.add(sample_draft)
            db.commit()
            created_drafts += 1

        return {
            "status": "success",
            "user": user.email,
            "message": f"Seeded: {created_consents} consents, {created_evidence} evidence items, {created_analyses} analyses, {created_alerts} alerts, {created_drafts} drafts."
        }

    finally:
        if should_close:
            db.close()

if __name__ == "__main__":
    result = seed_database()
    print(result)
