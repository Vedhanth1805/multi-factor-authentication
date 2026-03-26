from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Dict
import json, base64, math, secrets

from dependencies import get_db, get_current_user, get_pre_auth_user, get_fp_auth_user
from models import User
from schemas import UserLogin, FaceDescriptorRequest, WebAuthnCredential, OtpRequestSchema, OtpLoginRequest, ForgotPasswordRequest, ResetPasswordRequest
from auth import authenticate_user
from utils import create_access_token, generate_otp, hash_password, verify_password
from rate_limit import limiter

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
    base64url_to_bytes,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    ResidentKeyRequirement,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    AuthenticatorAttestationResponse,
    AuthenticationCredential,
    AuthenticatorAssertionResponse,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier

router = APIRouter()

RP_ID = "localhost"
RP_NAME = "MFA Demo"
ORIGIN = "http://localhost:8000"

_reg_challenges: Dict[str, bytes] = {}
_auth_challenges: Dict[str, bytes] = {}


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _face_match(stored: list, incoming: list, threshold: float = 0.45) -> bool:
    if len(stored) != len(incoming):
        return False
    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(stored, incoming)))
    print(f"[FACE] euclidean distance = {dist:.4f} (threshold={threshold})")
    return dist < threshold


# ── LOGIN ─────────────────────────────────────────────────────────────────────

@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, login_data: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, login_data)
    # Always issue pre_auth token — frontend decides setup vs verify based on mfa_enabled
    pre_token = create_access_token({"sub": user.email, "pre_auth": True}, expires_minutes=10)
    return {
        "pre_token": pre_token,
        "mfa_enabled": user.mfa_enabled,
        "setup_required": not user.mfa_enabled,
    }


# ── MFA SETUP (one-time, permanent) ──────────────────────────────────────────
# Step 1: Register Fingerprint (requires pre_auth token)

@router.post("/mfa/setup/webauthn/begin")
def setup_webauthn_begin(user: User = Depends(get_pre_auth_user)):
    if user.mfa_enabled:
        raise HTTPException(400, "MFA already set up — cannot change")
    opts = generate_registration_options(
        rp_id=RP_ID, rp_name=RP_NAME,
        user_id=str(user.id).encode(),
        user_name=user.email, user_display_name=user.email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
            resident_key=ResidentKeyRequirement.DISCOURAGED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )
    _reg_challenges[user.email] = opts.challenge
    return json.loads(options_to_json(opts))


@router.post("/mfa/setup/webauthn/complete")
def setup_webauthn_complete(cred: WebAuthnCredential, user: User = Depends(get_pre_auth_user), db: Session = Depends(get_db)):
    if user.mfa_enabled:
        raise HTTPException(400, "MFA already set up — cannot change")
    challenge = _reg_challenges.get(user.email)
    if not challenge:
        raise HTTPException(400, "No registration challenge found")
    try:
        reg_cred = RegistrationCredential(
            id=cred.id, raw_id=base64url_to_bytes(cred.rawId),
            response=AuthenticatorAttestationResponse(
                client_data_json=base64url_to_bytes(cred.response["clientDataJSON"]),
                attestation_object=base64url_to_bytes(cred.response["attestationObject"]),
            ),
            type=cred.type,
        )
        v = verify_registration_response(
            credential=reg_cred, expected_challenge=challenge,
            expected_rp_id=RP_ID, expected_origin=ORIGIN,
            require_user_verification=True,
        )
    except Exception as e:
        raise HTTPException(400, f"Fingerprint registration failed: {e}")
    user.webauthn_credential_id = _b64url(v.credential_id)
    user.webauthn_public_key = base64.b64encode(v.credential_public_key).decode()
    user.webauthn_sign_count = v.sign_count
    db.commit()
    _reg_challenges.pop(user.email, None)
    # Return setup_fp token so frontend knows fingerprint step is done (but MFA not yet active)
    setup_fp_token = create_access_token({"sub": user.email, "pre_auth": True, "fp_setup_done": True}, expires_minutes=10)
    return {"message": "Fingerprint registered", "setup_fp_token": setup_fp_token}


