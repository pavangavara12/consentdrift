from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Notification, User
from app.schemas import NotificationRead
from app.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("", response_model=List[NotificationRead])
def list_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()

@router.post("/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read."}
