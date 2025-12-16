from flask import render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from app.admin import bp
from flask import request
from .forms import (
    GeneralSettingsForm, SecuritySettingsForm, AuditSettingsForm,
    EmailSettingsForm, APISettingsForm, BackupSettingsForm, ComplianceSettingsForm,
    AppearanceSettingsForm
)
from app.extensions import limiter

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))

    return render_template('admin/dashboard.html')

@bp.route('/system-settings')
@limiter.limit(lambda: "1/second" if not (current_user.is_authenticated and current_user.role == "admin") else None)
def system_settings():
    # Which section to show? Defaults to 'general'
    active_section = request.args.get('section', 'general')

    # Instantiate all forms
    general_form = GeneralSettingsForm()
    security_form = SecuritySettingsForm()
    audit_form = AuditSettingsForm()
    email_form = EmailSettingsForm()
    api_form = APISettingsForm()
    backup_form = BackupSettingsForm()
    compliance_form = ComplianceSettingsForm()
    appearance_form = AppearanceSettingsForm()

    # Sidebar sections (key, label, icon)
    sections = [
        ('general', 'General Settings', 'fas fa-cogs'),
        ('security', 'Security', 'fas fa-shield-alt'),
        ('audit', 'Audit & Logging', 'fas fa-file-alt'),
        ('email', 'Email & Notifications', 'fas fa-envelope'),
        ('api', 'API & Integrations', 'fas fa-network-wired'),
        ('backup', 'Backup & Maintenance', 'fas fa-database'),
        ('compliance', 'Compliance & Legal', 'fas fa-balance-scale'),
        ('appearance', 'Appearance', 'fas fa-paint-brush'),
    ]

    return render_template(
        'admin/settings/system_settings.html',
        active_section=active_section,
        sections=sections,
        general_form=general_form,
        security_form=security_form,
        audit_form=audit_form,
        email_form=email_form,
        api_form=api_form,
        backup_form=backup_form,
        compliance_form=compliance_form,
        appearance_form=appearance_form
    )