# Step 2: Register Face (requires pre_auth token with fp_setup_done)
@router.post("/mfa/setup/face")
def setup_face(data: FaceDescriptorRequest, request: Request, db: Session = Depends(get_db)):
    # Parse token manually to check fp_setup_done
    from fastapi.security import OAuth2PasswordBearer
    from utils import decode_access_token
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "")
    payload = decode_access_token(token)
    if not payload or not payload.get("pre_auth") or not payload.get("fp_setup_done"):
        raise HTTPException(401, "Fingerprint must be registered first")
    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.mfa_enabled:
        raise HTTPException(400, "MFA already set up — cannot change")
    if not user.webauthn_credential_id:
        raise HTTPException(400, "Register fingerprint first")
    if len(data.face_descriptor) != 128:
        raise HTTPException(400, "Invalid face descriptor")
    user.face_descriptor = json.dumps(data.face_descriptor)
    user.mfa_enabled = True  # ← PERMANENTLY ENABLED
    user.mfa_type = "both"
    db.commit()
    # Issue full token — setup complete
    full_token = create_access_token({"sub": user.email})
    return {"message": "Face registered. MFA fully active.", "access_token": full_token, "token_type": "bearer"}


# ── MFA VERIFICATION (login flow) ────────────────────────────────────────────
# Step 1: Verify Fingerprint (accepts pre_auth) → returns fp_auth token

@router.post("/mfa/verify/webauthn/begin")
def verify_webauthn_begin(user: User = Depends(get_pre_auth_user)):
    if not user.webauthn_credential_id:
        raise HTTPException(400, "No fingerprint registered")
    opts = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(user.webauthn_credential_id))],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    _auth_challenges[user.email] = opts.challenge
    return json.loads(options_to_json(opts))


@router.post("/mfa/verify/webauthn/complete")
@limiter.limit("5/minute")
def verify_webauthn_complete(request: Request, cred: WebAuthnCredential, user: User = Depends(get_pre_auth_user), db: Session = Depends(get_db)):
    challenge = _auth_challenges.get(user.email)
    if not challenge:
        raise HTTPException(400, "No auth challenge")
    try:
        auth_cred = AuthenticationCredential(
            id=cred.id, raw_id=base64url_to_bytes(cred.rawId),
            response=AuthenticatorAssertionResponse(
                client_data_json=base64url_to_bytes(cred.response["clientDataJSON"]),
                authenticator_data=base64url_to_bytes(cred.response["authenticatorData"]),
                signature=base64url_to_bytes(cred.response["signature"]),
                user_handle=base64url_to_bytes(cred.response["userHandle"]) if cred.response.get("userHandle") else None,
            ),
            type=cred.type,
        )
        v = verify_authentication_response(
            credential=auth_cred, expected_challenge=challenge,
            expected_rp_id=RP_ID, expected_origin=ORIGIN,
            credential_public_key=base64.b64decode(user.webauthn_public_key),
            credential_current_sign_count=user.webauthn_sign_count,
            require_user_verification=True,
        )
    except Exception as e:
        raise HTTPException(400, f"Fingerprint failed: {e}")
    user.webauthn_sign_count = v.new_sign_count
    db.commit()
    _auth_challenges.pop(user.email, None)
    # Return fp_auth token — fingerprint passed, face scan next
    fp_token = create_access_token({"sub": user.email, "fp_auth": True}, expires_minutes=5)
    return {"fp_token": fp_token, "message": "Fingerprint verified — scan your face next"}


# Step 2: Verify Face (accepts fp_auth token) → returns full token
@router.post("/mfa/verify/face")
@limiter.limit("5/minute")
def verify_face(request: Request, data: FaceDescriptorRequest, user: User = Depends(get_fp_auth_user)):
    if not user.face_descriptor:
        raise HTTPException(400, "No face registered")
    stored = json.loads(user.face_descriptor)
    if not _face_match(stored, data.face_descriptor):
        raise HTTPException(401, "Face does not match. Access denied.")
    full_token = create_access_token({"sub": user.email})
    return {"access_token": full_token, "token_type": "bearer"}


