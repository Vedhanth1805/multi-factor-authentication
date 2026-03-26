# Architecture Diagram Description: Advanced Multi-Factor Authentication System

This document provides a structural layout designed to be recreated in drawing tools like Draw.io, Lucidchart, or PowerPoint.

## 1. Top Level (Client Layer)
*This is the entry point for the user.*

- **[Actor] User:** Interacts with the interface. Uses a physical authenticator app and device fingerprint scanner.
- **[Component] Frontend Application:** (React/Next.js)
  - Handles the UI for login forms.
  - Manages the Webcam WebRTC stream for Face Capture.
  - Interacts with the browser's WebAuthn API for Fingerprint scanning.

*Flow Arrow:* User `---(HTTPS)--->` Frontend Application

## 2. Gateway Layer (Traffic Management)
*This sits between the open internet and our backend.*

- **[Component] API Gateway & Load Balancer:** (Nginx / Kong / AWS API Gateway)
  - Handles SSL Termination.
  - Enforces IP-level Rate Limiting.
  - Routes traffic to the correct backend service.

*Flow Arrow:* Frontend Application `---(REST API over TLS)--->` API Gateway

## 3. Application Layer (Backend Microservices)
*The core logic engines processing the authentication phases.*

- **[Service] FastAPI Core Auth Backend:** (The primary orchestrator)
  - Validates Passwords (Step 1).
  - Handles JWT issuance and Session refresh.
  - Routes complex biometric/OTP requests to specialized modules.
- **[Module] OTP Service:** (Integrated or Microservice)
  - Generates TOTP secrets.
  - Verifies time-based codes (Step 2).
- **[Module] Face Recognition Module:** (Python/OpenCV/dlib running on GPU nodes)
  - Analyzes liveness from the webcam feed.
  - Extracts the 512-dimensional facial vector (Step 3).
- **[Module] Fingerprint (WebAuthn) Module:** 
  - Generates cryptographic challenges.
  - Verifies ECDSA signatures from the user's hardware (Step 4).
- **[Component] Access Control Engine:** (Policy Decision Point)
  - Evaluates if Steps 1, 2, 3, and 4 are complete.
  - Evaluates Account Lockout policies.
  - Issues final JWT Access Tokens.

*Flow Arrows:* 
- API Gateway `---(Routes traffic)--->` FastAPI Core Auth Backend
- FastAPI Core Auth Backend `---(Calls)--->` OTP Service
- FastAPI Core Auth Backend `---(gRPC / Internal REST)--->` Face Recognition Module
- FastAPI Core Auth Backend `---(Calls)--->` Fingerprint Module
- FastAPI Core Auth Backend `---(Queries final state)--->` Access Control Engine

## 4. State & Infrastructure Layer (Storage)
*Where the transient state and permanent encrypted records live.*

- **[Database] Transient Session Cache:** (Redis Cluster)
  - Stores the 5-minute ephemeral `auth_session_id`.
  - Tracks which of the 4 steps have been completed.
- **[Database] Encrypted Primary Database:** (PostgreSQL)
  - Stores User profiles, Argon2 password hashes.
  - Stores AES-encrypted TOTP secrets.
  - Stores encrypted Face Embeddings (`pgvector`).
  - Stores WebAuthn public keys.
- **[Storage] Cloud Storage:** (AWS S3 / Azure Blob)
  - Stores long-term, encrypted Audit Logs for compliance.
  - *Note: Raw face images are NEVER stored here; they are analyzed in-memory and dropped.*
- **[Security] Key Management Service (KMS):** (HashiCorp Vault / AWS KMS)
  - Hardware Security Module (HSM) holding the Master Keys.
  - Provides runtime keys to the backend to decrypt the database rows.

*Flow Arrows:*
- FastAPI Core Auth Backend `---(Read/Write TTL states)--->` Transient Session Cache (Redis)
- FastAPI Core Auth Backend `---(Fetches KMS Keys)--->` KMS Vault
- FastAPI Core Auth Backend `---(Reads/Writes Encrypted Data)--->` Encrypted Primary Database
- Access Control Engine `---(Writes Audit Events)--->` Cloud Storage

---

## Suggested Layout for Diagram (Left to Right, or Top to Bottom)

1. **Left Column (or Top):** User & Frontend App.
2. **Middle-Left Column:** API Gateway.
3. **Center Column (The Brains):** A large box representing the "Backend Cluster", containing the FastAPI Core, flanked by the OTP, Face, and Fingerprint modules. Below them, the Access Control Engine.
4. **Right Column (or Bottom):** A container labeled "Secure Storage Network" containing Redis, PostgreSQL, Cloud Storage, and the KMS Vault icon connected distinctly to the backend, highlighting the envelope encryption pattern.
