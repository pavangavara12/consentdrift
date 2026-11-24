from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Alert, AlertEvent, Notification, ConsentRecord, Analysis, User
from app.schemas import AlertRead, AlertUpdate, AlertEventRead
from app.auth import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

@router.get("", response_model=List[AlertRead])
def list_alerts(
    risk: Optional[str] = Query(None, description="Filter by risk: MEDIUM, HIGH"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: new, acknowledged, clarification_sent, resolved, dismissed"),
    q: Optional[str] = Query(None, description="Search term for organisation or service name"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Alert).filter(Alert.user_id == current_user.id)

    if risk and risk != "all":
        query = query.filter(Alert.risk == risk.upper())

    if status_filter and status_filter != "all":
        query = query.filter(Alert.status == status_filter.lower())

    alerts = query.order_by(Alert.created_at.desc()).all()

    results: List[AlertRead] = []
    for al in alerts:
        consent = db.query(ConsentRecord).filter(ConsentRecord.id == al.consent_id).first()
        analysis = db.query(Analysis).filter(Analysis.id == al.analysis_id).first()

        # If q search provided, filter by service or organisation
        if q:
            term = q.lower().strip()
            org_match = consent and term in consent.organisation.lower()
            srv_match = consent and term in consent.service_name.lower()
            note_match = al.notes and term in al.notes.lower()
            if not (org_match or srv_match or note_match):
                continue

        events = db.query(AlertEvent).filter(AlertEvent.alert_id == al.id).order_by(AlertEvent.created_at.desc()).all()

        results.append(AlertRead(
            id=al.id,
            user_id=al.user_id,
            analysis_id=al.analysis_id,
            consent_id=al.consent_id,
            risk=al.risk,
            status=al.status,
            notes=al.notes,
            created_at=al.created_at,
            updated_at=al.updated_at,
            service_name=consent.service_name if consent else None,
            organisation=consent.organisation if consent else None,
            score=analysis.score if analysis else None,
            events=[AlertEventRead.model_validate(e) for e in events]
        ))

    return results

@router.patch("/{id}", response_model=AlertRead)
def update_alert(
    id: int,
    req: AlertUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    alert = db.query(Alert).filter(
        Alert.id == id,
        Alert.user_id == current_user.id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {id} not found."
        )

    consent = db.query(ConsentRecord).filter(ConsentRecord.id == alert.consent_id).first()
    analysis = db.query(Analysis).filter(Analysis.id == alert.analysis_id).first()

    changes = []
    if req.status and req.status != alert.status:
        old_status = alert.status
        alert.status = req.status
        changes.append(f"Status changed from '{old_status}' to '{req.status}'")

    if req.notes is not None and req.notes != alert.notes:
        alert.notes = req.notes
        changes.append("Notes updated")

    if changes:
        db.commit()
        db.refresh(alert)

        # Write activity log event
        event = AlertEvent(
            alert_id=alert.id,
            event=". ".join(changes) + "."
        )
        db.add(event)

        # Write notification
        notification = Notification(
            user_id=current_user.id,
            message=f"Alert for {consent.service_name if consent else 'service'} updated: {', '.join(changes)}.",
            link="/alerts",
            is_read=False
        )
        db.add(notification)
        db.commit()

    events = db.query(AlertEvent).filter(AlertEvent.alert_id == alert.id).order_by(AlertEvent.created_at.desc()).all()

    return AlertRead(
        id=alert.id,
        user_id=alert.user_id,
        analysis_id=alert.analysis_id,
        consent_id=alert.consent_id,
        risk=alert.risk,
        status=alert.status,
        notes=alert.notes,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
        service_name=consent.service_name if consent else None,
        organisation=consent.organisation if consent else None,
        score=analysis.score if analysis else None,
        events=[AlertEventRead.model_validate(e) for e in events]
    )

@router.get("/{id}/events", response_model=List[AlertEventRead])
def get_alert_events(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    alert = db.query(Alert).filter(
        Alert.id == id,
        Alert.user_id == current_user.id
    ).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")

    events = db.query(AlertEvent).filter(AlertEvent.alert_id == id).order_by(AlertEvent.created_at.asc()).all()
    return events