# ── OTP LOGIN (phone-based, passwordless) ────────────────────────────────────

@router.post("/otp/request")
@limiter.limit("5/minute")
def otp_request(request: Request, body: OtpRequestSchema, db: Session = Depends(get_db)):
    """Generate a 6-digit OTP and send via SMS (Twilio) or console in demo mode."""
    from datetime import datetime, timedelta
    from sms_service import send_otp_sms

    # Normalize phone: removing spaces
    clean_phone = body.phone.replace(" ", "")
    user = db.query(User).filter(User.phone == clean_phone).first()
    if not user:
        # Fallback check just in case the DB has it saved *with* a space
        user = db.query(User).filter(User.phone == body.phone).first()
        
    if not user:
        # Generic message to avoid phone enumeration
        print(f"[OTP DEBUG] User not found for phone '{body.phone}' or '{clean_phone}'")
        return {"message": "If that number is registered, an OTP has been sent."}

    otp = generate_otp()
    user.otp_code = hash_password(otp)
    user.otp_expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    db.commit()

    send_otp_sms(clean_phone, otp)

    return {"message": "If that number is registered, an OTP has been sent."}


@router.post("/otp/verify")
@limiter.limit("5/minute")
def otp_verify(request: Request, body: OtpLoginRequest, db: Session = Depends(get_db)):
    """Verify the phone OTP and return a pre_auth token (if MFA) or full access token."""
    from datetime import datetime
    INVALID_MSG = "Invalid or expired OTP."

    clean_phone = body.phone.replace(" ", "")
    user = db.query(User).filter(User.phone == clean_phone).first()
    if not user:
        user = db.query(User).filter(User.phone == body.phone).first()

    if not user or not user.otp_code or not user.otp_expires_at:
        raise HTTPException(status_code=401, detail=INVALID_MSG)

    expires_at = datetime.fromisoformat(user.otp_expires_at)
    if datetime.utcnow() > expires_at:
        user.otp_code = None
        user.otp_expires_at = None
        db.commit()
        raise HTTPException(status_code=401, detail=INVALID_MSG)

    if not verify_password(body.otp_code, user.otp_code):
        raise HTTPException(status_code=401, detail=INVALID_MSG)

    # Consume OTP (one-time use)
    user.otp_code = None
    user.otp_expires_at = None
    db.commit()

    if user.mfa_enabled:
        # Require biometrics next
        pre_token = create_access_token({"sub": user.email, "pre_auth": True}, expires_minutes=10)
        return {"access_token": pre_token, "token_type": "pre_auth"}
    else:
        # No biometrics, log in immediately
        full_token = create_access_token({"sub": user.email})
        return {"access_token": full_token, "token_type": "bearer"}


# ── FORGOT / RESET PASSWORD ───────────────────────────────────────────────────

@router.post("/forgot-password")
@limiter.limit("3/minute")
def forgot_password(request: Request, body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Send a password-reset email with a 30-min token."""
    from datetime import datetime, timedelta
    from email_service import send_reset_email

    user = db.query(User).filter(User.email == body.email).first()
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_expires_at = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
        db.commit()
        send_reset_email(body.email, token)

    # Always return generic message
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
@limiter.limit("5/minute")
def reset_password(request: Request, body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Validate reset token and update the user's password."""
    from datetime import datetime

    user = db.query(User).filter(User.reset_token == body.token).first()
    if not user or not user.reset_expires_at:
        raise HTTPException(400, "Invalid or expired reset link.")

    if datetime.utcnow() > datetime.fromisoformat(user.reset_expires_at):
        user.reset_token = None
        user.reset_expires_at = None
        db.commit()
        raise HTTPException(400, "Reset link has expired. Please request a new one.")

    user.hashed_password = hash_password(body.new_password)
    user.reset_token = None
    user.reset_expires_at = None
    db.commit()
    return {"message": "Password updated successfully. You can now log in."}

