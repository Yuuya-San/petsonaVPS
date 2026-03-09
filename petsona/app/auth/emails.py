"""Email helpers. In production send emails asynchronously (Celery/RQ)."""
from flask import render_template, current_app, url_for
from flask_mail import Message
from ..extensions import mail

def send_email(subject: str, recipients: list, html_body: str, text_body: str = None):
    """Sends an email synchronously via Flask-Mail (example)."""
    msg = Message(subject=subject, recipients=recipients)
    msg.html = html_body
    if text_body:
        msg.body = text_body
    mail.send(msg)

def send_password_reset_email(user, token: str):
    """Composes and sends a reset email. Uses FRONTEND_URL if set, or generates external URL."""
    front_url = current_app.config.get('FRONTEND_URL')
    if front_url:
        reset_url = f"{front_url.rstrip('/')}/auth/reset-password/{token}"
    else:
        reset_url = url_for('auth.reset_password', token=token, _external=True)

    html = render_template('auth/reset_password_email.html', user=user, reset_url=reset_url)
    send_email('Password reset request', [user.email], html)

def send_temp_credentials(email, password):
    html = f"""
    <p>Your account has been created by an administrator.</p>
    <p><strong>Email:</strong> {email}</p>
    <p><strong>Temporary Password:</strong> {password}</p>
    <p>Please log in and change your password immediately.</p>
    """

    send_email(
        "Your Temporary Account Credentials",
        [email],
        html
    )


def send_backup_codes_email(user, backup_codes):
    """Send backup codes to user email after enabling 2FA"""
    codes_list = '<br>'.join([f"<code style='font-family: monospace; background: #f0f0f0; padding: 5px 10px;'>{code}</code>" for code in backup_codes])
    
    html = render_template(
        'auth/backup_codes_email.html',
        user=user,
        codes_list=codes_list,
        backup_codes=backup_codes
    )
    
    send_email(
        '2FA Backup Codes - Save These Codes',
        [user.email],
        html
    )

