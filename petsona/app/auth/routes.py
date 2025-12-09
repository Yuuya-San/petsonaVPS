
import pyotp
"""Authentication routes + audit logging on critical paths."""
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from . import bp
from .forms import RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from ..models import User, AuditLog
from ..extensions import db
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
from ..extensions import limiter
from .emails import send_password_reset_email


def log_audit(event: str, actor=None, request=None, metadata: dict = None):
    """
    Writes a record to AuditLog and commits immediately.
    Fields saved: event, actor_id, actor_email, ip, user agent, timestamp, metadata JSON.
    IMPORTANT: We commit immediately to ensure audit persistence (append-only behavior).
    """
    ip = None
    ua = None
    if request is not None:
        # If behind proxy; ensure X-Forwarded-For is set by your proxy
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        ua = request.headers.get('User-Agent')

    entry = AuditLog(
        event=event,
        actor_id=getattr(actor, 'id', None) if actor else None,
        actor_email=getattr(actor, 'email', None) if actor else None,
        ip_address=ip,
        user_agent=ua,
    )
    if metadata:
        entry.set_metadata(metadata)

    db.session.add(entry)
    db.session.commit()

def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(email=form.email.data.lower(), role='user')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        # Audit: record registration (actor = new user)
        log_audit('user.register', actor=user, request=request, metadata={'action': 'register'})

        flash('Registration successful. You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    # Flash form validation errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'danger')
    
    return render_template('auth/register.html', form=form)

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        user = User.query.filter_by(email=email).first()
        base_meta = {'email': email}

        if not user:
            log_audit('user.login_failed', actor=None, request=request, metadata={**base_meta, 'reason': 'no_user'})
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('auth.login'))

        # Lockout check
        if user.lockout_until and user.lockout_until > datetime.utcnow():
            log_audit('user.login_locked', actor=user, request=request, metadata={'locked_until': user.lockout_until.isoformat()})
            flash('Account temporarily locked due to too many failed login attempts. Try again later.', 'danger')
            return redirect(url_for('auth.login'))

        if user.check_password(form.password.data):
            # 2FA check (if enabled)
            if user.is_2fa_enabled:
                code = form.two_factor_code.data or ''
                if not code or not user.totp_secret or not pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):
                    log_audit('user.login_failed_2fa', actor=user, request=request, metadata={'reason': '2fa_failed'})
                    flash('2FA code required or invalid.', 'danger')
                    return redirect(url_for('auth.login'))
            # Success: reset counters
            user.failed_login_attempts = 0
            user.lockout_until = None
            db.session.commit()

            login_user(user)
            log_audit('user.login_success', actor=user, request=request, metadata={'ip': request.remote_addr})
            # Redirect based on role
            if user.role == 'user':
                return redirect(url_for('auth.user_dashboard'))
            elif user.role == 'merchant':
                return redirect(url_for('auth.merchant_dashboard'))
            else:
                flash('You do not have the required permissions to access this page.', 'danger')
                return redirect(url_for('auth.login'))
        else:
            # Failure: increment failed attempts and potentially lock account
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= current_app.config['MAX_FAILED_LOGIN']:
                user.lockout_until = datetime.utcnow() + timedelta(seconds=current_app.config['LOCKOUT_TIME'])
                db.session.commit()
                log_audit('user.account_locked', actor=user, request=request, metadata={'failed_attempts': user.failed_login_attempts})
                flash('Account locked due to many failed attempts. Please try again later.', 'danger')
            else:
                db.session.commit()
                log_audit('user.login_failed', actor=user, request=request, metadata={'failed_attempts': user.failed_login_attempts})
                flash('Invalid email or password.', 'danger')
            return redirect(url_for('auth.login'))
    # Always flash validation errors if present
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'danger')
    return render_template('auth/login.html', form=form)
        
