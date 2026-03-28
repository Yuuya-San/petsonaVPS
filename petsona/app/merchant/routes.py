import os
import json
from ..extensions import limiter
import requests # pyright: ignore[reportMissingModuleSource]
import pytz # pyright: ignore[reportMissingModuleSource]
from datetime import datetime, time as dt_time
from werkzeug.utils import secure_filename # pyright: ignore[reportMissingImports]
from flask import render_template, flash, redirect, request, url_for, jsonify # pyright: ignore[reportMissingImports]
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]
from app.merchant import bp
from app.decorators import merchant_required, user_required
from app.models.breed import Breed
from app.models.species import Species
from app.models.merchant import Merchant
from app.models.booking import Booking
from app.models.notification import Notification
from app.models.user import User
from app.extensions import db, csrf
from app.merchant.forms import MerchantApplicationForm, MerchantStoreUpdateForm
from app.models.audit_log import AuditLog
from sqlalchemy import func, and_ # pyright: ignore[reportMissingImports]
from app.utils.notification_manager import NotificationManager
import logging

logger = logging.getLogger(__name__)

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


def _normalize_province_for_region(region_name):
    if not region_name or not isinstance(region_name, str):
        return None
    normalized = region_name.strip().upper()
    if 'NCR' in normalized or 'METRO MANILA' in normalized or 'NATIONAL CAPITAL REGION' in normalized:
        return 'Metropolitan Manila'
    return None

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf', 'gif', 'webp'}
MAX_SINGLE_FILE_SIZE = 2 * 1024 * 1024  # 2MB per logo / government ID / business permit
MAX_FACILITY_PHOTOS_TOTAL_SIZE = 5 * 1024 * 1024  # 5MB total for facility photo uploads
MIN_FACILITY_PHOTOS = 3
MAX_FACILITY_PHOTOS = 5


def get_file_size(file):
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/dashboard')
@login_required
@merchant_required
def dashboard():
    """Display merchant dashboard with booking stats and trending pet species"""
    if current_user.role != 'merchant':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))

    # Retrieve merchant profile associated with current user
    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    
    # Query booking counts by status for dashboard metrics
    total_bookings = Booking.query.filter_by(merchant_id=merchant.id).count()
    total_pending = Booking.query.filter_by(merchant_id=merchant.id, status='pending').count()
    total_confirmed = Booking.query.filter_by(merchant_id=merchant.id, status='confirmed').count()
    total_completed = Booking.query.filter_by(merchant_id=merchant.id, status='completed').count()
    total_rejected = Booking.query.filter_by(merchant_id=merchant.id, status='rejected').count()
    total_no_show = Booking.query.filter_by(merchant_id=merchant.id, status='no-show').count()
    
    # Fetch 5 most recent bookings for preview
    recent_bookings = Booking.query.filter_by(merchant_id=merchant.id).order_by(Booking.created_at.desc()).limit(5).all()
    
    # Calculate completion rate as percentage of completed vs total bookings
    completion_rate = round((total_completed / total_bookings * 100) if total_bookings > 0 else 0)
    
    # Retrieve top 3 active pet species by popularity
    top_species = Species.query.filter(
        Species.deleted_at.is_(None)
    ).order_by(Species.heart_vote_count.desc()).limit(3).all()
    
    return render_template(
        'merchant/dashboard.html',
        merchant=merchant,
        top_species=top_species,
        total_bookings=total_bookings,
        pending_count=total_pending,
        approved_count=total_confirmed,
        rejected_count=total_rejected,
        completed_count=total_completed,
        no_show_count=total_no_show,
        completion_rate=completion_rate,
        recent_bookings=recent_bookings
    )

