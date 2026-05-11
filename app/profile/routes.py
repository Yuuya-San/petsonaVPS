"""Profile routes for user profile management."""
from flask import render_template, redirect, url_for, flash, current_app, request
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]
from werkzeug.utils import secure_filename
import os
from . import bp
from .forms import ProfileForm
from ..models import User, AuditLog
from ..extensions import db
from datetime import datetime
from app.utils.audit import log_event
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)

# Allowed file extensions for uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

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

def log_audit(event: str, actor=None, request_obj=None, metadata: dict = None):
    """Log audit event with all details to audit_logs table."""
    ip_address = None
    user_agent = None
    
    if request_obj:
        ip_address = request_obj.headers.get('X-Forwarded-For', request_obj.remote_addr)
        user_agent = request_obj.headers.get('User-Agent')
    
    audit_entry = AuditLog(
        event=event,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        ip_address=ip_address,
        user_agent=user_agent,
        timestamp=get_ph_datetime()
    )
    
    if metadata:
        audit_entry.set_details(metadata)
    
    db.session.add(audit_entry)
    db.session.commit()


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_user_template_and_redirect():
    """
    Always return the single profile template.
    Redirect target depends on user role.
    """
    dashboard_map = {
        'admin': 'admin.dashboard',
        'merchant': 'merchant.dashboard',
        'user': 'user.dashboard',
    }

    return (
        'profile/profile.html',
        dashboard_map.get(current_user.role, 'user.dashboard')
    )



@bp.route('/', methods=['GET', 'POST'])
@login_required
def profile():
    """View and edit user profile on single page - supports user, admin, and merchant roles."""
    form = ProfileForm()
    template, dashboard_redirect = get_user_template_and_redirect()
    
    if form.validate_on_submit():
        # Track changes for audit log
        changes = {}
        
        # Check if first name changed
        new_first_name = form.first_name.data.strip()
        if current_user.first_name != new_first_name:
            changes['first_name'] = {
                'old': current_user.first_name,
                'new': new_first_name
            }
            current_user.first_name = new_first_name
        
        # Check if last name changed
        new_last_name = form.last_name.data.strip()
        if current_user.last_name != new_last_name:
            changes['last_name'] = {
                'old': current_user.last_name,
                'new': new_last_name
            }
            current_user.last_name = new_last_name
        
        # Handle avatar - prioritize upload over selection
        avatar_changed = False
        if form.avatar_upload.data:
            # User uploaded a custom avatar
            file = form.avatar_upload.data
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{current_user.id}_{file.filename}")
                upload_folder = os.path.join(
                    current_app.root_path,
                    'static',
                    'images',
                    'avatar',
                    'uploads'
                )
                
                # Create uploads folder if it doesn't exist
                os.makedirs(upload_folder, exist_ok=True)
                
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)
                
                # Store relative path for use in templates
                new_avatar = f"images/avatar/uploads/{filename}"
                if current_user.photo_url != new_avatar:
                    changes['photo_url'] = {
                        'old': current_user.photo_url,
                        'new': new_avatar,
                        'type': 'custom_upload',
                        'filename': filename
                    }
                    current_user.photo_url = new_avatar
                    avatar_changed = True
                flash('Avatar uploaded successfully!', 'success')
            else:
                flash('Invalid file format. Please upload jpg, jpeg, png, or gif.', 'danger')
        elif form.avatar_choice.data:
            # User selected a default avatar
            if form.avatar_choice.data in DEFAULT_AVATARS:
                if current_user.photo_url != form.avatar_choice.data:
                    changes['photo_url'] = {
                        'old': current_user.photo_url,
                        'new': form.avatar_choice.data,
                        'type': 'predefined_selection'
                    }
                    current_user.photo_url = form.avatar_choice.data
                    avatar_changed = True
                flash('Avatar changed successfully!', 'success')
            else:
                flash('Invalid avatar selection.', 'danger')
        
        # Commit changes
        db.session.commit()
        
        # Log audit event only if there were changes
        if changes:
            log_event(
                event=f"user.updated",
                details={
                    'changes': changes,
                    'user_role': current_user.role
                }
            )
            flash('Profile updated successfully!', 'success')
        
        return redirect(url_for('profile.profile'))
    
    # Pre-populate form with current user data
    elif form.is_submitted() is False:
        form.first_name.data = current_user.first_name or ''
        form.last_name.data = current_user.last_name or ''
        if current_user.photo_url and current_user.photo_url in DEFAULT_AVATARS:
            form.avatar_choice.data = current_user.photo_url
    
    return render_template(
        template,
        form=form,
        default_avatars=DEFAULT_AVATARS,
        user=current_user,
        edit_mode=False
    )
