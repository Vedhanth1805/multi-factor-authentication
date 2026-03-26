from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse
import os
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import Base, engine
from models import User
from schemas import UserCreate, UserResponse
from dependencies import get_db, get_current_user
from utils import hash_password
from routers import auth_router
from rate_limit import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MFA Demo API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/auth", tags=["auth"])


@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(
        email=user.email,
        hashed_password=hash_password(user.password),
        phone=user.phone or None,
    )
    db.add(new_user)
    db.commit()
    return {"message": "User successfully registered"}


@app.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "mfa_enabled": current_user.mfa_enabled,
        "mfa_type": current_user.mfa_type,
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/reset-password")
@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))
