
from app.models.species import Species
from app.models.breed import Breed
from app.models import BackupCode, PasswordResetToken

from flask import g, render_template, redirect, url_for, flash, request, current_app, session # pyright: ignore[reportMissingImports]
from flask_login import login_user, logout_user, login_required, current_user # pyright: ignore[reportMissingImports]
from . import bp
from .forms import RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from ..models import User, AuditLog
from ..extensions import db, oauth
from itsdangerous import URLSafeTimedSerializer # pyright: ignore[reportMissingImports]
import random
from datetime import datetime, timedelta
from ..extensions import limiter
from .emails import send_password_reset_email, send_backup_codes_email, send_registration_otp_email, send_email
from app.utils.audit import log_event, user_snapshot
from sqlalchemy import func # pyright: ignore[reportMissingImports]
import pyotp # pyright: ignore[reportMissingImports]
import secrets
import requests
import pytz
import hashlib


# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


def verify_recaptcha(token, secret_key=None):
    """Verify reCAPTCHA v3 token"""
    if not secret_key:
        secret_key = current_app.config.get('RECAPTCHA_SECRET_KEY')
    
    if not secret_key or not token:
        return False, "Missing configuration or token"
    
    try:
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': secret_key,
                'response': token
            },
            timeout=10
        )
        result = response.json()
        
        if result.get('success'):
            score = result.get('score', 0)
            # For v3, score >= 0.5 is typically considered valid
            if score >= 0.5:
                return True, f"Score: {score}"
            else:
                return False, f"Low score: {score}"
        else:
            error_codes = result.get('error-codes', [])
            return False, f"reCAPTCHA error: {', '.join(error_codes)}"
    except Exception as e:
        return False, f"Verification failed: {str(e)}"


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
    # Get dynamic stats from database
    from app.models import Breed, Merchant, MatchHistory
    
    # Count total active breeds
    total_breeds = Breed.query.filter(Breed.is_active == True).count()
    
    # Count total merchants
    total_merchants = Merchant.query.count()
    
    # Count total matches
    total_matches = MatchHistory.query.count()
    
    return render_template(
        'auth/home.html',
        total_breeds=total_breeds,
        total_merchants=total_merchants,
        total_matches=total_matches
    )

@bp.route('/feature')
def feature():
    return render_template('auth/feature.html')

@bp.route('/about')
def about():
    return render_template('auth/about.html')


