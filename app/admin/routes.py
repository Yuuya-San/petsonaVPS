from flask import render_template, flash, redirect, url_for, abort, jsonify, make_response # pyright: ignore[reportMissingImports]
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]
from app.admin import bp
from flask import request # pyright: ignore[reportMissingImports]
from .forms import (
    GeneralSettingsForm, SecuritySettingsForm, AuditSettingsForm,
    EmailSettingsForm, APISettingsForm, BackupSettingsForm, ComplianceSettingsForm,
    AppearanceSettingsForm, AdminAddUserForm, AdminEditUserForm
)
from app.extensions import limiter, csrf
from app.models import User, AuditLog, Merchant
from app.models.notification import Notification
from app import db
from sqlalchemy import func, or_, cast # pyright: ignore[reportMissingImports]
import random
from app.auth.emails import send_temp_credentials
from app.utils.audit import log_event, user_snapshot
import csv
import json
from io import StringIO
from datetime import datetime
from pytz import timezone, UTC # pyright: ignore[reportMissingModuleSource]
from app.utils.activity_formatter import format_activity
from app.utils.activity_config import RECENT_ACTIVITY_EVENTS
from app.utils.dashboard_stats import get_dashboard_stats
from app.decorators import admin_required
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


def to_ph_time(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = UTC.localize(dt)
    return dt.astimezone(PH_TZ)

# Default avatars
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

@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Display admin dashboard with stats and recent activities"""
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))

    # Retrieve aggregated dashboard statistics
    stats = get_dashboard_stats()

    # Define trackable event types for recent activity dashboard
    RECENT_ACTIVITY_EVENTS = [
        "species.created", "species.updated", "species.deleted", "species.restored",
        "breed.created", "breed.updated", "breed.deleted", "breed.restored",
        "user.registered", "user.updated",
    ]

    # Fetch 5 most recent undeleted audit logs matching tracked events
    logs = (
        AuditLog.query
        .filter(AuditLog.deleted_at.is_(None))
        .filter(AuditLog.event.in_(RECENT_ACTIVITY_EVENTS))
        .order_by(AuditLog.timestamp.desc())
        .limit(5)
        .all()
    )

    # Convert timestamps to Philippine timezone for display
    ph_tz = timezone("Asia/Manila")

    recent_activities = []
    for log in logs:
        act = format_activity(log)
        if act["time"]:
            utc_time = act["time"]
            if utc_time.tzinfo is None:
                utc_time = UTC.localize(utc_time)
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
    """List all active users with optional role filtering and pagination"""
    if current_user.role != "admin":
        abort(403)

    role = request.args.get("role")
    page = request.args.get("page", 1, type=int)

    # Query only active (non-deleted) users sorted by first name
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
    """Display archived (soft-deleted) users with pagination"""
    if current_user.role != "admin":
        abort(403)

    page = request.args.get("page", 1, type=int)

    # Query soft-deleted users sorted by deletion date (newest first)
    query = User.query.filter_by(is_active=False).order_by(User.deleted_at.desc())

    # Paginate 10 users per page
    users_paginated = query.paginate(page=page, per_page=10)

    # Convert deletion timestamps to Manila timezone for display consistency
    import pytz # pyright: ignore[reportMissingModuleSource]
    manila = pytz.timezone('Asia/Manila')
    for user in users_paginated.items:
        if user.deleted_at:
            user.deleted_at_manila = user.deleted_at.astimezone(manila)
        else:
            user.deleted_at_manila = None

    return render_template(
        "admin/archive_users.html",
        users=users_paginated
    )

@bp.route("/users/restore/<int:id>", methods=["POST"])
@login_required
@admin_required
def restore_user(id):
    """Restore a soft-deleted user account"""
    if current_user.role != "admin":
        abort(403)

    user = User.query.get_or_404(id)

    # Capture user state before restoration
    before = user_snapshot(user)

    # Mark user as active again and clear deletion timestamp
    user.is_active = True
    user.deleted_at = None
    db.session.commit()

    # Capture user state after restoration for audit trail
    after = user_snapshot(user)

    # Record restoration action in audit log
    log_event(event="user.restored", details={"before": before, "after": after})

    flash(f"User {user.first_name} restored successfully.", "success")
    return redirect(url_for("admin.archive_users"))

@bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_user():
    """Create new user account and send temporary credentials"""
    if current_user.role != 'admin':
        abort(403)

    form = AdminAddUserForm()

    if form.validate_on_submit():
        temp_password = form.password.data

        # Initialize new user with provided details and random avatar
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

        # Record user creation in audit log
        log_event(
            event='user.created',
            details={
                'created_user_id': user.id,
                'created_user_email': user.email,
                'assigned_role': user.role
            }
        )

        # Email credentials to new user
        send_temp_credentials(user.email, temp_password)

        flash('User created and credentials sent via email.', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/add_user.html',
                            form=form,
                            button_text="Save")

@bp.route("/users/edit/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(id):
    """Edit user details and track changes in audit log"""
    if current_user.role != "admin":
        abort(403)

    user = User.query.get_or_404(id)

    # Initialize form with current user data
    form = AdminEditUserForm(obj=user, original_email=user.email)

    if form.validate_on_submit():
        # Dictionary to track which fields changed
        changes = {}

        def track_change(field_name, new_value):
            """Compare old vs new value and record changes"""
            old_value = getattr(user, field_name, None)
            if old_value != new_value:
                changes[field_name] = {"old": old_value, "new": new_value}
                setattr(user, field_name, new_value)

        # Check each editable field for changes
        track_change("first_name", form.first_name.data.strip())
        track_change("last_name", form.last_name.data.strip())
        track_change("email", form.email.data.lower())
        track_change("role", form.role.data)

        # Only commit and log if changes exist
        if changes:
            db.session.commit()
            # Record changes in audit log
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

    # Populate form fields with current user data on GET request
    elif not form.is_submitted():
        form.first_name.data = user.first_name or ""
        form.last_name.data = user.last_name or ""
        form.email.data = user.email or ""
        form.role.data = user.role

    return render_template(
        "admin/edit_user.html",
        user=user,
        form=form,
        button_text="Update"
    )

@bp.route("/users/delete/<int:id>", methods=["POST"])
@login_required
@admin_required
def delete_user(id):
    """Soft-delete user account (mark inactive with timestamp)"""
    if current_user.role != "admin":
        abort(403)

    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        abort(400, "You cannot delete your own account.")

    # Mark user as inactive and record deletion time
    user.is_active = False
    user.deleted_at = get_ph_datetime()
    db.session.commit()

    # Capture user state and record deletion in audit log
    snapshot = user_snapshot(user)
    log_event(event="user.deleted", details=snapshot)
    flash("User deleted successfully (soft delete).", "success")
    return redirect(url_for("admin.users"))

@bp.route("/audit_logs")
@login_required
@admin_required
def audit_logs():
    """Display paginated audit logs (non-deleted entries only)"""
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("admin.dashboard"))

    page = request.args.get("page", 1, type=int)
    per_page = 10

    # Fetch non-deleted logs sorted by timestamp (newest first) with pagination
    pagination = (
        AuditLog.query
        .filter_by(deleted_at=None)
        .order_by(AuditLog.timestamp.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    for log in pagination.items:
        log.ph_timestamp = to_ph_time(log.timestamp)

    return render_template(
        "admin/audit_logs.html",
        logs=pagination.items,
        pagination=pagination,
        page_title="Audit Logs"
    )

@bp.route("/audit_logs/export")
@login_required
@admin_required
def export_audit_logs():
    """Export visible audit logs to a CSV file for Excel."""
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("admin.audit_logs"))

    search = request.args.get("search", "", type=str).strip()
    start_date = request.args.get("start_date", type=str)
    end_date = request.args.get("end_date", type=str)

    query = AuditLog.query.filter_by(deleted_at=None)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                AuditLog.event.ilike(search_term),
                AuditLog.actor_email.ilike(search_term),
                cast(AuditLog.actor_id, db.String).ilike(search_term),
            )
        )

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(AuditLog.timestamp >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            query = query.filter(AuditLog.timestamp <= end)
        except ValueError:
            pass

    logs = query.order_by(AuditLog.timestamp.desc()).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Event", "Actor", "Timestamp", "IP Address", "User Agent", "Details"])

    for log in logs:
        actor = log.actor_email if log.actor_email else (f"User #{log.actor_id}" if log.actor_id else "System")
        details = log.get_details()
        if isinstance(details, dict):
            details = json.dumps(details, ensure_ascii=False)
        csv_timestamp = to_ph_time(log.timestamp)
        writer.writerow([
            log.id,
            log.event,
            actor,
            csv_timestamp.strftime("%Y-%m-%d %H:%M:%S") if csv_timestamp else "",
            log.ip_address or "",
            log.user_agent or "",
            details or ""
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=audit_logs.csv"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response

@bp.route("/audit_logs/delete/<int:log_id>", methods=["POST"])
@login_required
@admin_required
def delete_audit_log(log_id):
    """Soft-delete an audit log entry"""
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("admin.audit_logs"))

    log = AuditLog.query.get_or_404(log_id)

    # Mark log as deleted with timestamp
    log.deleted_at = get_ph_datetime()
    db.session.commit()

    flash("Audit log deleted successfully (soft delete).", "success")
    return redirect(url_for("admin.audit_logs"))

@bp.route("/audit_logs/archive")
@login_required
@admin_required
def archive_audit_logs():
    """Display archived (soft-deleted) audit logs with pagination"""
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("admin.dashboard"))

    page = request.args.get("page", 1, type=int)
    per_page = 10

    # Fetch soft-deleted logs sorted by deletion date (newest first)
    pagination = AuditLog.query.filter(AuditLog.deleted_at.isnot(None))\
        .order_by(AuditLog.deleted_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    logs = pagination.items
    return render_template("admin/archive_audit_logs.html",
                            logs=logs,
                            pagination=pagination,
                            page_title="Archived Audit Logs")

@bp.route("/audit_logs/restore/<int:log_id>", methods=["POST"])
@login_required
@admin_required
def restore_audit_log(log_id):
    """Restore a soft-deleted audit log entry"""
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("admin.archive_audit_logs"))

    log = AuditLog.query.get_or_404(log_id)

    # Restore log by clearing deletion timestamp
    log.deleted_at = None
    db.session.commit()

    flash("Audit log restored successfully.", "success")
    return redirect(url_for("admin.archive_audit_logs"))

@bp.route("/api/merchants", methods=["GET"])
@login_required
@admin_required
def get_merchants():
    """Retrieve merchant applications as JSON, optionally filtered by status"""
    if current_user.role != "admin":
        abort(403)
    
    try:
        # Get status filter from query params (default: show all non-deleted)
        status = request.args.get('status', 'all')
        
        # Query non-deleted merchants and apply status filter if specified
        query = Merchant.query.filter(Merchant.deleted_at.is_(None))
        
        if status and status != 'all':
            query = query.filter_by(application_status=status)
        
        # Sort by submission date if available, otherwise by creation date (newest first)
        merchants = query.order_by(func.coalesce(Merchant.submitted_at, Merchant.created_at).desc()).all()
        
        merchants_data = []
        for merchant in merchants:
            try:
                # Safely retrieve associated user information
                user_email = 'N/A'
                user_name = 'N/A'
                if merchant.user_id:
                    user = User.query.get(merchant.user_id)
                    if user:
                        user_email = user.email or 'N/A'
                        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or 'N/A'
                
                # Build comprehensive merchant data object for JSON response
                merchant_dict = {
                    'id': merchant.id,
                    'year': merchant.created_at.year if merchant.created_at else '',
                    'business_name': merchant.business_name or 'N/A',
                    'business_category': merchant.business_category or 'N/A',
                    'owner_manager_name': merchant.owner_manager_name or 'N/A',
                    'contact_email': merchant.contact_email or 'N/A',
                    'contact_phone': merchant.contact_phone or 'N/A',
                    'user_email': user_email,
                    'user_name': user_name,
                    'city': merchant.city or 'N/A',
                    'province': merchant.province or 'N/A',
                    'barangay': merchant.barangay or 'N/A',
                    'postal_code': merchant.postal_code or 'N/A',
                    'latitude': float(merchant.latitude) if merchant.latitude else None,
                    'longitude': float(merchant.longitude) if merchant.longitude else None,
                    'full_address': merchant.full_address or 'N/A',
                    'services_offered': merchant.services_offered or [],
                    'pets_accepted': merchant.pets_accepted or [],
                    'service_pricing': merchant.service_pricing or {},
                    'cancellation_policy': merchant.cancellation_policy or '',
                    'government_id_path': merchant.government_id_path or '',
                    'business_permit_path': merchant.business_permit_path or '',
                    'facility_photos_paths': merchant.facility_photos_paths or [],
                    'submitted_at': merchant.submitted_at.isoformat() if merchant.submitted_at else '',
                    'reviewed_at': merchant.reviewed_at.isoformat() if merchant.reviewed_at else None,
                    'rejection_reason': merchant.rejection_reason or '',
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
                # Skip merchants with processing errors
                continue
        
        return jsonify({'merchants': merchants_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route("/api/merchants/<int:merchant_id>/approve", methods=["POST"])
@csrf.exempt
@login_required
@admin_required
def approve_merchant(merchant_id):
    """Approve a pending merchant application and upgrade user role"""
    try:
        merchant = Merchant.query.get_or_404(merchant_id)
        
        if merchant.application_status != 'pending':
            return jsonify({'success': False, 'message': 'Application is not in pending status'}), 400
        
        # Update merchant status and verification info
        merchant.application_status = 'approved'
        merchant.reviewed_at = get_ph_datetime()
        merchant.reviewed_by = current_user.id
        merchant.is_verified = True
        
        # Upgrade associated user to merchant role
        user = User.query.get(merchant.user_id)
        if user:
            user.role = 'merchant'
        else:
            return jsonify({'success': False, 'message': 'Associated user not found'}), 404
        
        db.session.commit()
        
        # Notify merchant of approval and redirect them to store setup
        Notification.create_notification(
            user_id=user.id,
            title='Application Approved!',
            message=f'Congratulations! Your merchant application for "{merchant.business_name}" has been approved by the admin team. You can now start listing your services and accepting bookings!',
            notification_type='success',
            icon='fas fa-check-circle',
            link=f'/merchant/store',
            related_id=merchant.id,
            related_type='merchant_application',
            from_user_id=current_user.id
        )
        
        # Record approval action in audit log
        log_event(
            event='merchant.approved',
            details={
                'merchant_id': merchant.id,
                'business_name': merchant.business_name,
                'approved_by': current_user.email,
                'user_id': user.id
            }
        )
        
        flash(f"Merchant '{merchant.business_name}' has been approved successfully!", 'success')
        return jsonify({'success': True, 'message': 'Merchant approved successfully'})
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving merchant: {str(e)}', 'danger')
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route("/api/merchants/<int:merchant_id>/reject", methods=["POST"])
@csrf.exempt
@login_required
@admin_required
def reject_merchant(merchant_id):
    """Reject a pending merchant application with reason provided"""
    try:
        # Extract rejection reason from request JSON
        data = request.get_json()
        reason = data.get('reason', '') if data else ''
        
        if not reason.strip():
            return jsonify({'success': False, 'message': 'Rejection reason is required'}), 400
        
        merchant = Merchant.query.get_or_404(merchant_id)
        
        if merchant.application_status != 'pending':
            return jsonify({'success': False, 'message': 'Application is not in pending status'}), 400
        
        # Update merchant status with rejection details
        merchant.application_status = 'rejected'
        merchant.reviewed_at = get_ph_datetime()
        merchant.rejection_reason = reason.strip()
        merchant.reviewed_by = current_user.id
        
        # Retrieve user for notification
        user = User.query.get(merchant.user_id)
        db.session.commit()
        
        # Notify merchant of rejection with reason
        if user:
            Notification.create_notification(
                user_id=user.id,
                title='Application Status Update',
                message=f'Your merchant application for "{merchant.business_name}" has been reviewed and unfortunately was not approved at this time. Reason: {reason.strip()}',
                notification_type='danger',
                icon='fas fa-times-circle',
                link=f'/merchant/apply',
                related_id=merchant.id,
                related_type='merchant_application',
                from_user_id=current_user.id
            )
        
        # Record rejection action in audit log
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
        flash(f'Error rejecting merchant: {str(e)}', 'danger')
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route("/merchants/applications")
@login_required
@admin_required
def merchant_applications():
    """Render merchant applications review dashboard"""
    if current_user.role != "admin":
        abort(403)
    
    return render_template("admin/merchant_applications.html")

