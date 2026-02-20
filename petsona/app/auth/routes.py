
from app.models.species import Species
from app.models.breed import Breed

from flask import g, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user # pyright: ignore[reportMissingImports]
from . import bp
from .forms import RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from ..models import User, AuditLog
from ..extensions import db, oauth
from itsdangerous import URLSafeTimedSerializer
import random
from datetime import datetime, timedelta
from ..extensions import limiter
from .emails import send_password_reset_email
from app.utils.audit import log_event, user_snapshot
from sqlalchemy import func # pyright: ignore[reportMissingImports]
import pyotp
import secrets
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


DEFAULT_AVATARS = [
    "images/avatar/avatar-1.png",
    "images/avatar/avatar-2.png",
    "images/avatar/avatar-3.png",
    "images/avatar/avatar-4.png",
    "images/avatar/avatar-5.png",
    "images/avatar/avatar-6.png",
    "images/avatar/avatar-7.png",
    "images/avatar/avatar-8.png",
    "images/avatar/avatar-9.png",
    "images/avatar/avatar-10.png",
    "images/avatar/avatar-11.png",
    "images/avatar/avatar-12.png",
    "images/avatar/avatar-13.png",
    "images/avatar/avatar-14.png",
    "images/avatar/avatar-15.png",
    "images/avatar/avatar-16.png",
]

def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

@bp.route('/home')
def home():
    page = request.args.get('page', 1, type=int)

    # Paginate active species
    pagination = Species.query.filter(
        Species.deleted_at.is_(None)
    ).order_by(Species.name.asc()).paginate(
        page=page, per_page=1000, error_out=False
    )

    species_list = pagination.items

    # Count active breeds per species
    # Returns a dictionary {species_id: breed_count}
    breed_counts = dict(
        db.session.query(
            Breed.species_id,
            func.count(Breed.id)
        )
        .filter(Breed.is_active==True)  # only active breeds
        .group_by(Breed.species_id)
        .all()
    )
    

    return render_template(
        'auth/home.html',
        species_list=species_list,
        pagination=pagination,
        page_title="Pet Species"
    )

@bp.route('/feature')
def feature():
    return render_template('auth/feature.html')

@bp.route('/about')
def about():
    return render_template('auth/about.html')


@bp.route('/contact')
def contact():
    return render_template('auth/contact.html')


@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if email already exists
        email = form.email.data.lower()
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('This email is already registered. Please log in or use a different email.', 'warning')
            return redirect(url_for('auth.register'))
        
        # Store registration data in session
        session['registration'] = {
            'first_name': form.first_name.data,
            'last_name': form.last_name.data,
            'email': email,
            'password': form.password.data,
            'photo_url': random.choice(DEFAULT_AVATARS)
        }
        # Generate OTP
        otp = str(random.randint(100000, 999999))
        session['registration_otp'] = otp
        # Send OTP email
        from .emails import send_email
        html = f"""
        <p>Your OTP code for registration is: <b>{otp}</b></p>
        <p>This code will expire in 10 minutes.</p>
        """
        send_email('Your Registration OTP', [email], html)
        return redirect(url_for('auth.verify_otp'))
    # Flash form validation errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'danger')
    return render_template('auth/register.html', form=form)

# OTP Verification Form
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length

