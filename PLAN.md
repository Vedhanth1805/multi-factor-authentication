# PLAN.md: Advanced Multi-Factor Authentication System (Refined)

## 1. Requirements Clarification

**Target Users:** Enterprise cloud administrators, Banking/Financial institutions, Healthcare systems, SaaS platforms requiring high-assurance login.
**Main Problem:** Single-layer authentication (passwords) is vulnerable to phishing, credential stuffing, and leaks.
**Core Value Proposition:** A high-assurance identity verification system combining four rigorous layers:
1. **Knowledge Factor:** Password Verification
2. **Possession Factor:** Time-Based One-Time Password (TOTP)
3. **Inherence Factor 1:** Facial Recognition Verification (with Liveness Detection)
4. **Inherence Factor 2:** Fingerprint (FIDO2/WebAuthn) Validation

*Constraint:* Access is granted **only** when all four layers are successfully validated, barring emergency fallback scenarios.

---

## 2. System Architecture: Microservices Topology

**Decision:** The system will utilize a **Microservices Architecture** rather than a monolith.

**Reasoning:**
1. **Compute Asymmetry:** The Core Auth Service (handling passwords, TOTP, and state routing) is heavily **I/O bound**. The Facial Recognition Service is heavily **CPU/GPU bound**. A monolith would risk the lightweight OTP checking being starved of compute resources during spikes in facial verification traffic.
2. **Independent Scaling:** At 1 million users, we must scale the Core Auth pods aggressively during morning login rushes, while the Face Verification pods can be scaled on distinct GPU-backed node pools.
3. **Security Isolation:** The Facial Recognition service holds memory space that processes sensitive biometric hashes. Isolating this behind an internal boundary ensures edge vulnerabilities in the Auth router cannot easily access the biometric processing memory.

### Core Services Structure
- **API Gateway (Kong / Nginx):** Rate limiting, SSL termination, request routing.
- **Core Auth Service (Node.js/NestJS):** Handles User DB interactons, passwords, TOTP, WebAuthn handshakes, and issues JWTs.
- **Face Verification Service (Python/FastAPI):** Internal-only service. Accepts a cropped frame plus liveness data, compares it against the stored embedding, and returns a boolean match.
- **Session State Cache (Redis Cluster):** Manages the transient phase of multi-step logins.

---

## 3. Storage and Cryptography Strategy

### Database Schema Strategy
- **Users:** UUID, Email, Password Hash (Argon2id), Active Status.
- **MFA Secrets:** Encrypted TOTP secrets.
- **Biometric Embeddings:** Mathematical vector representations of faces (PostgreSQL `pgvector` or JSONB). *Raw images are purged immediately.*
- **WebAuthn Credentials:** Public keys, Credential IDs, Sign Counts.

### Biometric Encryption Key Management
Keys are managed using a strict **Envelope Encryption** pattern backed by a central KMS (e.g., HashiCorp Vault, AWS KMS, or Azure Key Vault):
- **Data Encryption Keys (DEK):** Unique runtime keys used to encrypt/decrypt database payloads (like Face Embeddings and TOTP secrets) at the application layer before DB insertion.
- **Key Encryption Keys (KEK):** Master keys stored entirely within a Hardware Security Module (HSM) via the KMS. The KEK encrypts the DEKs.
- **Lifecycle:** Keys are automatically rotated every 30 days. Application code never stores cryptographic keys; instances authenticate to the KMS via short-lived IAM roles to request encryption/decryption operations.

---

## 4. Auth & Security Model Definitions

### Face Matching Similarity Threshold
- **Algorithm:** Models like ArcFace or FaceNet extract a 128/512-dimensional vector.
- **Threshold:** We enforce a strict **Cosine Similarity > 0.95** (or low Euclidean distance), configured for a False Acceptance Rate (FAR) of less than 0.001%. 
- **Liveness Detection:** To prevent spoofing via photos or iPads, the frontend must dictate a random active challenge (e.g., "blink twice", "turn head slightly") or utilize 3D depth APIs if available, validating liveness before executing the vector mapping.

