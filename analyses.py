import hashlib
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Analysis, Evidence, ConsentRecord, ComplaintDraft, Notification, User
from app.schemas import AnalysisRead, ClarificationRequestCreate, DraftRead
from app.auth import get_current_user
from app.engine.clarification import generate_clarification_email
from app.engine.validator import find_quote_span

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

@router.get("/{id}", response_model=AnalysisRead)
def get_analysis(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis = db.query(Analysis).filter(
        Analysis.id == id,
        Analysis.user_id == current_user.id
    ).first()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with id {id} not found."
        )

    evidence = db.query(Evidence).filter(
        Evidence.id == analysis.evidence_id,
        Evidence.user_id == current_user.id
    ).first()

    consent = db.query(ConsentRecord).filter(
        ConsentRecord.id == analysis.consent_id,
        ConsentRecord.user_id == current_user.id
    ).first()

    # Recompute SHA-256 integrity check on view
    current_hash = hashlib.sha256(evidence.content.encode("utf-8")).hexdigest() if evidence else ""
    integrity_status = "unchanged" if (evidence and current_hash == evidence.content_hash) else "modified"

    # Compute quote spans for UI highlighting
    quote_spans = []
    if evidence and analysis.evidence_quotes:
        for q in analysis.evidence_quotes:
            span_res = find_quote_span(q, evidence.content)
            if span_res:
                quote_spans.append({"start": span_res[0], "end": span_res[1], "text": span_res[2]})

    return AnalysisRead(
        id=analysis.id,
        evidence_id=analysis.evidence_id,
        consent_id=analysis.consent_id,
        mode=analysis.mode,
        risk=analysis.risk,
        score=analysis.score,
        score_breakdown=analysis.score_breakdown,
        highlight_spans=analysis.highlight_spans,
        original_purposes=analysis.original_purposes,
        new_purposes=analysis.new_purposes,
        data_categories_affected=analysis.data_categories_affected,
        third_party_sharing=analysis.third_party_sharing,
        evidence_quotes=analysis.evidence_quotes,
        rule_signals=analysis.rule_signals,
        explanation=analysis.explanation,
        recommended_action=analysis.recommended_action,
        statement_labels=analysis.statement_labels,
        warnings=analysis.warnings,
        created_at=analysis.created_at,
        evidence_content=evidence.content if evidence else None,
        quote_spans=quote_spans,
        consent_service_name=consent.service_name if consent else None,
        consent_organisation=consent.organisation if consent else None,
        consent_original_purpose=consent.original_purpose if consent else None,
        integrity_status=integrity_status
    )

@router.post("/{id}/clarification", response_model=DraftRead, status_code=status.HTTP_201_CREATED)
def create_clarification_draft(
    id: int,
    req: ClarificationRequestCreate = ClarificationRequestCreate(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis = db.query(Analysis).filter(
        Analysis.id == id,
        Analysis.user_id == current_user.id
    ).first()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with id {id} not found."
        )

    consent = db.query(ConsentRecord).filter(
        ConsentRecord.id == analysis.consent_id,
        ConsentRecord.user_id == current_user.id
    ).first()
    evidence = db.query(Evidence).filter(
        Evidence.id == analysis.evidence_id,
        Evidence.user_id == current_user.id
    ).first()

    template_type = req.template or "general"
    email_data = generate_clarification_email(
        service_name=consent.service_name if consent else "Service",
        organisation=consent.organisation if consent else "Organisation",
        original_purpose=consent.original_purpose if consent else "",
        evidence_type=evidence.evidence_type if evidence else "notice",
        evidence_source=evidence.source if evidence else None,
        evidence_date=evidence.submitted_at.strftime("%Y-%m-%d") if evidence else None,
        evidence_quotes=analysis.evidence_quotes,
        data_categories=analysis.data_categories_affected,
        template=template_type
    )

    draft = ComplaintDraft(
        user_id=current_user.id,
        consent_id=consent.id if consent else 0,
        analysis_id=analysis.id,
        template=template_type,
        subject=email_data["subject"],
        body=email_data["body"],
        status="draft"
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    notification = Notification(
        user_id=current_user.id,
        message=f"New {template_type.upper()} clarification request drafted for {consent.service_name}.",
        link="/drafts",
        is_read=False
    )
    db.add(notification)
    db.commit()

    return DraftRead(
        id=draft.id,
        user_id=draft.user_id,
        consent_id=draft.consent_id,
        analysis_id=draft.analysis_id,
        template=draft.template,
        subject=draft.subject,
        body=draft.body,
        status=draft.status,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        service_name=consent.service_name if consent else None,
        organisation=consent.organisation if consent else None
    )
