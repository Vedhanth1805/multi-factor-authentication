from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import User
from schemas import UserLogin
from utils import verify_password


def authenticate_user(db: Session, login_data: UserLogin) -> User:
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return user
