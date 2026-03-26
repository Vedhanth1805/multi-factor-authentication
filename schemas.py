from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    phone: Optional[str] = None   # mobile number for OTP login

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    mfa_enabled: bool
    mfa_type: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class MfaTypeSelect(BaseModel):
    mfa_type: str  # 'face', 'fingerprint', 'otp'

class OtpVerifyRequest(BaseModel):
    otp_code: str

# Phone-based OTP login
class OtpRequestSchema(BaseModel):
    phone: str                    # mobile number

class OtpLoginRequest(BaseModel):
    phone: str
    otp_code: str

# Password reset via email
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class FaceDescriptorRequest(BaseModel):
    face_descriptor: List[float]

class WebAuthnCredential(BaseModel):
    id: str
    rawId: str
    response: dict
    type: str
    clientExtensionResults: Optional[dict] = None
