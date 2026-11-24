import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, SessionLocal
from app.models import User, ConsentRecord, Evidence, Analysis, Alert, ComplaintDraft, Notification
from app.auth import FAILED_ATTEMPTS, PLAYGROUND_ATTEMPTS

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    FAILED_ATTEMPTS.clear()
    PLAYGROUND_ATTEMPTS.clear()
    yield

def test_registration_and_duplicate_rejection():
    # Register user 1
    res1 = client.post("/api/auth/register", json={
        "full_name": "Alice Smith",
        "email": "alice@example.com",
        "password": "Password123",
        "phone": "+1234567890"
    })
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["email"] == "alice@example.com"
    assert "password" not in data1
    assert "password_hash" not in data1

    # Attempt duplicate registration with same email
    res2 = client.post("/api/auth/register", json={
        "full_name": "Alice Two",
        "email": "alice@example.com",
        "password": "DifferentPassword123"
    })
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]

def test_login_success_failure_and_rate_limit():
    # Register user
    client.post("/api/auth/register", json={
        "full_name": "Bob Jones",
        "email": "bob@example.com",
        "password": "SecretPassword1"
    })

    # Successful login
    res_ok = client.post("/api/auth/login", json={
        "email": "bob@example.com",
        "password": "SecretPassword1"
    })
    assert res_ok.status_code == 200
    assert "access_token" in res_ok.cookies
    assert "password" not in res_ok.text
    assert "password_hash" not in res_ok.text

    # Failed login attempts
    for _ in range(5):
        res_fail = client.post("/api/auth/login", json={
            "email": "bob@example.com",
            "password": "WrongPassword9"
        })
        assert res_fail.status_code == 401
        assert res_fail.json()["detail"] == "Invalid email or password."

    # 6th attempt should be rate limited (429)
    res_limited = client.post("/api/auth/login", json={
        "email": "bob@example.com",
        "password": "SecretPassword1"
    })
    assert res_limited.status_code == 429
    assert "Too many failed login attempts" in res_limited.json()["detail"]

def test_protected_route_without_token_returns_401():
    # Anonymous request to protected routes returns 401
    res1 = client.get("/api/auth/me")
    assert res1.status_code == 401

    res2 = client.get("/api/consents")
    assert res2.status_code == 401

    res3 = client.get("/api/alerts")
    assert res3.status_code == 401

    res4 = client.get("/api/drafts")
    assert res4.status_code == 401

def test_user_isolation_user_a_cannot_read_user_b_returns_404():
    # Create User A
    res_a = client.post("/api/auth/register", json={
        "full_name": "User Alpha",
        "email": "alpha@example.com",
        "password": "Password123"
    })
    cookies_a = res_a.cookies

    # User A creates a consent
    c_res_a = client.post("/api/consents", json={
        "organisation": "Alpha Org",
        "service_name": "Alpha Service",
        "original_purpose": "Data processing for Alpha service.",
        "data_categories": ["email", "name"],
        "source_type": "official_text"
    }, cookies=cookies_a)
    assert c_res_a.status_code == 201
    consent_a_id = c_res_a.json()["id"]

    # User A submits evidence (>= 15 words)
    ev_res_a = client.post("/api/evidence", json={
        "consent_id": consent_a_id,
        "title": "Alpha Marketing Notice",
        "evidence_type": "email",
        "content": "Please note that we may share your registered personal email address with advertising partners and third parties for promotional communications, special deals, and partner offers."
    }, cookies=cookies_a)
    assert ev_res_a.status_code == 201
    assert ev_res_a.json()["analysis"]["risk"] == "HIGH"
    evidence_a_id = ev_res_a.json()["evidence_id"]
    analysis_a_id = ev_res_a.json()["analysis"]["id"]

    # User A has an auto-generated alert
    alerts_a = client.get("/api/alerts", cookies=cookies_a).json()
    assert len(alerts_a) > 0
    alert_a_id = alerts_a[0]["id"]

    # User A creates a draft
    draft_res_a = client.post(f"/api/analyses/{analysis_a_id}/clarification", cookies=cookies_a)
    assert draft_res_a.status_code == 201
    draft_a_id = draft_res_a.json()["id"]

    # Create User B
    res_b = client.post("/api/auth/register", json={
        "full_name": "User Beta",
        "email": "beta@example.com",
        "password": "Password123"
    })
    cookies_b = res_b.cookies

    # User B tries to access User A's Consent -> MUST return 404
    assert client.get(f"/api/consents/{consent_a_id}", cookies=cookies_b).status_code == 404

    # User B tries to access User A's Analysis -> MUST return 404
    assert client.get(f"/api/analyses/{analysis_a_id}", cookies=cookies_b).status_code == 404

    # User B tries to access User A's Alert -> MUST return 404
    assert client.patch(f"/api/alerts/{alert_a_id}", json={"status": "acknowledged"}, cookies=cookies_b).status_code == 404

    # User B tries to access User A's Draft -> MUST return 404
    assert client.get(f"/api/drafts/{draft_a_id}", cookies=cookies_b).status_code == 404

    # User B lists consents -> sees 0 items
    assert len(client.get("/api/consents", cookies=cookies_b).json()) == 0

