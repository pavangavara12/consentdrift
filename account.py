import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import ConsentRecord, Evidence, Analysis, Alert, ComplaintDraft, User
from app.auth import get_current_user

# ReportLab imports for P2 PDF Report
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib import colors

router = APIRouter(prefix="/api/account", tags=["account"])

@router.get("/export")
def export_all_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    consents = db.query(ConsentRecord).filter(ConsentRecord.user_id == current_user.id).all()
    evidence_list = db.query(Evidence).filter(Evidence.user_id == current_user.id).all()
    analyses_list = db.query(Analysis).filter(Analysis.user_id == current_user.id).all()
    alerts_list = db.query(Alert).filter(Alert.user_id == current_user.id).all()
    drafts_list = db.query(ComplaintDraft).filter(ComplaintDraft.user_id == current_user.id).all()

    return {
        "export_metadata": {
            "format": "ConsentDrift Full Data Export",
            "version": "2.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "created_at": current_user.created_at.isoformat()
            }
        },
        "applications": [
            {
                "id": c.id,
                "organisation": c.organisation,
                "service_name": c.service_name,
                "original_purpose": c.original_purpose,
                "original_consent_text": c.original_consent_text,
                "data_categories": c.data_categories,
                "source_type": c.source_type,
                "consent_date": c.consent_date.isoformat() if c.consent_date else None,
                "created_at": c.created_at.isoformat()
            }
            for c in consents
        ],
        "evidence": [
            {
                "id": e.id,
                "consent_id": e.consent_id,
                "title": e.title,
                "evidence_type": e.evidence_type,
                "source": e.source,
                "content_hash": e.content_hash,
                "submitted_at": e.submitted_at.isoformat(),
                "content": e.content
            }
            for e in evidence_list
        ],
        "analyses": [
            {
                "id": a.id,
                "consent_id": a.consent_id,
                "evidence_id": a.evidence_id,
                "mode": a.mode,
                "risk": a.risk,
                "score": a.score,
                "score_breakdown": a.score_breakdown,
                "rule_signals": a.rule_signals,
                "evidence_quotes": a.evidence_quotes,
                "explanation": a.explanation,
                "recommended_action": a.recommended_action,
                "warnings": a.warnings,
                "created_at": a.created_at.isoformat()
            }
            for a in analyses_list
        ],
        "alerts": [
            {
                "id": al.id,
                "analysis_id": al.analysis_id,
                "consent_id": al.consent_id,
                "risk": al.risk,
                "status": al.status,
                "notes": al.notes,
                "created_at": al.created_at.isoformat()
            }
            for al in alerts_list
        ],
        "complaint_drafts": [
            {
                "id": dr.id,
                "consent_id": dr.consent_id,
                "analysis_id": dr.analysis_id,
                "template": dr.template,
                "subject": dr.subject,
                "body": dr.body,
                "status": dr.status,
                "created_at": dr.created_at.isoformat()
            }
            for dr in drafts_list
        ]
    }

@router.get("/report.pdf")
def export_user_report_pdf(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    (P2) Generate a comprehensive PDF Privacy Audit Report for the user.
    """
    consents = db.query(ConsentRecord).filter(ConsentRecord.user_id == current_user.id).all()
    alerts = db.query(Alert).filter(Alert.user_id == current_user.id).all()
    analyses = db.query(Analysis).filter(Analysis.user_id == current_user.id).all()

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
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#0F172A'))
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#64748B'))
    h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontSize=13, leading=17, textColor=colors.HexColor('#1E293B'))
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#334155'))

    story = []
    story.append(Paragraph("ConsentDrift — Personal Privacy Audit Report", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Account:</b> {current_user.full_name} ({current_user.email}) | <b>Generated:</b> {datetime.now().strftime('%B %d, %Y')}", meta_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=14))

    # Summary table
    high_count = sum(1 for a in analyses if a.risk == "HIGH")
    med_count = sum(1 for a in analyses if a.risk == "MEDIUM")
    low_count = sum(1 for a in analyses if a.risk == "LOW")

    summary_data = [
        ["Total Applications", "Evidence Disclosures", "High Risk Discrepancies", "Medium Risk Discrepancies", "Low / Verified"],
        [str(len(consents)), str(len(analyses)), str(high_count), str(med_count), str(low_count)]
    ]
    t = Table(summary_data, colWidths=[100, 100, 105, 105, 94])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#334155')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0'))
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

    # Active Applications & Discrepancies
    story.append(Paragraph("Registered Privacy Baselines & Surveillance Status", h2_style))
    story.append(Spacer(1, 8))

    for c in consents:
        c_analyses = [a for a in analyses if a.consent_id == c.id]
        latest_risk = c_analyses[0].risk if c_analyses else "NO EVIDENCE"
        score_str = f"Score: {c_analyses[0].score}/100" if c_analyses else ""

        story.append(Paragraph(f"<b>{c.service_name}</b> ({c.organisation}) — <i>{latest_risk}</i> {score_str}", ParagraphStyle('Svc', parent=body_style, fontName='Helvetica-Bold')))
        story.append(Paragraph(f"<b>Baseline Purpose:</b> {c.original_purpose[:160]}...", meta_style))

        if c_analyses:
            an = c_analyses[0]
            story.append(Paragraph(f"<b>Finding:</b> {an.explanation}", body_style))
            if an.evidence_quotes:
                story.append(Paragraph(f"<b>Verified Quote:</b> \"{an.evidence_quotes[0]}\"", ParagraphStyle('Q', parent=meta_style, textColor=colors.HexColor('#1D4ED8'))))

        story.append(Spacer(1, 10))

    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=8))
    disclaimer = "ConsentDrift findings are potential discrepancies based on submitted evidence. They are not proof of misuse or a legal violation. This report does not constitute formal legal advice."
    story.append(Paragraph(disclaimer, ParagraphStyle('Disclaimer', parent=meta_style, fontSize=7, leading=9)))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"privacy_audit_report_{current_user.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
