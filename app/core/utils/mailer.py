"""
mailer.py — SMTP email utility.

Reads config live from os.environ (set by admin or .env at startup).
Returns (bool, str) — success flag and message.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _smtp_cfg() -> dict:
    return {
        'host':     os.environ.get('SMTP_HOST', '').strip(),
        'port':     int(os.environ.get('SMTP_PORT', '587') or '587'),
        'user':     os.environ.get('SMTP_USER', '').strip(),
        'password': os.environ.get('SMTP_PASSWORD', '').strip(),
        'sender':   os.environ.get('SMTP_SENDER', '').strip(),
        'use_tls':  os.environ.get('SMTP_USE_TLS', '1').strip() == '1',
    }


def _app_name() -> str:
    return os.environ.get('APP_NAME', 'Flask Launchpad').strip()


def is_smtp_configured() -> bool:
    cfg = _smtp_cfg()
    return bool(cfg['host'] and cfg['user'])


def _send(cfg: dict, sender: str, to_email: str, msg) -> tuple:
    try:
        if cfg['use_tls']:
            server = smtplib.SMTP(cfg['host'], cfg['port'], timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(cfg['host'], cfg['port'], timeout=10)
        server.login(cfg['user'], cfg['password'])
        server.sendmail(sender, [to_email], msg.as_string())
        server.quit()
        return True, "Email sent"
    except Exception as exc:
        return False, f"SMTP error: {exc}"


# ── HTML email templates ──────────────────────────────────────────────────────

def _base_html(header_color: str, header_text: str, body_html: str, app_name: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{header_text}</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f1f5f9;">
    <tr>
      <td align="center" style="padding:40px 16px 48px;">

        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;">

          <!-- Header bar -->
          <tr>
            <td style="background-color:{header_color};border-radius:12px 12px 0 0;padding:28px 40px;text-align:center;">
              <p style="margin:0;color:#ffffff;font-size:1.125rem;font-weight:700;letter-spacing:-0.01em;">{app_name}</p>
            </td>
          </tr>

          <!-- Card body -->
          <tr>
            <td style="background-color:#ffffff;border-radius:0 0 12px 12px;padding:40px;box-shadow:0 4px 24px rgba(0,0,0,.07);">
              {body_html}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:24px 40px;text-align:center;">
              <p style="margin:0;font-size:.75rem;color:#94a3b8;line-height:1.5;">
                This message was sent automatically by {app_name}.<br>
                Please do not reply to this email.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _verification_html(first_name: str, code: str, app_name: str) -> str:
    body = f"""
      <p style="margin:0 0 6px;font-size:.6875rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;">Account verification</p>
      <h1 style="margin:0 0 20px;font-size:1.375rem;font-weight:700;color:#0f172a;line-height:1.3;">Hi {first_name}, welcome!</h1>

      <p style="margin:0 0 28px;font-size:.9375rem;color:#475569;line-height:1.65;">
        Thanks for signing up. To activate your account, enter the 6-digit code below on the verification page. The code is valid for <strong>30 minutes</strong>.
      </p>

      <!-- Code box -->
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:28px;">
        <tr>
          <td align="center" style="background-color:#f8fafc;border:2px dashed #cbd5e1;border-radius:12px;padding:32px 24px;">
            <p style="margin:0 0 8px;font-size:.6875rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.12em;">Your code</p>
            <p style="margin:0;font-size:2.75rem;font-weight:800;letter-spacing:.6rem;color:#6366f1;font-family:'Courier New',Courier,monospace;line-height:1;">{code}</p>
          </td>
        </tr>
      </table>

      <!-- Expiry notice -->
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:32px;">
        <tr>
          <td style="background-color:#fffbeb;border-left:3px solid #f59e0b;border-radius:0 8px 8px 0;padding:12px 16px;">
            <p style="margin:0;font-size:.8125rem;color:#92400e;line-height:1.5;">
              &#8987; This code expires in <strong>30 minutes</strong>. If it expires, you can request a new one from the verification page.
            </p>
          </td>
        </tr>
      </table>

      <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 24px;">

      <p style="margin:0;font-size:.8125rem;color:#94a3b8;line-height:1.6;">
        Didn&rsquo;t create an account? You can safely ignore this email &mdash; no account will be activated without the code.
      </p>"""

    return _base_html('#6366f1', 'Verify your account', body, app_name)


def _test_email_html(app_name: str) -> str:
    body = f"""
      <p style="margin:0 0 6px;font-size:.6875rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;">Configuration test</p>
      <h1 style="margin:0 0 20px;font-size:1.375rem;font-weight:700;color:#0f172a;">SMTP is working!</h1>

      <p style="margin:0 0 28px;font-size:.9375rem;color:#475569;line-height:1.65;">
        This is a test email sent from the <strong>{app_name}</strong> server settings panel. Your SMTP configuration is working correctly.
      </p>

      <!-- Success box -->
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:32px;">
        <tr>
          <td align="center" style="background-color:#f0fdf4;border:1.5px solid #86efac;border-radius:10px;padding:24px;">
            <p style="margin:0 0 6px;font-size:1.75rem;line-height:1;">&#10003;</p>
            <p style="margin:0;font-size:.9375rem;font-weight:600;color:#15803d;">Email delivered successfully</p>
          </td>
        </tr>
      </table>

      <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 24px;">

      <p style="margin:0;font-size:.8125rem;color:#94a3b8;line-height:1.6;">
        This email was triggered manually from the admin panel. No action is required.
      </p>"""

    return _base_html('#16a34a', 'SMTP test', body, app_name)


# ── Public send functions ─────────────────────────────────────────────────────

def send_verification_email(to_email: str, first_name: str, code: str) -> tuple:
    cfg = _smtp_cfg()
    if not cfg['host']:
        return False, "SMTP_HOST not configured"
    if not cfg['user']:
        return False, "SMTP_USER not configured"

    app_name = _app_name()
    sender   = cfg['sender'] or cfg['user']

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'Your verification code — {app_name}'
    msg['From']    = f'{app_name} <{sender}>'
    msg['To']      = to_email

    text = (
        f"Hi {first_name},\n\n"
        f"Your verification code is: {code}\n\n"
        f"This code expires in 30 minutes.\n\n"
        f"If you did not register, ignore this email.\n\n"
        f"— {app_name}"
    )

    msg.attach(MIMEText(text, 'plain'))
    msg.attach(MIMEText(_verification_html(first_name, code, app_name), 'html'))

    return _send(cfg, sender, to_email, msg)


def send_db_restore_confirmation(to_email: str, filename: str, code: str) -> tuple:
    cfg = _smtp_cfg()
    if not cfg['host']:
        return False, "SMTP_HOST not configured"
    if not cfg['user']:
        return False, "SMTP_USER not configured"

    app_name = _app_name()
    sender   = cfg['sender'] or cfg['user']

    body = f"""
      <p style="margin:0 0 6px;font-size:.6875rem;font-weight:700;color:#dc2626;text-transform:uppercase;letter-spacing:.08em;">Critical operation</p>
      <h1 style="margin:0 0 20px;font-size:1.375rem;font-weight:700;color:#0f172a;line-height:1.3;">Database Restore Requested</h1>
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
        <tr>
          <td style="background-color:#fef2f2;border-left:3px solid #dc2626;border-radius:0 8px 8px 0;padding:14px 16px;">
            <p style="margin:0;font-size:.875rem;font-weight:600;color:#991b1b;">
              &#9888; This will overwrite the current database with:
              <code style="background:rgba(0,0,0,.06);padding:2px 6px;border-radius:4px;">{filename}</code>
            </p>
          </td>
        </tr>
      </table>
      <p style="margin:0 0 28px;font-size:.9375rem;color:#475569;line-height:1.65;">
        Enter the code below in the admin panel to confirm. Valid for <strong>10 minutes</strong>.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:28px;">
        <tr>
          <td align="center" style="background-color:#f8fafc;border:2px dashed #dc2626;border-radius:12px;padding:32px 24px;">
            <p style="margin:0 0 8px;font-size:.6875rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.12em;">Confirmation code</p>
            <p style="margin:0;font-size:2.75rem;font-weight:800;letter-spacing:.6rem;color:#dc2626;font-family:'Courier New',Courier,monospace;line-height:1;">{code}</p>
          </td>
        </tr>
      </table>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 24px;">
      <p style="margin:0;font-size:.8125rem;color:#94a3b8;line-height:1.6;">
        If you did not initiate this restore, contact your administrator immediately.
      </p>"""

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'[ACTION REQUIRED] DB restore confirmation — {app_name}'
    msg['From']    = f'{app_name} <{sender}>'
    msg['To']      = to_email

    text = (
        f"CRITICAL: Database restore requested.\n\n"
        f"File: {filename}\nCode: {code}\n\nExpires in 10 minutes.\n\n"
        f"If you did not initiate this, contact your administrator.\n\n— {app_name}"
    )
    msg.attach(MIMEText(text, 'plain'))
    msg.attach(MIMEText(_base_html('#dc2626', 'DB Restore Confirmation', body, app_name), 'html'))
    return _send(cfg, sender, to_email, msg)


def send_db_action_confirmation(to_email: str, action: str, filename: str, code: str) -> tuple:
    """Send a backup confirmation code for delete or download actions."""
    cfg = _smtp_cfg()
    if not cfg['host']:
        return False, "SMTP_HOST not configured"
    if not cfg['user']:
        return False, "SMTP_USER not configured"

    app_name = _app_name()
    sender   = cfg['sender'] or cfg['user']

    _meta = {
        'delete':   {'color': '#f59e0b', 'label': 'Delete Backup',   'warn': 'This will permanently delete the backup file:',    'subject': 'DB Backup Delete'},
        'download': {'color': '#3b82f6', 'label': 'Download Backup',  'warn': 'A download has been requested for the backup file:', 'subject': 'DB Backup Download'},
    }
    m = _meta.get(action, {'color': '#dc2626', 'label': action.title(), 'warn': 'Action requested on:', 'subject': action.title()})

    body = f"""
      <p style="margin:0 0 6px;font-size:.6875rem;font-weight:700;color:{m['color']};text-transform:uppercase;letter-spacing:.08em;">Action required</p>
      <h1 style="margin:0 0 20px;font-size:1.375rem;font-weight:700;color:#0f172a;line-height:1.3;">{m['label']} Requested</h1>
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
        <tr>
          <td style="background-color:#fffbeb;border-left:3px solid {m['color']};border-radius:0 8px 8px 0;padding:14px 16px;">
            <p style="margin:0;font-size:.875rem;font-weight:600;color:#92400e;">
              {m['warn']}
              <code style="background:rgba(0,0,0,.06);padding:2px 6px;border-radius:4px;">{filename}</code>
            </p>
          </td>
        </tr>
      </table>
      <p style="margin:0 0 28px;font-size:.9375rem;color:#475569;line-height:1.65;">
        Enter the code below in the admin panel to confirm. Valid for <strong>10 minutes</strong>.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:28px;">
        <tr>
          <td align="center" style="background-color:#f8fafc;border:2px dashed {m['color']};border-radius:12px;padding:32px 24px;">
            <p style="margin:0 0 8px;font-size:.6875rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.12em;">Confirmation code</p>
            <p style="margin:0;font-size:2.75rem;font-weight:800;letter-spacing:.6rem;color:{m['color']};font-family:'Courier New',Courier,monospace;line-height:1;">{code}</p>
          </td>
        </tr>
      </table>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 24px;">
      <p style="margin:0;font-size:.8125rem;color:#94a3b8;line-height:1.6;">
        If you did not initiate this action, contact your administrator immediately.
      </p>"""

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'[ACTION REQUIRED] {m["subject"]} confirmation — {app_name}'
    msg['From']    = f'{app_name} <{sender}>'
    msg['To']      = to_email

    text = (
        f"{m['label']} requested.\n\n"
        f"File: {filename}\nCode: {code}\n\nExpires in 10 minutes.\n\n"
        f"If you did not initiate this, contact your administrator.\n\n— {app_name}"
    )
    msg.attach(MIMEText(text, 'plain'))
    msg.attach(MIMEText(_base_html(m['color'], f'{m["label"]} Confirmation', body, app_name), 'html'))
    return _send(cfg, sender, to_email, msg)


def send_test_email(to_email: str) -> tuple:
    cfg = _smtp_cfg()
    if not cfg['host']:
        return False, "SMTP_HOST not configured"
    if not cfg['user']:
        return False, "SMTP_USER not configured"

    app_name = _app_name()
    sender   = cfg['sender'] or cfg['user']

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'SMTP test — {app_name}'
    msg['From']    = f'{app_name} <{sender}>'
    msg['To']      = to_email

    text = f"SMTP test from {app_name}. Your configuration is working correctly."

    msg.attach(MIMEText(text, 'plain'))
    msg.attach(MIMEText(_test_email_html(app_name), 'html'))

    return _send(cfg, sender, to_email, msg)
