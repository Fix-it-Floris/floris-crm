"""
Email sending helper — shared across all scripts.
Uses Gmail SMTP with an App Password.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

EMAIL_SENDER    = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD  = os.environ["EMAIL_PASSWORD"]
EMAIL_RECIPIENT = os.environ["EMAIL_RECIPIENT"]


def send_html_email(subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())


def email_wrapper(title: str, subtitle: str, body_html: str, footer_note: str = "") -> str:
    """Wrap content in a consistent branded email shell."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif;">
<div style="max-width:640px;margin:32px auto;background:#fff;border-radius:12px;
            overflow:hidden;border:1px solid #e5e7eb;">
  <div style="background:#111;padding:24px 28px;">
    <p style="margin:0;font-size:12px;color:#9ca3af;">Fix-it Floris · Lead CRM</p>
    <h1 style="margin:6px 0 0;font-size:20px;color:#fff;font-weight:600;">{title}</h1>
    <p style="margin:4px 0 0;font-size:13px;color:#6b7280;">{subtitle}</p>
  </div>
  <div style="padding:24px 28px;">
    {body_html}
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:28px 0 16px;">
    <p style="margin:0;font-size:11px;color:#9ca3af;">
      {footer_note}
      To stop this service, set the <code>STOP_SERVICE</code> secret to
      <code>true</code> in your GitHub repository settings.
    </p>
  </div>
</div>
</body></html>"""
