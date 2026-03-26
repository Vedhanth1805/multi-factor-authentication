# API Specification: Advanced Multi-Factor Authentication System

## Base URL
`${API_GATEWAY_URL}/api/v1/auth`

---

## 1. POST /register

**Purpose:** Registers a new user, hashes their password, and establishes their initial account state.
**Authentication Required:** No
**Rate Limiting:** 5 requests per 10 minutes per IP.

### Request Body
```json
{
  "email": "user@enterprise.com",
  "password": "SecurePassword123!",
  "first_name": "Jane",
  "last_name": "Doe"
}
```

### Success Response (201 Created)
```json
{
  "status": "success",
  "message": "User registered successfully.",
  "data": {
    "user_id": "uuid-v4-string",
    "email": "user@enterprise.com",
    "next_steps_required": ["setup_totp", "setup_face", "setup_fingerprint"]
  }
}
```

### Error Responses
- **400 Bad Request:** Missing fields, weak password, or invalid email format.
- **409 Conflict:** Email already registered.

---

## 2. POST /login

**Purpose:** Initiates the authentication flow (Step 1). Validates the user's password and issues a transient session token to proceed to Phase 2.
**Authentication Required:** No
**Rate Limiting:** 10 requests per minute per IP. Account lockout after 5 consecutive failed password attempts.

### Request Body
```json
{
  "email": "user@enterprise.com",
  "password": "SecurePassword123!"
}
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Password verified. Proceed to Step 2.",
  "data": {
    "auth_session_id": "redis-session-uuid",
    "expires_in_seconds": 300,
    "next_step": "/verify-otp"
  }
}
```

### Error Responses
- **401 Unauthorized:** Invalid email or password.
- **403 Forbidden:** Account locked due to too many failed attempts.

---

## 3. POST /verify-otp

**Purpose:** Validates the Time-Based One-Time Password (TOTP) from an authenticator app (Step 2).
**Authentication Required:** Yes (Transient Context via `auth_session_id`)
**Rate Limiting:** Session-bound. 3 failed attempts incur a 5-second delay. 5 failed attempts destroy the `auth_session_id`.

### Request Body
```json
{
  "auth_session_id": "redis-session-uuid",
  "otp_code": "123456"
}
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "OTP verified. Proceed to Step 3.",
  "data": {
    "auth_session_id": "redis-session-uuid",
    "next_step": "/verify-face"
  }
}
```

### Error Responses
- **400 Bad Request:** OTP code format invalid.
- **401 Unauthorized:** Incorrect OTP code.
- **404 Not Found:** `auth_session_id` expired or invalid.

---

## 4. POST /verify-face

**Purpose:** Internal routing point to the Python microservice. Secures Inherence Factor 1 by comparing the provided live capture against the stored mathematical embedding (Step 3).
**Authentication Required:** Yes (Transient Context via `auth_session_id`)
**Rate Limiting:** 5 attempts per session.

### Request Body
```json
{
  "auth_session_id": "redis-session-uuid",
  "face_image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...",
  "liveness_data": {
    "challenge_type": "blink",
    "challenge_passed": true
  }
}
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Biometric face match verified. Proceed to Step 4.",
  "data": {
    "auth_session_id": "redis-session-uuid",
    "next_step": "/verify-fingerprint"
  }
}
```

### Error Responses
- **401 Unauthorized:** Face match confidence below 95% threshold.
- **403 Forbidden:** Liveness check failed (suspicion of spoofing).
- **404 Not Found:** `auth_session_id` expired or invalid.
- **503 Service Unavailable:** Face Verification microservice unreachable or GPU queue full.

---

## 5. POST /verify-fingerprint

**Purpose:** Validates the FIDO2/WebAuthn cryptographic payload (Step 4). If successful, issues the final JWT access tokens.
**Authentication Required:** Yes (Transient Context via `auth_session_id` with Steps 1-3 complete)
**Rate Limiting:** 3 attempts per session.

### Request Body
```json
{
  "auth_session_id": "redis-session-uuid",
  "webauthn_response": {
    "id": "credential-id-string",
    "rawId": "base64-encoded-raw-id",
    "type": "public-key",
    "authenticatorAttachment": "platform",
    "response": {
      "clientDataJSON": "base64-encoded-client-data",
      "authenticatorData": "base64-encoded-auth-data",
      "signature": "base64-encoded-signature",
      "userHandle": "base64-encoded-user-id"
    }
  }
}
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Authentication complete.",
  "data": {
    "access_token": "jwt-eyJhbG...",
    "expires_in": 900,
    "user": {
      "id": "uuid-v4-string",
      "email": "user@enterprise.com",
      "roles": ["admin"]
    }
  }
}
```
*(Note: A `refresh_token` will also be set as a secure `HttpOnly` cookie in the response headers).*

### Error Responses
- **401 Unauthorized:** WebAuthn signature invalid or replay attack detected.
- **403 Forbidden:** Steps 1-3 were not successfully completed for this session.
- **404 Not Found:** `auth_session_id` expired or invalid.

---

## 6. GET /health

**Purpose:** Liveness and readiness probe for Kubernetes/Load Balancers. Verifies connections to the DB, Redis, and Face Microservice.
**Authentication Required:** No
**Rate Limiting:** 60 requests per minute per IP.

### Request Body
*None*

### Success Response (200 OK)
```json
{
  "status": "healthy",
  "timestamp": "2026-02-22T19:00:00Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "face_microservice": "connected"
  },
  "version": "1.0.0"
}
```

### Error Responses
- **503 Service Unavailable:** One or more critical downstream dependencies are unreachable (returns the failing component in the payload).
