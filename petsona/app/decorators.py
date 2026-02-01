from functools import wraps
from flask import redirect, url_for, jsonify, request
from flask_login import current_user

def admin_required(func):
    """Decorator to ensure the user is an admin."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:  # Check if the user is an admin
            # If this is an API request, return JSON error
            if '/api/' in request.path or request.is_json:
                return jsonify({'success': False, 'message': 'Unauthorized: Admin access required'}), 403
            return redirect(url_for('auth.home'))  # Redirect to home if not an admin
        return func(*args, **kwargs)
    return wrapper

def user_required(func):
    """Decorator to ensure the user is a regular user."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_user:  # Check if the user is a regular user
            # If this is an API request, return JSON error
            if '/api/' in request.path or request.is_json:
                return jsonify({'success': False, 'message': 'Unauthorized: User access required'}), 403
            return redirect(url_for('auth.home'))  # Redirect to home if not a user
        return func(*args, **kwargs)
    return wrapper

def merchant_required(func):
    """Decorator to ensure the user is a merchant."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_merchant:  # Check if the user is a merchant
            # If this is an API request, return JSON error
            if '/api/' in request.path or request.is_json:
                return jsonify({'success': False, 'message': 'Unauthorized: Merchant access required'}), 403
            return redirect(url_for('auth.home'))  # Redirect to home if not a merchant
        return func(*args, **kwargs)
    return wrapper
