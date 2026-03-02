import os
import json
import requests
import pytz
from datetime import datetime, time as dt_time
from werkzeug.utils import secure_filename
from flask import render_template, flash, redirect, request, url_for, jsonify
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]
from app.merchant import bp
from app.decorators import merchant_required
from app.models.breed import Breed
from app.models.species import Species
from app.models.merchant import Merchant
from app.models.booking import Booking
from app.extensions import db, csrf
from app.merchant.forms import MerchantApplicationForm, MerchantStoreUpdateForm
from app.models.audit_log import AuditLog
from sqlalchemy import func, and_
from app.utils.notification_manager import NotificationManager
import logging

logger = logging.getLogger(__name__)

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_province_name(province_code):
    """Convert province code to name"""
    if not province_code:
        return None
    try:
        response = requests.get(f'https://psgc.gitlab.io/api/provinces/{province_code}/', timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('name', province_code)
    except:
        pass
    return province_code

def get_city_name(city_code):
    """Convert city code to name"""
    if not city_code:
        return None
    try:
        # Try city endpoint first
        response = requests.get(f'https://psgc.gitlab.io/api/cities/{city_code}/', timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('name', city_code)
        
        # Try municipality endpoint
        response = requests.get(f'https://psgc.gitlab.io/api/municipalities/{city_code}/', timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('name', city_code)
    except:
        pass
    return city_code

def get_barangay_name(barangay_code):
    """Convert barangay code to name"""
    if not barangay_code:
        return None
    try:
        response = requests.get(f'https://psgc.gitlab.io/api/barangays/{barangay_code}/', timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('name', barangay_code)
    except:
        pass
    return barangay_code

@bp.route('/dashboard')
@login_required
@merchant_required
def dashboard():
    if current_user.role != 'merchant':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))

    # Check if merchant has completed application
    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    
    # Get bookings statistics
    total_bookings = Booking.query.filter_by(merchant_id=merchant.id).count()
    total_pending = Booking.query.filter_by(merchant_id=merchant.id, status='pending').count()
    total_confirmed = Booking.query.filter_by(merchant_id=merchant.id, status='confirmed').count()
    total_completed = Booking.query.filter_by(merchant_id=merchant.id, status='completed').count()
    total_rejected = Booking.query.filter_by(merchant_id=merchant.id, status='rejected').count()
    total_no_show = Booking.query.filter_by(merchant_id=merchant.id, status='no-show').count()
    
    # Get recent bookings (latest 5)
    recent_bookings = Booking.query.filter_by(merchant_id=merchant.id).order_by(Booking.created_at.desc()).limit(5).all()
    
    # Calculate completion rate (completed / total) * 100
    completion_rate = round((total_completed / total_bookings * 100) if total_bookings > 0 else 0)
    
    # Get top species by vote count
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
    """Display merchant store information with real statistics from bookings"""
    if current_user.role != 'merchant':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))

    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    
    if not merchant:
        flash('Store information not found. Please complete your merchant application first.', 'warning')
        return redirect(url_for('merchant.apply'))
    
    # ========== REAL DATA QUERIES FROM BOOKING MODEL ==========
    
    # 1. Total Bookings Count
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
    store_rating = 0
    
    # 7. Total Reviews Count (Not yet implemented in simplified booking system)
    total_reviews = 0
    
    # 8. Completion Rate (%)
    completion_rate = 0
    if total_bookings > 0:
        completion_rate = round((completed_bookings / total_bookings) * 100, 1)
    
    # 9. Average Response Time (hours) - MySQL compatible
    # Calculate time from booking created to merchant_confirmed_at
    avg_response_hours = 24  # Default
    try:
        # MySQL-compatible way to calculate time difference in seconds, then convert to hours
        from sqlalchemy import literal_column
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
        logger.error(f"Error calculating response time: {e}")
        avg_response_hours = 24  # Fallback to default
    
    # Format response time
    if avg_response_hours < 1:
        avg_response_time = f"{int(avg_response_hours * 60)}m"
    elif avg_response_hours < 24:
        avg_response_time = f"{int(avg_response_hours)}h"
    else:
        avg_response_time = f"{round(avg_response_hours / 24, 1)}d"
    
    # 10. Total Revenue (sum of all completed booking amounts)
    total_revenue = db.session.query(func.sum(Booking.total_amount)).filter(
        Booking.merchant_id == merchant.id,
        Booking.status == 'completed',
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    total_revenue = float(total_revenue)
    
    # 11. Merchant Earnings (after commission)
    merchant_earnings = db.session.query(func.sum(Booking.total_amount)).filter(
        Booking.merchant_id == merchant.id,
        Booking.status == 'completed',
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    merchant_earnings = float(merchant_earnings)
    
    # 12. Platform Fee Collected
    platform_fees = total_revenue - merchant_earnings if total_revenue > 0 else 0
    
    # 13. Bookings this month (30 days)
    from datetime import timedelta
    thirty_days_ago = get_ph_datetime() - timedelta(days=30)
    bookings_this_month = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.created_at >= thirty_days_ago,
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    # 14. No-show Rate (Booking model doesn't currently track no-shows)
    no_show_count = 0  # TODO: Add no_show field to Booking model when feature is implemented
    no_show_rate = 0
    
    # 15. Recent bookings (last 5 for dashboard preview)
    recent_bookings = db.session.query(Booking).filter(
        Booking.merchant_id == merchant.id,
        Booking.deleted_at.is_(None)
    ).order_by(Booking.created_at.desc()).limit(5).all()
    
    # 16. Month-over-month growth
    sixty_days_ago = get_ph_datetime() - timedelta(days=60)
    prev_month_bookings = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.created_at >= sixty_days_ago,
        Booking.created_at < thirty_days_ago,
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    month_growth = 0
    if prev_month_bookings > 0:
        month_growth = round(((bookings_this_month - prev_month_bookings) / prev_month_bookings) * 100, 1)
    else:
        month_growth = 100 if bookings_this_month > 0 else 0
    
    # Determine growth direction
    growth_direction = "up" if month_growth >= 0 else "down"

    logo_path = merchant.logo_path
    logo_url = url_for('static', filename=f'uploads/merchants/{merchant.id}/{logo_path}') if logo_path else None
    
    # Prepare statistics dictionary
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
            logger.warning(f"User {current_user.id} has no merchant record")
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
            logger.warning(f"Logo upload: file too large ({file_size} bytes) from user {current_user.id}")
            return jsonify({'success': False, 'message': 'File too large. Max 5MB'}), 400
        
        logger.info(f"Logo upload: file validated ({file.filename}, {file_size} bytes)")
        
        # Create user upload directory if it doesn't exist (using user_id not merchant_id)
        upload_dir = os.path.join('app/static/uploads/merchants', str(current_user.id))
        os.makedirs(upload_dir, exist_ok=True)
        logger.info(f"Logo upload: directory ready at {upload_dir}")
        
        # Generate unique filename
        timestamp = int(datetime.utcnow().timestamp())
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"logo_{timestamp}.{file_extension}")
        
        # Save file
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        logger.info(f"Logo upload: file saved to {filepath}")
        
        # Delete old logo if exists
        if merchant.logo_path:
            # Extract just the filename from the stored path
            old_filename = merchant.logo_path.split('/')[-1] if '/' in merchant.logo_path else merchant.logo_path
            old_path = os.path.join('app/static/uploads/merchants', str(current_user.id), old_filename)
            try:
                if os.path.exists(old_path):
                    os.remove(old_path)
                    logger.info(f"Logo upload: old logo deleted from {old_path}")
            except Exception as e:
                logger.error(f"Error deleting old logo: {e}")
        
        # Update merchant record with full relative path (using user_id)
        merchant.logo_path = f"merchants/{current_user.id}/{filename}"
        merchant.updated_at = get_ph_datetime()
        db.session.add(merchant)
        db.session.commit()
        logger.info(f"Logo upload: merchant record updated for merchant {merchant.id}")
        
        # Log the action
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
        logger.info(f"Logo upload: audit log created")
        
        # Get fresh logo URL
        logo_url = url_for('static', filename=f'uploads/merchants/{merchant.id}/{filename}')
        logger.info(f"Logo upload: success, URL = {logo_url}")
        
        return jsonify({
            'success': True,
            'message': 'Logo uploaded successfully',
            'logo_url': logo_url
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading logo: {str(e)}", exc_info=True)
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({'success': False, 'message': f'Upload failed: {str(e)}'}), 500


@bp.route('/store/edit', methods=['GET', 'POST'])
@login_required
@merchant_required
def store_edit():
    """Edit merchant store information"""
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
            # Custom validation: Check operating schedule requirements
            if not form.is_24h.data:
                # Manual schedule mode - hours and days are required
                if not form.opening_time.data or not form.closing_time.data:
                    flash('Opening and closing times are required when not using 24/7 mode.', 'danger')
                    return render_template('merchant/store_edit.html', form=form, merchant=merchant)
                
                if not form.operating_days.data or len(form.operating_days.data) == 0:
                    flash('Please select at least one operating day when not using 24/7 mode.', 'danger')
                    return render_template('merchant/store_edit.html', form=form, merchant=merchant)
            
            # Store previous values for audit log
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
            
            # Update merchant information - SECTION 1: BUSINESS INFO
            merchant.business_name = form.business_name.data
            merchant.business_category = form.business_category.data
            merchant.business_description = form.business_description.data
            
            
            # Handle logo upload if provided
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
                                logger.error(f"Error deleting old logo: {e}")
                        
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
                    # Validate file size
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size <= MAX_FILE_SIZE:
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
                            except Exception as e:
                                logger.error(f"Error deleting old government ID: {e}")
                        
                        # Generate unique filename and save
                        timestamp = datetime.utcnow().timestamp()
                        file_extension = file.filename.rsplit('.', 1)[1].lower()
                        filename = secure_filename(f"gov_id_{timestamp}.{file_extension}")
                        filepath = os.path.join(upload_dir, filename)
                        file.save(filepath)
                        
                        # Update merchant with full path
                        merchant.government_id_path = f"merchants/{current_user.id}/{filename}"
                        logger.info(f"Government ID updated for merchant {merchant.id}: {merchant.government_id_path}")
            
            # Handle business permit upload
            if request.files.get('business_permit') and request.files['business_permit'].filename:
                file = request.files['business_permit']
                if file and allowed_file(file.filename):
                    # Validate file size
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size <= MAX_FILE_SIZE:
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
                            except Exception as e:
                                logger.error(f"Error deleting old business permit: {e}")
                        
                        # Generate unique filename and save
                        timestamp = datetime.utcnow().timestamp()
                        file_extension = file.filename.rsplit('.', 1)[1].lower()
                        filename = secure_filename(f"permit_{timestamp}.{file_extension}")
                        filepath = os.path.join(upload_dir, filename)
                        file.save(filepath)
                        
                        # Update merchant with full path
                        merchant.business_permit_path = f"merchants/{current_user.id}/{filename}"
                        logger.info(f"Business permit updated for merchant {merchant.id}: {merchant.business_permit_path}")
            
            # Handle facility photos upload
            facility_photos = []
            if request.files.getlist('facility_photos'):
                files = request.files.getlist('facility_photos')
                upload_dir = os.path.join('app/static/uploads/merchants', str(current_user.id))
                os.makedirs(upload_dir, exist_ok=True)
                
                for idx, file in enumerate(files):
                    if file and file.filename and allowed_file(file.filename):
                        # Validate file size
                        file.seek(0, os.SEEK_END)
                        file_size = file.tell()
                        file.seek(0)
                        
                        if file_size <= MAX_FILE_SIZE:
                            # Generate unique filename and save
                            timestamp = datetime.utcnow().timestamp()
                            file_extension = file.filename.rsplit('.', 1)[1].lower()
                            filename = secure_filename(f"facility_{idx}_{timestamp}.{file_extension}")
                            filepath = os.path.join(upload_dir, filename)
                            file.save(filepath)
                            facility_photos.append(f"merchants/{current_user.id}/{filename}")
                
                if len(facility_photos) > 0:
                    # Update facility photos (allow editing existing ones)
                    merchant.facility_photos_paths = facility_photos
                    logger.info(f"Facility photos updated for merchant {merchant.id}: {len(facility_photos)} photos")
            
            # SECTION 2: CONTACT PERSON
            merchant.owner_manager_name = form.owner_manager_name.data
            merchant.contact_email = form.contact_email.data
            merchant.contact_phone = form.contact_phone.data
            
            # SECTION 3: LOCATION
            # Convert codes to human-readable names
            province_code = form.province.data
            city_code = form.city.data
            barangay_code = form.barangay.data
            
            # Get human-readable names from API
            province_name = get_province_name(province_code)
            city_name = get_city_name(city_code)
            barangay_name = get_barangay_name(barangay_code)
            
            merchant.full_address = form.full_address.data
            merchant.city = city_name
            merchant.province = province_name
            merchant.barangay = barangay_name
            merchant.postal_code = form.postal_code.data or ''
            merchant.google_maps_link = form.google_maps_link.data
            
            # Update coordinates from hidden fields
            if request.form.get('latitude'):
                merchant.latitude = float(request.form.get('latitude'))
            if request.form.get('longitude'):
                merchant.longitude = float(request.form.get('longitude'))
            
            # SECTION 4: SERVICES OFFERED
            merchant.services_offered = form.services_offered.data if form.services_offered.data else []
            
            # SECTION 5: PETS ACCEPTED
            merchant.pets_accepted = form.pets_accepted.data if form.pets_accepted.data else []
            
            # Parse service pricing JSON from form
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
        # Pre-fill form with existing data
        form.business_name.data = merchant.business_name
        form.business_category.data = merchant.business_category
        form.business_description.data = merchant.business_description
        form.owner_manager_name.data = merchant.owner_manager_name
        form.contact_email.data = merchant.contact_email
        form.contact_phone.data = merchant.contact_phone
        form.full_address.data = merchant.full_address
        # Skip province/city/barangay - they're names in DB but form expects codes
        # These will be handled by JavaScript loading from API
        form.postal_code.data = merchant.postal_code
        form.google_maps_link.data = merchant.google_maps_link
        form.services_offered.data = merchant.services_offered or []
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
def store_public(merchant_id):
    """Display public view of merchant store - no login required"""
    merchant = Merchant.query.filter_by(id=merchant_id).first()
    
    if not merchant:
        flash('Store not found.', 'danger')
        return redirect(url_for('user.nearby_services'))
    
    # Rating stats not yet implemented in simplified booking system
    store_rating = 0
    total_reviews = 0
    
    # Check if store is open right now
    is_open = False
    if merchant.opening_time and merchant.closing_time and merchant.operating_days:
        from datetime import datetime, time
        now = datetime.now()  # Use local time for business hours
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        current_time = now.time()
        
        # Check if today is in operating days
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
    page = request.args.get('page', 1, type=int)

    # Paginate active species
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
    species = Species.query.get_or_404(id)

    # Only fetch active breeds (not soft-deleted)
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


# ========== MERCHANT APPLICATION ROUTES ==========

@bp.route('/apply', methods=['GET', 'POST'])
@login_required
def apply():
    """Merchant application form"""
    
    # Check if user already has merchant application
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
            
            # Location - convert codes to names
            merchant.province = get_province_name(form.province.data)
            merchant.city = get_city_name(form.city.data)
            merchant.barangay = get_barangay_name(form.barangay.data) if form.barangay.data else None
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
            
            # Services and pets (convert to JSON)
            merchant.services_offered = form.services_offered.data if form.services_offered.data else []
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
            merchant.vaccination_required = form.vaccination_required.data
            merchant.cancellation_policy = form.cancellation_policy.data or None
            
            # Create merchant uploads directory
            merchant_upload_dir = os.path.join('app/static/uploads/merchants', str(current_user.id))
            os.makedirs(merchant_upload_dir, exist_ok=True)
            
            # Handle store logo upload
            if request.files.get('store_logo') and request.files['store_logo'].filename:
                file = request.files['store_logo']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"logo_{datetime.utcnow().timestamp()}_{file.filename}")
                    file.save(os.path.join(merchant_upload_dir, filename))
                    merchant.logo_path = f'merchants/{current_user.id}/{filename}'
            
            # Handle file uploads
            if request.files.get('government_id') and request.files['government_id'].filename:
                file = request.files['government_id']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"gov_id_{datetime.utcnow().timestamp()}_{file.filename}")
                    file.save(os.path.join(merchant_upload_dir, filename))
                    merchant.government_id_path = f'merchants/{current_user.id}/{filename}'
            
            if request.files.get('business_permit') and request.files['business_permit'].filename:
                file = request.files['business_permit']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"permit_{datetime.utcnow().timestamp()}_{file.filename}")
                    file.save(os.path.join(merchant_upload_dir, filename))
                    merchant.business_permit_path = f'merchants/{current_user.id}/{filename}'
            
            # Handle multiple facility photos
            facility_photos = []
            if request.files.getlist('facility_photos'):
                files = request.files.getlist('facility_photos')
                for idx, file in enumerate(files):
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(f"facility_{idx}_{datetime.utcnow().timestamp()}_{file.filename}")
                        file.save(os.path.join(merchant_upload_dir, filename))
                        facility_photos.append(f'merchants/{current_user.id}/{filename}')
                
                if len(facility_photos) >= 3:
                    merchant.facility_photos_paths = facility_photos
                else:
                    flash('Please upload at least 3 facility photos.', 'danger')
                    return render_template('merchant/apply.html', form=form)
            
            # Set application status
            merchant.application_status = 'pending'
            merchant.submitted_at = get_ph_datetime()
            
            db.session.add(merchant)
            db.session.commit()
            
            flash('Application submitted successfully! Our team will review your application and contact you within 5-7 business days.', 'success')
            return redirect(url_for('user.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error submitting merchant application: {str(e)}")
            flash('An error occurred while submitting your application. Please try again.', 'danger')
            return render_template('merchant/apply.html', form=form)
    
    # Log form errors if any
    if request.method == 'POST' and not form.validate_on_submit():
        for field, errors in form.errors.items():
            for error in errors:
                logger.warning(f"Form validation error - {field}: {error}")
                flash(f"{field}: {error}", 'danger')
    
    return render_template('merchant/apply.html', form=form)


@bp.route('/api/get-provinces')
def get_provinces():
    """Get all provinces AND special regions in Philippines
    
    This includes:
    - Regular provinces
    - Special administrative regions (Metro Manila, Cordillera, etc.)
    These are returned as "provinces" for the frontend, but special regions
    won't have sub-provinces (they go directly to cities).
    """
    try:
        all_locations = []
        
        # 1️⃣ Try to get all regions first (includes special administrative regions)
        # The PSGC API has a regions endpoint that includes Metro Manila, CALABARZON, etc.
        try:
            regions_response = requests.get(
                'https://psgc.gitlab.io/api/regions/',
                timeout=5
            )
            if regions_response.status_code == 200:
                regions_data = regions_response.json()
                
                # Convert to list
                regions_list = []
                if isinstance(regions_data, list):
                    regions_list = regions_data
                elif isinstance(regions_data, dict):
                    if 'data' in regions_data:
                        regions_list = regions_data['data']
                    else:
                        regions_list = [regions_data]
                
                # Mark as region type for frontend handling
                for region in regions_list:
                    if isinstance(region, dict):
                        region['_type'] = 'region'
                        all_locations.append(region)
        except Exception as e:
            logger.warning(f"Could not fetch regions: {str(e)}")
        
        # 2️⃣ Get regular provinces
        try:
            provinces_response = requests.get(
                'https://psgc.gitlab.io/api/provinces/',
                timeout=5
            )
            if provinces_response.status_code == 200:
                provinces_data = provinces_response.json()
                
                # Convert to list
                provinces_list = []
                if isinstance(provinces_data, list):
                    provinces_list = provinces_data
                elif isinstance(provinces_data, dict):
                    if 'data' in provinces_data:
                        provinces_list = provinces_data['data']
                    else:
                        provinces_list = [provinces_data]
                
                # Mark as province type
                for province in provinces_list:
                    if isinstance(province, dict):
                        province['_type'] = 'province'
                        all_locations.append(province)
        except Exception as e:
            logger.warning(f"Could not fetch provinces: {str(e)}")
        
        # 3️⃣ If we have no locations, fallback to provinces only
        if not all_locations:
            provinces_response = requests.get(
                'https://psgc.gitlab.io/api/provinces/',
                timeout=5
            )
            if provinces_response.status_code == 200:
                provinces_data = provinces_response.json()
                if isinstance(provinces_data, list):
                    all_locations = provinces_data
                elif isinstance(provinces_data, dict) and 'data' in provinces_data:
                    all_locations = provinces_data['data']
        
        # 4️⃣ Remove duplicates by code
        seen = {}
        unique_locations = []
        for loc in all_locations:
            if isinstance(loc, dict) and 'code' in loc:
                if loc['code'] not in seen:
                    seen[loc['code']] = True
                    unique_locations.append(loc)
        
        # 5️⃣ Sort alphabetically by name
        unique_locations.sort(key=lambda x: x.get('name', '').lower())
        
        logger.info(f"Returning {len(unique_locations)} locations (provinces + regions)")
        return jsonify(unique_locations)
    except Exception as e:
        logger.error(f"Error fetching provinces/regions: {str(e)}")
    
    return jsonify({'error': 'Failed to fetch provinces'}), 500


@bp.route('/api/get-cities/<location_code>')
def get_cities(location_code):
    """Get cities and municipalities for a given province OR region
    
    Handles both:
    - Regular provinces (uses /provinces/{code}/cities/)
    - Special regions like Metro Manila (uses /regions/{code}/cities/)
    """
    try:
        all_cities = []
        
        # 1️⃣ Try as a region first (for Metro Manila, CALABARZON, etc.)
        try:
            region_response = requests.get(
                f'https://psgc.gitlab.io/api/regions/{location_code}/cities/',
                timeout=5
            )
            
            if region_response.status_code == 200:
                cities = region_response.json()
                if isinstance(cities, list):
                    all_cities.extend(cities)
                elif isinstance(cities, dict):
                    if 'data' in cities:
                        all_cities.extend(cities['data'])
                    else:
                        all_cities.extend([cities])
        except Exception as e:
            logger.debug(f"Not a region code or failed to fetch: {str(e)}")
        
        # 2️⃣ If no cities from region, try as province
        if not all_cities:
            try:
                province_response = requests.get(
                    f'https://psgc.gitlab.io/api/provinces/{location_code}/cities/',
                    timeout=5
                )
                
                if province_response.status_code == 200:
                    cities = province_response.json()
                    if isinstance(cities, list):
                        all_cities.extend(cities)
                    elif isinstance(cities, dict):
                        if 'data' in cities:
                            all_cities.extend(cities['data'])
                        else:
                            all_cities.extend([cities])
            except Exception as e:
                logger.debug(f"Not a province code or failed to fetch cities: {str(e)}")
        
        # 3️⃣ Also try to fetch municipalities (for completeness)
        try:
            mun_response = requests.get(
                f'https://psgc.gitlab.io/api/provinces/{location_code}/municipalities/',
                timeout=5
            )
            if mun_response.status_code == 200:
                municipalities = mun_response.json()
                if isinstance(municipalities, list):
                    all_cities.extend(municipalities)
                elif isinstance(municipalities, dict):
                    if 'data' in municipalities:
                        all_cities.extend(municipalities['data'])
                    else:
                        all_cities.extend([municipalities])
        except:
            pass  # If municipalities endpoint fails, just use cities
        
        # 4️⃣ Remove duplicates by code
        seen = set()
        unique_cities = []
        for city in all_cities:
            if isinstance(city, dict) and 'code' in city:
                if city['code'] not in seen:
                    seen.add(city['code'])
                    unique_cities.append(city)
        
        # 5️⃣ Sort alphabetically by name
        unique_cities.sort(key=lambda x: x.get('name', '').lower())
        
        logger.info(f"Found {len(unique_cities)} cities/municipalities for location {location_code}")
        return jsonify(unique_cities)
    except Exception as e:
        logger.error(f"Error fetching cities/municipalities for {location_code}: {str(e)}")
    
    return jsonify({'error': 'Failed to fetch cities/municipalities'}), 500


@bp.route('/api/get-barangays/<city_code>')
def get_barangays(city_code):
    """Get barangays for a given city or municipality (robust fallback)
    
    Tries multiple endpoints to find barangays:
    1. City endpoint: /cities/{code}/barangays/
    2. Municipality endpoint: /municipalities/{code}/barangays/
    3. District endpoint: /districts/{code}/barangays/
    """
    try:
        barangay_list = []

        # 1️⃣ Try city endpoint first
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

        # 2️⃣ If empty, try municipality endpoint
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

        # 3️⃣ If still empty, try district endpoint (some areas use districts)
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

        # 4️⃣ Still empty = invalid or no barangays available
        if not barangay_list:
            logger.warning(f"No barangays found for city code: {city_code}")
            return jsonify([])

        # 5️⃣ Sort safely by name
        barangay_list.sort(key=lambda x: x.get('name', '').lower() if isinstance(x, dict) else '')

        logger.info(f"Found {len(barangay_list)} barangays for city {city_code}")
        return jsonify(barangay_list)

    except Exception as e:
        logger.error(f"Error fetching barangays for {city_code}: {str(e)}")
        return jsonify({'error': 'Failed to fetch barangays'}), 500


@bp.route('/api/get-services/<category>')
def get_services_for_category(category):
    """Get services allowed for a given business category"""
    from app.utils.merchant_service_config import CATEGORY_TO_SERVICES
    
    category_services = CATEGORY_TO_SERVICES.get(category, [])
    
    if not category_services:
        return jsonify({'error': f'No services found for category: {category}'}), 404
    
    return jsonify({
        'category': category,
        'services': category_services
    })


@bp.route('/api/geocode', methods=['POST'])
def geocode():
    """Geocode address to get coordinates"""
    data = request.get_json()
    address = data.get('address')
    city = data.get('city')
    province = data.get('province')
    
    if not address:
        return jsonify({'error': 'Address is required'}), 400
    
    try:
        # Build full address for geocoding
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
            result = response.json()[0]
            return jsonify({
                'latitude': float(result['lat']),
                'longitude': float(result['lon']),
                'display_name': result['display_name']
            })
    except Exception as e:
        logger.error(f"Error geocoding address: {str(e)}")
    
    return jsonify({'error': 'Failed to geocode address'}), 500


@bp.route('/api/search-location', methods=['POST'])
def search_location():
    """Search for locations using Nominatim"""
    data = request.get_json()
    query = data.get('q', '').strip()
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': query,
                'format': 'json',
                'limit': 8,
                'countrycodes': 'ph'
            },
            headers={'User-Agent': 'PetsonaApp/1.0'},
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Search failed'}), response.status_code
    except Exception as e:
        logger.error(f"Error searching location: {str(e)}")
        return jsonify({'error': 'Failed to search location'}), 500


@bp.route('/api/reverse-geocode', methods=['POST', 'OPTIONS'])
@csrf.exempt
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
        
        # Extract coordinates - accept both 'lon' and 'lng'
        lat = data.get('lat')
        lon = data.get('lon') or data.get('lng')
        
        logger.info(f"Reverse geocode request - lat: {lat}, lon: {lon}")
        
        if lat is None or lon is None:
            logger.error(f"Missing coordinates - lat: {lat}, lon: {lon}")
            return jsonify({'error': 'Latitude and longitude are required'}), 400
        
        # Convert to float
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid coordinate format - lat: {lat}, lon: {lon}, error: {str(e)}")
            return jsonify({'error': 'Latitude and longitude must be numbers'}), 400
        
        # Call Nominatim reverse geocoding
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


# ========== BOOKING ROUTES ==========

@bp.route('/booking/<int:merchant_id>')
def booking(merchant_id):
    """Display booking form for a specific merchant"""
    merchant = Merchant.query.filter_by(id=merchant_id).first()
    
    if not merchant:
        flash('Store not found.', 'danger')
        return redirect(url_for('user.nearby_services'))
    
    # Merchant ratings not yet implemented in simplified booking system
    store_rating = 0
    total_reviews = 0
    
    return render_template('merchant/booking.html', 
                         merchant=merchant,
                         store_rating=store_rating,
                         total_reviews=total_reviews)


@bp.route('/booking/<int:merchant_id>/create', methods=['POST'])
@login_required
def create_booking(merchant_id):
    """Create a new appointment-based booking from form submission"""
    try:
        merchant = Merchant.query.filter_by(id=merchant_id).first()
        
        if not merchant:
            flash('Store not found.', 'danger')
            return redirect(url_for('user.nearby_services'))
        
        # Parse appointment-based data
        appointment_date_str = request.form.get('check_in_date')
        appointment_time = request.form.get('check_in_time', '09:00')
        
        # Validate required appointment fields
        if not appointment_date_str:
            flash('Please select an appointment date.', 'warning')
            return redirect(url_for('merchant.booking', merchant_id=merchant_id))
        
        # Parse appointment date
        try:
            appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d')
        except Exception as e:
            logger.error(f"Date parsing error: {str(e)}")
            flash('Invalid date format.', 'danger')
            return redirect(url_for('merchant.booking', merchant_id=merchant_id))
        
        # Parse pets from form array (pets[0][pet_name], pets[0][pet_species], etc.)
        pets_data = []
        pet_index = 0
        while True:
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
        
        # Get price breakdown from form (pre-calculated by JavaScript)
        try:
            price_breakdown_str = request.form.get('price_breakdown', '{}')
            price_breakdown = json.loads(price_breakdown_str) if price_breakdown_str else {}
        except:
            price_breakdown = {}
        
        # Calculate total amount from price breakdown
        total_amount = 0
        for size_data in price_breakdown.values():
            if isinstance(size_data, dict) and 'price' in size_data:
                total_amount += float(size_data.get('price', 0))
        
        if total_amount <= 0:
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
        
        # Create appointment-based booking
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


@bp.route('/booking/confirmation/<int:booking_id>')
def booking_confirmation(booking_id):
    """Display booking confirmation page"""
    booking = Booking.query.get(booking_id)
    
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('user.dashboard'))
    
    # Security check: user can only view their own booking
    if booking.user_id != current_user.id and current_user.role != 'admin':
        # Allow access via confirmation code if not logged in as the booker
        confirmation_code = request.args.get('confirmation_code')
        if not confirmation_code or confirmation_code != booking.confirmation_code:
            flash('Unauthorized access.', 'danger')
            return redirect(url_for('user.dashboard'))
    
    return render_template('merchant/booking_confirmation.html', booking=booking)


