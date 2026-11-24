import re
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import ConsentRecord, Evidence, Analysis, Alert, ComplaintDraft, User
from app.schemas import (
    ConsentCreate, ConsentDetail, ConsentListItem, TimelineEvent
)
from app.auth import get_current_user
from app.engine.rules import detect_signals

router = APIRouter(prefix="/api/consents", tags=["consents"])

@router.post("", response_model=ConsentDetail, status_code=status.HTTP_201_CREATED)
def create_consent(
    consent_in: ConsentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    consent = ConsentRecord(
        user_id=current_user.id,
        organisation=consent_in.organisation,
        service_name=consent_in.service_name,
        original_purpose=consent_in.original_purpose,
        original_consent_text=consent_in.original_consent_text,
        data_categories=consent_in.data_categories or [],
        source_type=consent_in.source_type,
        consent_date=consent_in.consent_date
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)

    return ConsentDetail(
        id=consent.id,
        organisation=consent.organisation,
        service_name=consent.service_name,
        original_purpose=consent.original_purpose,
        original_consent_text=consent.original_consent_text,
        data_categories=consent.data_categories,
        source_type=consent.source_type,
        consent_date=consent.consent_date,
        created_at=consent.created_at,
        latest_risk=None,
        latest_score=None,
        analyses_count=0,
        evidence=[],
        analyses=[]
    )

@router.get("", response_model=List[ConsentListItem])
def list_consents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    records = db.query(ConsentRecord).filter(
        ConsentRecord.user_id == current_user.id
    ).order_by(ConsentRecord.created_at.desc()).all()

    items = []
    for r in records:
        latest_analysis = (
            db.query(Analysis)
            .filter(Analysis.consent_id == r.id, Analysis.user_id == current_user.id)
            .order_by(Analysis.created_at.desc())
            .first()
        )
        count = db.query(Analysis).filter(
            Analysis.consent_id == r.id, Analysis.user_id == current_user.id
        ).count()

        items.append(ConsentListItem(
            id=r.id,
            organisation=r.organisation,
            service_name=r.service_name,
            original_purpose=r.original_purpose,
            original_consent_text=r.original_consent_text,
            data_categories=r.data_categories or [],
            source_type=r.source_type,
            consent_date=r.consent_date,
            created_at=r.created_at,
            latest_risk=latest_analysis.risk if latest_analysis else None,
            latest_score=latest_analysis.score if latest_analysis else None,
            analyses_count=count
        ))
    return items

@router.get("/{id}", response_model=ConsentDetail)
def get_consent(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    consent = db.query(ConsentRecord).filter(
        ConsentRecord.id == id,
        ConsentRecord.user_id == current_user.id
    ).first()

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consent record with id {id} not found."
        )

    latest_analysis = (
        db.query(Analysis)
        .filter(Analysis.consent_id == consent.id, Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc())
        .first()
    )
    count = db.query(Analysis).filter(
        Analysis.consent_id == consent.id, Analysis.user_id == current_user.id
    ).count()

    return ConsentDetail(
        id=consent.id,
        organisation=consent.organisation,
        service_name=consent.service_name,
        original_purpose=consent.original_purpose,
        original_consent_text=consent.original_consent_text,
        data_categories=consent.data_categories or [],
        source_type=consent.source_type,
        consent_date=consent.consent_date,
        created_at=consent.created_at,
        latest_risk=latest_analysis.risk if latest_analysis else None,
        latest_score=latest_analysis.score if latest_analysis else None,
        analyses_count=count,
        evidence=consent.evidence,
        analyses=consent.analyses
    )

@router.delete("/{id}")
def delete_consent(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    consent = db.query(ConsentRecord).filter(
        ConsentRecord.id == id,
        ConsentRecord.user_id == current_user.id
    ).first()

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consent record with id {id} not found."
        )

    db.delete(consent)
    db.commit()
    return {"message": f"Consent record {id} deleted successfully."}

@router.get("/{id}/timeline", response_model=List[TimelineEvent])
def get_consent_timeline(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    consent = db.query(ConsentRecord).filter(
        ConsentRecord.id == id,
        ConsentRecord.user_id == current_user.id
    ).first()

    if not consent:
        raise HTTPException(status_code=404, detail="Consent record not found.")

    events: List[TimelineEvent] = []

    # 1. Baseline Created
    events.append(TimelineEvent(
        id=f"consent-{consent.id}",
        type="consent_created",
        title=f"Baseline Registered: {consent.service_name}",
        description=f"Original purpose registered under {consent.source_type.replace('_', ' ')}.",
        timestamp=consent.created_at,
        risk=None,
        score=None,
        link=f"/consents/{consent.id}"
    ))

    # 2. Evidence Submissions & Analyses
    for ev in consent.evidence:
        analysis = (
            db.query(Analysis)
            .filter(Analysis.evidence_id == ev.id, Analysis.user_id == current_user.id)
            .first()
        )
        events.append(TimelineEvent(
            id=f"evidence-{ev.id}",
            type="evidence_submitted",
            title=f"Evidence: {ev.title}",
            description=f"Submitted {ev.evidence_type.upper()} disclosure ({len(ev.content.split())} words).",
            timestamp=ev.submitted_at,
            risk=analysis.risk if analysis else None,
            score=analysis.score if analysis else None,
            link=f"/analyses/{analysis.id}" if analysis else None
        ))

    # 3. Alerts Raised
    alerts = db.query(Alert).filter(Alert.consent_id == consent.id, Alert.user_id == current_user.id).all()
    for al in alerts:
        events.append(TimelineEvent(
            id=f"alert-{al.id}",
            type="alert_raised",
            title=f"{al.risk} Mismatch Alert: {al.status.replace('_', ' ').title()}",
            description=al.notes or f"Automated discrepancy alert flagged at {al.risk} risk level.",
            timestamp=al.created_at,
            risk=al.risk,
            score=al.analysis.score if al.analysis else None,
            link="/alerts"
        ))

    # 4. Drafts Generated
    drafts = db.query(ComplaintDraft).filter(ComplaintDraft.consent_id == consent.id, ComplaintDraft.user_id == current_user.id).all()
    for dr in drafts:
        events.append(TimelineEvent(
            id=f"draft-{dr.id}",
            type="draft_generated",
            title=f"Letter Draft: {dr.template.upper()} Template",
            description=f"Draft inquiry '{dr.subject[:60]}...' (Status: {dr.status.title()}).",
            timestamp=dr.created_at,
            risk=None,
            score=None,
            link="/drafts"
        ))

    # Sort descending by timestamp
    events.sort(key=lambda x: x.timestamp, reverse=True)
    return events

@router.get("/{id}/export")
def export_consent_json(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    consent = db.query(ConsentRecord).filter(
        ConsentRecord.id == id,
        ConsentRecord.user_id == current_user.id
    ).first()

    if not consent:
        raise HTTPException(status_code=404, detail="Consent record not found.")

    evidence_data = []
    for ev in consent.evidence:
        analyses_data = []
        for an in ev.analyses:
            analyses_data.append({
                "id": an.id,
                "mode": an.mode,
                "risk": an.risk,
                "score": an.score,
                "score_breakdown": an.score_breakdown,
                "explanation": an.explanation,
                "rule_signals": an.rule_signals,
                "evidence_quotes": an.evidence_quotes,
                "recommended_action": an.recommended_action,
                "created_at": an.created_at.isoformat()
            })
        evidence_data.append({
            "id": ev.id,
            "title": ev.title,
            "evidence_type": ev.evidence_type,
            "content": ev.content,
            "source": ev.source,
            "content_hash": ev.content_hash,
            "submitted_at": ev.submitted_at.isoformat(),
            "analyses": analyses_data
        })

    return {
        "export_version": "2.0",
        "exported_by": current_user.email,
        "consent": {
            "id": consent.id,
            "organisation": consent.organisation,
            "service_name": consent.service_name,
            "original_purpose": consent.original_purpose,
            "original_consent_text": consent.original_consent_text,
            "data_categories": consent.data_categories,
            "source_type": consent.source_type,
            "consent_date": consent.consent_date.isoformat() if consent.consent_date else None,
            "created_at": consent.created_at.isoformat(),
            "evidence": evidence_data
        }
    }

@router.post("/{id}/policy-diff")
def compare_policies(
    id: int,
    payload: Dict[str, int],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    (P2) Pick two 'policy' evidence items for one consent record
    and compute added/removed sentences with risky signals highlighted.
    """
    ev1_id = payload.get("evidence_id_1")
    ev2_id = payload.get("evidence_id_2")

    if not ev1_id or not ev2_id:
        raise HTTPException(status_code=400, detail="evidence_id_1 and evidence_id_2 are required.")

    ev1 = db.query(Evidence).filter(Evidence.id == ev1_id, Evidence.consent_id == id, Evidence.user_id == current_user.id).first()
    ev2 = db.query(Evidence).filter(Evidence.id == ev2_id, Evidence.consent_id == id, Evidence.user_id == current_user.id).first()

    if not ev1 or not ev2:
        raise HTTPException(status_code=404, detail="One or both policy evidence items not found.")

    # Split into normalized sentences
    sents1 = set(re.split(r"(?<=[.!?])\s+", ev1.content.strip()))
    sents2 = set(re.split(r"(?<=[.!?])\s+", ev2.content.strip()))

    added = [s for s in sents2 if s not in sents1 and len(s.strip()) > 5]
    removed = [s for s in sents1 if s not in sents2 and len(s.strip()) > 5]

    added_with_signals = []
    for s in added:
        signals = detect_signals(s)
        added_with_signals.append({
            "sentence": s,
            "signals": signals
        })

    return {
        "policy_1": {"id": ev1.id, "title": ev1.title, "submitted_at": ev1.submitted_at.isoformat()},
        "policy_2": {"id": ev2.id, "title": ev2.title, "submitted_at": ev2.submitted_at.isoformat()},
        "added_sentences": added_with_signals,
        "removed_sentences": removed
    }
