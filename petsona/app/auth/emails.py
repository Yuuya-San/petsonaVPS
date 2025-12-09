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