@bp.route('/bookings-list')
@login_required
@merchant_required
def bookings_list():
    """Display all bookings for the merchant"""
    if current_user.role != 'merchant':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    
    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    
    if not merchant:
        flash('Store information not found.', 'warning')
        return redirect(url_for('merchant.apply'))
    
    # Get page pagination parameter
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '', type=str)
    
    # Base query for merchant's bookings
    query = Booking.query.filter(
        Booking.merchant_id == merchant.id,
        Booking.deleted_at.is_(None)
    )
    
    # Calculate statistics for all bookings (not filtered)
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
    
    # Apply status filter if provided
    if status_filter and status_filter != '':
        query = query.filter(Booking.status == status_filter)
    
    # Order by most recent first
    query = query.order_by(Booking.created_at.desc())
    
    # Paginate with 10 bookings per page
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    
    # Get unique statuses for filter dropdown
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
    """Confirm a pending booking"""
    if current_user.role != 'merchant':
        if request.is_json or request.args.get('api'):
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
        booking.status = 'confirmed'
        booking.merchant_confirmed = True
        booking.merchant_confirmed_at = get_ph_datetime()
        db.session.commit()
        
        # Log the action
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
        
        # Send notification to customer
        appointment_date_str = booking.appointment_date.strftime('%B %d, %Y') if booking.appointment_date else 'Scheduled'
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
            return jsonify({'success': False, 'error': str(e)}), 500
        flash('Error confirming booking.', 'danger')
    
    return redirect(url_for('merchant.bookings_list'))


@bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
@merchant_required
def cancel_booking(booking_id):
    """Cancel a booking"""
    if current_user.role != 'merchant':
        if request.is_json or request.args.get('api'):
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
            return jsonify({'success': False, 'error': str(e)}), 500
        flash('Error rejecting booking.', 'danger')
    
    return redirect(url_for('merchant.bookings_list'))


# ========== CUSTOMER BOOKING ROUTES ==========

@bp.route('/book/<int:merchant_id>', methods=['GET'])
@login_required
def book_now(merchant_id):
    """Display booking form for customer"""
    merchant = Merchant.query.filter_by(id=merchant_id).first()
    
    if not merchant:
        flash('Merchant not found.', 'danger')
        return redirect(url_for('user.nearby_services'))
    
    return render_template('merchant/booking.html', 
                         merchant=merchant)


@bp.route('/book/<int:merchant_id>', methods=['POST'])
@login_required
def customer_create_booking(merchant_id):
    """Create a new appointment-based booking from customer"""
    merchant = Merchant.query.filter_by(id=merchant_id).first()
    
    if not merchant:
        flash('Merchant not found.', 'danger')
        return redirect(url_for('user.nearby_services'))
    
    try:
        import uuid
        
        # Get form data
        customer_name = request.form.get('customer_name', '').strip()
        customer_email = request.form.get('customer_email', '').strip()
        customer_phone = request.form.get('customer_phone', '').strip()
        appointment_date_str = request.form.get('check_in_date')
        appointment_time = request.form.get('check_in_time')
        
        # Validation
        if not customer_phone:
            flash('Phone number is required.', 'danger')
            return redirect(url_for('merchant.book_now', merchant_id=merchant_id))
        
        if not appointment_date_str or not appointment_time:
            flash('Appointment date and time are required.', 'danger')
            return redirect(url_for('merchant.book_now', merchant_id=merchant_id))
        
        # Parse appointment date
        try:
            appointment_date = datetime.strptime(f"{appointment_date_str} {appointment_time}", "%Y-%m-%d %H:%M")
        except (ValueError, TypeError) as e:
            logger.error(f"Date parsing error: {str(e)}")
            flash('Invalid date or time format.', 'danger')
            return redirect(url_for('merchant.book_now', merchant_id=merchant_id))
        
        # Collect multi-pet form data
        pets_data = []
        pet_index = 0
        while True:
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
        
        # Validate we have at least one pet
        if not pets_data:
            flash('Please add at least one pet to your booking.', 'danger')
            return redirect(url_for('merchant.book_now', merchant_id=merchant_id))
        
        total_pets = len(pets_data)
        
        # Get price breakdown from form (calculated by JavaScript)
        price_breakdown_str = request.form.get('price_breakdown', '{}')
        try:
            import json
            price_breakdown = json.loads(price_breakdown_str)
        except (json.JSONDecodeError, ValueError):
            price_breakdown = {}
        
        # Calculate total amount from price breakdown
        total_amount = 0.0
        if price_breakdown:
            for size_data in price_breakdown.values():
                if isinstance(size_data, dict) and 'price' in size_data:
                    total_amount += float(size_data['price'])
        
        # If no price breakdown, calculate from merchant pricing and pet sizes
        if total_amount == 0 or not price_breakdown:
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
        
        # Generate booking number and confirmation code
        booking_number = f"BK-{datetime.now().strftime('%Y')}-{int(datetime.now().timestamp()) % 100000:05d}"
        confirmation_code = str(uuid.uuid4())[:12].upper()
        
        # Create booking record
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
        
        # Log the booking creation
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
        
        # Send notification to merchant about new booking
        if merchant.user_id:
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
    """Mark a booking as completed"""
    booking = Booking.query.filter_by(id=booking_id).first()
    
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('merchant.bookings_list'))
    
    # Check if merchant owns this booking
    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    if not merchant or booking.merchant_id != merchant.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('merchant.bookings_list'))
    
    try:
        # Update booking status to completed
        booking.status = 'completed'
        db.session.commit()
        
        # Log the action
        from app.models.audit_log import AuditLog
        from datetime import datetime
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
        
        # Send notification to customer that booking is completed
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
    """Mark a booking as no-show"""
    booking = Booking.query.filter_by(id=booking_id).first()
    
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('merchant.bookings_list'))
    
    # Check if merchant owns this booking
    merchant = Merchant.query.filter_by(user_id=current_user.id).first()
    if not merchant or booking.merchant_id != merchant.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('merchant.bookings_list'))
    
    try:
        # Update booking status to no-show
        booking.status = 'no-show'
        db.session.commit()
        
        # Log the action
        from app.models.audit_log import AuditLog
        from datetime import datetime
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
        
        # Send notification to customer about no-show
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
    """API endpoint to get merchant services and pricing"""
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




