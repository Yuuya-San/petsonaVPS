"""Account API utilities for password and 2FA management."""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models import BackupCode
from ..auth.emails import send_backup_codes_email
import pyotp
import qrcode
from io import BytesIO
import base64
from datetime import datetime
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)

def generate_2fa_setup():
    """Generate 2FA setup data including secret and QR code."""
    # Generate a new secret
    secret = pyotp.random_base32()
    
    # Create TOTP object
    totp = pyotp.TOTP(secret)
    
    # Generate provisioning URI for QR code
    totp_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name='Petsona'
    )
    
    return {
        'secret': secret,
        'totp_uri': totp_uri,
        'qr_code_data_url': generate_qr_code_data_url(totp_uri)
    }

def generate_qr_code_data_url(data):
    """Generate QR code as data URL."""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None

def verify_password(user, password):
    """Verify user password."""
    return user.check_password(password)

def change_password(user, current_password, new_password):
    """Change user password with validation."""
    import re
    
    # Verify current password
    if not verify_password(user, current_password):
        return False, "Current password is incorrect"
    
    # Validate new password requirements (match forms.py)
    password_errors = []
    
    if len(new_password) < 8:
        password_errors.append('At least 8 characters')
    if not re.search(r'[A-Z]', new_password):
        password_errors.append('At least one uppercase letter')
    if not re.search(r'[a-z]', new_password):
        password_errors.append('At least one lowercase letter')
    if not re.search(r'\d', new_password):
        password_errors.append('At least one number')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
        password_errors.append('At least one special character')
    
    if password_errors:
        return False, f"Password must include: {', '.join(password_errors)}"
    
    # Set new password
    user.set_password(new_password)
    user.has_temp_password = False  # Clear temporary password flag
    db.session.commit()
    
    return True, "Password changed successfully"

def enable_2fa(user, secret, verification_code):
    """Enable 2FA for user and generate backup codes."""
    # Verify the code is correct
    totp = pyotp.TOTP(secret)
    
    if not totp.verify(verification_code, valid_window=1):
        return False, "Verification code is incorrect"
    
    try:
        # Save TOTP secret first
        user.totp_secret = secret
        user.is_2fa_enabled = True
        db.session.commit()
        
        # Generate and save backup codes
        backup_codes = BackupCode.create_for_user(user.id, count=10)
        
        # Verify backup codes were created
        if not backup_codes or len(backup_codes) == 0:
            raise Exception("Failed to generate backup codes")
        
        print(f"✓ 2FA enabled for user {user.id}")
        print(f"✓ Generated {len(backup_codes)} backup codes")
        
        # Send backup codes to email
        try:
            send_backup_codes_email(user, backup_codes)
            print(f"✓ Backup codes email sent to {user.email}")
        except Exception as email_error:
            print(f"⚠ Warning: Failed to send backup codes email: {str(email_error)}")
            # Don't fail the 2FA setup if email fails, codes are still saved
        
        return True, {
            "message": "2FA enabled successfully. Backup codes have been sent to your email.",
            "backup_codes": backup_codes
        }
    except Exception as e:
        db.session.rollback()
        print(f"✗ Error enabling 2FA: {str(e)}")
        return False, f"Error enabling 2FA: {str(e)}"

def disable_2fa(user):
    """Disable 2FA for user and delete backup codes."""
    try:
        # Get count of backup codes before deletion (for logging)
        backup_code_count = BackupCode.query.filter_by(user_id=user.id).count()
        
        # Disable 2FA
        user.totp_secret = None
        user.is_2fa_enabled = False
        db.session.commit()
        
        # Delete all backup codes
        deleted_count = BackupCode.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        
        print(f"✓ 2FA disabled for user {user.id}")
        print(f"✓ Deleted {deleted_count} backup codes (had {backup_code_count} before deletion)")
        
        return True, "2FA disabled successfully. All backup codes have been deleted."
    except Exception as e:
        db.session.rollback()
        print(f"✗ Error disabling 2FA: {str(e)}")
        return False, f"Error disabling 2FA: {str(e)}"

def get_2fa_status(user):
    """Get current 2FA status for user."""
    # Ensure we're returning consistent boolean values
    is_enabled = bool(user.is_2fa_enabled)
    has_secret = bool(user.totp_secret)
    
    return {
        "is_2fa_enabled": is_enabled,  # Always return as boolean
        "has_totp_secret": has_secret,
        "debug_info": {
            "user_id": user.id,
            "totp_secret_exists": has_secret,
            "is_2fa_flag": is_enabled
        }
    }

def reset_2fa_start(user, verification_type, verification_value):
    """Reset 2FA with password or backup code verification."""
    try:
        # Verify identity
        if verification_type == 'password':
            if not verify_password(user, verification_value):
                return False, "Password is incorrect"
        
        elif verification_type == 'backup_code':
            # Check if the backup code exists and is valid
            if not BackupCode.verify_code(user.id, verification_value):
                return False, "Invalid or already used backup code"
        
        else:
            return False, "Invalid verification type"
        
        # Identity verified - disable current 2FA
        user.totp_secret = None
        user.is_2fa_enabled = False
        db.session.commit()
        
        # Delete all backup codes
        BackupCode.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        
        # Generate new setup data for fresh 2FA setup
        setup_data = generate_2fa_setup()
        
        return True, {
            "message": "2FA has been reset. Complete the setup below to enable it again.",
            "secret": setup_data['secret'],
            "totp_uri": setup_data['totp_uri'],
            "qr_code_url": setup_data['qr_code_data_url']
        }
    
    except Exception as e:
        db.session.rollback()
        return False, f"Error resetting 2FA: {str(e)}"