@bp.route('/contact', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        if not all([name, email, message]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('auth.contact'))
        
        # Send email to admin
        html_body = render_template('auth/contact_email.html', 
                                   name=name, 
                                   email=email, 
                                   message=message,
                                   current_time=get_ph_datetime().strftime('%B %d, %Y at %I:%M %p'))
        send_email('New Contact Message - Petsona', ['petsona.helpcare@gmail.com'], html_body)
        
        # Send confirmation email to user
        reply_body = render_template('auth/contact_reply_email.html', 
                                    name=name, 
                                    message=message)
        send_email('Thank You for Contacting Petsona', [email], reply_body)
        
        flash('Message sent successfully!', 'success')
        return redirect(url_for('auth.contact'))
    
    return render_template('auth/contact.html')


@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Verify reCAPTCHA
        recaptcha_valid, recaptcha_message = verify_recaptcha(form.recaptcha_token.data)
        if not recaptcha_valid:
            flash('reCAPTCHA verification failed. Please try again.', 'danger')
            return redirect(url_for('auth.register'))
        
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
        session['otp_generated_time'] = datetime.now().isoformat()
        # Send OTP email using professional template
        send_registration_otp_email(email, otp)
        return redirect(url_for('auth.verify_otp'))
    # Flash form validation errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'danger')
    return render_template('auth/register.html', form=form, recaptcha_site_key=current_app.config.get('RECAPTCHA_SITE_KEY'))

# OTP Verification Form
from flask_wtf import FlaskForm # pyright: ignore[reportMissingImports]
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
    
    # Check if OTP has expired (10 minutes)
    otp_generated_time_str = session.get('otp_generated_time')
    if otp_generated_time_str:
        otp_generated_time = datetime.fromisoformat(otp_generated_time_str)
        if datetime.now() - otp_generated_time > timedelta(minutes=10):
            flash('Your verification code has expired. Please register again to get a new code.', 'danger')
            session.pop('registration', None)
            session.pop('registration_otp', None)
            session.pop('otp_generated_time', None)
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
                role='user',
                registration_method='system'
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

@bp.route('/resend-otp', methods=['GET'])
@limiter.limit("5 per minute")
def resend_otp():
    reg = session.get('registration')
    if not reg:
        flash('Session expired or invalid. Please register again.', 'danger')
        return redirect(url_for('auth.register'))
    otp = str(random.randint(100000, 999999))
    session['registration_otp'] = otp
    session['otp_generated_time'] = datetime.now().isoformat()
    send_registration_otp_email(reg['email'], otp)
    flash('A new verification code has been sent to your email.', 'info')
    return redirect(url_for('auth.verify_otp'))

@bp.route("/login/google")
def login_google():
    # For LOGIN: Always ask permission (prompt='consent' forces Google to ask)
    session['google_intent'] = 'login'
    session['google_action'] = 'Sign in'
    redirect_uri = url_for("auth.google_callback", _external=True)
    current_app.logger.info(f"Google OAuth - User attempting sign in")
    return oauth.google.authorize_redirect(redirect_uri, prompt='consent')


@bp.route("/register/google")
def register_google():
    # For REGISTER: Always ask permission (prompt='consent' forces Google to ask)
    session['google_intent'] = 'register'
    session['google_action'] = 'Sign up'
    redirect_uri = url_for("auth.google_callback", _external=True)
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
                role='user',
                registration_method='google'
            )
            user.set_password(secrets.token_urlsafe(32))
            db.session.add(user)
            db.session.commit()
            log_event('user.register_google', details={'user': user_snapshot(user)})
            flash(f'✓ Account created with {email}. Welcome to Petsona!', 'success')
        else:
            # User exists - check if they registered via Google
            if user.registration_method != 'google':
                flash('This account was created using email registration. Please use the login form to sign in.', 'danger')
                log_event('user.login_google_failed', details={'email': email, 'reason': 'wrong_registration_method', 'registration_method': user.registration_method})
                return redirect(url_for('auth.login'))
            
            # User exists and registered via Google - just login
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
        # Verify reCAPTCHA
        recaptcha_valid, recaptcha_message = verify_recaptcha(form.recaptcha_token.data)
        if not recaptcha_valid:
            log_event('user.login_failed', details={'email': form.email.data.lower(), 'reason': 'recaptcha_failed', 'message': recaptcha_message})
            flash('reCAPTCHA verification failed. Please try again.', 'danger')
            return redirect(url_for('auth.login'))
        
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
        
        # Check if user registered via Google - they must use Google login
        if user.registration_method == 'google':
            log_event('user.login_failed', details={**base_meta, 'reason': 'google_account_must_use_google_login'})
            flash('This account was created using Google Sign-In. Please use the Google login button instead.', 'danger')
            return redirect(url_for('auth.login'))

        # Lockout check
        if user.lockout_until and user.lockout_until > get_ph_datetime():
            log_event('user.login_locked', details={'locked_until': user.lockout_until.isoformat()})
            flash('Account temporarily locked due to too many failed login attempts. Try again later.', 'danger')
            return redirect(url_for('auth.login'))

        if user.check_password(form.password.data):
            # Check if user has temporary password - force password change
            if user.has_temp_password:
                # Store user info in session for password change
                session['pending_password_change_user_id'] = user.id
                session['pending_password_change_reason'] = 'temp_password'
                log_event('user.login_temp_password', details={'email': email})
                flash('For security reasons, you must change your temporary password before accessing your account.', 'warning')
                return redirect(url_for('auth.change_temp_password'))

            # 2FA check (if enabled)
            if user.is_2fa_enabled:
                # Store user info in session for 2FA verification
                session['pending_2fa_user_id'] = user.id
                session['pending_2fa_login_type'] = 'user'
                log_event('user.login_pending_2fa', details={'email': email})
                return redirect(url_for('auth.verify_2fa'))

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

    return render_template('auth/login.html', form=form, recaptcha_site_key=current_app.config.get('RECAPTCHA_SITE_KEY'))

        
@bp.route('/debug/session')
def debug_session():
    """Debug route to check session state - REMOVE IN PRODUCTION"""
    from flask import jsonify
    return jsonify({
        'current_user_authenticated': current_user.is_authenticated,
        'current_user_id': current_user.id if current_user.is_authenticated else None,
        'current_user_email': current_user.email if current_user.is_authenticated else None,
        'session_keys': list(session.keys()),
        'session_permanent': session.permanent,
        'session_modified': session.modified,
        'cookies': dict(request.cookies),
        'headers': dict(request.headers)
    })