@bp.route('/store')
@login_required
@merchant_required
def store():
    """Display merchant store profile with real-time booking statistics and analytics"""
    if current_user.role != 'merchant':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))

    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    
    if not merchant:
        flash('Store information not found. Please complete your merchant application first.', 'warning')
        return redirect(url_for('merchant.apply'))
    
    # Query booking statistics from Booking model (non-deleted bookings only)
    
    # Count total, confirmed, pending, completed, and cancelled bookings
    total_bookings = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    # 2. Confirmed Bookings Count
    confirmed_bookings = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.status == 'confirmed',
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    # 3. Pending Bookings Count
    pending_bookings = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.status == 'pending',
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    # 4. Completed Bookings Count
    completed_bookings = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.status == 'completed',
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    # 5. Cancelled Bookings Count
    cancelled_bookings = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.status == 'cancelled',
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    # 6. Store Rating (Not yet implemented in simplified booking system)
    store_rating = 4.0
    
    # 7. Total Reviews Count (Not yet implemented in simplified booking system)
    total_reviews = 0
    
    # Calculate completion rate as percentage
    completion_rate = 0
    if total_bookings > 0:
        completion_rate = round((completed_bookings / total_bookings) * 100, 1)
    
    # Calculate average merchant response time (from booking creation to confirmation)
    avg_response_hours = 24  # Default fallback
    try:
        # Use MySQL unix_timestamp to compute time difference in hours
        response_times = db.session.query(
            func.avg(
                (func.unix_timestamp(Booking.merchant_confirmed_at) - 
                 func.unix_timestamp(Booking.created_at)) / 3600.0
            )
        ).filter(
            Booking.merchant_id == merchant.id,
            Booking.merchant_confirmed_at.isnot(None),
            Booking.deleted_at.is_(None)
        ).scalar()
        
        if response_times and response_times > 0:
            avg_response_hours = max(1, round(float(response_times), 1))
    except Exception as e:
        avg_response_hours = 24
    
    # Format response time
    if avg_response_hours < 1:
        avg_response_time = f"{int(avg_response_hours * 60)}m"
    elif avg_response_hours < 24:
        avg_response_time = f"{int(avg_response_hours)}h"
    else:
        avg_response_time = f"{round(avg_response_hours / 24, 1)}d"
    
    # Calculate total revenue from completed bookings
    total_revenue = db.session.query(func.sum(Booking.total_amount)).filter(
        Booking.merchant_id == merchant.id,
        Booking.status == 'completed',
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    total_revenue = float(total_revenue)
    
    # Calculate merchant earnings (currently same as revenue, can add commission logic later)
    merchant_earnings = db.session.query(func.sum(Booking.total_amount)).filter(
        Booking.merchant_id == merchant.id,
        Booking.status == 'completed',
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    merchant_earnings = float(merchant_earnings)
    
    # Calculate platform fees (revenue difference after commission)
    platform_fees = total_revenue - merchant_earnings if total_revenue > 0 else 0
    
    # Count bookings created in last 30 days
    from datetime import timedelta
    thirty_days_ago = get_ph_datetime() - timedelta(days=30)
    bookings_this_month = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.created_at >= thirty_days_ago,
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    # No-show tracking (placeholder for future implementation)
    no_show_count = 0
    no_show_rate = 0
    
    # Fetch 5 most recent bookings for analytics preview
    recent_bookings = db.session.query(Booking).filter(
        Booking.merchant_id == merchant.id,
        Booking.deleted_at.is_(None)
    ).order_by(Booking.created_at.desc()).limit(5).all()
    
    # Calculate month-over-month booking growth percentage (compare last month vs previous month)
    sixty_days_ago = get_ph_datetime() - timedelta(days=60)
    prev_month_bookings = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.created_at >= sixty_days_ago,
        Booking.created_at < thirty_days_ago,
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    # Compute growth rate as percentage change
    month_growth = 0
    if prev_month_bookings > 0:
        month_growth = round(((bookings_this_month - prev_month_bookings) / prev_month_bookings) * 100, 1)
    else:
        month_growth = 100 if bookings_this_month > 0 else 0
    
    # Determine if growth is positive or negative
    growth_direction = "up" if month_growth >= 0 else "down"

    # Build public URL for merchant logo if exists
    logo_path = merchant.logo_path
    logo_url = url_for('static', filename=f'uploads/merchants/{merchant.id}/{logo_path}') if logo_path else None
    
    # Compile all store statistics for template rendering
    store_stats = {
        'booking_count': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'pending_bookings': pending_bookings,
        'completed_bookings': completed_bookings,
        'cancelled_bookings': cancelled_bookings,
        'store_rating': store_rating,
        'total_reviews': total_reviews,
        'avg_response_time': avg_response_time,
        'completion_rate': completion_rate,
        'total_revenue': f"₱{total_revenue:,.2f}",
        'merchant_earnings': f"₱{merchant_earnings:,.2f}",
        'platform_fees': f"₱{platform_fees:,.2f}",
        'bookings_this_month': bookings_this_month,
        'month_growth': month_growth,
        'growth_direction': growth_direction,
        'no_show_rate': no_show_rate,
        'recent_bookings': recent_bookings,
    }
    
    return render_template(
        'merchant/store.html',
        merchant=merchant,
        **store_stats
    )

@bp.route('/store/logo-upload', methods=['POST'])
@login_required
@merchant_required
@csrf.exempt
def upload_logo():
    """Upload merchant store logo"""
    try:
        logger.info(f"Logo upload requested by user {current_user.id}")
        
        if current_user.role != 'merchant':
            logger.warning(f"Non-merchant user {current_user.id} tried to upload logo")
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        merchant = Merchant.query.filter_by(user_id=current_user.id).first()
        
        if not merchant:
            return jsonify({'success': False, 'message': 'Store not found'}), 404
        
        # Check if file is in request
        if 'logo' not in request.files:
            logger.warning(f"Logo upload: no file in request from user {current_user.id}")
            return jsonify({'success': False, 'message': 'No file provided'}), 400
        
        file = request.files['logo']
        
        if file.filename == '':
            logger.warning(f"Logo upload: empty filename from user {current_user.id}")
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Validate file extension
        if not allowed_file(file.filename):
            logger.warning(f"Logo upload: invalid file type {file.filename} from user {current_user.id}")
            return jsonify({'success': False, 'message': 'Invalid file type. Allowed: JPG, PNG'}), 400
        
        # Validate file size (max 5MB)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({'success': False, 'message': 'File too large. Max 5MB'}), 400
        
        # Create upload directory using user ID (grouped by user, not merchant)
        upload_dir = os.path.join('app/static/uploads/merchants', str(current_user.id))
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename with timestamp to avoid conflicts
        timestamp = int(datetime.utcnow().timestamp())
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"logo_{timestamp}.{file_extension}")
        
        # Persist uploaded file to disk
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        
        # Remove previous logo file if one exists
        if merchant.logo_path:
            # Extract just the filename from the stored path
            old_filename = merchant.logo_path.split('/')[-1] if '/' in merchant.logo_path else merchant.logo_path
            old_path = os.path.join('app/static/uploads/merchants', str(current_user.id), old_filename)
            try:
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception as e:
                pass
        
        # Update merchant record with relative path to uploaded logo
        merchant.logo_path = f"merchants/{current_user.id}/{filename}"
        merchant.updated_at = get_ph_datetime()
        db.session.add(merchant)
        db.session.commit()
        
        # Record upload action in audit log
        audit_log = AuditLog(
            event='merchant_logo_uploaded',
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=get_ph_datetime()
        )
        audit_log.set_details({'merchant_id': merchant.id, 'filename': filename})
        db.session.add(audit_log)
        db.session.commit()
        
        # Build public URL for the uploaded logo
        logo_url = url_for('static', filename=f'uploads/merchants/{merchant.id}/{filename}')
        
        return jsonify({
            'success': True,
            'message': 'Logo uploaded successfully',
            'logo_url': logo_url
        }), 200
        
    except Exception as e:
        # Log error and rollback transaction on upload failure
        logger.error(f"Error uploading logo: {str(e)}", exc_info=True)
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({'success': False, 'message': 'Upload failed'}), 500

@bp.route('/store/edit', methods=['GET', 'POST'])
@login_required
@merchant_required
def store_edit():
    """Edit merchant store profile with validation and audit logging"""
    if current_user.role != 'merchant':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))

    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    
    if not merchant:
        flash('Store information not found. Please complete your merchant application first.', 'warning')
        return redirect(url_for('merchant.apply'))
    
    form = MerchantStoreUpdateForm()
    
    if form.validate_on_submit():
        try:
            # Validate operating hours if not 24-hour operation
            if not form.is_24h.data:
                # Manual schedule mode - hours and days are required
                if not form.opening_time.data or not form.closing_time.data:
                    flash('Opening and closing times are required when not using 24/7 mode.', 'danger')
                    return render_template('merchant/store_edit.html', form=form, merchant=merchant)
                
                if not form.operating_days.data or len(form.operating_days.data) == 0:
                    flash('Please select at least one operating day when not using 24/7 mode.', 'danger')
                    return render_template('merchant/store_edit.html', form=form, merchant=merchant)
            
            # Capture merchant state before updates for audit trail
            previous_values = {
                'business_name': merchant.business_name,
                'business_category': merchant.business_category,
                'business_description': merchant.business_description,
                'owner_manager_name': merchant.owner_manager_name,
                'contact_email': merchant.contact_email,
                'contact_phone': merchant.contact_phone,
                'full_address': merchant.full_address,
                'city': merchant.city,
                'province': merchant.province,
                'barangay': merchant.barangay,
                'postal_code': merchant.postal_code,
                'google_maps_link': merchant.google_maps_link,
                'services_offered': merchant.services_offered,
                'pets_accepted': merchant.pets_accepted,
                'opening_time': merchant.opening_time,
                'closing_time': merchant.closing_time,
                'operating_days': merchant.operating_days,
                'cancellation_policy': merchant.cancellation_policy,
            }
            
            # SECTION 1: Update business details
            merchant.business_name = form.business_name.data
            merchant.business_category = form.business_category.data
            merchant.business_description = form.business_description.data
            
            # Process logo upload if file provided
            if 'store_logo' in request.files and request.files['store_logo'].filename:
                logo_file = request.files['store_logo']
                if allowed_file(logo_file.filename):
                    # Validate file size
                    logo_file.seek(0, os.SEEK_END)
                    file_size = logo_file.tell()
                    logo_file.seek(0)
                    
                    if file_size <= MAX_FILE_SIZE:
                        # Create merchant upload directory
                        upload_dir = os.path.join('app/static/uploads/merchants', str(current_user.id))
                        os.makedirs(upload_dir, exist_ok=True)
                        
                        # Delete old logo if exists
                        if merchant.logo_path:
                            old_filename = merchant.logo_path.split('/')[-1] if '/' in merchant.logo_path else merchant.logo_path
                            old_path = os.path.join(upload_dir, old_filename)
                            try:
                                if os.path.exists(old_path):
                                    os.remove(old_path)
                            except Exception as e:
                                pass
                        
                        # Generate unique filename and save
                        timestamp = int(datetime.utcnow().timestamp())
                        file_extension = logo_file.filename.rsplit('.', 1)[1].lower()
                        filename = secure_filename(f"logo_{timestamp}.{file_extension}")
                        filepath = os.path.join(upload_dir, filename)
                        logo_file.save(filepath)
                        
                        # Update merchant with full path
                        merchant.logo_path = f"merchants/{current_user.id}/{filename}"
                        logger.info(f"Logo updated for merchant {merchant.id}: {merchant.logo_path}")
            
            # Handle government ID upload
            if request.files.get('government_id') and request.files['government_id'].filename:
                file = request.files['government_id']
                if file and allowed_file(file.filename):
                    file_size = get_file_size(file)
                    if file_size <= MAX_SINGLE_FILE_SIZE:
                        # Create merchant upload directory
                        upload_dir = os.path.join('app/static/uploads/merchants', str(current_user.id))
                        os.makedirs(upload_dir, exist_ok=True)
                        
                        # Delete old file if exists
                        if merchant.government_id_path:
                            old_filename = merchant.government_id_path.split('/')[-1] if '/' in merchant.government_id_path else merchant.government_id_path
                            old_path = os.path.join(upload_dir, old_filename)
                            try:
                                if os.path.exists(old_path):
                                    os.remove(old_path)
                            except Exception:
                                pass
                        
                        # Generate unique filename and save
                        timestamp = datetime.utcnow().timestamp()
                        file_extension = file.filename.rsplit('.', 1)[1].lower()
                        filename = secure_filename(f"gov_id_{timestamp}.{file_extension}")
                        filepath = os.path.join(upload_dir, filename)
                        file.save(filepath)
                        
                        # Update merchant with full path
                        merchant.government_id_path = f"merchants/{current_user.id}/{filename}"
                        logger.info(f"Government ID updated for merchant {merchant.id}: {merchant.government_id_path}")
                    else:
                        flash('Government ID must be 2MB or smaller.', 'danger')
                        return render_template('merchant/store_edit.html', form=form, merchant=merchant)
            
            # Handle business permit upload
            if request.files.get('business_permit') and request.files['business_permit'].filename:
                file = request.files['business_permit']
                if file and allowed_file(file.filename):
                    file_size = get_file_size(file)
                    if file_size <= MAX_SINGLE_FILE_SIZE:
                        # Create merchant upload directory
                        upload_dir = os.path.join('app/static/uploads/merchants', str(current_user.id))
                        os.makedirs(upload_dir, exist_ok=True)
                        
                        # Delete old file if exists
                        if merchant.business_permit_path:
                            old_filename = merchant.business_permit_path.split('/')[-1] if '/' in merchant.business_permit_path else merchant.business_permit_path
                            old_path = os.path.join(upload_dir, old_filename)
                            try:
                                if os.path.exists(old_path):
                                    os.remove(old_path)
                            except Exception:
                                pass
                        
                        # Generate unique filename and save
                        timestamp = datetime.utcnow().timestamp()
                        file_extension = file.filename.rsplit('.', 1)[1].lower()
                        filename = secure_filename(f"permit_{timestamp}.{file_extension}")
                        filepath = os.path.join(upload_dir, filename)
                        file.save(filepath)
                        
                        # Update merchant with full path
                        merchant.business_permit_path = f"merchants/{current_user.id}/{filename}"
                        logger.info(f"Business permit updated for merchant {merchant.id}: {merchant.business_permit_path}")
                    else:
                        flash('Business permit must be 2MB or smaller.', 'danger')
                        return render_template('merchant/store_edit.html', form=form, merchant=merchant)
            
            # Handle facility photos upload
            all_files = request.files.getlist('facility_photos') or []
            files = [file for file in all_files if file and getattr(file, 'filename', None)]
            if files:
                upload_dir = os.path.join('app/static/uploads/merchants', str(current_user.id))
                os.makedirs(upload_dir, exist_ok=True)
                valid_files = []
                total_photo_size = 0
                for file in files:
                    if file and file.filename and allowed_file(file.filename):
                        file_size = get_file_size(file)
                        total_photo_size += file_size
                        valid_files.append((file, file_size))
                
                if len(valid_files) < MIN_FACILITY_PHOTOS:
                    flash(f'Please upload at least {MIN_FACILITY_PHOTOS} facility photos.', 'danger')
                    return render_template('merchant/store_edit.html', form=form, merchant=merchant)
                if len(valid_files) > MAX_FACILITY_PHOTOS:
                    flash(f'Please upload no more than {MAX_FACILITY_PHOTOS} facility photos.', 'danger')
                    return render_template('merchant/store_edit.html', form=form, merchant=merchant)
                if total_photo_size > MAX_FACILITY_PHOTOS_TOTAL_SIZE:
                    flash(f'Facility photos must be {MAX_FACILITY_PHOTOS_TOTAL_SIZE // (1024 * 1024)}MB or smaller in total.', 'danger')
                    return render_template('merchant/store_edit.html', form=form, merchant=merchant)
                
                facility_photos = []
                for idx, (file, _) in enumerate(valid_files):
                    timestamp = datetime.utcnow().timestamp()
                    file_extension = file.filename.rsplit('.', 1)[1].lower()
                    filename = secure_filename(f"facility_{idx}_{timestamp}.{file_extension}")
                    filepath = os.path.join(upload_dir, filename)
                    file.save(filepath)
                    facility_photos.append(f"merchants/{current_user.id}/{filename}")
                
                merchant.facility_photos_paths = facility_photos
                logger.info(f"Facility photos updated for merchant {merchant.id}: {len(facility_photos)} photos")
            
            # SECTION 2: Update contact person information
            merchant.owner_manager_name = form.owner_manager_name.data
            merchant.contact_email = form.contact_email.data
            merchant.contact_phone = form.contact_phone.data
            
            # SECTION 3: Update location details
            region_name = form.region.data or ''
            merchant.region = region_name or None
            merchant.province = _normalize_province_for_region(region_name) or form.province.data or region_name or None

            merchant.full_address = form.full_address.data
            merchant.city = form.city.data
            merchant.barangay = form.barangay.data or ''
            merchant.google_maps_link = form.google_maps_link.data
            
            # Update coordinates from hidden fields
            if request.form.get('latitude'):
                merchant.latitude = float(request.form.get('latitude'))
            if request.form.get('longitude'):
                merchant.longitude = float(request.form.get('longitude'))
            
            # SECTION 4: Update pet types
            merchant.pets_accepted = form.pets_accepted.data if form.pets_accepted.data else []
            
            # Parse service pricing configuration from form JSON
            service_pricing_json = form.service_pricing_json.data
            if service_pricing_json:
                try:
                    merchant.service_pricing = json.loads(service_pricing_json)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Invalid service pricing JSON provided: {service_pricing_json}")
            
            # SECTION 6: OPERATING SCHEDULE with 24/7 support and Philippine timezone
            if form.is_24h.data:
                # 24/7 operation
                merchant.opening_time = '00:00'  # 12:00 AM
                merchant.closing_time = '23:59'  # 11:59 PM
                merchant.operating_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                merchant.is_24h = True
                logger.info(f"Merchant {current_user.id} updated to 24/7 operation")
            else:
                # Custom hours
                merchant.opening_time = form.opening_time.data
                merchant.closing_time = form.closing_time.data
                merchant.operating_days = form.operating_days.data if form.operating_days.data else []
                merchant.is_24h = False
            
            # SECTION 8: POLICIES
            merchant.cancellation_policy = form.cancellation_policy.data
            
            merchant.updated_at = get_ph_datetime()
            
            # Mark as pending approval if it was approved, and set verified to false
            if merchant.application_status != 'pending' or merchant.application_status == 'pending':
                merchant.application_status = 'pending'
                merchant.is_verified = False
            
            db.session.commit()
            
            # Log the update
            audit_log = AuditLog(
                event='merchant_store_updated',
                actor_id=current_user.id,
                actor_email=current_user.email,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                timestamp=get_ph_datetime()
            )
            audit_log.set_details({
                'merchant_id': merchant.id,
                'previous_values': previous_values,
                'new_values': {
                    'business_name': merchant.business_name,
                    'business_category': merchant.business_category,
                    'business_description': merchant.business_description,
                    'owner_manager_name': merchant.owner_manager_name,
                    'contact_email': merchant.contact_email,
                    'contact_phone': merchant.contact_phone,
                    'full_address': merchant.full_address,
                    'city': merchant.city,
                    'province': merchant.province,
                    'barangay': merchant.barangay,
                    'postal_code': merchant.postal_code,
                    'google_maps_link': merchant.google_maps_link,
                    'services_offered': merchant.services_offered,
                    'pets_accepted': merchant.pets_accepted,
                    'opening_time': merchant.opening_time,
                    'closing_time': merchant.closing_time,
                    'operating_days': merchant.operating_days,
                    'cancellation_policy': merchant.cancellation_policy,
                }
            })
            db.session.add(audit_log)
            db.session.commit()
            
            flash('Store information updated! Your changes are pending admin approval.', 'success')
            return redirect(url_for('merchant.store'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating store: {str(e)}", exc_info=True)
            flash(f'Error updating store information: {str(e)}', 'danger')
            return render_template('merchant/store_edit.html', form=form, merchant=merchant)
    
    elif request.method == 'GET':
        # Populate form fields with current merchant data for editing
        form.business_name.data = merchant.business_name
        form.business_category.data = merchant.business_category
        form.business_description.data = merchant.business_description
        form.owner_manager_name.data = merchant.owner_manager_name
        form.contact_email.data = merchant.contact_email
        form.contact_phone.data = merchant.contact_phone
        form.full_address.data = merchant.full_address
        form.region.data = merchant.region or (merchant.province if merchant.province and ('NCR' in merchant.province.upper() or 'METRO MANILA' in merchant.province.upper() or 'NATIONAL CAPITAL REGION' in merchant.province.upper()) else '')
        # Skip province/city/barangay - they're names in DB but form expects codes
        # These will be handled by JavaScript loading from API
        form.postal_code.data = merchant.postal_code
        form.google_maps_link.data = merchant.google_maps_link
        form.pets_accepted.data = merchant.pets_accepted or []
        form.opening_time.data = merchant.opening_time
        form.closing_time.data = merchant.closing_time
        form.operating_days.data = merchant.operating_days or []
        form.cancellation_policy.data = merchant.cancellation_policy
        
        # Pre-fill service pricing JSON
        if merchant.service_pricing:
            form.service_pricing_json.data = json.dumps(merchant.service_pricing)
        
        # Pre-fill coordinates
        if merchant.latitude:
            form.latitude.data = str(merchant.latitude)
        if merchant.longitude:
            form.longitude.data = str(merchant.longitude)
    
    return render_template('merchant/store_edit.html', form=form, merchant=merchant)

@bp.route('/store-status', methods=['POST'])
@login_required
@merchant_required
def update_store_status():
    """Toggle store open/closed status"""
    if current_user.role != 'merchant':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    if not merchant:
        return jsonify({'success': False, 'message': 'Store not found'}), 404

    try:
        data = request.get_json()
        status = data.get('status')  # 'open' or 'closed'
        
        if status == 'closed':
            merchant.is_open = False
        elif status == 'open':
            merchant.is_open = True
        else:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400
        
        db.session.commit()

        # Log the action
        action_desc = f"Store status changed to: {'OPEN' if merchant.is_open else 'CLOSED'}"
        audit_log = AuditLog(
            event='merchant_store_status_updated',
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        audit_log.set_details({
            'merchant_id': merchant.id,
            'description': action_desc,
            'new_status': 'open' if merchant.is_open else 'closed'
        })
        db.session.add(audit_log)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Store is now {("open" if merchant.is_open else "closed")}',
            'is_open': merchant.is_open
        })
    except Exception as e:
        logger.error(f'Error updating store status: {str(e)}')
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred'}), 500

@bp.route('/store-public/<int:merchant_id>')
@login_required
@user_required
def store_public(merchant_id):
    """Display public merchant store profile (no authentication required)"""
    merchant = Merchant.query.filter_by(id=merchant_id).first()
    
    if not merchant:
        flash('Store not found.', 'danger')
        return redirect(url_for('user.nearby_services'))
    
    # Placeholder for ratings/reviews (not yet implemented)
    store_rating = 0
    total_reviews = 0
    
    # Determine if store is currently open based on operating hours
    is_open = False
    if merchant.opening_time and merchant.closing_time and merchant.operating_days:
        from datetime import datetime, time
        now = datetime.now()
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        current_time = now.time()
        
        # Check if current day and time fall within operating schedule
        operating_days = merchant.get_operating_days()
        if current_day in operating_days:
            # Check if current time is within operating hours
            try:
                # Convert opening time string, handling 24:00 case
                opening_str = merchant.opening_time if isinstance(merchant.opening_time, str) else str(merchant.opening_time)
                if opening_str == '24:00':
                    opening = datetime.strptime('00:00', '%H:%M').time()
                else:
                    opening = datetime.strptime(opening_str, '%H:%M').time()
                
                # Convert closing time string, handling 24:00 case
                closing_str = merchant.closing_time if isinstance(merchant.closing_time, str) else str(merchant.closing_time)
                if closing_str == '24:00':
                    closing = datetime.strptime('00:00', '%H:%M').time()
                else:
                    closing = datetime.strptime(closing_str, '%H:%M').time()
                
                # Handle stores that close at midnight or after
                if closing > opening:
                    # Normal case: opening before closing (e.g., 9 AM - 6 PM)
                    is_open = opening <= current_time <= closing
                else:
                    # Crosses midnight (e.g., 10 PM - 6 AM or 8 AM - 12 AM)
                    is_open = current_time >= opening or current_time <= closing
            except (ValueError, TypeError):
                is_open = False
    
    return render_template('merchant/store_public.html', 
                         merchant=merchant, 
                         store_rating=store_rating, 
                         total_reviews=total_reviews,
                         is_open=is_open)

@bp.route('/species')
@login_required
@merchant_required
def species_index():
    """Display paginated list of all active pet species"""
    page = request.args.get('page', 1, type=int)

    # Query active (non-deleted) species sorted alphabetically with pagination
    pagination = Species.query.filter(
        Species.deleted_at.is_(None)
    ).order_by(Species.name.asc()).paginate(
        page=page, per_page=1000, error_out=False
    )

    species_list = pagination.items

    return render_template(
        'merchant/species_index.html',
        species_list=species_list,
        pagination=pagination,
        page_title="Pet Species"
    )

@bp.route('/species/<int:id>')
@login_required
@merchant_required
def view_species(id):
    """Display specific pet species with all active breeds"""
    species = Species.query.get_or_404(id)

    # Fetch active breeds for the selected species, sorted alphabetically
    breeds = Breed.query.filter_by(
        species_id=species.id,
        is_active=True   
    ).order_by(Breed.name.asc()).all()

    return render_template(
        'merchant/view_species.html',
        species=species,
        breeds=breeds,
        page_title=f"{species.name} Breeds"
    )

@bp.route('/apply', methods=['GET', 'POST'])
@login_required
@user_required
def apply():
    """Merchant application form - collect business details and documents from user"""
    
    # Prevent duplicate merchant applications
    existing_merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    
    if existing_merchant and existing_merchant.application_status in ['pending', 'under_review']:
        flash('You already have a pending application. Please wait for admin review.', 'warning')
        return redirect(url_for('user.dashboard'))
    
    form = MerchantApplicationForm()
    
    if form.validate_on_submit():
        try:
            # Check if merchant already exists
            merchant = Merchant.query.filter_by(user_id=current_user.id).first()
            
            if not merchant:
                merchant = Merchant(user_id=current_user.id)
            
            # Fill basic information
            merchant.business_name = form.business_name.data
            merchant.business_category = form.business_category.data
            merchant.business_description = form.business_description.data
            
            # Contact information
            merchant.owner_manager_name = form.owner_manager_name.data
            merchant.contact_email = form.contact_email.data
            merchant.contact_phone = form.contact_phone.data
            
            # Location - store human-readable names
            region_name = form.region.data or ''
            merchant.region = region_name or None
            merchant.province = _normalize_province_for_region(region_name) or form.province.data or region_name or None
            merchant.city = form.city.data
            merchant.barangay = form.barangay.data or ''
            merchant.postal_code = form.postal_code.data or None
            merchant.full_address = form.full_address.data
            merchant.google_maps_link = form.google_maps_link.data or None
            
            # Store coordinates - safely convert to float
            try:
                if form.latitude.data and form.longitude.data:
                    lat = float(form.latitude.data)
                    lng = float(form.longitude.data)
                    merchant.set_coordinates(lat, lng)
            except (ValueError, TypeError):
                logger.warning(f"Invalid coordinates provided: lat={form.latitude.data}, lng={form.longitude.data}")
            
            # Pets accepted (service offerings were removed from the form)
            merchant.pets_accepted = form.pets_accepted.data if form.pets_accepted.data else []
            
            # Parse service pricing JSON from form
            service_pricing_json = form.service_pricing_json.data
            if service_pricing_json:
                try:
                    merchant.service_pricing = json.loads(service_pricing_json)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Invalid service pricing JSON provided: {service_pricing_json}")
                    merchant.service_pricing = {}
            else:
                merchant.service_pricing = {}
            
            
            # Operating schedule with 24/7 support and Philippine timezone
            
            if form.is_24h.data:
                # 24/7 operation
                merchant.opening_time = '00:00'  # 12:00 AM
                merchant.closing_time = '23:59'  # 11:59 PM
                merchant.operating_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                merchant.is_24h = True
                logger.info(f"Merchant {current_user.id} set to 24/7 operation")
            else:
                # Custom hours - store as Philippine Time
                merchant.opening_time = form.opening_time.data
                merchant.closing_time = form.closing_time.data
                merchant.operating_days = form.operating_days.data if form.operating_days.data else []
                merchant.is_24h = False
            
            # Policies
            merchant.cancellation_policy = form.cancellation_policy.data or None
            
            # Create merchant uploads directory
            merchant_upload_dir = os.path.join('app/static/uploads/merchants', str(current_user.id))
            os.makedirs(merchant_upload_dir, exist_ok=True)
            
            # Handle store logo upload
            if request.files.get('store_logo') and request.files['store_logo'].filename:
                file = request.files['store_logo']
                if file and allowed_file(file.filename):
                    file_size = get_file_size(file)
                    if file_size <= MAX_SINGLE_FILE_SIZE:
                        filename = secure_filename(f"logo_{datetime.utcnow().timestamp()}_{file.filename}")
                        file.save(os.path.join(merchant_upload_dir, filename))
                        merchant.logo_path = f'merchants/{current_user.id}/{filename}'
                    else:
                        flash('Store logo must be 2MB or smaller.', 'danger')
                        return render_template('merchant/apply.html', form=form)
            
            # Handle government ID upload
            if request.files.get('government_id') and request.files['government_id'].filename:
                file = request.files['government_id']
                if file and allowed_file(file.filename):
                    file_size = get_file_size(file)
                    if file_size <= MAX_SINGLE_FILE_SIZE:
                        filename = secure_filename(f"gov_id_{datetime.utcnow().timestamp()}_{file.filename}")
                        file.save(os.path.join(merchant_upload_dir, filename))
                        merchant.government_id_path = f'merchants/{current_user.id}/{filename}'
                    else:
                        flash('Government ID must be 2MB or smaller.', 'danger')
                        return render_template('merchant/apply.html', form=form)
            
            # Handle business permit upload
            if request.files.get('business_permit') and request.files['business_permit'].filename:
                file = request.files['business_permit']
                if file and allowed_file(file.filename):
                    file_size = get_file_size(file)
                    if file_size <= MAX_SINGLE_FILE_SIZE:
                        filename = secure_filename(f"permit_{datetime.utcnow().timestamp()}_{file.filename}")
                        file.save(os.path.join(merchant_upload_dir, filename))
                        merchant.business_permit_path = f'merchants/{current_user.id}/{filename}'
                    else:
                        flash('Business permit must be 2MB or smaller.', 'danger')
                        return render_template('merchant/apply.html', form=form)
            
            # Handle multiple facility photos
            facility_photos = []
            all_files = request.files.getlist('facility_photos') or []
            files = [file for file in all_files if file and getattr(file, 'filename', None)]
            if files:
                valid_files = []
                total_photo_size = 0
                for file in files:
                    if file and file.filename and allowed_file(file.filename):
                        file_size = get_file_size(file)
                        total_photo_size += file_size
                        valid_files.append((file, file_size))
                
                if len(valid_files) < MIN_FACILITY_PHOTOS:
                    flash(f'Please upload at least {MIN_FACILITY_PHOTOS} facility photos.', 'danger')
                    return render_template('merchant/apply.html', form=form)
                if len(valid_files) > MAX_FACILITY_PHOTOS:
                    flash(f'Please upload no more than {MAX_FACILITY_PHOTOS} facility photos.', 'danger')
                    return render_template('merchant/apply.html', form=form)
                if total_photo_size > MAX_FACILITY_PHOTOS_TOTAL_SIZE:
                    flash(f'Facility photos must be {MAX_FACILITY_PHOTOS_TOTAL_SIZE // (1024 * 1024)}MB or smaller in total.', 'danger')
                    return render_template('merchant/apply.html', form=form)
                
                for idx, (file, file_size) in enumerate(valid_files):
                    filename = secure_filename(f"facility_{idx}_{datetime.utcnow().timestamp()}_{file.filename}")
                    file.save(os.path.join(merchant_upload_dir, filename))
                    facility_photos.append(f'merchants/{current_user.id}/{filename}')
                
                merchant.facility_photos_paths = facility_photos
            
            # Set application status
            merchant.application_status = 'pending'
            merchant.submitted_at = get_ph_datetime()
            
            db.session.add(merchant)
            db.session.commit()
            
            # ========== CREATE NOTIFICATIONS ==========
            
            # 1️ Notify all admin users about the new merchant application
            admin_users = User.query.filter_by(role='admin').all()
            
            for admin_user in admin_users:
                Notification.create_notification(
                    user_id=admin_user.id,
                    title='New Merchant Application',
                    message=f'{current_user.first_name} {current_user.last_name} has submitted a merchant application for "{merchant.business_name}"',
                    notification_type='warning',
                    icon='fas fa-store',
                    link=f'/admin/merchants/applications',
                    related_id=merchant.id,
                    related_type='merchant_application',
                    from_user_id=current_user.id
                )
                logger.info(f"Notification created for admin {admin_user.id} about merchant application {merchant.id}")
            
            # 2 Optionally, create a notification for the merchant user about submission
            Notification.create_notification(
                user_id=current_user.id,
                title='Application Submitted',
                message=f'Your merchant application for "{merchant.business_name}" has been submitted successfully. Our admin team will review it within 5-7 business days.',
                notification_type='success',
                icon='fas fa-check-circle',
                link=f'/user/dashboard',
                related_id=merchant.id,
                related_type='merchant_application'
            )
            logger.info(f"Notification created for merchant user {current_user.id} about their application submission")
            
            flash('Application submitted successfully! Our team will review your application and contact you within 5-7 business days.', 'success')
            return redirect(url_for('user.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            logger.exception('Error submitting merchant application')
            flash('An error occurred while submitting your application. Please try again.', 'danger')
            return render_template('merchant/apply.html', form=form)
    
    # Log validation errors if form submission fails
    if request.method == 'POST' and not form.validate_on_submit():
        for field, errors in form.errors.items():
            for error in errors:
                logger.warning(f"Form validation error - {field}: {error}")
                flash(f"{field}: {error}", 'danger')
    
    return render_template('merchant/apply.html', form=form)

def _parse_psgc_list(raw_data):
    if isinstance(raw_data, list):
        return raw_data
    if isinstance(raw_data, dict):
        if 'data' in raw_data and isinstance(raw_data['data'], list):
            return raw_data['data']
        return [raw_data]
    return []


def _normalize_region_name(region):
    if not isinstance(region, dict):
        return region

    name = str(region.get('name', '')).strip()
    code = str(region.get('code', '')).strip().upper()

    if not name:
        return region

    if code == 'NCR' or 'national capital region' in name.lower() or 'metro manila' in name.lower():
        region['name'] = 'NCR / Metro Manila'
    elif 'calabarzon' in name.lower():
        region['name'] = 'CALABARZON (Region IV-A)'
    elif '(' not in name and code:
        region['name'] = f'{name} ({code})'

    return region


@bp.route('/api/get-regions')
@login_required
def get_regions():
    """Fetch Philippine regions from the PSGC API."""
    try:
        regions = []
        response = requests.get('https://psgc.gitlab.io/api/regions/', timeout=5)
        if response.status_code == 200:
            regions = _parse_psgc_list(response.json())

        unique_regions = []
        seen = set()
        for region in regions:
            if not isinstance(region, dict):
                continue
            if 'code' not in region or 'name' not in region:
                continue

            region = _normalize_region_name(region)
            code = str(region.get('code', '')).strip()
            if code and code not in seen:
                region['_type'] = 'region'
                seen.add(code)
                unique_regions.append(region)

        unique_regions.sort(key=lambda x: x.get('name', '').lower())
        return jsonify(unique_regions)
    except Exception as e:
        logger.error(f'Error fetching regions: {str(e)}')
    return jsonify({'error': 'Failed to fetch regions'}), 500


@bp.route('/api/get-provinces', defaults={'region_code': None})
@bp.route('/api/get-provinces/<region_code>')
@login_required
def get_provinces(region_code):
    """Fetch all Philippine provinces or region-specific provinces from PSGC API."""
    try:
        provinces = []
        response = requests.get('https://psgc.gitlab.io/api/provinces/', timeout=5)
        if response.status_code == 200:
            provinces = _parse_psgc_list(response.json())

        if region_code:
            region_key = str(region_code).strip().upper()
            if region_key == 'NCR':
                provinces = []
            else:
                filtered = []
                for province in provinces:
                    if not isinstance(province, dict):
                        continue
                    # PSGC province data can use different keys for the region code field
                    region_code_field = ''
                    for key in ('regionCode', 'region_code', 'region'):
                        if province.get(key):
                            region_code_field = str(province.get(key)).strip().upper()
                            break
                    if region_code_field == region_key or region_key in region_code_field:
                        filtered.append(province)
                provinces = filtered

        unique_provinces = []
        seen = set()
        for province in provinces:
            if not isinstance(province, dict) or 'code' not in province or 'name' not in province:
                continue
            code = str(province['code']).strip()
            if code and code not in seen:
                province['_type'] = 'province'
                seen.add(code)
                unique_provinces.append(province)

        unique_provinces.sort(key=lambda x: x.get('name', '').lower())
        return jsonify(unique_provinces)
    except Exception as e:
        logger.error(f'Error fetching provinces: {str(e)}')
    return jsonify({'error': 'Failed to fetch provinces'}), 500


@bp.route('/api/get-cities/<location_code>')
@login_required
def get_cities(location_code):
    """Fetch cities/municipalities for a province or region from PSGC API."""
    try:
        all_cities = []
        location_code = str(location_code or '').strip()
        location_code_upper = location_code.upper()

        # 1) Region lookup: cities and municipalities for special regions like NCR
        try:
            response = requests.get(
                f'https://psgc.gitlab.io/api/regions/{location_code}/cities/',
                timeout=5
            )
            if response.status_code == 200:
                all_cities.extend(_parse_psgc_list(response.json()))
        except Exception as e:
            logger.debug(f'Region cities lookup failed for {location_code}: {str(e)}')

        try:
            response = requests.get(
                f'https://psgc.gitlab.io/api/regions/{location_code}/municipalities/',
                timeout=5
            )
            if response.status_code == 200:
                all_cities.extend(_parse_psgc_list(response.json()))
        except Exception as e:
            logger.debug(f'Region municipalities lookup failed for {location_code}: {str(e)}')

        # 2) Province lookup: cities + municipalities
        try:
            response = requests.get(
                f'https://psgc.gitlab.io/api/provinces/{location_code}/cities/',
                timeout=5
            )
            if response.status_code == 200:
                all_cities.extend(_parse_psgc_list(response.json()))
        except Exception as e:
            logger.debug(f'Province cities lookup failed for {location_code}: {str(e)}')

        try:
            response = requests.get(
                f'https://psgc.gitlab.io/api/provinces/{location_code}/municipalities/',
                timeout=5
            )
            if response.status_code == 200:
                all_cities.extend(_parse_psgc_list(response.json()))
        except Exception as e:
            logger.debug(f'Province municipalities lookup failed for {location_code}: {str(e)}')

        # 3) Deduplicate and normalize results
        seen = set()
        unique_cities = []
        for city in all_cities:
            if not isinstance(city, dict) or 'code' not in city or 'name' not in city:
                continue
            code = str(city['code']).strip()
            if not code or code in seen:
                continue
            seen.add(code)
            unique_cities.append(city)

        unique_cities.sort(key=lambda x: x.get('name', '').lower())

        if location_code_upper == 'NCR' and len(unique_cities) != 17:
            logger.warning(f'NCR / Metro Manila expected 17 cities/municipalities, found {len(unique_cities)}')

        logger.info(f'Found {len(unique_cities)} cities/municipalities for {location_code}')
        return jsonify(unique_cities)
    except Exception as e:
        logger.error(f'Error fetching cities/municipalities for {location_code}: {str(e)}')
    return jsonify({'error': 'Failed to fetch cities/municipalities'}), 500


@bp.route('/api/get-barangays/<city_code>')
@login_required
def get_barangays(city_code):
    """Fetch barangays for city/municipality from PSGC API with multiple fallbacks"""
    try:
        barangay_list = []

        # 1 Try city endpoint first
        try:
            city_url = f'https://psgc.gitlab.io/api/cities/{city_code}/barangays/'
            response = requests.get(city_url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    barangay_list = data
                elif isinstance(data, dict) and 'data' in data:
                    barangay_list = data['data']
        except Exception as e:
            logger.debug(f"City endpoint failed: {str(e)}")

        # 2️ If empty, try municipality endpoint
        if not barangay_list:
            try:
                muni_url = f'https://psgc.gitlab.io/api/municipalities/{city_code}/barangays/'
                muni_response = requests.get(muni_url, timeout=5)

                if muni_response.status_code == 200:
                    data = muni_response.json()
                    if isinstance(data, list):
                        barangay_list = data
                    elif isinstance(data, dict) and 'data' in data:
                        barangay_list = data['data']
            except Exception as e:
                logger.debug(f"Municipality endpoint failed: {str(e)}")

        # 3️ If still empty, try district endpoint (some areas use districts)
        if not barangay_list:
            try:
                dist_url = f'https://psgc.gitlab.io/api/districts/{city_code}/barangays/'
                dist_response = requests.get(dist_url, timeout=5)

                if dist_response.status_code == 200:
                    data = dist_response.json()
                    if isinstance(data, list):
                        barangay_list = data
                    elif isinstance(data, dict) and 'data' in data:
                        barangay_list = data['data']
            except Exception as e:
                logger.debug(f"District endpoint failed: {str(e)}")

        # 4️ Still empty = invalid or no barangays available
        if not barangay_list:
            logger.warning(f"No barangays found for city code: {city_code}")
            return jsonify([])

        # 5 Sort barangays alphabetically for consistent display
        barangay_list.sort(key=lambda x: x.get('name', '').lower() if isinstance(x, dict) else '')
        return jsonify(barangay_list)

    except Exception as e:
        logger.error(f"Error fetching barangays for {city_code}: {str(e)}")
        return jsonify({'error': 'Failed to fetch barangays'}), 500


@bp.route('/api/get-services/<category>')
@login_required
def get_services_for_category(category):
    """Fetch available services for merchant business category"""
    from app.utils.merchant_service_config import CATEGORY_TO_SERVICES
    
    # Look up services for selected business category from configuration
    category_services = CATEGORY_TO_SERVICES.get(category, [])
    
    if not category_services:
        return jsonify({'services': []}) 
    
    return jsonify({
        'category': category,
        'services': category_services
    })

@bp.route('/api/geocode', methods=['POST'])
@login_required
def geocode():
    """Convert address to geographic coordinates using Nominatim API"""
    data = request.get_json()
    address = data.get('address')
    city = data.get('city')
    province = data.get('province')
    
    if not address:
        return jsonify({'error': 'Address required'}), 400 
    
    try:
        # Construct complete address and query Nominatim geocoding service
        full_address = f"{address}, {city}, {province}, Philippines"
        
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': full_address,
                'format': 'json',
                'limit': 1
            },
            headers={'User-Agent': 'PetsonaApp/1.0'},
            timeout=5
        )
        
        if response.status_code == 200 and response.json():
            pass
            result = response.json()[0]
            return jsonify({
                'latitude': float(result['lat']),
                'longitude': float(result['lon']),
                'display_name': result['display_name']
            })
    except Exception as e:
        logger.error(f"Error geocoding address: {str(e)}")
        pass
    
    return jsonify({'error': 'Failed to geocode address'}), 500

@bp.route('/api/reverse-geocode', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
def reverse_geocode():
    """Reverse geocode coordinates to get address"""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        # Get JSON data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing JSON data'}), 400
        
        # Extract coordinates (accept both 'lon' and 'lng' for flexibility)
        lat = data.get('lat')
        lon = data.get('lon') or data.get('lng')
        
        if lat is None or lon is None:
            return jsonify({'error': 'Coordinates required'}), 400
            logger.error(f"Missing coordinates - lat: {lat}, lon: {lon}")
            return jsonify({'error': 'Latitude and longitude are required'}), 400
        
        # Validate and convert coordinates to float type
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid coordinate format - lat: {lat}, lon: {lon}, error: {str(e)}")
            return jsonify({'error': 'Latitude and longitude must be numbers'}), 400
        
        # Query Nominatim reverse geocoding API with coordinate details
        response = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={
                'format': 'json',
                'lat': lat,
                'lon': lon,
                'zoom': 18,
                'addressdetails': 1
            },
            headers={'User-Agent': 'PetSona-App'},
            timeout=5
        )
        
        if response.status_code == 200:
            pass
            geocode_data = response.json()
            
            # Use the full display_name (works like Google Maps)
            # This includes street, barangay, city, province, etc.
            full_address = geocode_data.get('display_name', 'Location selected on map')
            
            return jsonify({
                'success': True,
                'address': full_address,
                'display_name': full_address,
                'address_components': geocode_data.get('address', {})
            })
        else:
            logger.error(f"Nominatim error: {response.status_code}")
            return jsonify({
                'success': False,
                'address': 'Location selected on map',
                'error': 'Reverse geocoding service error'
            }), 200
    
    except requests.exceptions.Timeout:
        logger.error("Reverse geocoding timeout")
        return jsonify({
            'success': False,
            'address': 'Location selected on map',
            'error': 'Geocoding service timeout'
        }), 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Reverse geocoding request error: {str(e)}")
        return jsonify({
            'success': False,
            'address': 'Location selected on map',
            'error': str(e)
        }), 200
    except Exception as e:
        logger.error(f'Reverse geocoding error: {str(e)}')
        return jsonify({
            'success': False,
            'address': 'Location selected on map',
            'error': str(e)
        }), 200
    except Exception as e:
        logger.error(f"Error reverse geocoding: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to reverse geocode', 'details': str(e)}), 500

@bp.route('/booking/<int:merchant_id>')
@login_required
@user_required
def booking(merchant_id):
    """Display booking form for customer to book appointment at merchant"""
    merchant = Merchant.query.filter_by(id=merchant_id).first()
    
    if not merchant:
        flash('Store not found.', 'danger')
        return redirect(url_for('user.nearby_services'))
    
    # Placeholder for ratings/reviews (not yet implemented)
    store_rating = 0
    total_reviews = 0
    
    return render_template('merchant/booking.html', 
                         merchant=merchant,
                         store_rating=store_rating,
                         total_reviews=total_reviews)

@bp.route('/booking/<int:merchant_id>/create', methods=['POST'])
@login_required
def create_booking(merchant_id):
    """Create booking from form submission with customer details and pet info"""
    try:
        merchant = Merchant.query.filter_by(id=merchant_id).first()
        
        if not merchant:
            return jsonify({'error': 'Merchant not found'}), 404
            flash('Store not found.', 'danger')
            return redirect(url_for('user.nearby_services'))
        
        # Extract appointment date and time from form
        appointment_date_str = request.form.get('check_in_date')
        appointment_time = request.form.get('check_in_time', '09:00')
        
        # Validate appointment date is provided
        if not appointment_date_str:
            return jsonify({'error': 'Date required'}), 400
            flash('Please select an appointment date.', 'warning')
            return redirect(url_for('merchant.booking', merchant_id=merchant_id))
        
        # Parse appointment date
        try:
            appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d')
        except Exception as e:
            logger.error(f"Date parsing error: {str(e)}")
            flash('Invalid date format.', 'danger')
            return redirect(url_for('merchant.booking', merchant_id=merchant_id))
        
        # Extract multi-pet booking data from form (pets[index][field] format)
        pets_data = []
        pet_index = 0
        while True:
            pass
            pet_name = request.form.get(f'pets[{pet_index}][pet_name]')
            if not pet_name:
                break
            
            pets_data.append({
                'pet_name': pet_name,
                'pet_species': request.form.get(f'pets[{pet_index}][pet_species]', ''),
                'pet_breed': request.form.get(f'pets[{pet_index}][pet_breed]', ''),
                'pet_age': request.form.get(f'pets[{pet_index}][pet_age]', ''),
                'pet_weight': request.form.get(f'pets[{pet_index}][pet_weight]', ''),
                'pet_medical_conditions': request.form.get(f'pets[{pet_index}][pet_medical_conditions]', '')
            })
            pet_index += 1
        
        if not pets_data:
            flash('Please add at least one pet.', 'warning')
            return redirect(url_for('merchant.booking', merchant_id=merchant_id))
        
        total_pets = len(pets_data)
        
        # Parse pre-calculated price breakdown from form JSON
        try:
            pass
            price_breakdown_str = request.form.get('price_breakdown', '{}')
            price_breakdown = json.loads(price_breakdown_str) if price_breakdown_str else {}
        except:
            price_breakdown = {}
        
        # Calculate total amount from price breakdown
        total_amount = 0
        for size_data in price_breakdown.values():
            if isinstance(size_data, dict) and 'price' in size_data:
                total_amount += float(size_data.get('price', 0))
        
        # Validate booking amount is positive
        if total_amount <= 0:
            return jsonify({'error': 'Invalid booking amount'}), 400
            flash('Invalid pricing information. Please refresh and try again.', 'danger')
            return redirect(url_for('merchant.booking', merchant_id=merchant_id))
        
        # Get customer information
        customer_name = request.form.get('customer_name', f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email)
        customer_email = request.form.get('customer_email', current_user.email)
        customer_phone = request.form.get('customer_phone', '')
        
        # Get special requests
        pet_special_notes = request.form.get('pet_special_notes', '')
        special_requests = request.form.get('special_requests', '')
        
        # Generate booking number and confirmation code
        import random
        import string
        booking_number = f"BK-{datetime.now().year}-{random.randint(100000, 999999)}"
        confirmation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Ensure total_amount is a proper float
        total_amount = float(total_amount) if total_amount else 0.0
        
        # Persist booking record to database
        booking = Booking(
            user_id=current_user.id,
            merchant_id=merchant_id,
            booking_number=booking_number,
            confirmation_code=confirmation_code,
            status='pending',
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            pets_booked=pets_data,
            total_pets=total_pets,
            pet_special_notes=pet_special_notes,
            # Appointment-based fields
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            service_type=request.form.get('service_type', 'Per Night'),
            business_category=merchant.business_category,
            # Pricing fields
            price_breakdown=price_breakdown,
            total_amount=total_amount,
            # Notes
            special_requests=special_requests,
        )
        
        db.session.add(booking)
        db.session.commit()
        
        # Log the booking creation
        audit_log = AuditLog(
            user_id=current_user.id,
            action='booking_created',
            resource_type='Booking',
            resource_id=booking.id,
            details=f'Booking {booking.booking_number} created for merchant {merchant.business_name}',
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        # Send notification to merchant about new booking
        if merchant.user_id:
            NotificationManager.notify_merchant_new_booking(
                user_id=merchant.user_id,
                booking_number=booking.booking_number,
                customer_name=booking.customer_name,
                appointment_date=booking.appointment_date.strftime('%B %d, %Y') if booking.appointment_date else 'N/A',
                related_booking_id=booking.id,
                from_user_id=current_user.id
            )
        
        flash('Booking created successfully! The merchant will review your request.', 'success')
        return redirect(url_for('merchant.booking_confirmation', booking_id=booking.id))
        
    except Exception as e:
        logger.error(f"Error creating booking: {str(e)}", exc_info=True)
        flash('An error occurred while creating your booking. Please try again.', 'danger')
        return redirect(url_for('merchant.booking', merchant_id=merchant_id))

@bp.route('/bookings-list')
@login_required
@merchant_required
def bookings_list():
    """Display merchant booking list with status filtering and statistics"""
    if current_user.role != 'merchant':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    
    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    
    if not merchant:
        flash('Store information not found.', 'warning')
        return redirect(url_for('merchant.apply'))
    
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '', type=str)
    
    # Query all non-deleted bookings for this merchant
    query = Booking.query.filter(
        Booking.merchant_id == merchant.id,
        Booking.deleted_at.is_(None)
    )
    
    # Calculate booking counts by status for dashboard metrics
    all_bookings = Booking.query.filter(
        Booking.merchant_id == merchant.id,
        Booking.deleted_at.is_(None)
    )
    total_bookings = all_bookings.count()
    total_pending = all_bookings.filter(Booking.status == 'pending').count()
    total_confirmed = all_bookings.filter(Booking.status == 'confirmed').count()
    total_completed = all_bookings.filter(Booking.status == 'completed').count()
    total_cancelled = all_bookings.filter(Booking.status == 'cancelled').count()
    total_rejected = all_bookings.filter(Booking.status == 'rejected').count()
    total_no_show = all_bookings.filter(Booking.status == 'no-show').count()
    
    # Apply status filter if specified
    if status_filter and status_filter != '':
        query = query.filter(Booking.status == status_filter)
    
    # Sort by creation date (newest first)
    query = query.order_by(Booking.created_at.desc())
    
    # Paginate results (10 bookings per page)
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    
    # Retrieve distinct booking statuses for filter dropdown
    statuses = db.session.query(Booking.status.distinct()).filter(
        Booking.merchant_id == merchant.id,
        Booking.deleted_at.is_(None)
    ).all()
    statuses = [s[0] for s in statuses if s[0]]
    
    return render_template(
        'merchant/bookings_list.html',
        bookings=pagination,
        merchant=merchant,
        selected_status=status_filter,
        statuses=statuses,
        total_bookings=total_bookings,
        total_pending=total_pending,
        total_confirmed=total_confirmed,
        total_completed=total_completed,
        total_cancelled=total_cancelled,
        total_rejected=total_rejected,
        total_no_show=total_no_show
    )

@bp.route('/bookings/<int:booking_id>/confirm', methods=['POST'])
@login_required
@merchant_required
def confirm_booking(booking_id):
    """Confirm pending booking and notify customer"""
    if current_user.role != 'merchant':
        if request.is_json or request.args.get('api'):
            return jsonify({'success': False, 'message': 'Access denied'}), 403
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    
    booking = Booking.query.get(booking_id)
    
    if not booking:
        if request.is_json or request.args.get('api'):
            return jsonify({'success': False, 'error': 'Booking not found'}), 404
        flash('Booking not found.', 'danger')
        return redirect(url_for('merchant.bookings_list'))
    
    # Check if merchant owns this booking
    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    if booking.merchant_id != merchant.id:
        if request.is_json or request.args.get('api'):
            return jsonify({'success': False, 'error': 'Unauthorized access'}), 403
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('merchant.bookings_list'))
    
    try:
        # Update booking to confirmed status
        booking.status = 'confirmed'
        booking.merchant_confirmed = True
        booking.merchant_confirmed_at = get_ph_datetime()
        db.session.commit()
        
        # Record confirmation action in audit log
        audit_log = AuditLog(
            event='booking_confirmed',
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=get_ph_datetime()
        )
        audit_log.set_details({'booking_id': booking.id, 'booking_number': booking.booking_number})
        db.session.add(audit_log)
        db.session.commit()
        
        # Send confirmation notification to customer
        NotificationManager.notify_booking_confirmed(
            user_id=booking.user_id,
            booking_number=booking.booking_number,
            merchant_name=merchant.business_name,
            related_booking_id=booking.id,
            from_user_id=current_user.id  # Merchant confirming the booking
        )
        
        # Return JSON response if AJAX call
        if request.is_json or request.args.get('api'):
            return jsonify({'success': True, 'message': 'Booking confirmed successfully'}), 200
        
        flash('Booking confirmed successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error confirming booking: {str(e)}")
        if request.is_json or request.args.get('api'):
            return jsonify({'success': False, 'message': 'Error confirming booking'}), 500
            return jsonify({'success': False, 'error': str(e)}), 500
        flash('Error confirming booking.', 'danger')
    
    return redirect(url_for('merchant.bookings_list'))

@bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
@merchant_required
def reject_booking(booking_id):
    """Reject/cancel booking and notify customer"""
    if current_user.role != 'merchant':
        if request.is_json or request.args.get('api'):
            return jsonify({'success': False, 'message': 'Access denied'}), 403
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    
    booking = Booking.query.get(booking_id)
    
    if not booking:
        if request.is_json or request.args.get('api'):
            return jsonify({'success': False, 'error': 'Booking not found'}), 404
        flash('Booking not found.', 'danger')
        return redirect(url_for('merchant.bookings_list'))
    
    # Check if merchant owns this booking
    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    if booking.merchant_id != merchant.id:
        if request.is_json or request.args.get('api'):
            return jsonify({'success': False, 'error': 'Unauthorized access'}), 403
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('merchant.bookings_list'))
    
    try:
        booking.status = 'rejected'
        if hasattr(booking, 'cancellation_date'):
            booking.cancellation_date = get_ph_datetime()
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            event='booking_rejected',
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=get_ph_datetime()
        )
        audit_log.set_details({'booking_id': booking.id, 'booking_number': booking.booking_number})
        db.session.add(audit_log)
        db.session.commit()
        
        # Send notification to customer
        NotificationManager.notify_booking_rejected(
            user_id=booking.user_id,
            booking_number=booking.booking_number,
            merchant_name=merchant.business_name,
            related_booking_id=booking.id,
            from_user_id=current_user.id
        )
        
        # Return JSON response if AJAX call
        if request.is_json or request.args.get('api'):
            return jsonify({'success': True, 'message': 'Booking rejected successfully'}), 200
        
        flash('Booking rejected successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error rejecting booking: {str(e)}")
        if request.is_json or request.args.get('api'):
            return jsonify({'success': False, 'message': 'Error rejecting booking'}), 500
            return jsonify({'success': False, 'error': str(e)}), 500
        flash('Error rejecting booking.', 'danger')
    
    return redirect(url_for('merchant.bookings_list'))


# ========== CUSTOMER BOOKING ROUTES ==========

@bp.route('/book/<int:merchant_id>', methods=['GET'])
@login_required
@user_required
def book_now(merchant_id):
    """Display customer booking form for merchant"""
    merchant = Merchant.query.filter_by(id=merchant_id).first()
    
    if not merchant:
        flash('Merchant not found.', 'danger')
        return redirect(url_for('user.nearby_services'))
    
    return render_template('merchant/booking.html', 
                         merchant=merchant)


@bp.route('/book/<int:merchant_id>', methods=['POST'])
@login_required
@user_required
def customer_create_booking(merchant_id):
    """Process customer booking submission with pet and appointment details"""
    merchant = Merchant.query.filter_by(id=merchant_id).first()
    
    if not merchant:
        flash('Merchant not found.', 'danger')
        return redirect(url_for('user.nearby_services'))
    
    try:
        import uuid
        
        # Extract form data: customer info and appointment details
        customer_name = request.form.get('customer_name', '').strip()
        customer_email = request.form.get('customer_email', '').strip()
        customer_phone = request.form.get('customer_phone', '').strip()
        appointment_date_str = request.form.get('check_in_date')
        appointment_time = request.form.get('check_in_time')
        
        # Validate required customer fields
        if not customer_phone:
            return jsonify({'error': 'Phone required'}), 400
            flash('Phone number is required.', 'danger')
            return redirect(url_for('merchant.book_now', merchant_id=merchant_id))
        
        # Validate appointment date and time
        if not appointment_date_str or not appointment_time:
            return jsonify({'error': 'Date and time required'}), 400
            flash('Appointment date and time are required.', 'danger')
            return redirect(url_for('merchant.book_now', merchant_id=merchant_id))
        
        # Parse appointment date
        try:
            appointment_date = datetime.strptime(f"{appointment_date_str} {appointment_time}", "%Y-%m-%d %H:%M")
        except (ValueError, TypeError) as e:
            logger.error(f"Date parsing error: {str(e)}")
            flash('Invalid date or time format.', 'danger')
            return redirect(url_for('merchant.book_now', merchant_id=merchant_id))
        
        # Collect pet data from multi-pet form fields
        pets_data = []
        pet_index = 0
        while True:
            pass
            pet_name_key = f'pets[{pet_index}][pet_name]'
            pet_species_key = f'pets[{pet_index}][pet_species]'
            
            if pet_name_key not in request.form or pet_species_key not in request.form:
                break
                
            pet_name = request.form.get(pet_name_key, '').strip()
            pet_species = request.form.get(pet_species_key, '').strip()
            
            if pet_name and pet_species:
                pet_weight_str = request.form.get(f'pets[{pet_index}][pet_weight]', '0')
                try:
                    pet_weight = float(pet_weight_str) if pet_weight_str else 0
                except (ValueError, TypeError):
                    pet_weight = 0
                
                pets_data.append({
                    'pet_name': pet_name,
                    'species': pet_species,
                    'breed': request.form.get(f'pets[{pet_index}][pet_breed]', '').strip(),
                    'age': request.form.get(f'pets[{pet_index}][pet_age]', '').strip(),
                    'weight': pet_weight,
                    'medical_conditions': request.form.get(f'pets[{pet_index}][pet_medical_conditions]', '').strip(),
                })
            pet_index += 1
        
        # Ensure booking includes at least one pet
        if not pets_data:
            return jsonify({'error': 'At least one pet required'}), 400
            flash('Please add at least one pet to your booking.', 'danger')
            return redirect(url_for('merchant.book_now', merchant_id=merchant_id))
        
        total_pets = len(pets_data)
        
        # Parse price breakdown JSON pre-calculated by frontend
        price_breakdown_str = request.form.get('price_breakdown', '{}')
        try:
            pass
            import json
            price_breakdown = json.loads(price_breakdown_str)
            price_breakdown = json.loads(price_breakdown_str)
        except (json.JSONDecodeError, ValueError):
            price_breakdown = {}
            price_breakdown = {}
        
        # Sum total booking amount from price breakdown
        total_amount = 0.0
        if price_breakdown:
            pass
            for size_data in price_breakdown.values():
                if isinstance(size_data, dict) and 'price' in size_data:
                    total_amount += float(size_data['price'])
        
        # Fallback calculation if price breakdown unavailable
        if total_amount == 0 or not price_breakdown:
            pass
            service_pricing = merchant.get_service_pricing() or {}
            
            # Get first service type and prices
            service_type = None
            business_category = merchant.business_category or 'Pet Booking'
            size_prices = {}
            
            # Extract pricing by size from merchant's service pricing
            if service_pricing:
                for category, pricing_data in service_pricing.items():
                    if isinstance(pricing_data, dict):
                        for duration, duration_prices in pricing_data.items():
                            if isinstance(duration_prices, dict):
                                size_prices = {k.lower(): float(v) for k, v in duration_prices.items()}
                                service_type = duration
                                break
                    if size_prices:
                        break
            
            # Default sizes if not found
            if not size_prices:
                size_prices = {'small': 500, 'medium': 750, 'large': 1000, 'xlarge': 1500}
                service_type = 'Per Appointment'
            
            # Calculate price breakdown by pet size
            price_breakdown = {}
            for pet in pets_data:
                weight = pet.get('weight', 0)
                # Determine size category
                if weight < 5:
                    size = 'small'
                elif weight < 15:
                    size = 'medium'
                elif weight < 30:
                    size = 'large'
                else:
                    size = 'xlarge'
                
                price = float(size_prices.get(size, 500))
                
                if size not in price_breakdown:
                    price_breakdown[size] = {'count': 0, 'price': 0}
                
                price_breakdown[size]['count'] += 1
                price_breakdown[size]['price'] += price
                total_amount += price
        else:
            service_type = 'Per Appointment'
        
        pet_special_notes = request.form.get('pet_special_notes', '').strip()
        special_requests = request.form.get('special_requests', '').strip()
        
        # Generate unique booking number and confirmation code
        booking_number = f"BK-{datetime.now().strftime('%Y')}-{int(datetime.now().timestamp()) % 100000:05d}"
        confirmation_code = str(uuid.uuid4())[:12].upper()
        
        # Persist booking to database
        booking = Booking(
            user_id=current_user.id,
            merchant_id=merchant.id,
            booking_number=booking_number,
            confirmation_code=confirmation_code,
            status='pending',
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            pets_booked=pets_data,
            total_pets=total_pets,
            pet_special_notes=pet_special_notes,
            special_requests=special_requests,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            price_breakdown=price_breakdown,
            total_amount=total_amount,
            service_type=service_type,
            business_category=merchant.business_category,
        )
        
        db.session.add(booking)
        db.session.commit()
        
        # Record booking creation in audit log
        audit_log = AuditLog(
            event='booking_created',
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=get_ph_datetime()
        )
        audit_log.set_details({
            'booking_id': booking.id,
            'booking_number': booking_number,
            'merchant_id': merchant.id,
            'total_amount': total_amount,
            'total_pets': total_pets,
        })
        db.session.add(audit_log)
        db.session.commit()
        
        # Notify merchant about new booking request
        if merchant.user_id:
            pass
            NotificationManager.notify_merchant_new_booking(
                user_id=merchant.user_id,
                booking_number=booking_number,
                customer_name=customer_name,
                appointment_date=appointment_date.strftime('%B %d, %Y') if appointment_date else 'N/A',
                related_booking_id=booking.id,
                from_user_id=current_user.id
            )
        
        flash('Booking created successfully! Please wait for merchant confirmation.', 'success')
        return redirect(url_for('user.my_bookings'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating booking: {str(e)}")
        flash(f'Error creating booking: {str(e)}', 'danger')
        return redirect(url_for('merchant.book_now', merchant_id=merchant_id))


@bp.route('/bookings/<int:booking_id>/complete', methods=['POST'])
@login_required
@merchant_required
def mark_booking_complete(booking_id):
    """Mark booking as completed and notify customer"""
    booking = Booking.query.filter_by(id=booking_id).first()
    
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('merchant.bookings_list'))
    
    # Verify merchant ownership
    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    if not merchant or booking.merchant_id != merchant.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('merchant.bookings_list'))
    
    try:
        # Update booking status to completed
        booking.status = 'completed'
        db.session.commit()
        
        # Record completion in audit log
        audit_log = AuditLog(
            event='booking_completed',
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=get_ph_datetime()
        )
        audit_log.set_details({'booking_id': booking.id, 'booking_number': booking.booking_number})
        db.session.add(audit_log)
        db.session.commit()
        
        # Send completion notification to customer
        NotificationManager.notify_booking_completed(
            user_id=booking.user_id,
            booking_number=booking.booking_number,
            merchant_name=merchant.business_name if merchant else 'Merchant',
            related_booking_id=booking.id,
            from_user_id=current_user.id
        )
        
        flash('Booking marked as completed', 'success')
        return redirect(url_for('merchant.bookings_list'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('merchant.bookings_list'))


@bp.route('/bookings/<int:booking_id>/no-show', methods=['POST'])
@login_required
@merchant_required
def mark_booking_no_show(booking_id):
    """Mark booking as no-show and notify customer"""
    booking = Booking.query.filter_by(id=booking_id).first()
    
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('merchant.bookings_list'))
    
    # Verify merchant ownership
    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    if not merchant or booking.merchant_id != merchant.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('merchant.bookings_list'))
    
    try:
        # Update booking status to no-show
        booking.status = 'no-show'
        db.session.commit()
        
        # Record no-show in audit log
        audit_log = AuditLog(
            event='booking_no_show',
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=get_ph_datetime()
        )
        audit_log.set_details({'booking_id': booking.id, 'booking_number': booking.booking_number})
        db.session.add(audit_log)
        db.session.commit()
        
        # Send no-show notification to customer
        NotificationManager.notify_booking_no_show(
            user_id=booking.user_id,
            booking_number=booking.booking_number,
            merchant_name=merchant.business_name if merchant else 'Merchant',
            related_booking_id=booking.id,
            from_user_id=current_user.id
        )
        
        flash('Booking marked as no-show', 'success')
        return redirect(url_for('merchant.bookings_list'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('merchant.bookings_list'))

@bp.route('/api/merchant/<int:merchant_id>/services', methods=['GET'])
@login_required
def get_merchant_services(merchant_id):
    """Fetch merchant services, pricing, and accepted pet types via API"""
    merchant = Merchant.query.filter_by(id=merchant_id).first()
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404 
    services = merchant.services_offered or []
    pricing = merchant.get_service_pricing() or {}
    pets_accepted = merchant.get_pets_list() or []
    
    return jsonify({
        'services': services,
        'pricing': pricing,
        'pets_accepted': pets_accepted,
    })




