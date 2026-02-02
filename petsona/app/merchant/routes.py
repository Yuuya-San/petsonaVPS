import os
import json
import requests
from datetime import datetime
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
import logging

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf'}
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
    
    # Get top 3 species by vote count
    top_species = Species.query.filter(
        Species.deleted_at.is_(None)
    ).order_by(Species.heart_vote_count.desc()).limit(3).all()
    
    return render_template('merchant/dashboard.html', merchant=merchant, top_species=top_species)


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
    
    # 6. Store Rating (Average customer rating from completed bookings)
    avg_rating = db.session.query(func.avg(Booking.customer_rating)).filter(
        Booking.merchant_id == merchant.id,
        Booking.customer_rating.isnot(None),
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    store_rating = round(float(avg_rating), 1) if avg_rating else 0
    
    # 7. Total Reviews Count (bookings with ratings)
    total_reviews = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.customer_rating.isnot(None),
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
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
        Booking.payment_status == 'completed',
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    total_revenue = float(total_revenue)
    
    # 11. Merchant Earnings (after commission)
    merchant_earnings = db.session.query(func.sum(Booking.merchant_receives)).filter(
        Booking.merchant_id == merchant.id,
        Booking.payment_status == 'completed',
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    merchant_earnings = float(merchant_earnings)
    
    # 12. Platform Fee Collected
    platform_fees = total_revenue - merchant_earnings if total_revenue > 0 else 0
    
    # 13. Bookings this month (30 days)
    from datetime import timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    bookings_this_month = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.created_at >= thirty_days_ago,
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    # 14. No-show Rate
    no_show_count = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.no_show == True,
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    no_show_rate = 0
    if completed_bookings > 0:
        no_show_rate = round((no_show_count / completed_bookings) * 100, 1)
    
    # 15. Recent bookings (last 5 for dashboard preview)
    recent_bookings = db.session.query(Booking).filter(
        Booking.merchant_id == merchant.id,
        Booking.deleted_at.is_(None)
    ).order_by(Booking.created_at.desc()).limit(5).all()
    
    # 16. Month-over-month growth
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
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
        merchant.logo_path = f"uploads/merchants/{current_user.id}/{filename}"
        merchant.updated_at = datetime.utcnow()
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
            timestamp=datetime.utcnow()
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
            # Store previous values for audit log
            previous_values = {
                'business_name': merchant.business_name,
                'business_type': merchant.business_type,
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
                'max_pets_per_day': merchant.max_pets_per_day,
                'min_price_per_day': merchant.min_price_per_day,
                'max_price_per_day': merchant.max_price_per_day,
                'opening_time': merchant.opening_time,
                'closing_time': merchant.closing_time,
                'operating_days': merchant.operating_days,
                'cancellation_policy': merchant.cancellation_policy,
                'years_in_operation': merchant.years_in_operation
            }
            
            # Update merchant information - SECTION 1: BUSINESS INFO
            merchant.business_name = form.business_name.data
            merchant.business_type = form.business_type.data
            merchant.business_description = form.business_description.data
            merchant.years_in_operation = form.years_in_operation.data
            
            # Handle logo upload if provided
            if 'logo_path' in request.files and request.files['logo_path'].filename:
                logo_file = request.files['logo_path']
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
                        merchant.logo_path = f"uploads/merchants/{current_user.id}/{filename}"
                        logger.info(f"Logo updated for merchant {merchant.id}: {merchant.logo_path}")
            
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
            
            # SECTION 6: CAPACITY & PRICING
            merchant.max_pets_per_day = form.max_pets_per_day.data
            merchant.min_price_per_day = form.min_price_per_day.data
            merchant.max_price_per_day = form.max_price_per_day.data
            
            # SECTION 7: OPERATING SCHEDULE
            merchant.opening_time = form.opening_time.data
            merchant.closing_time = form.closing_time.data
            merchant.operating_days = form.operating_days.data if form.operating_days.data else []
            
            # SECTION 8: POLICIES
            merchant.cancellation_policy = form.cancellation_policy.data
            
            merchant.updated_at = datetime.utcnow()
            
            # Mark as pending approval if it was approved
            if merchant.application_status == 'approved':
                merchant.application_status = 'pending'
            
            db.session.commit()
            
            # Log the update
            audit_log = AuditLog(
                event='merchant_store_updated',
                actor_id=current_user.id,
                actor_email=current_user.email,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                timestamp=datetime.utcnow()
            )
            audit_log.set_details({
                'merchant_id': merchant.id,
                'previous_values': previous_values,
                'new_values': {
                    'business_name': merchant.business_name,
                    'business_type': merchant.business_type,
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
                    'max_pets_per_day': merchant.max_pets_per_day,
                    'min_price_per_day': merchant.min_price_per_day,
                    'max_price_per_day': merchant.max_price_per_day,
                    'opening_time': merchant.opening_time,
                    'closing_time': merchant.closing_time,
                    'operating_days': merchant.operating_days,
                    'cancellation_policy': merchant.cancellation_policy,
                    'years_in_operation': merchant.years_in_operation
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
    
    elif request.method == 'GET':
        # Pre-fill form with existing data
        form.business_name.data = merchant.business_name
        form.business_type.data = merchant.business_type
        form.business_description.data = merchant.business_description
        form.years_in_operation.data = merchant.years_in_operation
        form.owner_manager_name.data = merchant.owner_manager_name
        form.contact_email.data = merchant.contact_email
        form.contact_phone.data = merchant.contact_phone
        form.full_address.data = merchant.full_address
        form.city.data = merchant.city
        form.province.data = merchant.province
        form.barangay.data = merchant.barangay
        form.postal_code.data = merchant.postal_code
        form.google_maps_link.data = merchant.google_maps_link
        form.services_offered.data = merchant.services_offered or []
        form.pets_accepted.data = merchant.pets_accepted or []
        form.max_pets_per_day.data = merchant.max_pets_per_day
        form.min_price_per_day.data = merchant.min_price_per_day
        form.max_price_per_day.data = merchant.max_price_per_day
        form.opening_time.data = merchant.opening_time
        form.closing_time.data = merchant.closing_time
        form.operating_days.data = merchant.operating_days or []
        form.cancellation_policy.data = merchant.cancellation_policy
    
    return render_template('merchant/store_edit.html', form=form, merchant=merchant)



@bp.route('/store-public/<int:merchant_id>')
def store_public(merchant_id):
    """Display public view of merchant store - no login required"""
    merchant = Merchant.query.filter_by(id=merchant_id).first()
    
    if not merchant:
        flash('Store not found.', 'danger')
        return redirect(url_for('user.nearby_services'))
    
    # Compute rating stats from bookings (like store() route does)
    avg_rating = db.session.query(func.avg(Booking.customer_rating)).filter(
        Booking.merchant_id == merchant.id,
        Booking.customer_rating.isnot(None),
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    store_rating = round(float(avg_rating), 1) if avg_rating else 0
    
    # Total reviews count (bookings with ratings)
    total_reviews = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant.id,
        Booking.customer_rating.isnot(None),
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    # Check if store is open right now
    is_open = False
    if merchant.opening_time and merchant.closing_time and merchant.operating_days:
        from datetime import datetime, time
        now = datetime.now()
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        current_time = now.time()
        
        # Check if today is in operating days
        operating_days = merchant.get_operating_days()
        if current_day in operating_days:
            # Check if current time is within operating hours
            try:
                opening = datetime.strptime(merchant.opening_time, '%H:%M').time() if isinstance(merchant.opening_time, str) else merchant.opening_time
                closing = datetime.strptime(merchant.closing_time, '%H:%M').time() if isinstance(merchant.closing_time, str) else merchant.closing_time
                is_open = opening <= current_time < closing
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
            merchant.business_type = form.business_type.data
            merchant.business_description = form.business_description.data
            merchant.years_in_operation = form.years_in_operation.data or None
            
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
            
            # Store coordinates
            if form.latitude.data and form.longitude.data:
                merchant.set_coordinates(form.latitude.data, form.longitude.data)
            
            # Services and pets (convert to JSON)
            merchant.services_offered = form.services_offered.data if form.services_offered.data else []
            merchant.pets_accepted = form.pets_accepted.data if form.pets_accepted.data else []
            
            # Capacity and pricing
            merchant.max_pets_per_day = form.max_pets_per_day.data
            merchant.min_price_per_day = form.min_price_per_day.data
            merchant.max_price_per_day = form.max_price_per_day.data
            
            # Operating schedule
            merchant.opening_time = form.opening_time.data
            merchant.closing_time = form.closing_time.data
            merchant.operating_days = form.operating_days.data if form.operating_days.data else []
            
            # Policies
            merchant.vaccination_required = form.vaccination_required.data
            merchant.cancellation_policy = form.cancellation_policy.data or None
            
            # Create merchant uploads directory
            merchant_upload_dir = os.path.join('app/static/uploads/merchants', f'merchant_{current_user.id}')
            os.makedirs(merchant_upload_dir, exist_ok=True)
            
            # Handle file uploads
            if request.files.get('government_id') and request.files['government_id'].filename:
                file = request.files['government_id']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"gov_id_{datetime.utcnow().timestamp()}_{file.filename}")
                    file.save(os.path.join(merchant_upload_dir, filename))
                    merchant.government_id_path = f'merchants/merchant_{current_user.id}/{filename}'
            
            if request.files.get('business_permit') and request.files['business_permit'].filename:
                file = request.files['business_permit']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"permit_{datetime.utcnow().timestamp()}_{file.filename}")
                    file.save(os.path.join(merchant_upload_dir, filename))
                    merchant.business_permit_path = f'merchants/merchant_{current_user.id}/{filename}'
            
            # Handle multiple facility photos
            facility_photos = []
            if request.files.getlist('facility_photos'):
                files = request.files.getlist('facility_photos')
                for idx, file in enumerate(files):
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(f"facility_{idx}_{datetime.utcnow().timestamp()}_{file.filename}")
                        file.save(os.path.join(merchant_upload_dir, filename))
                        facility_photos.append(f'merchants/merchant_{current_user.id}/{filename}')
                
                if len(facility_photos) >= 3:
                    merchant.facility_photos_paths = facility_photos
                else:
                    flash('Please upload at least 3 facility photos.', 'danger')
                    return render_template('merchant/apply.html', form=form)
            
            # Set application status
            merchant.application_status = 'pending'
            merchant.submitted_at = datetime.utcnow()
            
            db.session.add(merchant)
            db.session.commit()
            
            flash('Application submitted successfully! Our team will review your application and contact you within 5-7 business days.', 'success')
            return redirect(url_for('user.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error submitting merchant application: {str(e)}")
            flash('An error occurred while submitting your application. Please try again.', 'danger')
            return render_template('merchant/apply.html', form=form)
    
    return render_template('merchant/apply.html', form=form)


@bp.route('/api/get-provinces')
def get_provinces():
    """Get all provinces in Philippines via API"""
    try:
        response = requests.get(
            'https://psgc.gitlab.io/api/provinces/',
            timeout=5
        )
        if response.status_code == 200:
            provinces = response.json()
            
            # Convert to list if needed
            if isinstance(provinces, list):
                province_list = provinces
            elif isinstance(provinces, dict):
                if 'data' in provinces:
                    province_list = provinces['data']
                else:
                    province_list = [provinces]
            else:
                province_list = []
            
            # Sort alphabetically by name
            province_list.sort(key=lambda x: x.get('name', '').lower() if isinstance(x, dict) else '')
            
            return jsonify(province_list)
    except Exception as e:
        logger.error(f"Error fetching provinces: {str(e)}")
    
    return jsonify({'error': 'Failed to fetch provinces'}), 500


@bp.route('/api/get-cities/<province_code>')
def get_cities(province_code):
    """Get cities and municipalities for a given province"""
    try:
        # Fetch cities
        response = requests.get(
            f'https://psgc.gitlab.io/api/provinces/{province_code}/cities/',
            timeout=5
        )
        
        all_cities = []
        
        if response.status_code == 200:
            cities = response.json()
            # Handle both list and dict responses
            if isinstance(cities, list):
                all_cities.extend(cities)
            elif isinstance(cities, dict):
                # If it's a dict, extract the list
                if 'data' in cities:
                    all_cities.extend(cities['data'])
                else:
                    all_cities.extend([cities])
        
        # Also try to fetch municipalities
        try:
            mun_response = requests.get(
                f'https://psgc.gitlab.io/api/provinces/{province_code}/municipalities/',
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
        
        # Remove duplicates and sort alphabetically by name
        seen = set()
        unique_cities = []
        for city in all_cities:
            if isinstance(city, dict) and 'code' in city:
                if city['code'] not in seen:
                    seen.add(city['code'])
                    unique_cities.append(city)
        
        # Sort by name (case-insensitive)
        unique_cities.sort(key=lambda x: x.get('name', '').lower())
        
        return jsonify(unique_cities)
    except Exception as e:
        logger.error(f"Error fetching cities/municipalities for {province_code}: {str(e)}")
    
    return jsonify({'error': 'Failed to fetch cities/municipalities'}), 500


@bp.route('/api/get-barangays/<city_code>')
def get_barangays(city_code):
    """Get barangays for a given city or municipality (robust fallback)"""
    try:
        barangay_list = []

        # 1️⃣ Try city endpoint first
        city_url = f'https://psgc.gitlab.io/api/cities/{city_code}/barangays/'
        response = requests.get(city_url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                barangay_list = data
            elif isinstance(data, dict) and 'data' in data:
                barangay_list = data['data']

        # 2️⃣ If empty, try municipality endpoint
        if not barangay_list:
            muni_url = f'https://psgc.gitlab.io/api/municipalities/{city_code}/barangays/'
            muni_response = requests.get(muni_url, timeout=5)

            if muni_response.status_code == 200:
                data = muni_response.json()
                if isinstance(data, list):
                    barangay_list = data
                elif isinstance(data, dict) and 'data' in data:
                    barangay_list = data['data']

        # 3️⃣ Still empty = invalid PSGC code
        if not barangay_list:
            return jsonify([])

        # 4️⃣ Sort safely
        barangay_list.sort(key=lambda x: x.get('name', '').lower())

        return jsonify(barangay_list)

    except Exception as e:
        logger.error(f"Error fetching barangays for {city_code}: {str(e)}")
        return jsonify({'error': 'Failed to fetch barangays'}), 500



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
        # Try to get JSON data with multiple fallbacks
        data = None
        
        # First try: standard get_json()
        if request.is_json:
            data = request.get_json()
        
        # Second try: force JSON parsing
        if data is None:
            try:
                data = request.get_json(force=True, silent=True)
            except:
                pass
        
        # Third try: check request.data
        if data is None and request.data:
            try:
                import json as json_module
                data = json_module.loads(request.data.decode())
            except:
                pass
        
        # Fourth try: form data
        if data is None:
            data = request.form.to_dict()
        
        # Extract coordinates
        lat = data.get('lat') if data else None
        lon = data.get('lon') if data else None
        
        # Debug logging
        logger.info(f"Reverse geocode request - Content-Type: {request.content_type}, Data: {data}")
        
        if lat is None or lon is None:
            logger.error(f"Missing coordinates - lat: {lat}, lon: {lon}, data: {data}")
            return jsonify({'error': 'Latitude and longitude are required', 'data': data}), 400
        
        # Convert to float
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid coordinate format - lat: {lat}, lon: {lon}, error: {str(e)}")
            return jsonify({'error': 'Latitude and longitude must be numbers'}), 400
        
        response = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={
                'format': 'json',
                'lat': lat,
                'lon': lon
            },
            headers={'User-Agent': 'PetsonaApp/1.0'},
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            logger.error(f"Nominatim error: {response.status_code}")
            return jsonify({'error': 'Reverse geocoding failed'}), response.status_code
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
    
    # Get user's pets if authenticated
    user_pets = []
    if current_user.is_authenticated:
        from app.models.user import User
        from app.models.breed import Breed
        from app.models.species import Species
        
        # Query pets for current user - assuming a pets relationship exists
        # This may need to be adjusted based on your actual pet model structure
        try:
            user_pets = db.session.query(db.func.json_extract(db.func.json_array_elements(User.pets), '$.id')).filter(
                User.id == current_user.id
            ).all()
        except:
            user_pets = []
    
    # Get merchant ratings
    avg_rating = db.session.query(func.avg(Booking.customer_rating)).filter(
        Booking.merchant_id == merchant_id,
        Booking.customer_rating.isnot(None),
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    store_rating = round(float(avg_rating), 1) if avg_rating else 0
    
    total_reviews = db.session.query(func.count(Booking.id)).filter(
        Booking.merchant_id == merchant_id,
        Booking.customer_rating.isnot(None),
        Booking.deleted_at.is_(None)
    ).scalar() or 0
    
    return render_template('merchant/booking.html', 
                         merchant=merchant,
                         user_pets=user_pets,
                         store_rating=store_rating,
                         total_reviews=total_reviews)


@bp.route('/api/booking/create', methods=['POST'])
@login_required
def api_create_booking():
    """Create a new booking"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['merchant_id', 'services_booked', 'pets_booked', 'check_in_date', 
                          'check_out_date', 'check_in_time', 'check_out_time', 
                          'customer_name', 'customer_email', 'customer_phone']
        
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        merchant_id = data.get('merchant_id')
        merchant = Merchant.query.get(merchant_id)
        
        if not merchant:
            return jsonify({'error': 'Merchant not found'}), 404
        
        # Parse dates
        from datetime import datetime
        try:
            check_in_date = datetime.fromisoformat(data['check_in_date'])
            check_out_date = datetime.fromisoformat(data['check_out_date'])
        except:
            return jsonify({'error': 'Invalid date format'}), 400
        
        if check_out_date <= check_in_date:
            return jsonify({'error': 'Check-out date must be after check-in date'}), 400
        
        # Calculate duration
        duration_days = (check_out_date - check_in_date).days
        if duration_days <= 0:
            duration_days = 1
        
        # Get pricing info
        base_price = float(merchant.max_price_per_day or 0)
        pets_count = len(data.get('pets_booked', []))
        
        # Calculate pricing
        service_cost = base_price * duration_days * max(pets_count, 1)
        pickup_fee = 0
        delivery_fee = 0
        additional_services_fee = 0
        discount_amount = 0
        subtotal = service_cost + pickup_fee + delivery_fee + additional_services_fee
        total_amount = subtotal - discount_amount
        
        # Generate booking number and confirmation code
        import random
        import string
        booking_number = f"BK-{datetime.now().year}-{random.randint(100000, 999999)}"
        confirmation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Create booking
        booking = Booking(
            user_id=current_user.id,
            merchant_id=merchant_id,
            booking_number=booking_number,
            confirmation_code=confirmation_code,
            status='pending',
            customer_name=data['customer_name'],
            customer_email=data['customer_email'],
            customer_phone=data['customer_phone'],
            services_booked=data.get('services_booked', []),
            pets_booked=data.get('pets_booked', []),
            total_pets=pets_count,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            check_in_time=data.get('check_in_time', '09:00'),
            check_out_time=data.get('check_out_time', '17:00'),
            duration_days=duration_days,
            base_price_per_day=base_price,
            total_service_cost=service_cost,
            pickup_fee=pickup_fee,
            delivery_fee=delivery_fee,
            additional_services_fee=additional_services_fee,
            discount_amount=discount_amount,
            subtotal=subtotal,
            total_amount=total_amount,
            payment_method='simulated',
            payment_status='pending',
            special_requests=data.get('special_requests', ''),
            source='web',
        )
        
        # Calculate merchant split
        booking.calculate_merchant_split()
        
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
        
        return jsonify({
            'success': True,
            'booking_id': booking.id,
            'confirmation_code': booking.confirmation_code,
            'message': 'Booking created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating booking: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to create booking', 'details': str(e)}), 500


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

