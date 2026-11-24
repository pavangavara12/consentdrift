import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.db import Base, engine, get_db
from app import models
from app.config import LLM_API_KEY, LLM_MODEL
from app.schemas import HealthResponse
from app.seed import seed_database
from app.auth import get_current_user

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ConsentDrift API",
    description="Privacy Purpose Drift Detection Platform",
    version="2.0.0"
)

# CORS configuration for frontend and extensions
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_origin_regex=r"^chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health", response_model=HealthResponse)
def health_check():
    mode = "hybrid" if bool(LLM_API_KEY) else "rules-only"
    return HealthResponse(
        status="ok",
        mode=mode,
        llm_available=bool(LLM_API_KEY),
        llm_model=LLM_MODEL if bool(LLM_API_KEY) else None
    )

@app.post("/api/seed")
def seed_endpoint(request: Request, db: Session = Depends(get_db)):
    target_user = None
    try:
        target_user = get_current_user(request=request, db=db)
    except Exception:
        target_user = None

    result = seed_database(db=db, target_user=target_user)
    return result

from app.routers import (
    auth, playground, consents, evidence, analyses,
    alerts, drafts, notifications, analytics, account, eval_api
)

app.include_router(auth.router)
app.include_router(playground.router)
app.include_router(consents.router)
app.include_router(evidence.router)
app.include_router(analyses.router)
app.include_router(alerts.router)
app.include_router(drafts.router)
app.include_router(notifications.router)
app.include_router(analytics.router)
app.include_router(account.router)
app.include_router(eval_api.router)
