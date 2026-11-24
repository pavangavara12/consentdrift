from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date, ForeignKey, JSON, Boolean
)
from sqlalchemy.orm import relationship
from app.db import Base

def utc_now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    consents = relationship("ConsentRecord", back_populates="user", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="user", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    drafts = relationship("ComplaintDraft", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="reset_tokens")

class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organisation = Column(String(255), nullable=False)
    service_name = Column(String(255), nullable=False)
    original_purpose = Column(Text, nullable=False)
    original_consent_text = Column(Text, nullable=True)
    data_categories = Column(JSON, default=list, nullable=False)
    source_type = Column(String(50), nullable=False, default="official_text")
    consent_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="consents")
    evidence = relationship("Evidence", back_populates="consent", cascade="all, delete-orphan", order_by="Evidence.submitted_at.desc()")
    analyses = relationship("Analysis", back_populates="consent", cascade="all, delete-orphan", order_by="Analysis.created_at.desc()")
    alerts = relationship("Alert", back_populates="consent", cascade="all, delete-orphan")
    drafts = relationship("ComplaintDraft", back_populates="consent", cascade="all, delete-orphan")

class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    consent_id = Column(Integer, ForeignKey("consent_records.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    evidence_type = Column(String(50), nullable=False)  # email | policy | notification | sms | other
    content = Column(Text, nullable=False)
    source = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=True)
    content_hash = Column(String(64), nullable=False)  # SHA-256 hex
    submitted_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="evidence")
    consent = relationship("ConsentRecord", back_populates="evidence")
    analyses = relationship("Analysis", back_populates="evidence", cascade="all, delete-orphan", order_by="Analysis.created_at.desc()")

class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    consent_id = Column(Integer, ForeignKey("consent_records.id", ondelete="CASCADE"), nullable=False, index=True)
    mode = Column(String(50), nullable=False)  # rules-only | hybrid
    risk = Column(String(50), nullable=False)  # LOW | MEDIUM | HIGH | INSUFFICIENT_EVIDENCE
    score = Column(Integer, nullable=False, default=0)  # 0 to 100
    score_breakdown = Column(JSON, default=dict, nullable=False)  # signals, weights, formula
    highlight_spans = Column(JSON, default=list, nullable=False)  # list of [start, end]
    original_purposes = Column(JSON, default=list, nullable=False)
    new_purposes = Column(JSON, default=list, nullable=False)
    data_categories_affected = Column(JSON, default=list, nullable=False)
    third_party_sharing = Column(String(20), nullable=False, default="unclear")
    evidence_quotes = Column(JSON, default=list, nullable=False)
    rule_signals = Column(JSON, default=list, nullable=False)
    explanation = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=False)
    statement_labels = Column(JSON, default=dict, nullable=False)
    warnings = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="analyses")
    consent = relationship("ConsentRecord", back_populates="analyses")
    evidence = relationship("Evidence", back_populates="analyses")
    alerts = relationship("Alert", back_populates="analysis", cascade="all, delete-orphan")
    drafts = relationship("ComplaintDraft", back_populates="analysis", cascade="all, delete-orphan")

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    consent_id = Column(Integer, ForeignKey("consent_records.id", ondelete="CASCADE"), nullable=False, index=True)
    risk = Column(String(50), nullable=False)  # MEDIUM | HIGH
    status = Column(String(50), nullable=False, default="new")  # new | acknowledged | clarification_sent | resolved | dismissed
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="alerts")
    analysis = relationship("Analysis", back_populates="alerts")
    consent = relationship("ConsentRecord", back_populates="alerts")
    events = relationship("AlertEvent", back_populates="alert", cascade="all, delete-orphan", order_by="AlertEvent.created_at.asc()")

class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    event = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    alert = relationship("Alert", back_populates="events")

class ComplaintDraft(Base):
    __tablename__ = "complaint_drafts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    consent_id = Column(Integer, ForeignKey("consent_records.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=True, index=True)
    template = Column(String(50), nullable=False, default="general")  # general | dpdp | gdpr | ccpa
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="draft")  # draft | sent | responded
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="drafts")
    consent = relationship("ConsentRecord", back_populates="drafts")
    analysis = relationship("Analysis", back_populates="drafts")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    link = Column(String(500), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="notifications")
