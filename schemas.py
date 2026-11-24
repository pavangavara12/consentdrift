import re
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# ----------------- AUTH SCHEMAS -----------------
class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    phone: Optional[str] = Field(None, max_length=50)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        s = v.strip().lower()
        if not re.match(EMAIL_REGEX, s):
            raise ValueError("Invalid email format")
        return s

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Full name cannot be empty")
        return s

class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        s = v.strip().lower()
        if not re.match(EMAIL_REGEX, s):
            raise ValueError("Invalid email format")
        return s

class UserRead(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        s = v.strip().lower()
        if not re.match(EMAIL_REGEX, s):
            raise ValueError("Invalid email format")
        return s

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

class DeleteAccountRequest(BaseModel):
    password: str
    confirm_text: str  # Must match "DELETE MY ACCOUNT"

# ----------------- CONSENT SCHEMAS -----------------
class ConsentBase(BaseModel):
    organisation: str = Field(..., min_length=1, max_length=255, description="Organisation name")
    service_name: str = Field(..., min_length=1, max_length=255, description="Service name")
    original_purpose: str = Field(..., min_length=1, max_length=20000, description="Original purpose text")
    original_consent_text: Optional[str] = Field(None, max_length=50000, description="Full pasted consent policy text")
    data_categories: List[str] = Field(default_factory=list, description="Data categories")
    source_type: Literal["official_text", "user_summary"] = "official_text"
    consent_date: Optional[date] = None

    @field_validator("organisation", "service_name", "original_purpose")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace only")
        return s

class ConsentCreate(ConsentBase):
    pass

class EvidenceRead(BaseModel):
    id: int
    consent_id: int
    title: str
    evidence_type: str
    content: str
    source: Optional[str] = None
    file_name: Optional[str] = None
    content_hash: str
    submitted_at: datetime
    integrity_status: str = "unchanged"

    class Config:
        from_attributes = True

class AnalysisRead(BaseModel):
    id: int
    evidence_id: int
    consent_id: int
    mode: str  # rules-only | hybrid
    risk: str  # LOW | MEDIUM | HIGH | INSUFFICIENT_EVIDENCE
    score: int = 0
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    highlight_spans: List[Any] = Field(default_factory=list)
    original_purposes: List[str] = Field(default_factory=list)
    new_purposes: List[str] = Field(default_factory=list)
    data_categories_affected: List[str] = Field(default_factory=list)
    third_party_sharing: str = "unclear"  # yes | no | unclear
    evidence_quotes: List[str] = Field(default_factory=list)
    rule_signals: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: str
    recommended_action: str
    statement_labels: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    created_at: datetime
    evidence_content: Optional[str] = None
    quote_spans: Optional[List[Dict[str, Any]]] = None
    consent_service_name: Optional[str] = None
    consent_organisation: Optional[str] = None
    consent_original_purpose: Optional[str] = None
    integrity_status: str = "unchanged"

    class Config:
        from_attributes = True

class ConsentListItem(ConsentBase):
    id: int
    created_at: datetime
    latest_risk: Optional[str] = None
    latest_score: Optional[int] = None
    analyses_count: int = 0

    class Config:
        from_attributes = True

class ConsentDetail(ConsentBase):
    id: int
    created_at: datetime
    latest_risk: Optional[str] = None
    latest_score: Optional[int] = None
    analyses_count: int = 0
    evidence: List[EvidenceRead] = Field(default_factory=list)
    analyses: List[AnalysisRead] = Field(default_factory=list)

    class Config:
        from_attributes = True

class EvidenceCreate(BaseModel):
    consent_id: int
    title: str = Field(..., min_length=1, max_length=255)
    evidence_type: Literal["email", "policy", "notification", "sms", "other"]
    content: str = Field(..., min_length=1, max_length=50000)
    source: Optional[str] = Field(None, max_length=500)
    file_name: Optional[str] = None

    @field_validator("title", "content")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace only")
        return s

# ----------------- ALERT SCHEMAS -----------------
class AlertEventRead(BaseModel):
    id: int
    alert_id: int
    event: str
    created_at: datetime

    class Config:
        from_attributes = True

class AlertRead(BaseModel):
    id: int
    user_id: int
    analysis_id: int
    consent_id: int
    risk: str
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    service_name: Optional[str] = None
    organisation: Optional[str] = None
    score: Optional[int] = None
    events: List[AlertEventRead] = Field(default_factory=list)

    class Config:
        from_attributes = True

class AlertUpdate(BaseModel):
    status: Optional[Literal["new", "acknowledged", "clarification_sent", "resolved", "dismissed"]] = None
    notes: Optional[str] = None

# ----------------- COMPLAINT DRAFT SCHEMAS -----------------
class ClarificationRequestCreate(BaseModel):
    template: Optional[Literal["general", "dpdp", "gdpr", "ccpa"]] = "general"

class DraftCreate(BaseModel):
    consent_id: int
    analysis_id: Optional[int] = None
    template: Literal["general", "dpdp", "gdpr", "ccpa"] = "general"
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)

class DraftUpdate(BaseModel):
    template: Optional[Literal["general", "dpdp", "gdpr", "ccpa"]] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Optional[Literal["draft", "sent", "responded"]] = None

class DraftRead(BaseModel):
    id: int
    user_id: int
    consent_id: int
    analysis_id: Optional[int] = None
    template: str
    subject: str
    body: str
    status: str
    created_at: datetime
    updated_at: datetime
    service_name: Optional[str] = None
    organisation: Optional[str] = None

    class Config:
        from_attributes = True

# ----------------- NOTIFICATION SCHEMAS -----------------
class NotificationRead(BaseModel):
    id: int
    user_id: int
    message: str
    link: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- PLAYGROUND & SIMULATOR -----------------
class PlaygroundRequest(BaseModel):
    original_purpose: str = Field(..., min_length=1, max_length=20000)
    evidence_text: str = Field(..., min_length=1, max_length=20000)

# ----------------- TIMELINE EVENT -----------------
class TimelineEvent(BaseModel):
    id: str
    type: Literal["consent_created", "evidence_submitted", "alert_raised", "draft_generated"]
    title: str
    description: str
    risk: Optional[str] = None
    score: Optional[int] = None
    timestamp: datetime
    link: Optional[str] = None

class HealthResponse(BaseModel):
    status: str = "ok"
    mode: str = "rules-only"
    llm_available: bool = False
    llm_model: Optional[str] = None
