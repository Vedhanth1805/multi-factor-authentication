# Security Model: Advanced Multi-Factor Authentication System

## 1. Authentication Layers & Cryptography

### 1.1 Password Hashing Strategy (Knowledge Factor)
- **Algorithm:** Argon2id
- **Reasoning:** Argon2id provides resistance against both GPU cracking (via memory hard computation) and side-channel timing attacks.
- **Parameters:**
  - Memory cost (`m`): 65536 KB (64 MB)
  - Time cost (`t`): 3 iterations
  - Parallelism (`p`): 4 threads
- **Salt Generation:** A unique 16-byte cryptographically secure random salt is generated per user upon registration.

### 1.2 OTP Logic (Possession Factor)
- **Standard:** RFC 6238 Time-Based One-Time Password (TOTP)
- **Algorithm:** HMAC-SHA1 (or HMAC-SHA256 if supported by enterprise authenticators).
- **Secret Generation:** A unique 160-bit base32-encoded secret is generated securely on the backend server.
- **Validation Window:** A 30-second window is used, allowing a drift of ±1 window (so codes remain valid for 90 seconds total to account for clock skew).
- **Storage:** The TOTP secret is encrypted at rest in the database using Envelope Encryption (AES-256-GCM).

### 1.3 Face Embedding Storage Strategy (Inherence Factor 1)
- **Data Extracted:** Raw face images are **never stored**. The Face Verification Microservice extracts a mathematical vector representation (embedding, e.g., a 512-dimensional float array).
- **Storage:** Embeddings are stored in PostgreSQL using the `pgvector` extension or as JSONB.
- **Encryption:** The embeddings stored in the database are encrypted at rest using AES-256-GCM.
- **Privacy:** If an attacker compromises the database, they retrieve an encrypted mathematical array, not a reproducible photo of the user's face.

### 1.4 Fingerprint/WebAuthn Template Storage (Inherence Factor 2)
- **Standard:** W3C Web Authentication (WebAuthn) / FIDO2
- **Data Extracted:** The system does **not** receive or store the user's fingerprint data. The biometric scan happens purely within the client's secure local hardware (Secure Enclave / TPM).
- **Storage Strategy:** 
  - The server stores the **Credential Public Key** associated with the authenticator device, relying on asymmetric cryptography.
  - Standard used: `ECDSA` (Elliptic Curve Digital Signature Algorithm) with `P-256` curve and `SHA-256` hash.
- **Replay Protection:** The server tracks a `sign_count` integer to ensure a signed payload is not reused by an attacker.

### 1.5 Encryption Standards Review
- **Data at Rest:** Envelope Encryption pattern.
  - Data Encryption Key (DEK): `AES-256-GCM` (Authenticated encryption).
  - Key Encryption Key (KEK): Stored in highly secure external KMS (e.g., HashiCorp Vault).
- **Data in Transit:** Mandatory `TLS 1.3` for all external and internal microservice communication.

---

## 2. Session & Access Management

### 2.1 JWT Session Management
- **Short-Lived Access Tokens:** JWT access tokens are valid for **15 minutes**.
- **Cryptographic Signature:** Signed using `RS256` (RSA Signature with SHA-256) or `EdDSA`. Asymmetric signatures allow internal stateless microservices to verify the token using a public key without querying the core Auth database.
- **Secure Refresh Tokens:** Opaque, long random strings (UUIDv4) stored strictly as `HttpOnly`, `Secure`, `SameSite=Strict` cookies. Max lifespan is 7 days, refreshed dynamically on use via a sliding window.
- **Transient Auth Sessions:** The `auth_session_id` used during the 4-step login phase is a UUID stored purely in Redis with a strict 5-minute absolute TTL.

---

## 3. Threat Mitigation & Rate Limiting

### 3.1 Rate Limiting Strategy
Handled hierarchically:
- **L4/L7 Edge (Cloudflare/AWS WAF):** Filters obvious volumetric DDoS bots before they hit the API gateway.
- **API Gateway (Nginx/Kong):** Limits global requests to 60 req/min per IP. Limits `/login` initiations to 10 req/min per IP.
- **Service Level (Redis tracking):** Limits OTP attempts to 3 failures (with penalty delays) and 5 failures (session destruction).

### 3.2 Brute-Force & Credential Stuffing Protection
- 5 consecutive failed Step 1 (password) attempts trigger an automatic account lock.
- User receives an email alert: "Multiple failed login attempts detected".
- Account automatically unlocks after 15 minutes, or can be unlocked via email verification link.

### 3.3 Account Lockout Policy Summary
| Action / Failure Type       | Threshold Limit | Consequence / Action Taken                               |
|-----------------------------|-----------------|----------------------------------------------------------|
| Invalid Password            | 5 attempts      | Account locked for 15 minutes; email alert sent.         |
| Invalid OTP Code            | 5 attempts      | Auth Session destroyed; must start Step 1 over.          |
| WebAuthn Sign Count Replay  | 1 attempt       | Account locked immediately; IT Admin intervention needed.|

---

## 4. Threat Model Assessment Let

| Threat Vector | Attack Description | Mitigation Built In |
|---|---|---|
| **Phishing/MitM** | Attacker intercepts credentials or OTP. | Hardware-bound WebAuthn (Step 4) verifies domain origination, preventing use of phished tokens. |
| **Credential Stuffing** | Attacker uses breached passwords from other sites. | Blocked instantly by MFA requirements (Steps 2-4) and IP rate-limiting. |
| **Database Compromise** | Attacker dumps the PostgreSQL instance. | Passwords hashed (Argon2id). TOTP secrets and Face vectors are AES-encrypted with rotating keys held outside DB (KMS). Fingerprints are never held on server. |
| **Biometric Spoofing** | Attacker uses a 3D mask or photo of user's face. | Frontend requires hardware 3D depth API if available; Python backend dictates dynamic liveness challenges (e.g., "blink twice"). |
| **Replay Attack** | Attacker captures Step 4 FIDO packet and re-submits it. | Server tracks increasing `sign_count`. Nonce mismatch fails verify. |
| **Session Hijacking** | XSS attack steals JWT in LocalStorage. | Access tokens expire in 15 mins. Long-lived Refresh tokens are protected by `HttpOnly` and cannot be accessed via JavaScript. |

---

## 5. NIST Alignment

This System Architecture heavily aligns with the **NIST Special Publication 800-63B (Digital Identity Guidelines)**:
- **Authenticator Assurance Level (AAL):** Achieves **AAL3** (Highest Security).
- **Requirement Met:** Utilizes multi-factor authentication involving a hardware-based crypto token (FIDO2) and a biometric (Inherence factor).
- **Requirement Met:** Employs verifier compromise resistance (Argon2id password hashing, isolated key management).

