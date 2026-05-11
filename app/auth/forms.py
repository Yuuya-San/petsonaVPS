from flask_wtf import FlaskForm # pyright: ignore[reportMissingImports]
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
import re


class RegisterForm(FlaskForm):
    first_name = StringField(
        'First Name',
        validators=[DataRequired(), Length(max=50)]
    )
    last_name = StringField(
        'Last Name',
        validators=[DataRequired(), Length(max=50)]
    )
    email = StringField(
        'Email',
        validators=[DataRequired(), Email(), Length(max=255)]
    )
    password = PasswordField(
        'Password',
        validators=[DataRequired(), Length(min=8, message='At least 8 characters')]
    )
    password2 = PasswordField(
        'Repeat Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match')]
    )
    submit = SubmitField('Register')

    def validate_first_name(self, field):
        if not re.match(r'^[A-Za-z]+$', field.data):
            raise ValidationError('First name must contain only letters.')

    def validate_last_name(self, field):
        if not re.match(r'^[A-Za-z]+$', field.data):
            raise ValidationError('Last name must contain only letters.')

    def validate_password(self, field):
        """
        Enforce strong password:
        - At least 1 uppercase
        - At least 1 lowercase
        - At least 1 number
        - At least 1 special character
        """
        password = field.data
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must include at least one uppercase letter.')
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must include at least one lowercase letter.')
        if not re.search(r'\d', password):
            raise ValidationError('Password must include at least one number.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must include at least one special character (!@#$%^&*(),.?":{}|<>).')

class LoginForm(FlaskForm):
    email = StringField(
        'Email',
        validators=[DataRequired(), Email(), Length(max=255)]
    )
    password = PasswordField(
        'Password',
        validators=[DataRequired()]
    )
    two_factor_code = StringField(
        '2FA Code (if enabled)',
        validators=[]
    )
    submit = SubmitField('Login')


# Admin login form (separate, not linked in UI)
class AdminLoginForm(FlaskForm):
    email = StringField(
        'Admin Email',
        validators=[DataRequired(), Email(), Length(max=255)]
    )
    password = PasswordField(
        'Password',
        validators=[DataRequired()]
    )
    two_factor_code = StringField(
        '2FA Code (if enabled)',
        validators=[]
    )
    submit = SubmitField('Admin Login')

# 2FA setup form (for enabling/disabling 2FA)
class TwoFactorSetupForm(FlaskForm):
    two_factor_code = StringField(
        'Enter 2FA Code',
        validators=[DataRequired(), Length(min=6, max=6)]
    )
    submit = SubmitField('Verify & Enable 2FA')

class ForgotPasswordForm(FlaskForm):
    email = StringField(
        'Email',
        validators=[DataRequired(), Email(), Length(max=255)]
    )
    submit = SubmitField('Send Reset Link')

class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        'New Password',
        validators=[DataRequired(), Length(min=8)]
    )
    password2 = PasswordField(
        'Repeat Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match')]
    )
    submit = SubmitField('Reset Password')

    def validate_password(self, field):
        """Same complexity rules as RegisterForm"""
        password = field.data
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must include at least one uppercase letter.')
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must include at least one lowercase letter.')
        if not re.search(r'\d', password):
            raise ValidationError('Password must include at least one number.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must include at least one special character (!@#$%^&*(),.?":{}|<>).')