### OTP Brute-Force Prevention
1. **Temporal Rate Limiting:** The API Gateway restricts attempts to 3 requests per second per IP.
2. **Session-Bound Lockout:** The intermediate `auth_session_id` strictly tracks attempt counts in Redis. 
   - 3 failed OTP inputs -> Artificial delay of 5 seconds.
   - 5 failed OTP inputs -> The authentication session is destroyed. The user must restart from Step 1.
3. **Global Account Lockout:** If an account triggers 3 destroyed sessions sequentially, the account is temporarily frozen for 15 minutes, and an alert is sent to the registered email/administrator.

### Handling Session Expiration
- **Intermediate Authentication State:** The Redis transient session has an absolute Time-To-Live (TTL) of **5 minutes**. A user has exactly 5 minutes to complete all 4 steps. If TTL expires, all intermediate progress is flushed, enforcing a fresh login.
- **Post-Login State:**
  - **Access Tokens (JWT):** Short-lived (15 minutes). Statelessly verified.
  - **Refresh Tokens:** Opaque strings stored as `HttpOnly`, `SameSite=Strict` cookies. Max lifespan of 7 days. Managed via an inactivity sliding window. If a user logs out or anomalous IP behavior is detected mid-session, the refresh token is immediately blacklisted in Redis.

### Biometric Fallback Mechanism
Since hardware can fail (broken webcam, injured finger), a strict zero-trust fallback is required:
1. **Offline Recovery Codes:** Upon account setup, users are issued 5 uniquely generated, heavily hashed emergency recovery codes (to be stored in a physical safe/password manager). Entering a recovery code bypasses Steps 3 and 4 but marks the session as `ELEVATED_RISK`.
2. **ITSM Escalation:** If codes are lost, the user clicks "Biometric Failure". The system pauses entry and pushes an approval request to their Enterprise System Administrator / Security Operations Center (SOC). The admin must verify identity out-of-band (e.g., video call or HR check) and push a one-time bypass token to the user.

---

## 5. Scaling Strategy (1 Million Users)

To reliably serve 1 million highly active users entering a morning login rush, the architecture is designed for immense horizontal scale:

1. **Traffic Entry:** API gateways are globally distributed via Anycast DNS and CDN edge nodes to absorb network-level DDoS attempts and TLS handshakes locally.
2. **Data Layer Scaling:**
   - **PostgreSQL Partitioning & Replication:** Base user data is horizontally partitioned by tenant/organization ID. We use multi-AZ read-replicas for Step 1 validations, relieving exact-write pressures to the primary DB.
   - **PgBouncer:** Mandatory connection pooling to ensure thousands of Node.js pods do not exhaust database connections.
3. **Session State (Redis):** Deploy Redis in Cluster Mode with shards partitioned by `auth_session_id`. This prevents a single node from choking on the immense volume of intermediate read/writes required to orchestrate a 4-step flow.
4. **Computational Elasticity (Kubernetes HPA):**
   - Core Auth pods are aggressively scaled based on HTTP request queue length.
   - Face Verification pods are deployed on specialized GPU-backed nodes. They autoscale based on GPU utilization. If traffic exceeds GPU thresholds, requests queue via a lightweight circuit breaker to prevent total system cascade failure, returning a "Please try again in a moment" UX rather than crashing.

---

## 6. Execution Roadmap

- **Phase 1: Foundation & Base Auth (Core Node.js + DB)**
  - Establish Mono-repo, Postgres, and Redis clusters.
  - Build Auth Step 1 (Passwords), Step 2 (TOTP), and Rate Limiting.
- **Phase 2: KMS & Key Management Infrastructure**
  - Implement Vault/KMS.
  - Implement Envelope encryption for all secrets in DB.
- **Phase 3: Face Biometrics Integration (Python Microservice)**
  - Build Liveness verification, Embedding mapping, and strict Cosine threshold engine.
- **Phase 4: FIDO2 / Fingerprint Integration**
  - WebAuthn Server-side challenge generation and Client-side verifications.
- **Phase 5: Fallbacks, Security Hardening, & State Machine**
  - Connect Recovery Codes, Admin bypass flows, Global lockouts, and strictly enforce the 5-Minute Redis Auth Pipeline.
- **Phase 6: Load Testing & Enterprise UAT**
  - Simulate 100k+ concurrent Phase 1-4 logins.
  - Final end-to-end security audit and penetration testing.
