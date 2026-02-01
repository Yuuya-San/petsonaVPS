from flask import render_template, flash, redirect, url_for, abort, jsonify
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]
from app.admin import bp
from flask import request
from .forms import (
    GeneralSettingsForm, SecuritySettingsForm, AuditSettingsForm,
    EmailSettingsForm, APISettingsForm, BackupSettingsForm, ComplianceSettingsForm,
    AppearanceSettingsForm, AdminAddUserForm, AdminEditUserForm
)
from app.extensions import limiter, csrf
from app.models import User, AuditLog, Merchant
from app import db
import random
from app.auth.emails import send_temp_credentials
from app.utils.audit import log_event, user_snapshot
from datetime import datetime
from pytz import timezone, UTC # pyright: ignore[reportMissingModuleSource]
from app.utils.activity_formatter import format_activity
from app.utils.activity_config import RECENT_ACTIVITY_EVENTS
from app.utils.dashboard_stats import get_dashboard_stats
from app.decorators import admin_required


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
@admin_required
def dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))

    # Get dashboard stats (function should return a dict with stats)
    stats = get_dashboard_stats()

    # Define which events to include in recent activities
    RECENT_ACTIVITY_EVENTS = [
        "species.created", "species.updated", "species.deleted", "species.restored",
        "breed.created", "breed.updated", "breed.deleted", "breed.restored",
        "user.registered", "user.updated",
    ]

    # Fetch recent audit logs (limit 5, newest first)
    logs = (
        AuditLog.query
        .filter(AuditLog.deleted_at.is_(None))
        .filter(AuditLog.event.in_(RECENT_ACTIVITY_EVENTS))
        .order_by(AuditLog.timestamp.desc())
        .limit(5)
        .all()
    )

    # Philippine timezone
    ph_tz = timezone("Asia/Manila")

    recent_activities = []
    for log in logs:
        act = format_activity(log)
        if act["time"]:
            # Make sure the timestamp is timezone-aware (assume it's UTC in DB)
            utc_time = act["time"]
            if utc_time.tzinfo is None:
                utc_time = UTC.localize(utc_time)
            # Convert to PH time
            act["time"] = utc_time.astimezone(ph_tz)
        recent_activities.append(act)

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_activities=recent_activities
    )


@bp.route("/users")
@login_required
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
def view_user(id):
    if current_user.role != "admin":
        abort(403)

    user = User.query.get_or_404(id)
    return render_template("admin/view_user.html", user=user)

@bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
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
@admin_required
def edit_user(id):
    if current_user.role != "admin":
        abort(403)

    user = User.query.get_or_404(id)

    # Pass the original email for validation
    form = AdminEditUserForm(obj=user, original_email=user.email)

    if form.validate_on_submit():
        # Track changes for audit log
        changes = {}

        def track_change(field_name, new_value):
            old_value = getattr(user, field_name, None)
            if old_value != new_value:
                changes[field_name] = {"old": old_value, "new": new_value}
                setattr(user, field_name, new_value)

        # Track editable fields
        track_change("first_name", form.first_name.data.strip())
        track_change("last_name", form.last_name.data.strip())
        track_change("email", form.email.data.lower())
        track_change("role", form.role.data)

        # Commit only if there are changes
        if changes:
            db.session.commit()
            # ---- AUDIT LOG ----
            log_event(
                event="user.updated",
                details={
                    "changes": changes,
                    "user_id": user.id,
                    "user_email": user.email
                }
            )
            flash("User updated successfully.", "success")
        else:
            flash("No changes detected.", "info")

        return redirect(url_for("admin.users"))

    # Pre-populate form with current user data if not submitted
    elif not form.is_submitted():
        form.first_name.data = user.first_name or ""
        form.last_name.data = user.last_name or ""
        form.email.data = user.email or ""
        form.role.data = user.role

    return render_template(
        "admin/edit_user.html",
        user=user,
        form=form,
        page_title="Edit User",
        button_text="Update User"
    )


# ------------------ DELETE USER ACTION ------------------
@bp.route("/users/delete/<int:id>", methods=["POST"])
@login_required
@admin_required
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
@login_required
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
def restore_audit_log(log_id):
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("admin.archive_audit_logs"))

    log = AuditLog.query.get_or_404(log_id)

    log.deleted_at = None
    db.session.commit()

    flash("Audit log restored successfully.", "success")
    return redirect(url_for("admin.archive_audit_logs"))


# ==================== MERCHANT MANAGEMENT ==================== 

