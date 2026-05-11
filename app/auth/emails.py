"""Email helpers. In production send emails asynchronously (Celery/RQ)."""
from flask import render_template, current_app, url_for # pyright: ignore[reportMissingImports]
from flask_mail import Message # pyright: ignore[reportMissingImports]
from ..extensions import mail
import os
import requests
import re
from urllib.parse import urlparse
import hashlib

def send_email(subject: str, recipients: list, html_body: str, text_body: str = None):
    """Sends an email synchronously via Flask-Mail with inline image embedding."""
    msg = Message(subject=subject, recipients=recipients)

    inline_images = {
        'petsona_logo': {
            'path': os.path.join(current_app.root_path, 'static', 'images', 'logo', 'petsona-logo.png'),
            'content_type': 'image/png',
        }
    }

    html_body = html_body.replace(
        'https://cdn.jsdelivr.net/gh/RealPeachy/petsona-assets/logo.png',
        'cid:petsona_logo'
    )

    img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
    img_matches = re.findall(img_pattern, html_body, re.IGNORECASE)

    for img_src in img_matches:
        if img_src.startswith('cid:'):
            cid_name = img_src.split(':', 1)[1]
            if cid_name in inline_images:
                image_info = inline_images[cid_name]
                try:
                    with open(image_info['path'], 'rb') as f:
                        image_data = f.read()

                    msg.attach(
                        filename=os.path.basename(image_info['path']),
                        content_type=image_info['content_type'],
                        data=image_data,
                        disposition='inline',
                        headers={'Content-ID': f'<{cid_name}>'}
                    )
                except Exception as e:
                    current_app.logger.warning(f"Failed to embed inline image {cid_name}: {e}")
            continue

        if img_src.startswith('http'):
            try:
                response = requests.get(img_src, timeout=10)
                response.raise_for_status()
                content_type = response.headers.get('content-type', 'image/png')
                filename = urlparse(img_src).path.split('/')[-1] or 'image.png'
                cid_name = hashlib.md5(img_src.encode()).hexdigest()[:16]

                msg.attach(
                    filename=filename,
                    content_type=content_type,
                    data=response.content,
                    disposition='inline',
                    headers={'Content-ID': f'<{cid_name}>'}
                )

                html_body = html_body.replace(img_src, f'cid:{cid_name}')
            except Exception as e:
                current_app.logger.warning(f"Failed to download inline image {img_src}: {e}")

    msg.html = html_body
    if text_body:
        msg.body = text_body

    mail.send(msg)

def send_password_reset_email(user, token: str):
    """Composes and sends a professional reset email with Petsona branding."""
    front_url = current_app.config.get('FRONTEND_URL')
    if front_url:
        reset_url = f"{front_url.rstrip('/')}/auth/reset-password/{token}"
    else:
        reset_url = url_for('auth.reset_password', token=token, _external=True)

    html = render_template(
        'auth/reset_password_email.html',
        user=user,
        reset_url=reset_url,
        config=current_app.config
    )
    send_email('Password Reset Request - Petsona', [user.email], html)

def send_temp_credentials(email, password):
    """Sends temporary account credentials to newly created admin accounts."""
    html = render_template(
        'auth/temp_credentials_email.html',
        email=email,
        password=password
    )
    
    send_email(
        "Welcome to Petsona - Your Account Credentials",
        [email],
        html
    )


def send_backup_codes_email(user, backup_codes):
    """Sends backup codes to user email with professional design after enabling 2FA."""
    html = render_template(
        'auth/backup_codes_email.html',
        user=user,
        backup_codes=backup_codes
    )
    
    send_email(
        'Your Petsona 2FA Backup Codes - Save These Immediately',
        [user.email],
        html
    )


def send_registration_otp_email(email: str, otp: str):
    """Sends registration OTP verification code with professional Petsona design."""
    html = render_template(
        'auth/registration_otp_email.html',
        otp=otp
    )
    
    send_email(
        'Verify Your Email - Petsona Registration',
        [email],
        html
    )

