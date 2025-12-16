from flask_wtf import FlaskForm
from wtforms import StringField, FileField, SelectField, BooleanField, SubmitField, IntegerField
from wtforms.validators import DataRequired, URL, NumberRange, Length

class GeneralSettingsForm(FlaskForm):
    site_name = StringField("Site Name", validators=[DataRequired()])
    logo = FileField("Upload Logo")
    timezone = SelectField("Timezone", choices=[("UTC", "UTC"), ("Asia/Manila", "Asia/Manila")], validators=[DataRequired()])
    language = SelectField("Default Language", choices=[("en", "English"), ("ph", "Filipino")], validators=[DataRequired()])
    submit = SubmitField("Save General Settings")

class SecuritySettingsForm(FlaskForm):
    password_policy = StringField("Password Policy Description")
    enable_2fa = BooleanField("Enable 2FA")
    session_timeout = IntegerField("Session Timeout (minutes)", validators=[NumberRange(min=5, max=1440)])
    submit = SubmitField("Save Security Settings")

class AuditSettingsForm(FlaskForm):
    enable_audit = BooleanField("Enable Audit Logs")
    log_retention_days = IntegerField("Log Retention (days)", validators=[NumberRange(min=1, max=365)])
    submit = SubmitField("Save Audit Settings")

class EmailSettingsForm(FlaskForm):
    smtp_host = StringField("SMTP Host", validators=[DataRequired()])
    smtp_port = IntegerField("SMTP Port", validators=[DataRequired()])
    from_email = StringField("From Email", validators=[DataRequired()])
    submit = SubmitField("Save Email Settings")

class APISettingsForm(FlaskForm):
    api_key = StringField("API Key")
    rate_limit = IntegerField("Rate Limit per Minute", validators=[NumberRange(min=1)])
    submit = SubmitField("Save API Settings")

class BackupSettingsForm(FlaskForm):
    enable_auto_backup = BooleanField("Enable Automatic Backup")
    backup_frequency = SelectField("Backup Frequency", choices=[("daily", "Daily"), ("weekly", "Weekly")])
    submit = SubmitField("Save Backup Settings")

class ComplianceSettingsForm(FlaskForm):
    gdpr_enabled = BooleanField("Enable GDPR Compliance")
    privacy_policy_url = StringField("Privacy Policy URL", validators=[URL()])
    terms_url = StringField("Terms & Conditions URL", validators=[URL()])
    submit = SubmitField("Save Compliance Settings")


class AppearanceSettingsForm(FlaskForm):
    # Fonts
    font_family = SelectField(
        'Font Family',
        choices=[
            ('Arial, sans-serif', 'Arial'),
            ('Helvetica, sans-serif', 'Helvetica'),
            ('Roboto, sans-serif', 'Roboto'),
            ('Open Sans, sans-serif', 'Open Sans'),
            ('Times New Roman, serif', 'Times New Roman')
        ],
        validators=[DataRequired()]
    )

    font_size = SelectField(
        'Base Font Size',
        choices=[('12px','12px'), ('14px','14px'), ('16px','16px'), ('18px','18px')],
        validators=[DataRequired()]
    )

    # Color Theme
    primary_color = StringField('Primary Color (HEX)', validators=[DataRequired(), Length(max=7)])
    secondary_color = StringField('Secondary Color (HEX)', validators=[DataRequired(), Length(max=7)])
    dark_mode = BooleanField('Enable Dark Mode')

    submit = SubmitField('Save Appearance Settings')