def test_playground_unauthenticated_and_stores_nothing():
    db = SessionLocal()
    initial_consents = db.query(ConsentRecord).count()
    initial_evidence = db.query(Evidence).count()
    initial_analyses = db.query(Analysis).count()

    # Call playground without cookies/auth
    res = client.post("/api/playground/analyze", json={
        "original_purpose": "We use your data solely to deliver online learning courses.",
        "evidence_text": "Please note that we will share your email address with external advertising partners and data brokers for special promotional deals and campaigns."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["risk"] == "HIGH"
    assert data["score"] >= 75
    assert "score_breakdown" in data
    assert len(data["evidence_quotes"]) > 0

    # Verify nothing was stored in the database
    assert db.query(ConsentRecord).count() == initial_consents
    assert db.query(Evidence).count() == initial_evidence
    assert db.query(Analysis).count() == initial_analyses
    db.close()

def test_alert_status_change_writes_event_and_notification():
    # Register & setup
    res = client.post("/api/auth/register", json={
        "full_name": "Charlie Day",
        "email": "charlie@example.com",
        "password": "Password123"
    })
    cookies = res.cookies

    c_res = client.post("/api/consents", json={
        "organisation": "Acme Corp",
        "service_name": "Acme Cloud",
        "original_purpose": "Storage of user backups.",
        "data_categories": ["files"],
        "source_type": "official_text"
    }, cookies=cookies)
    cid = c_res.json()["id"]

    # Submit evidence that triggers HIGH
    client.post("/api/evidence", json={
        "consent_id": cid,
        "title": "Marketing Terms",
        "evidence_type": "email",
        "content": "In addition to core services, we sell and share your personal data with third-party data brokers and marketing partners for direct targeted advertising."
    }, cookies=cookies)

    alerts = client.get("/api/alerts", cookies=cookies).json()
    assert len(alerts) == 1
    alert_id = alerts[0]["id"]
    assert alerts[0]["status"] == "new"

    # Patch status to "acknowledged"
    patch_res = client.patch(f"/api/alerts/{alert_id}", json={
        "status": "acknowledged",
        "notes": "Reviewed by user."
    }, cookies=cookies)
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "acknowledged"

    # Check alert events activity log
    events = client.get(f"/api/alerts/{alert_id}/events", cookies=cookies).json()
    assert len(events) >= 2  # initial creation + status update
    assert any("acknowledged" in e["event"] for e in events)

    # Check notifications
    notifs = client.get("/api/notifications", cookies=cookies).json()
    assert len(notifs) >= 2
    assert any("acknowledged" in n["message"] for n in notifs)

def test_upload_rejects_unsupported_and_empty_files():
    res = client.post("/api/auth/register", json={
        "full_name": "Diana Prince",
        "email": "diana@example.com",
        "password": "Password123"
    })
    cookies = res.cookies

    c_res = client.post("/api/consents", json={
        "organisation": "Themyscira Inc",
        "service_name": "Shield Portal",
        "original_purpose": "Security verification.",
        "data_categories": ["id"],
        "source_type": "official_text"
    }, cookies=cookies)
    cid = c_res.json()["id"]

    # 1. Unsupported file format (.exe)
    res_unsupported = client.post(
        "/api/evidence/upload",
        data={"consent_id": cid, "title": "Bad File", "evidence_type": "policy"},
        files={"file": ("malicious.exe", b"binarycontent", "application/octet-stream")},
        cookies=cookies
    )
    assert res_unsupported.status_code == 400
    assert "Unsupported file format" in res_unsupported.json()["detail"]

    # 2. Empty file
    res_empty = client.post(
        "/api/evidence/upload",
        data={"consent_id": cid, "title": "Empty File", "evidence_type": "policy"},
        files={"file": ("empty.txt", b"   ", "text/plain")},
        cookies=cookies
    )
    assert res_empty.status_code == 400
    assert "contains no readable text" in res_empty.json()["detail"]

    # 3. Valid .txt upload succeeds
    valid_content = "Please note that we will send promotional communication, advertising notices, and special partner deals directly to your registered personal email address."
    res_valid = client.post(
        "/api/evidence/upload",
        data={"consent_id": cid, "title": "Valid Notice", "evidence_type": "email"},
        files={"file": ("notice.txt", valid_content.encode("utf-8"), "text/plain")},
        cookies=cookies
    )
    assert res_valid.status_code == 201
    assert res_valid.json()["analysis"]["risk"] == "HIGH"

def test_evidence_hash_changes_detected():
    res = client.post("/api/auth/register", json={
        "full_name": "Edward Nygma",
        "email": "edward@example.com",
        "password": "Password123"
    })
    cookies = res.cookies

    c_res = client.post("/api/consents", json={
        "organisation": "Riddle Corp",
        "service_name": "Riddle Portal",
        "original_purpose": "Solving puzzles.",
        "data_categories": ["riddles"],
        "source_type": "official_text"
    }, cookies=cookies)
    cid = c_res.json()["id"]

    ev_res = client.post("/api/evidence", json={
        "consent_id": cid,
        "title": "Terms",
        "evidence_type": "policy",
        "content": "We do not share any puzzle solutions with external third parties or advertisers."
    }, cookies=cookies)
    aid = ev_res.json()["analysis"]["id"]
    eid = ev_res.json()["evidence_id"]

    # View analysis - integrity should be "unchanged"
    an_res1 = client.get(f"/api/analyses/{aid}", cookies=cookies)
    assert an_res1.status_code == 200
    assert an_res1.json()["integrity_status"] == "unchanged"

    # Simulate tampering with evidence in the database
    db = SessionLocal()
    ev_record = db.query(Evidence).filter(Evidence.id == eid).first()
    ev_record.content = "TAMPERED CONTENT: We secretly sell everything to data brokers."
    db.commit()
    db.close()

    # View analysis again - integrity must detect change ("modified")
    an_res2 = client.get(f"/api/analyses/{aid}", cookies=cookies)
    assert an_res2.status_code == 200
    assert an_res2.json()["integrity_status"] == "modified"
