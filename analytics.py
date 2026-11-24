from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import ConsentRecord, Evidence, Analysis, Alert, ComplaintDraft, User
from app.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("")
def get_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    total_consents = db.query(ConsentRecord).filter(ConsentRecord.user_id == current_user.id).count()
    total_evidence = db.query(Evidence).filter(Evidence.user_id == current_user.id).count()
    total_alerts = db.query(Alert).filter(Alert.user_id == current_user.id).count()
    total_drafts = db.query(ComplaintDraft).filter(ComplaintDraft.user_id == current_user.id).count()

    analyses = db.query(Analysis).filter(Analysis.user_id == current_user.id).all()

    # Risk Distribution
    risk_counts = Counter()
    signal_counts = Counter()
    high_orgs_counter = Counter()

    for a in analyses:
        risk_counts[a.risk] += 1
        for s in (a.rule_signals or []):
            sig_name = s.get("signal")
            if sig_name and sig_name != "BENIGN_STATUS":
                signal_counts[sig_name] += 1
        if a.risk == "HIGH":
            consent = db.query(ConsentRecord).filter(ConsentRecord.id == a.consent_id).first()
            if consent:
                high_orgs_counter[consent.organisation] += 1

    # Consent Health
    low_count = risk_counts.get("LOW", 0)
    if total_consents == 0 or total_evidence == 0:
        health_percentage = None
        health_status = "No data yet"
    else:
        health_percentage = round((low_count / total_evidence) * 100, 1)
        if health_percentage >= 80:
            health_status = "Good"
        elif health_percentage >= 50:
            health_status = "Moderate"
        else:
            health_status = "At Risk"

    consent_health = {
        "percentage": health_percentage,
        "status": health_status,
        "low_count": low_count,
        "total_evidence": total_evidence,
        "formula": "Percentage of submitted evidence rated LOW risk. Formula: (LOW Evidence Count / Total Evidence Count) × 100%."
    }

    # Top Triggering Signals
    top_signals = [
        {"signal": k.replace("_", " ").title(), "raw_signal": k, "count": v}
        for k, v in signal_counts.most_common(8)
    ]

    # Organisations with most HIGH findings
    top_high_orgs = [
        {"organisation": org, "count": cnt}
        for org, cnt in high_orgs_counter.most_common(5)
    ]

    # Alerts Over Time
    alerts = db.query(Alert).filter(Alert.user_id == current_user.id).order_by(Alert.created_at.asc()).all()
    time_map = defaultdict(lambda: {"total": 0, "HIGH": 0, "MEDIUM": 0})
    for al in alerts:
        date_str = al.created_at.strftime("%Y-%m-%d")
        time_map[date_str]["total"] += 1
        if al.risk in ("HIGH", "MEDIUM"):
            time_map[date_str][al.risk] += 1

    alerts_over_time = [
        {"date": d, "total": data["total"], "high": data["HIGH"], "medium": data["MEDIUM"]}
        for d, data in sorted(time_map.items())
    ]

    return {
        "summary": {
            "total_applications": total_consents,
            "total_evidence": total_evidence,
            "total_alerts": total_alerts,
            "total_drafts": total_drafts
        },
        "consent_health": consent_health,
        "risk_distribution": {
            "LOW": risk_counts.get("LOW", 0),
            "MEDIUM": risk_counts.get("MEDIUM", 0),
            "HIGH": risk_counts.get("HIGH", 0),
            "INSUFFICIENT_EVIDENCE": risk_counts.get("INSUFFICIENT_EVIDENCE", 0)
        },
        "top_signals": top_signals,
        "top_high_orgs": top_high_orgs,
        "alerts_over_time": alerts_over_time
    }
