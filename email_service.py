"""
Email service for sending password reset emails.
Uses Gmail SMTP with App Password.

Setup (one-time):
  1. Enable 2FA on your Gmail account
  2. Go to Google Account → Security → App Passwords
  3. Generate a password for "Mail"
  4. Set these env vars (or edit the defaults below):
       SMTP_EMAIL=your.email@gmail.com
       SMTP_PASSWORD=your_16_char_app_password

In demo mode (no credentials set), the reset link is printed to the server console.
"""
import smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")


def send_reset_email(to_email: str, reset_token: str) -> bool:
    """
    Send a password-reset link to the user's email.
    Returns True on success, False on failure.
    Falls back to console print when SMTP is not configured.
    """
    link = f"{SITE_URL}/reset-password?token={reset_token}"

    # ── DEMO fallback: no SMTP configured ────────────────────────────────────
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print(f"\n[RESET EMAIL] To: {to_email}")
        print(f"[RESET EMAIL] Link: {link}  (valid 30 min)\n")
        return True

    # ── Real email via Gmail SMTP ─────────────────────────────────────────────
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "SecureVault — Reset Your Password"
    msg["From"]    = f"SecureVault <{SMTP_EMAIL}>"
    msg["To"]      = to_email

    html = f"""
    <html><body style="font-family:Inter,sans-serif;background:#05080f;color:#e2e8f0;padding:40px;">
      <div style="max-width:500px;margin:0 auto;background:rgba(13,20,38,.95);border:1px solid rgba(99,102,241,.3);
                  border-radius:20px;padding:40px;">
        <div style="font-size:.75rem;font-weight:700;letter-spacing:.2em;color:#6366f1;
                    text-transform:uppercase;margin-bottom:16px;">🔐 SecureVault</div>
        <h1 style="font-size:1.5rem;margin-bottom:8px;">Reset Your Password</h1>
        <p style="color:#94a3b8;margin-bottom:28px;">
          Someone requested a password reset for your account. If this was you, click the button below.
          This link expires in <strong style="color:#e2e8f0;">30 minutes</strong>.
        </p>
        <a href="{link}" style="display:inline-block;background:linear-gradient(135deg,#6366f1,#8b5cf6);
           color:#fff;text-decoration:none;padding:14px 32px;border-radius:12px;font-weight:700;font-size:.95rem;">
          Reset Password →
        </a>
        <p style="color:#475569;font-size:.8rem;margin-top:28px;">
          If you didn't request this, ignore this email — your password won't change.<br/>
          <a href="{link}" style="color:#6366f1;word-break:break-all;">{link}</a>
        </p>
      </div>
    </body></html>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        print(f"[EMAIL] Reset link sent to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False