@bp.route("/api/merchants", methods=["GET"])
@login_required
@admin_required
def get_merchants():
    """Get all merchant applications as JSON with optional status filter"""
    if current_user.role != "admin":
        abort(403)
    
    try:
        status = request.args.get('status', 'all')
        
        query = Merchant.query.filter(Merchant.deleted_at == None)
        
        if status and status != 'all':
            query = query.filter_by(application_status=status)
        
        merchants = query.order_by(Merchant.submitted_at.desc()).all()
        
        merchants_data = []
        for merchant in merchants:
            try:
                merchant_dict = {
                    'id': merchant.id,
                    'business_name': merchant.business_name or 'N/A',
                    'business_type': merchant.business_type or 'N/A',
                    'owner_manager_name': merchant.owner_manager_name or 'N/A',
                    'contact_email': merchant.contact_email or 'N/A',
                    'contact_phone': merchant.contact_phone or 'N/A',
                    'user_email': merchant.user.email if merchant.user else 'N/A',
                    'user_name': f"{merchant.user.first_name} {merchant.user.last_name}" if merchant.user else 'N/A',
                    'city': merchant.city or 'N/A',
                    'province': merchant.province or 'N/A',
                    'barangay': merchant.barangay or 'N/A',
                    'postal_code': merchant.postal_code or 'N/A',
                    'latitude': float(merchant.latitude) if merchant.latitude else None,
                    'longitude': float(merchant.longitude) if merchant.longitude else None,
                    'full_address': merchant.full_address or 'N/A',
                    'services_offered': merchant.services_offered or [],
                    'pets_accepted': merchant.pets_accepted or [],
                    'max_pets_per_day': merchant.max_pets_per_day or 0,
                    'min_price_per_day': float(merchant.min_price_per_day) if merchant.min_price_per_day else 0.0,
                    'max_price_per_day': float(merchant.max_price_per_day) if merchant.max_price_per_day else 0.0,
                    'cancellation_policy': merchant.cancellation_policy or '',
                    'government_id_path': merchant.government_id_path or '',
                    'business_permit_path': merchant.business_permit_path or '',
                    'facility_photos_paths': merchant.facility_photos_paths or [],
                    'submitted_at': merchant.submitted_at.isoformat() if merchant.submitted_at else '',
                    'reviewed_at': merchant.reviewed_at.isoformat() if merchant.reviewed_at else None,
                    'rejection_reason': merchant.rejection_reason or '',
                    'years_in_operation': merchant.years_in_operation or 0,
                    'application_status': merchant.application_status or 'pending',
                    'business_description': merchant.business_description or '',
                    'opening_time': merchant.opening_time or '',
                    'closing_time': merchant.closing_time or '',
                    'operating_days': merchant.operating_days or [],
                    'google_maps_link': merchant.google_maps_link or '',
                    'is_verified': merchant.is_verified if hasattr(merchant, 'is_verified') else False,
                    'user_id': merchant.user_id,
                    'logo_path': merchant.logo_path or '',
                    'logo_url': f"/static/{merchant.logo_path}" if merchant.logo_path else '',
                    'created_at': merchant.created_at.isoformat() if merchant.created_at else '',
                    'updated_at': merchant.updated_at.isoformat() if merchant.updated_at else ''
                }
                merchants_data.append(merchant_dict)
            except Exception as e:
                continue
        
        return jsonify({'merchants': merchants_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route("/api/merchants/<int:merchant_id>/approve", methods=["POST"])
@csrf.exempt
@login_required
@admin_required
def approve_merchant(merchant_id):
    """Approve a merchant application"""
    try:
        merchant = Merchant.query.get_or_404(merchant_id)
        
        if merchant.application_status != 'pending':
            return jsonify({'success': False, 'message': 'Application is not in pending status'}), 400
        
        merchant.application_status = 'approved'
        merchant.reviewed_at = datetime.utcnow()
        merchant.reviewed_by = current_user.id
        merchant.is_verified = True
        
        db.session.commit()
        
        # Log the event
        log_event(
            event='merchant.approved',
            details={
                'merchant_id': merchant.id,
                'business_name': merchant.business_name,
                'approved_by': current_user.email
            }
        )
        
        flash(f"Merchant '{merchant.business_name}' has been approved successfully!", 'success')
        return jsonify({'success': True, 'message': 'Merchant approved successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error approving merchant: {str(e)}")
        flash(f'Error approving merchant: {str(e)}', 'danger')
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route("/api/merchants/<int:merchant_id>/reject", methods=["POST"])
@csrf.exempt
@login_required
@admin_required
def reject_merchant(merchant_id):
    """Reject a merchant application with reason"""
    try:
        data = request.get_json()
        reason = data.get('reason', '') if data else ''
        
        if not reason.strip():
            return jsonify({'success': False, 'message': 'Rejection reason is required'}), 400
        
        merchant = Merchant.query.get_or_404(merchant_id)
        
        if merchant.application_status != 'pending':
            return jsonify({'success': False, 'message': 'Application is not in pending status'}), 400
        
        merchant.application_status = 'rejected'
        merchant.reviewed_at = datetime.utcnow()
        merchant.rejection_reason = reason.strip()
        merchant.reviewed_by = current_user.id
        
        db.session.commit()
        
        # Log the event
        log_event(
            event='merchant.rejected',
            details={
                'merchant_id': merchant.id,
                'business_name': merchant.business_name,
                'rejected_by': current_user.email,
                'reason': reason
            }
        )
        
        flash(f"Merchant '{merchant.business_name}' has been rejected.", 'warning')
        return jsonify({'success': True, 'message': 'Merchant rejected successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error rejecting merchant: {str(e)}")
        flash(f'Error rejecting merchant: {str(e)}', 'danger')
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route("/merchants/applications")
@login_required
@admin_required
def merchant_applications():
    """Display all merchant applications"""
    if current_user.role != "admin":
        abort(403)
    
    return render_template("admin/merchant_applications.html")

