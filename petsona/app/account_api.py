"""API endpoints for account management (password, 2FA, etc)."""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.extensions import csrf
from app.utils.account_api import (
    generate_2fa_setup,
    change_password,
    enable_2fa,
    disable_2fa,
    get_2fa_status,
    reset_2fa_start
)
from app.utils.audit import log_event, user_snapshot

bp = Blueprint('api', __name__, url_prefix='/api/account')

@bp.route('/change-password', methods=['POST'])
@login_required
@csrf.exempt
def api_change_password():
    """Change user password."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'message': 'No data provided'}), 400
        
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        
        if not current_password or not new_password:
            return jsonify({'message': 'Missing required fields'}), 400
        
        # Attempt to change password
        success, message = change_password(current_user, current_password, new_password)
        
        if success:
            log_event('user.password_changed', details={'user': user_snapshot(current_user)})
            return jsonify({'message': message}), 200
        else:
            log_event('user.password_change_failed', details={'reason': message})
            return jsonify({'message': message}), 400
            
    except Exception as e:
        current_app.logger.error(f"Password change error: {str(e)}")
        return jsonify({'message': 'An error occurred'}), 500

@bp.route('/generate-2fa-setup', methods=['POST'])
@login_required
@csrf.exempt
def api_generate_2fa_setup():
    """Generate 2FA setup data and QR code."""
    try:
        # Generate 2FA setup
        setup_data = generate_2fa_setup()
        
        # Return URI and secret (not QR code data to client to reduce payload)
        return jsonify({
            'secret': setup_data['secret'],
            'totp_uri': setup_data['totp_uri'],
            'qr_code_url': setup_data['qr_code_data_url']
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"2FA setup generation error: {str(e)}")
        return jsonify({'message': 'Failed to generate 2FA setup'}), 500

@bp.route('/enable-2fa', methods=['POST'])
@login_required
@csrf.exempt
def api_enable_2fa():
    """Enable 2FA with verification code."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'message': 'No data provided'}), 400
        
        secret = data.get('secret', '')
        code = data.get('code', '')
        
        if not secret or not code:
            return jsonify({'message': 'Missing required fields'}), 400
        
        # Enable 2FA
        success, result = enable_2fa(current_user, secret, code)
        
        if success:
            log_event('user.2fa_enabled', details={'user': user_snapshot(current_user)})
            current_app.logger.info(f"✓ 2FA enabled for user {current_user.id}")
            return jsonify(result), 200
        else:
            log_event('user.2fa_enable_failed', details={'reason': result})
            current_app.logger.warning(f"✗ 2FA enable failed for user {current_user.id}: {result}")
            return jsonify({'message': result}), 400
            
    except Exception as e:
        current_app.logger.error(f"2FA enable error: {str(e)}")
        return jsonify({'message': 'An error occurred'}), 500

@bp.route('/disable-2fa', methods=['POST'])
@login_required
@csrf.exempt
def api_disable_2fa():
    """Disable 2FA for user."""
    try:
        success, message = disable_2fa(current_user)
        
        if success:
            log_event('user.2fa_disabled', details={'user': user_snapshot(current_user)})
            current_app.logger.info(f"✓ 2FA disabled for user {current_user.id}")
            return jsonify({'message': message}), 200
        else:
            current_app.logger.warning(f"✗ 2FA disable failed for user {current_user.id}: {message}")
            return jsonify({'message': message}), 400
            
    except Exception as e:
        current_app.logger.error(f"2FA disable error: {str(e)}")
        return jsonify({'message': 'An error occurred'}), 500

@bp.route('/2fa-status', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def api_2fa_status():
    """Get 2FA status for current user."""
    try:
        # Refresh current_user from database to get latest data
        from app.models import User
        user = User.query.get(current_user.id)
        
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Get status
        status = get_2fa_status(user)
        
        # Log for debugging
        current_app.logger.info(f"2FA Status check for user {user.id}: is_2fa_enabled={status['is_2fa_enabled']}, has_totp_secret={status['has_totp_secret']}")
        
        return jsonify(status), 200
        
    except Exception as e:
        current_app.logger.error(f"2FA status check error: {str(e)}")
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500

@bp.route('/reset-2fa', methods=['POST'])
@login_required
@csrf.exempt
def api_reset_2fa():
    """Reset 2FA with password or backup code verification."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'message': 'No data provided'}), 400
        
        verification_type = data.get('verification_type', '')  # 'password' or 'backup_code'
        verification_value = data.get('verification_value', '')
        
        if not verification_type or not verification_value:
            return jsonify({'message': 'Missing required fields'}), 400
        
        if verification_type not in ['password', 'backup_code']:
            return jsonify({'message': 'Invalid verification type'}), 400
        
        # Verify and reset 2FA
        success, result = reset_2fa_start(current_user, verification_type, verification_value)
        
        if success:
            log_event('user.2fa_reset_started', details={'user': user_snapshot(current_user), 'method': verification_type})
            return jsonify(result), 200
        else:
            log_event('user.2fa_reset_failed', details={'reason': result})
            return jsonify({'message': result}), 400
            
    except Exception as e:
        current_app.logger.error(f"2FA reset error: {str(e)}")
        return jsonify({'message': 'An error occurred'}), 500
