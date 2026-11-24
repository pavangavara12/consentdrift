from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, PasswordResetToken
from app.schemas import (
    UserRegister, UserLogin, UserRead, TokenResponse,
    ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest, DeleteAccountRequest
)
from app.auth import (
    hash_password, verify_password, check_login_rate_limit, record_failed_login,
    reset_failed_login, create_access_token, create_refresh_token, decode_token,
    get_current_user, generate_reset_token, hash_token_str
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(req: UserRegister, response: Response, db: Session = Depends(get_db)):
    email_clean = req.email.lower().strip()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    pwd_hash = hash_password(req.password)
    user = User(
        full_name=req.full_name.strip(),
        email=email_clean,
        password_hash=pwd_hash,
        phone=req.phone.strip() if req.phone else None,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Automatically set authentication cookies upon registration
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=15 * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=7 * 24 * 3600
    )

    return user

@router.post("/login", response_model=UserRead)
def login(req: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "127.0.0.1"
    email_clean = req.email.lower().strip()

    check_login_rate_limit(email_clean, client_ip)

    user = db.query(User).filter(User.email == email_clean).first()
    if not user or not verify_password(req.password, user.password_hash):
        record_failed_login(email_clean, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account has been deactivated."
        )

    reset_failed_login(email_clean, client_ip)

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=15 * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=7 * 24 * 3600
    )

    return user

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token", samesite="lax", httponly=True)
    response.delete_cookie(key="refresh_token", samesite="lax", httponly=True)
    return {"message": "Logged out successfully."}

@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing."
        )

    payload = decode_token(refresh_token, expected_type="refresh")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    user = db.query(User).filter(User.id == int(user_id_str), User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    new_access_token = create_access_token(user.id)
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=15 * 60
    )
    return {"message": "Access token refreshed."}

@router.post("/token", response_model=TokenResponse)
def get_bearer_token(req: UserLogin, request: Request, db: Session = Depends(get_db)):
    """
    Direct bearer token endpoint used by the Chrome Extension.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    email_clean = req.email.lower().strip()

    check_login_rate_limit(email_clean, client_ip)

    user = db.query(User).filter(User.email == email_clean).first()
    if not user or not verify_password(req.password, user.password_hash):
        record_failed_login(email_clean, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    reset_failed_login(email_clean, client_ip)
    access_token = create_access_token(user.id)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email_clean = req.email.lower().strip()
    user = db.query(User).filter(User.email == email_clean, User.is_active == True).first()

    if user:
        raw_token, token_hash = generate_reset_token()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=30)
        reset_entry = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            used=False
        )
        db.add(reset_entry)
        db.commit()

        # Dev mode log
        print(f"\n[DEV PASSWORD RESET] Link for {email_clean}: http://localhost:5173/reset-password?token={raw_token}\n")

    return {"message": "If that email is registered, password reset instructions have been generated."}

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hash_token_str(req.token)
    reset_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used == False
    ).first()

    now = datetime.now(timezone.utc)
    if not reset_record or reset_record.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token."
        )

    user = db.query(User).filter(User.id == reset_record.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found.")

    user.password_hash = hash_password(req.new_password)
    reset_record.used = True
    db.commit()

    return {"message": "Password has been successfully updated. You may now log in."}

@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password does not match."
        )

    current_user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"message": "Password updated successfully."}

@router.delete("/account")
def delete_account(
    req: DeleteAccountRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if req.confirm_text != "DELETE MY ACCOUNT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation text must exactly match 'DELETE MY ACCOUNT'."
        )

    if not verify_password(req.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password."
        )

    # Cascade deletes everything associated with this user
    db.delete(current_user)
    db.commit()

    response.delete_cookie(key="access_token", samesite="lax", httponly=True)
    response.delete_cookie(key="refresh_token", samesite="lax", httponly=True)
    return {"message": "Your account and all associated data have been permanently deleted."}
