"""
SMS service for sending OTP via Twilio.

Setup (free trial at twilio.com):
  1. Sign up at https://www.twilio.com/try-twilio
  2. Get your Account SID, Auth Token, and a Twilio phone number
  3. Set these 3 env vars:
       export TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
       export TWILIO_AUTH_TOKEN=your_auth_token
       export TWILIO_FROM=+1234567890   # your Twilio number

In demo mode (env vars not set), OTP is printed to server console.
"""
import os

TWILIO_SID   = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM  = os.getenv("TWILIO_FROM", "")


def send_otp_sms(to_phone: str, otp: str) -> bool:
    """
    Send a 6-digit OTP via SMS to `to_phone`.
    Returns True on success, False on failure.
    Falls back to console print when Twilio is not configured.
    """
    message_body = f"Your SecureVault OTP is: {otp}\nValid for 10 minutes. Do not share this code."

    # ── DEMO fallback: no Twilio credentials configured ──────────────────────
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_FROM:
        print(f"\n[OTP] SMS → {to_phone}  Code: {otp}  (valid 10 min)\n")
        print("[OTP] To send real SMS, set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM env vars")
        return True

    # ── Real SMS via Twilio ───────────────────────────────────────────────────
    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        msg = client.messages.create(
            body=message_body,
            from_=TWILIO_FROM,
            to=to_phone,
        )
        print(f"[SMS] Sent to {to_phone}, SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"[SMS ERROR] {e}")
        # Fall back to console so OTP still works in demo
        print(f"\n[OTP FALLBACK] {to_phone} → {otp}\n")
        return False
