from flask import render_template, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from app.admin import bp
from flask import request
from .forms import (
    GeneralSettingsForm, SecuritySettingsForm, AuditSettingsForm,
    EmailSettingsForm, APISettingsForm, BackupSettingsForm, ComplianceSettingsForm,
    AppearanceSettingsForm, AdminAddUserForm, AdminEditUserForm
)
from app.extensions import limiter
from app.models import User, AuditLog
from app import db
import random
from app.auth.emails import send_temp_credentials
from app.utils.audit import log_event, user_snapshot
from datetime import datetime
from app.utils.activity_formatter import format_activity
from app.utils.activity_config import RECENT_ACTIVITY_EVENTS
from app.utils.dashboard_stats import get_dashboard_stats

DEFAULT_AVATARS = [
    "images/avatar/cat.png",
    "images/avatar/dog.png",
    "images/avatar/frog-.png",
    "images/avatar/hamster.png",
    "images/avatar/penguin.png",
    "images/avatar/puffer-fish.png",
    "images/avatar/rabbit.png",
    "images/avatar/snake.png"
]



@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    
    stats = get_dashboard_stats()
    
    logs = (
        AuditLog.query
        .filter(AuditLog.deleted_at.is_(None))
        .filter(AuditLog.event.in_(RECENT_ACTIVITY_EVENTS))
        .order_by(AuditLog.timestamp.desc())
        .limit(5)
    )
       

    recent_activities = [format_activity(log) for log in logs]

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_activities=recent_activities
    )


@bp.route("/users")
@login_required
def users():
    if current_user.role != "admin":
        abort(403)

    role = request.args.get("role")
    page = request.args.get("page", 1, type=int)  # Get current page number

    # Only active users
    query = User.query.filter_by(is_active=True).order_by(User.first_name)

    # Filter by role if selected
    if role:
        query = query.filter_by(role=role)

    # Paginate 10 users per page
    users_paginated = query.paginate(page=page, per_page=10)

    # Get all distinct roles of active users for filter dropdown
    roles = db.session.query(User.role).filter_by(is_active=True).distinct().all()

    return render_template(
        "admin/users.html",
        users=users_paginated,
        roles=roles,
        selected_role=role
    )

@bp.route("/users/archive")
@login_required
def archive_users():
    if current_user.role != "admin":
        abort(403)

    page = request.args.get("page", 1, type=int)

    # Only show soft-deleted users
    query = User.query.filter_by(is_active=False).order_by(User.deleted_at.desc())

    # Paginate 10 users per page
    users_paginated = query.paginate(page=page, per_page=10)

    return render_template(
        "admin/archive_users.html",
        users=users_paginated
    )

@bp.route("/users/restore/<int:id>", methods=["POST"])
@login_required
def restore_user(id):
    if current_user.role != "admin":
        abort(403)

    user = User.query.get_or_404(id)

    # Take snapshot before restoring
    before = user_snapshot(user)

    # Restore user
    user.is_active = True
    user.deleted_at = None
    db.session.commit()

    # Take snapshot after restoring
    after = user_snapshot(user)

    # Log the event
    log_event(event="user.restored", details={"before": before, "after": after})

    flash(f"User {user.first_name} restored successfully.", "success")
    return redirect(url_for("admin.archive_users"))



@bp.route("/users/<int:id>")
@login_required
def view_user(id):
    if current_user.role != "admin":
        abort(403)

    user = User.query.get_or_404(id)
    return render_template("admin/view_user.html", user=user)

@bp.route('/users/add', methods=['GET', 'POST'])
@login_required
def admin_add_user():
    if current_user.role != 'admin':
        abort(403)

    form = AdminAddUserForm()

    if form.validate_on_submit():
        temp_password = form.password.data

        user = User(
            email=form.email.data.lower(),
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role=form.role.data,
            photo_url=random.choice(DEFAULT_AVATARS)
        )

        user.set_password(temp_password)

        db.session.add(user)
        db.session.commit()

        # AUDIT LOG 
        log_event(
            event='user.created',
            details={
                'created_user_id': user.id,
                'created_user_email': user.email,
                'assigned_role': user.role
            }
        )

        send_temp_credentials(user.email, temp_password)

        flash('User created and credentials sent via email.', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/add_user.html',
                            form=form,
                            page_title="Add User",
                            button_text="Save User")

# ------------------ EDIT USER ------------------
@bp.route("/users/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_user(id):
    if current_user.role != "admin":
        abort(403)

    user = User.query.get_or_404(id)

    # Pass the original email for validation
    form = AdminEditUserForm(obj=user, original_email=user.email)

    if form.validate_on_submit():
        before = user_snapshot(user)

        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.email = form.email.data.lower()
        user.role = form.role.data

        db.session.commit()
        log_event(event="user.updated", details={"before": before, "after": user_snapshot(user)})

        flash("User updated successfully.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/edit_user.html",
                            user=user, form=form,
                            page_title="Edit User",
                            button_text="Update User")


# ------------------ DELETE USER ACTION ------------------
@bp.route("/users/delete/<int:id>", methods=["POST"])
@login_required
def delete_user(id):
    if current_user.role != "admin":
        abort(403)

    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        abort(400, "You cannot delete your own account.")

    # Soft delete: mark inactive and store deletion timestamp
    user.is_active = False
    user.deleted_at = datetime.utcnow()
    db.session.commit()

    snapshot = user_snapshot(user)
    log_event(event="user.deleted", details=snapshot)
    flash("User deleted successfully (soft delete).", "success")
    return redirect(url_for("admin.users"))


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

@bp.route("/audit_logs")
@login_required
def audit_logs():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("admin.dashboard"))

    page = request.args.get("page", 1, type=int)
    per_page = 10  # 5–10 is ideal → using 10

    pagination = (
        AuditLog.query
        .filter_by(deleted_at=None)
        .order_by(AuditLog.timestamp.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        "admin/audit_logs.html",
        logs=pagination.items,
        pagination=pagination,
        page_title="Audit Logs"
    )


@bp.route("/audit_logs/delete/<int:log_id>", methods=["POST"])
@login_required
def delete_audit_log(log_id):
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("admin.audit_logs"))

    log = AuditLog.query.get_or_404(log_id)

    log.deleted_at = datetime.utcnow()
    db.session.commit()

    flash("Audit log deleted successfully (soft delete).", "success")
    return redirect(url_for("admin.audit_logs"))


# Archive Audit Logs page
@bp.route("/audit_logs/archive")
@login_required
def archive_audit_logs():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("admin.dashboard"))

    page = request.args.get("page", 1, type=int)
    per_page = 10

    pagination = AuditLog.query.filter(AuditLog.deleted_at.isnot(None))\
        .order_by(AuditLog.deleted_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    logs = pagination.items
    return render_template("admin/archive_audit_logs.html",
                            logs=logs,
                            pagination=pagination,
                            page_title="Archived Audit Logs")


# Restore soft-deleted audit log
@bp.route("/audit_logs/restore/<int:log_id>", methods=["POST"])
@login_required
def restore_audit_log(log_id):
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("admin.archive_audit_logs"))

    log = AuditLog.query.get_or_404(log_id)

    log.deleted_at = None
    db.session.commit()

    flash("Audit log restored successfully.", "success")
    return redirect(url_for("admin.archive_audit_logs"))
