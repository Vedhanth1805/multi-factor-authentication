# Secure Multi-Factor Authentication (MFA) System

A robust, sequentially enforced Dual-Factor Authentication system built with FastAPI and vanilla JavaScript. This project securely implements a mandatory multi-step login flow that requires standard password verification followed by immutable biometric (Fingerprint/Face) and OTP-based authentication.

## 🚀 Features
- **Mandatory Biometric MFA**: Enforces WebAuthn fingerprint/device-lock and JS-based face recognition. Biometrics are permanently bound to user accounts upon registration to prevent tampering.
- **Phone & Email OTP**: Secure fallback and secondary authentication factors using SMS and Email verification.
- **Secure Architecture**: Backend built with FastAPI, utilizing SQLite for state management and JWT for session security. 
- **Modular Services**: Separate modules for Email (`email_service.py`), SMS (`sms_service.py`), Rate Limiting (`rate_limit.py`), and Database Management.
- **Detailed Documentation**: Check out the included `SECURITY_MODEL.md`, `API_SPEC.md`, and `PLAN.md` for in-depth architectural and API guidelines.

## 🛠️ Tech Stack
- **Backend:** Python, FastAPI, SQLite, Pydantic, Passlib (Bcrypt)
- **Frontend:** HTML, Vanilla CSS, Vanilla JavaScript (WebAuthn API, Face-api.js)

## 📦 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Vedhanth1805/multi-factor-authentication.git
   cd multi-factor-authentication
   ```

2. **Set up a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the FastAPI server:**
   ```bash
   uvicorn main:app --reload
   ```

5. **Access the application:**
   Open your browser and navigate to `http://localhost:8000` to view the frontend `index.html`.

## 🔒 Security Model
For a complete breakdown of the cryptographic implementations, biometric immutability guarantees, and OTP expiry states, please read the [SECURITY_MODEL.md](SECURITY_MODEL.md).

## 📄 License
This project is open-source.