class OTPForm(FlaskForm):
    otp = StringField('OTP', validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField('Verify')

@bp.route('/verify-otp', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def verify_otp():
    form = OTPForm()
    if 'registration' not in session or 'registration_otp' not in session:
        flash('Session expired or invalid. Please register again.', 'danger')
        return redirect(url_for('auth.register'))
    if form.validate_on_submit():
        if form.otp.data == session.get('registration_otp'):
            reg = session['registration']
            # Save user to DB
            user = User(
                email=reg['email'],
                first_name=reg['first_name'],
                last_name=reg['last_name'],
                photo_url=reg.get('photo_url'),
                role='user'
            )

            user.set_password(reg['password'])
            db.session.add(user)
            db.session.commit()
            log_event(event='user.register', details={'user': user_snapshot(user)})
            # Clear session
            session.pop('registration', None)
            session.pop('registration_otp', None)
            flash('Registration successful. You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid OTP. Please try again.', 'danger')
    return render_template('auth/verify_otp.html', form=form)

# Resend OTP route for registration
@bp.route('/resend-otp', methods=['GET'])
@limiter.limit("5 per minute")
def resend_otp():
    reg = session.get('registration')
    if not reg:
        flash('Session expired or invalid. Please register again.', 'danger')
        return redirect(url_for('auth.register'))
    otp = str(random.randint(100000, 999999))
    session['registration_otp'] = otp
    from .emails import send_email
    html = f"""
    <p>Your OTP code for registration is: <b>{otp}</b></p>
    <p>This code will expire in 10 minutes.</p>
    """
    send_email('Your Registration OTP', [reg['email']], html)
    flash('A new OTP has been sent to your email.', 'info')
    return redirect(url_for('auth.verify_otp'))

@bp.route("/login/google")
def login_google():
    # For LOGIN: Always ask permission (prompt='consent' forces Google to ask)
    session['google_intent'] = 'login'
    session['google_action'] = 'Sign in'
    redirect_uri = url_for("auth.google_callback", _external=True)
    print(f"DEBUG: Login - Asking Google for permission")
    current_app.logger.info(f"Google OAuth - User attempting sign in")
    return oauth.google.authorize_redirect(redirect_uri, prompt='consent')


@bp.route("/register/google")
def register_google():
    # For REGISTER: Always ask permission (prompt='consent' forces Google to ask)
    session['google_intent'] = 'register'
    session['google_action'] = 'Sign up'
    redirect_uri = url_for("auth.google_callback", _external=True)
    print(f"DEBUG: Register - Asking Google for permission")
    current_app.logger.info(f"Google OAuth - User attempting sign up")
    return oauth.google.authorize_redirect(redirect_uri, prompt='consent')


@bp.route("/google/callback")
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        
        if not user_info:
            flash('Failed to retrieve user information from Google.', 'danger')
            return redirect(url_for('auth.login'))
        
        email = user_info.get('email', '').lower()
        name = user_info.get('name', '')
        
        if not email:
            flash('Email not provided by Google. Please try again.', 'danger')
            return redirect(url_for('auth.login'))
        
        # Check if user exists
        user = User.query.filter_by(email=email).first()
        intent = session.pop('google_intent', 'login')  # Default to login
        action = session.pop('google_action', 'Sign in')
        
        if not user:
            # User doesn't exist - Create account (user already gave permission)
            # Handle both formats:
            # Format 1: "John Smith" or "John Michael Smith"
            # Format 2: "Smith, John M." or "Smith, John"
            
            if ',' in name:
                # Format 2: "LastName, FirstName MiddleInitial"
                parts = name.split(',')
                last_name = parts[0].strip()
                first_name_part = parts[1].strip() if len(parts) > 1 else ''
                # Take only first word from first_name_part
                first_name = first_name_part.split()[0] if first_name_part else ''
            else:
                # Format 1: "FirstName MiddleName LastName"
                name_parts = name.strip().split()
                if len(name_parts) == 0:
                    first_name = ''
                    last_name = ''
                elif len(name_parts) == 1:
                    first_name = name_parts[0]
                    last_name = ''
                else:
                    first_name = name_parts[0]
                    last_name = name_parts[-1]  # Take last word only
            
            avatar_url = random.choice(DEFAULT_AVATARS)
            user = User(
                email=email,
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                photo_url=avatar_url,
                role='user'
            )
            user.set_password(secrets.token_urlsafe(32))
            db.session.add(user)
            db.session.commit()
            log_event('user.register_google', details={'user': user_snapshot(user)})
            flash(f'✓ Account created with {email}. Welcome to Petsona!', 'success')
        else:
            # User exists - just login
            log_event('user.login_google', details={'email': email})
        
        # Log in the user
        login_user(user)
        
        # Redirect based on role (same as regular login)
        if user.role == 'user':
            return redirect(url_for('user.dashboard'))
        elif user.role == 'merchant':
            return redirect(url_for('merchant.dashboard'))
        else:
            return redirect(url_for('auth.home'))
        
    except Exception as e:
        current_app.logger.error(f"Google OAuth error: {str(e)}")
        flash('Google login failed. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    form = LoginForm()


    if form.validate_on_submit():
        email = form.email.data.lower()
        user = User.query.filter_by(email=email).first()
        base_meta = {'email': email}

        # Always log out any existing user before a new login attempt
        if current_user.is_authenticated:
            logout_user()
            session.clear()

        # Clear session to ensure no old user data remains
        session.clear()

        import secrets
        # Generate a new session token for this login
        session_token = secrets.token_urlsafe(32)

        if not user:
            log_event('user.login_failed', details={**base_meta, 'reason': 'no_user'})
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('auth.login'))

        # Lockout check
        if user.lockout_until and user.lockout_until > get_ph_datetime():
            log_event('user.login_locked', details={'locked_until': user.lockout_until.isoformat()})
            flash('Account temporarily locked due to too many failed login attempts. Try again later.', 'danger')
            return redirect(url_for('auth.login'))

        if user.check_password(form.password.data):
            # 2FA check (if enabled)
            if user.is_2fa_enabled:
                code = form.two_factor_code.data or ''
                if not code or not user.totp_secret or not pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):
                    log_event('user.login_failed_2fa', details={'email': email, 'reason': '2fa_failed'})
                    flash('2FA code required or invalid.', 'danger')
                    return redirect(url_for('auth.login'))

            # Success: reset counters
            user.failed_login_attempts = 0
            user.lockout_until = None
            db.session.commit()

            # Save session token to user and session
            user.session_token = session_token
            db.session.commit()
            session['session_token'] = session_token
            login_user(user)
            log_event('user.login_success', details={'user': user_snapshot(user), 'ip': request.remote_addr})

            # Redirect based on role
            if user.role == 'user':
                return redirect(url_for('user.dashboard'))
            elif user.role == 'merchant':
                return redirect(url_for('merchant.dashboard'))
            else:
                flash('You do not have the required permissions to access this page.', 'danger')
                return redirect(url_for('auth.login'))
        else:
            # Failure: increment failed attempts and potentially lock account
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

            # Use safe defaults in case config keys are missing
            max_attempts = current_app.config.get('MAX_FAILED_LOGIN', 5)
            lockout_time = current_app.config.get('LOCKOUT_TIME', 900)  # 15 minutes default

            if user.failed_login_attempts >= max_attempts:
                user.lockout_until = get_ph_datetime() + timedelta(seconds=lockout_time)
                db.session.commit()
                log_event('user.account_locked', details={'user': user_snapshot(user), 'failed_attempts': user.failed_login_attempts})
                flash('Account locked due to many failed attempts. Please try again later.', 'danger')
            else:
                db.session.commit()
                log_event('user.login_failed', details={'user': user_snapshot(user), 'failed_attempts': user.failed_login_attempts})
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

        # Enforce single-login-per-session: if already logged in as another user, prevent login
        if current_user.is_authenticated:
            if current_user.id != (user.id if user else None):
                flash('You are already logged in as another user. Please log out first to switch accounts.', 'warning')
                return redirect(url_for('auth.login'))

        # Clear session to ensure no old user data remains
        session.clear()

        base_meta = {'email': email}

        # No admin found
        if not user:
            log_event(
                'admin.login_failed', details={**base_meta, 'reason': 'no_admin'})
            flash('Invalid admin credentials.', 'danger')
            return redirect(url_for('auth.admin_login'))

        # Account locked
        if user.lockout_until and user.lockout_until > get_ph_datetime():
            log_event(
                'admin.login_locked',
                details={'locked_until': user.lockout_until.isoformat()}
            )
            flash('Account temporarily locked. Try again later.', 'danger')
            return redirect(url_for('auth.admin_login'))

        # Password correct
        if user.check_password(form.password.data):

            # 2FA check
            if user.is_2fa_enabled:
                code = (form.two_factor_code.data or '').strip()
                if (
                    not code
                    or not user.totp_secret
                    or not pyotp.TOTP(user.totp_secret).verify(code, valid_window=1)
                ):
                    log_event(
                        'admin.login_failed_2fa',
                        details={'email': email, 'reason': '2fa_failed'}
                    )
                    flash('Invalid or missing 2FA code.', 'danger')
                    return redirect(url_for('auth.admin_login'))

            # Successful login
            user.failed_login_attempts = 0
            user.lockout_until = None
            db.session.commit()

            login_user(user)
            log_event(
                'admin.login_success',
                details={'user': user_snapshot(user), 'ip': request.remote_addr}
            )

            flash('Admin login successful.', 'success')
            return redirect(url_for('admin.dashboard'))

        # Wrong password
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

        # Safe config access
        max_attempts = current_app.config.get('MAX_FAILED_LOGIN', 5)
        lockout_time = current_app.config.get('LOCKOUT_TIME', 900)

        if user.failed_login_attempts >= max_attempts:
            user.lockout_until = get_ph_datetime() + timedelta(seconds=lockout_time)
            db.session.commit()

            log_event(
                'admin.account_locked',
                details={'user': user_snapshot(user), 'failed_attempts': user.failed_login_attempts}
            )
            flash(
                'Account locked due to many failed attempts. Please try again later.',
                'danger'
            )
        else:
            db.session.commit()
            log_event(
                'admin.login_failed',
                details={'user': user_snapshot(user), 'failed_attempts': user.failed_login_attempts}
            )
            flash('Invalid admin credentials.', 'danger')

        return redirect(url_for('auth.admin_login'))

    # Form validation errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'danger')

    return render_template('auth/admin_login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    # Audit logout event (capture actor before logout)
    log_event('user.logout', details={'user': user_snapshot(current_user), 'ip': request.remote_addr})
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
            log_event('user.password_reset_requested', details={'user': user_snapshot(user)})

            # send email (prefer background worker in production)
            try:
                send_password_reset_email(user, token)
                flash(f'A password reset link has been sent to {email}.', 'success')
            except Exception as e:
                # Audit mail-send failure
                log_event('email.send_failed', details={'user': user_snapshot(user), 'error': str(e)})
                flash('Failed to send password reset email. Please try again later.', 'danger')
            
            return redirect(url_for('auth.login'))
        else:
            # Audit unknown email reset request
            log_event('user.password_reset_requested_unknown', details={'email': email})
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
        log_event('user.password_reset_invalid_token', details={'token_excerpt': token[:32]})
        return redirect(url_for('auth.forgot_password'))

    user = User.query.get(user_id)
    if not user:
        flash('Invalid user for this reset token.', 'danger')
        log_event('user.password_reset_invalid_user', details={'token_excerpt': token[:32]})
        return redirect(url_for('auth.forgot_password'))

    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.failed_login_attempts = 0
        user.lockout_until = None
        db.session.commit()
        log_event('user.password_reset_success', details={'user': user_snapshot(user)})
        flash('Your password has been reset. You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    # Flash form validation errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'danger')

    return render_template('auth/reset_password.html', form=form)