@bp.route('/admin-login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def admin_login():
    from .forms import AdminLoginForm

    form = AdminLoginForm()

    if form.validate_on_submit():
        # Verify reCAPTCHA
        recaptcha_valid, recaptcha_message = verify_recaptcha(form.recaptcha_token.data)
        if not recaptcha_valid:
            log_event('admin.login_failed', details={'email': form.email.data.lower(), 'reason': 'recaptcha_failed', 'message': recaptcha_message})
            flash('reCAPTCHA verification failed. Please try again.', 'danger')
            return redirect(url_for('auth.admin_login'))
        
        email = form.email.data.lower()
        user = User.query.filter_by(email=email, role='admin').first()

        # Enforce single-login-per-session: if already logged in as another user, prevent login
        if current_user.is_authenticated:
            if current_user.id != (user.id if user else None):
                flash('You are already logged in as another user. Please log out first to switch accounts.', 'warning')
                return redirect(url_for('auth.login'))

        # DON'T clear session here - it can interfere with login process
        # Only clear if you need to remove specific keys, not the entire session

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
                # Store user info in session for 2FA verification
                session['pending_2fa_user_id'] = user.id
                session['pending_2fa_login_type'] = 'admin'
                log_event('admin.login_pending_2fa', details={'email': email})
                return redirect(url_for('auth.verify_2fa'))

            # Successful login
            user.failed_login_attempts = 0
            user.lockout_until = None
            db.session.commit()

            # Perform login and verify it worked
            login_success = login_user(user)
            if not login_success:
                current_app.logger.error(f"login_user() failed for user {user.id}")
                flash('Login failed. Please try again.', 'danger')
                return redirect(url_for('auth.admin_login'))

            # DEBUG: Add logging to verify session state
            current_app.logger.info(f"User {user.id} logged in successfully. current_user.is_authenticated: {current_user.is_authenticated}")
            current_app.logger.info(f"Session keys after login: {list(session.keys())}")
            current_app.logger.info(f"Session cookie name: {current_app.config.get('SESSION_COOKIE_NAME', 'session')}")
            current_app.logger.info(f"Session permanent: {session.permanent}")

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

    return render_template('auth/admin_login.html', form=form, recaptcha_site_key=current_app.config.get('RECAPTCHA_SITE_KEY'))


@bp.route('/verify-2fa', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def verify_2fa():
    """Verify 2FA code after successful password entry."""
    # Check if user has a pending 2FA verification
    if 'pending_2fa_user_id' not in session:
        flash('No pending 2FA verification. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))
    
    user_id = session.get('pending_2fa_user_id')
    login_type = session.get('pending_2fa_login_type', 'user')
    user = User.query.get(user_id)
    
    if not user:
        flash('User not found. Please log in again.', 'danger')
        session.pop('pending_2fa_user_id', None)
        session.pop('pending_2fa_login_type', None)
        return redirect(url_for('auth.login'))
    
    if not user.is_2fa_enabled or not user.totp_secret:
        flash('2FA is not enabled for this account.', 'danger')
        session.pop('pending_2fa_user_id', None)
        session.pop('pending_2fa_login_type', None)
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        code = request.form.get('two_factor_code', '').strip()
        
        if not code or len(code) < 6:
            flash('Please enter a valid code.', 'warning')
            return render_template('auth/verify_2fa.html', email=user.email)
        
        # Try TOTP verification first (authenticator app)
        if len(code) == 6 and code.isdigit():
            if pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):
                # TOTP code verified successfully
                session_token = secrets.token_urlsafe(32)
                user.failed_login_attempts = 0
                user.lockout_until = None
                user.session_token = session_token
                db.session.commit()
                
                session['session_token'] = session_token
                session.pop('pending_2fa_user_id', None)
                session.pop('pending_2fa_login_type', None)
                
                login_user(user)
                log_event('user.login_success', details={'user': user_snapshot(user), 'ip': request.remote_addr, '2fa': 'verified'})
                flash('✓ Login successful!', 'success')
                
                # Redirect based on role
                if user.role == 'user':
                    return redirect(url_for('user.dashboard'))
                elif user.role == 'merchant':
                    return redirect(url_for('merchant.dashboard'))
                elif user.role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('auth.login'))
            else:
                log_event('user.login_failed_2fa', details={'email': user.email, 'reason': '2fa_invalid'})
                flash('Invalid 2FA code. Please try again.', 'danger')
                return render_template('auth/verify_2fa.html', email=user.email)
        
        # Try backup code (with dashes)
        else:
            if BackupCode.verify_code(user_id, code):
                # Backup code verified successfully
                session_token = secrets.token_urlsafe(32)
                user.failed_login_attempts = 0
                user.lockout_until = None
                user.session_token = session_token
                db.session.commit()
                
                session['session_token'] = session_token
                session.pop('pending_2fa_user_id', None)
                session.pop('pending_2fa_login_type', None)
                
                login_user(user)
                log_event('user.login_success', details={'user': user_snapshot(user), 'ip': request.remote_addr, '2fa': 'backup_code'})
                flash('✓ Login successful! (Backup code used)', 'success')
                
                # Redirect based on role
                if user.role == 'user':
                    return redirect(url_for('user.dashboard'))
                elif user.role == 'merchant':
                    return redirect(url_for('merchant.dashboard'))
                elif user.role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('auth.login'))
            else:
                log_event('user.login_failed_2fa', details={'email': user.email, 'reason': 'backup_code_invalid'})
                flash('Invalid code. Use your 6-digit authenticator code or a backup code.', 'danger')
                return render_template('auth/verify_2fa.html', email=user.email)
    
    return render_template('auth/verify_2fa.html', email=user.email)


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
            # Check if account was created with Google OAuth
            if user.registration_method == 'google':
                log_event('user.password_reset_google_account', details={'user': user_snapshot(user)})
                flash('Your account is linked with Google. You cannot reset your password through this method. Please sign in with Google.', 'info')
                return redirect(url_for('auth.login'))
            
            s = get_serializer()
            token = s.dumps({'user_id': user.id})
            
            # Create token hash for one-time use tracking
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            # Store token in database with 30-minute expiry
            PasswordResetToken.create_token(user.id, token_hash, expiry_seconds=1800)

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
    
    # Hash the token for database lookup
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    # Check token status in database (one-time use + expiration)
    token_status = PasswordResetToken.check_token_status(token_hash)
    
    if token_status == 'already_used':
        flash('This password reset link has already been used. Please request a new one.', 'warning')
        log_event('user.password_reset_link_already_used', details={'token_excerpt': token[:32]})
        return redirect(url_for('auth.forgot_password'))
    
    if token_status == 'expired':
        flash('Your password reset link has expired. Please request a new one.', 'warning')
        log_event('user.password_reset_expired', details={'token_excerpt': token[:32]})
        return redirect(url_for('auth.forgot_password'))
    
    if token_status == 'not_found':
        flash('Invalid password reset link. Please request a new one.', 'danger')
        log_event('user.password_reset_invalid_token', details={'token_excerpt': token[:32]})
        return redirect(url_for('auth.forgot_password'))
    
    # Also validate with itsdangerous for additional security
    try:
        data = s.loads(token, max_age=1800)  # 30 minutes
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
        
        # Mark token as used
        reset_token = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
        if reset_token:
            reset_token.mark_as_used()
        
        log_event('user.password_reset_success', details={'user': user_snapshot(user)})
        flash('Your password has been reset. You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    # Flash form validation errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'danger')

    return render_template('auth/reset_password.html', form=form)


@bp.route('/change-temp-password', methods=['GET', 'POST'])
def change_temp_password():
    """Force password change for users with temporary passwords"""
    # Check if user is in pending password change session
    user_id = session.get('pending_password_change_user_id')
    reason = session.get('pending_password_change_reason')
    
    if not user_id or reason != 'temp_password':
        flash('Invalid session. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user:
        session.pop('pending_password_change_user_id', None)
        session.pop('pending_password_change_reason', None)
        flash('User not found. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))
    
    form = ResetPasswordForm()  # Reuse the reset password form
    
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.has_temp_password = False  # Clear temporary password flag
        user.failed_login_attempts = 0
        user.lockout_until = None
        db.session.commit()
        
        # Clear session
        session.pop('pending_password_change_user_id', None)
        session.pop('pending_password_change_reason', None)
        
        # Generate session token and log in user
        import secrets
        session_token = secrets.token_urlsafe(32)
        user.session_token = session_token
        db.session.commit()
        session['session_token'] = session_token
        login_user(user)
        
        log_event('user.temp_password_changed', details={'user': user_snapshot(user)})
        flash('Password changed successfully. Welcome to Petsona!', 'success')
        
        # Redirect based on role
        if user.role == 'user':
            return redirect(url_for('user.dashboard'))
        elif user.role == 'merchant':
            return redirect(url_for('merchant.dashboard'))
        else:
            return redirect(url_for('auth.home'))
    
    # Flash form validation errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'danger')
    
    return render_template('auth/change_temp_password.html', form=form)

