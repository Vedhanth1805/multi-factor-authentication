from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from utils import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Full access token — no pre_auth, no fp_auth flags."""
    payload = decode_access_token(token)
    if payload is None or payload.get("pre_auth") or payload.get("fp_auth"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_pre_auth_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Pre-auth token — issued after password check, before any MFA step."""
    payload = decode_access_token(token)
    if payload is None or not payload.get("pre_auth"):
        raise HTTPException(status_code=401, detail="Invalid pre-auth token")
    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_fp_auth_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Fingerprint-auth token — issued after fingerprint verified, before face scan."""
    payload = decode_access_token(token)
    if payload is None or not payload.get("fp_auth"):
        raise HTTPException(status_code=401, detail="Fingerprint not yet verified")
    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
