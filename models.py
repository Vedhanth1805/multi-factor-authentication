from sqlalchemy import Column, Integer, String, Boolean, Text
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    phone = Column(String, nullable=True)           # mobile number for OTP

    mfa_type = Column(String, nullable=True)       # 'face', 'fingerprint', 'otp'
    mfa_enabled = Column(Boolean, default=False)

    # OTP (phone-based login)
    otp_code = Column(String, nullable=True)
    otp_expires_at = Column(String, nullable=True)

    # Password reset (email link)
    reset_token = Column(String, nullable=True)
    reset_expires_at = Column(String, nullable=True)

    # WebAuthn (fingerprint / biometric)
    webauthn_credential_id = Column(Text, nullable=True)
    webauthn_public_key = Column(Text, nullable=True)
    webauthn_sign_count = Column(Integer, default=0)

    # Face recognition (JSON-encoded float array, length 128)
    face_descriptor = Column(Text, nullable=True)

