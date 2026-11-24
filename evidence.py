import io
import hashlib
import email
from email import policy
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import ConsentRecord, Evidence, Analysis, Alert, AlertEvent, Notification, User
from app.schemas import EvidenceCreate, AnalysisRead
from app.auth import get_current_user
from app.engine.pipeline import analyze

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

def process_evidence_submission(
    consent_id: int,
    title: str,
    evidence_type: str,
    content: str,
    source: Optional[str],
    file_name: Optional[str],
    current_user: User,
    db: Session
) -> AnalysisRead:
    # Verify consent ownership
    consent = db.query(ConsentRecord).filter(
        ConsentRecord.id == consent_id,
        ConsentRecord.user_id == current_user.id
    ).first()

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consent record with id {consent_id} not found."
        )

    # Content integrity hash
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    evidence = Evidence(
        user_id=current_user.id,
        consent_id=consent.id,
        title=title,
        evidence_type=evidence_type,
        content=content,
        source=source,
        file_name=file_name,
        content_hash=content_hash
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    # Run Analysis Pipeline
    analysis_payload = analyze(consent, evidence)

    analysis = Analysis(
        user_id=current_user.id,
        evidence_id=evidence.id,
        consent_id=consent.id,
        mode=analysis_payload["mode"],
        risk=analysis_payload["risk"],
        score=analysis_payload.get("score", 0),
        score_breakdown=analysis_payload.get("score_breakdown", {}),
        highlight_spans=analysis_payload.get("highlight_spans", []),
        original_purposes=analysis_payload["original_purposes"],
        new_purposes=analysis_payload["new_purposes"],
        data_categories_affected=analysis_payload["data_categories_affected"],
        third_party_sharing=analysis_payload["third_party_sharing"],
        evidence_quotes=analysis_payload["evidence_quotes"],
        rule_signals=analysis_payload["rule_signals"],
        explanation=analysis_payload["explanation"],
        recommended_action=analysis_payload["recommended_action"],
        statement_labels=analysis_payload["statement_labels"],
        warnings=analysis_payload["warnings"]
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Auto-create Alert for MEDIUM or HIGH findings
    if analysis.risk in ("MEDIUM", "HIGH"):
        alert = Alert(
            user_id=current_user.id,
            analysis_id=analysis.id,
            consent_id=consent.id,
            risk=analysis.risk,
            status="new",
            notes=f"Automated discrepancy flagged ({analysis.risk} risk, Score: {analysis.score}/100)."
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        # Activity log event
        event = AlertEvent(
            alert_id=alert.id,
            event=f"Alert generated automatically with risk level {analysis.risk}."
        )
        db.add(event)

        # In-app notification
        notification = Notification(
            user_id=current_user.id,
            message=f"New {analysis.risk} risk alert detected for {consent.service_name}.",
            link="/alerts",
            is_read=False
        )
        db.add(notification)
        db.commit()

    return AnalysisRead(
        id=analysis.id,
        evidence_id=evidence.id,
        consent_id=consent.id,
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
        evidence_content=evidence.content,
        quote_spans=analysis_payload.get("quote_spans", []),
        consent_service_name=consent.service_name,
        consent_organisation=consent.organisation,
        consent_original_purpose=consent.original_purpose,
        integrity_status="unchanged"
    )

@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def submit_evidence_text(
    req: EvidenceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis_res = process_evidence_submission(
        consent_id=req.consent_id,
        title=req.title,
        evidence_type=req.evidence_type,
        content=req.content,
        source=req.source,
        file_name=req.file_name,
        current_user=current_user,
        db=db
    )
    return {
        "analysis": analysis_res.model_dump(),
        "evidence_id": analysis_res.evidence_id,
        "consent_id": analysis_res.consent_id
    }

@router.post("/upload", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def upload_evidence_file(
    consent_id: int = Form(...),
    title: str = Form(...),
    evidence_type: str = Form(...),
    source: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 2 MB limit check
    file_bytes = await file.read()
    if len(file_bytes) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File exceeds the maximum allowed size of 2 MB."
        )

    filename = (file.filename or "").lower()
    extracted_text = ""

    if filename.endswith(".txt"):
        try:
            extracted_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            extracted_text = file_bytes.decode("latin-1", errors="replace")

    elif filename.endswith(".pdf"):
        if PdfReader is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PDF processing module not available."
            )
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            pages_text = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            extracted_text = "\n\n".join(pages_text)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse PDF file: {str(e)}"
            )

    elif filename.endswith(".eml"):
        try:
            msg = email.message_from_bytes(file_bytes, policy=policy.default)
            body_parts = []
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    if content_type == "text/plain" and "attachment" not in content_disposition:
                        body_parts.append(part.get_payload(decode=True).decode(errors="replace"))
            else:
                body_parts.append(msg.get_payload(decode=True).decode(errors="replace"))
            extracted_text = "\n".join(body_parts)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse EML email file: {str(e)}"
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a .txt, .pdf, or .eml file."
        )

    extracted_text = extracted_text.strip()
    if not extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file contains no readable text content."
        )

    analysis_res = process_evidence_submission(
        consent_id=consent_id,
        title=title,
        evidence_type=evidence_type,
        content=extracted_text,
        source=source or file.filename,
        file_name=file.filename,
        current_user=current_user,
        db=db
    )

    return {
        "analysis": analysis_res.model_dump(),
        "evidence_id": analysis_res.evidence_id,
        "consent_id": analysis_res.consent_id
    }