@bp.route('/admin-login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def admin_login():
        from .forms import AdminLoginForm
        form = AdminLoginForm()
        if form.validate_on_submit():
            email = form.email.data.lower()
            user = User.query.filter_by(email=email, role='admin').first()
            base_meta = {'email': email}
            if not user:
                log_audit('admin.login_failed', actor=None, request=request, metadata={**base_meta, 'reason': 'no_admin'})
                flash('Invalid admin credentials.', 'danger')
                return redirect(url_for('auth.admin_login'))
            if user.lockout_until and user.lockout_until > datetime.utcnow():
                log_audit('admin.login_locked', actor=user, request=request, metadata={'locked_until': user.lockout_until.isoformat()})
                flash('Account temporarily locked. Try again later.', 'danger')
                return redirect(url_for('auth.admin_login'))
            if user.check_password(form.password.data):
                # 2FA check (if enabled)
                if user.is_2fa_enabled:
                    code = form.two_factor_code.data or ''
                    if not code or not user.totp_secret or not pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):
                        log_audit('admin.login_failed_2fa', actor=user, request=request, metadata={'reason': '2fa_failed'})
                        flash('2FA code required or invalid.', 'danger')
                        return redirect(url_for('auth.admin_login'))
                user.failed_login_attempts = 0
                user.lockout_until = None
                db.session.commit()
                login_user(user)
                log_audit('admin.login_success', actor=user, request=request, metadata={'ip': request.remote_addr})
                flash('Admin login successful.', 'success')
                return redirect(url_for('auth.admin_dashboard'))
            else:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= current_app.config['MAX_FAILED_LOGIN']:
                    user.lockout_until = datetime.utcnow() + timedelta(seconds=current_app.config['LOCKOUT_TIME'])
                    db.session.commit()
                    log_audit('admin.account_locked', actor=user, request=request, metadata={'failed_attempts': user.failed_login_attempts})
                    flash('Account locked due to many failed attempts. Please try again later.', 'danger')
                else:
                    db.session.commit()
                    log_audit('admin.login_failed', actor=user, request=request, metadata={'failed_attempts': user.failed_login_attempts})
                    flash('Invalid admin credentials.', 'danger')
                return redirect(url_for('auth.admin_login'))
            
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, 'danger')
        return render_template('auth/admin_login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    # Audit logout event (capture actor before logout)
    log_audit('user.logout', actor=current_user, request=request)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        user = User.query.filter_by(email=email).first()
        if user:
            s = get_serializer()
            token = s.dumps({'user_id': user.id})

            # Audit: reset requested
            log_audit('user.password_reset_requested', actor=user, request=request)

            # send email (prefer background worker in production)
            try:
                send_password_reset_email(user, token)
                flash(f'A password reset link has been sent to {email}.', 'success')
            except Exception as e:
                # Audit mail-send failure
                log_audit('email.send_failed', actor=user, request=request, metadata={'error': str(e)})
                flash('Failed to send password reset email. Please try again later.', 'danger')
            
            return redirect(url_for('auth.login'))
        else:
            # Audit unknown email reset request
            log_audit('user.password_reset_requested_unknown', actor=None, request=request, metadata={'email': email})
            flash(f'The email {email} is not registered.', 'warning')
            return redirect(url_for('auth.login'))

    # Flash form validation errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'danger')
    
    return render_template('auth/forgot_password.html', form=form)


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    form = ResetPasswordForm()
    s = get_serializer()
    try:
        data = s.loads(token, max_age=current_app.config['RESET_TOKEN_EXPIRY'])
        user_id = data.get('user_id')
    except Exception:
        flash('Invalid or expired password reset token.', 'danger')
        log_audit('user.password_reset_invalid_token', actor=None, request=request, metadata={'token_excerpt': token[:32]})
        return redirect(url_for('auth.forgot_password'))

    user = User.query.get(user_id)
    if not user:
        flash('Invalid user for this reset token.', 'danger')
        log_audit('user.password_reset_invalid_user', actor=None, request=request, metadata={'token_excerpt': token[:32]})
        return redirect(url_for('auth.forgot_password'))

    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.failed_login_attempts = 0
        user.lockout_until = None
        db.session.commit()
        log_audit('user.password_reset_success', actor=user, request=request)
        flash('Your password has been reset. You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    # Flash form validation errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'danger')

    return render_template('auth/reset_password.html', form=form)
