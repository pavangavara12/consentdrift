import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import ComplaintDraft, ConsentRecord, User
from app.schemas import DraftRead, DraftCreate, DraftUpdate
from app.auth import get_current_user

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib import colors

router = APIRouter(prefix="/api/drafts", tags=["drafts"])

@router.get("", response_model=List[DraftRead])
def list_drafts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    drafts = db.query(ComplaintDraft).filter(
        ComplaintDraft.user_id == current_user.id
    ).order_by(ComplaintDraft.created_at.desc()).all()

    results: List[DraftRead] = []
    for d in drafts:
        consent = db.query(ConsentRecord).filter(ConsentRecord.id == d.consent_id).first()
        results.append(DraftRead(
            id=d.id,
            user_id=d.user_id,
            consent_id=d.consent_id,
            analysis_id=d.analysis_id,
            template=d.template,
            subject=d.subject,
            body=d.body,
            status=d.status,
            created_at=d.created_at,
            updated_at=d.updated_at,
            service_name=consent.service_name if consent else None,
            organisation=consent.organisation if consent else None
        ))
    return results

@router.get("/{id}", response_model=DraftRead)
def get_draft(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    d = db.query(ComplaintDraft).filter(
        ComplaintDraft.id == id,
        ComplaintDraft.user_id == current_user.id
    ).first()

    if not d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint draft with id {id} not found."
        )

    consent = db.query(ConsentRecord).filter(ConsentRecord.id == d.consent_id).first()
    return DraftRead(
        id=d.id,
        user_id=d.user_id,
        consent_id=d.consent_id,
        analysis_id=d.analysis_id,
        template=d.template,
        subject=d.subject,
        body=d.body,
        status=d.status,
        created_at=d.created_at,
        updated_at=d.updated_at,
        service_name=consent.service_name if consent else None,
        organisation=consent.organisation if consent else None
    )

@router.post("", response_model=DraftRead, status_code=status.HTTP_201_CREATED)
def create_draft(
    req: DraftCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    consent = db.query(ConsentRecord).filter(
        ConsentRecord.id == req.consent_id,
        ConsentRecord.user_id == current_user.id
    ).first()

    if not consent:
        raise HTTPException(status_code=404, detail="Consent record not found.")

    draft = ComplaintDraft(
        user_id=current_user.id,
        consent_id=req.consent_id,
        analysis_id=req.analysis_id,
        template=req.template,
        subject=req.subject,
        body=req.body,
        status="draft"
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

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
        service_name=consent.service_name,
        organisation=consent.organisation
    )

@router.patch("/{id}", response_model=DraftRead)
def update_draft(
    id: int,
    req: DraftUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    d = db.query(ComplaintDraft).filter(
        ComplaintDraft.id == id,
        ComplaintDraft.user_id == current_user.id
    ).first()

    if not d:
        raise HTTPException(status_code=404, detail="Draft not found.")

    if req.template:
        d.template = req.template
    if req.subject:
        d.subject = req.subject
    if req.body:
        d.body = req.body
    if req.status:
        d.status = req.status

    db.commit()
    db.refresh(d)

    consent = db.query(ConsentRecord).filter(ConsentRecord.id == d.consent_id).first()
    return DraftRead(
        id=d.id,
        user_id=d.user_id,
        consent_id=d.consent_id,
        analysis_id=d.analysis_id,
        template=d.template,
        subject=d.subject,
        body=d.body,
        status=d.status,
        created_at=d.created_at,
        updated_at=d.updated_at,
        service_name=consent.service_name if consent else None,
        organisation=consent.organisation if consent else None
    )

@router.delete("/{id}")
def delete_draft(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    d = db.query(ComplaintDraft).filter(
        ComplaintDraft.id == id,
        ComplaintDraft.user_id == current_user.id
    ).first()

    if not d:
        raise HTTPException(status_code=404, detail="Draft not found.")

    db.delete(d)
    db.commit()
    return {"message": "Draft deleted successfully."}

@router.get("/{id}/pdf")
def export_draft_pdf(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    d = db.query(ComplaintDraft).filter(
        ComplaintDraft.id == id,
        ComplaintDraft.user_id == current_user.id
    ).first()

    if not d:
        raise HTTPException(status_code=404, detail="Draft not found.")

    consent = db.query(ConsentRecord).filter(ConsentRecord.id == d.consent_id).first()

    # Generate PDF in-memory using ReportLab
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E293B')
    )
    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748B')
    )
    body_style = ParagraphStyle(
        'LetterBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=15,
        textColor=colors.HexColor('#0F172A')
    )

    story = []
    story.append(Paragraph("ConsentDrift — Clarification Request Letter", title_style))
    story.append(Spacer(1, 6))

    org_str = consent.organisation if consent else "Service Provider"
    svc_str = consent.service_name if consent else "Service"
    date_str = d.created_at.strftime("%B %d, %Y")

    story.append(Paragraph(f"<b>Organisation:</b> {org_str} | <b>Service:</b> {svc_str} | <b>Date:</b> {date_str}", meta_style))
    story.append(Paragraph(f"<b>Template:</b> {d.template.upper()} | <b>Status:</b> {d.status.title()}", meta_style))
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=14))

    story.append(Paragraph(f"<b>Subject:</b> {d.subject}", body_style))
    story.append(Spacer(1, 14))

    # Split body paragraphs
    paragraphs = d.body.split("\n\n")
    for para in paragraphs:
        clean_para = para.strip().replace("\n", "<br/>")
        if clean_para:
            story.append(Paragraph(clean_para, body_style))
            story.append(Spacer(1, 10))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=10))
    disclaimer = "Generated by ConsentDrift. Findings are potential discrepancies based on submitted evidence. This document does not constitute legal advice."
    story.append(Paragraph(disclaimer, ParagraphStyle('Disclaimer', parent=meta_style, fontSize=8, leading=10)))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"clarification_request_{d.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
