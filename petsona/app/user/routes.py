from flask import render_template, flash, redirect, url_for, request, abort, jsonify
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]
from app.user import bp
from app.decorators import user_required
from app.models import Species, Breed, Merchant, MatchHistory
from app import db
from app.extensions import csrf
from app.utils.notification_manager import NotificationManager
from sqlalchemy import func # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta
import pytz
import logging

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

logger = logging.getLogger(__name__)

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)
import math
import sys
import os
import logging
import requests

logger = logging.getLogger(__name__)


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two coordinates using Haversine formula (fallback for air distance)"""
    R = 6371  # Earth's radius in kilometers
    
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    
    a = math.sin(dLat / 2) * math.sin(dLat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon / 2) * math.sin(dLon / 2)
    
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def get_road_distance(lat1, lon1, lat2, lon2):
    """
    Calculate actual road distance in km using OpenRouteService API
    Falls back to Haversine distance if API fails
    """
    try:
        # Use OpenRouteService for road distance calculation
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        
        payload = {
            "coordinates": [[lon1, lat1], [lon2, lat2]],
            "format": "json"
        }
        
        headers = {
            "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
            "Content-Type": "application/json"
        }
        
        # Try with API key from environment, or use free tier
        api_key = os.environ.get('OPENROUTE_API_KEY')
        if api_key:
            headers["Authorization"] = api_key
        
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            # Distance is in meters, convert to km
            if 'routes' in data and len(data['routes']) > 0:
                distance_meters = data['routes'][0]['summary']['distance']
                distance_km = distance_meters / 1000
                logger.info(f"Road distance calculated: {distance_km:.2f} km")
                return distance_km
    except Exception as e:
        logger.warning(f"OpenRouteService failed: {str(e)}. Falling back to Haversine distance.")
    
    # Fallback to Haversine distance if API fails or no API key
    return haversine_distance(lat1, lon1, lat2, lon2)


@bp.route('/dashboard')
@login_required
@user_required
def dashboard():
    from app.models.breed import Breed
    from app.models.user import User
    from app.models.booking import Booking
    from datetime import datetime, timedelta
    
    # ======================== STATS SECTION ========================
    # Count total species (non-deleted)
    species_count = Species.query.filter(
        Species.deleted_at.is_(None)
    ).count()
    
    # Count total breeds (non-deleted/active)
    breed_count = Breed.query.filter(
        Breed.deleted_at.is_(None),
        Breed.is_active == True
    ).count()
    
    # Count total users
    user_count = User.query.count()
    
    # Count total completed/successful bookings (matches made)
    match_count = MatchHistory.query.count()
    
    # ======================== TOP SPECIES SECTION ========================
    # Get top 3 species by vote count
    top_species = Species.query.filter(
        Species.deleted_at.is_(None)
    ).order_by(Species.heart_vote_count.desc()).limit(3).all()
    
    # ======================== TOP BREEDS SECTION ========================
    # Get top 3 breeds by vote count
    top_breeds = Breed.query.filter(
        Breed.deleted_at.is_(None)
    ).order_by(Breed.heart_vote_count.desc()).limit(3).all()
    
    # ======================== RECENTLY ADDED/UPDATED ========================
    # Get recently added species (last 7 days)
    week_ago = get_ph_datetime() - timedelta(days=7)
    recent_species = Species.query.filter(
        Species.deleted_at.is_(None),
        Species.created_at >= week_ago
    ).order_by(Species.created_at.desc()).limit(8).all()
    
    # Get recently updated species (last 7 days)
    updated_species = Species.query.filter(
        Species.deleted_at.is_(None),
        Species.updated_at >= week_ago
    ).order_by(Species.updated_at.desc()).limit(8).all()
    
    return render_template(
        'user/dashboard.html',
        page_title="User Dashboard",
        # Stats
        species_count=species_count,
        breed_count=breed_count,
        user_count=user_count,
        match_count=match_count,
        # Top sections
        top_species=top_species,
        top_breeds=top_breeds,
        # Recent sections
        recent_species=recent_species,
        updated_species=updated_species
    )

@bp.route('/species')
@login_required
@user_required
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
        'user/species_index.html',
        species_list=species_list,
        pagination=pagination,
        page_title="Pet Species"
    )

@bp.route('/species/<int:id>')
@login_required
@user_required
def view_species(id):
    species = Species.query.get_or_404(id)

    # Only fetch active breeds (not soft-deleted)
    breeds = Breed.query.filter_by(
        species_id=species.id,
        is_active=True   
    ).order_by(Breed.name.asc()).all()

    return render_template(
        'user/view_species.html',
        species=species,
        breeds=breeds,
        page_title=f"{species.name} Breeds"
    )

@bp.route('/nearby-services')
@login_required
@user_required
def nearby_services():
    """Display nearby pet services based on user location"""
    return render_template(
        'user/nearby_services.html',
        page_title='Nearby Pet Services'
    )


@bp.route('/location-picker')
@login_required
@user_required
def location_picker():
    """Allow user to pick a location using OpenStreetMap"""
    return render_template(
        'user/location_picker.html',
        page_title='Pick Location'
    )


@bp.route('/api/merchants/nearby', methods=['POST'])
@csrf.exempt
@login_required
def get_nearby_merchants():
    """Get nearby merchants based on user location and filters"""
    try:
        data = request.get_json() or {}
        
        # Extract parameters
        user_lat = float(data.get('latitude', 14.5995))
        user_lon = float(data.get('longitude', 120.9842))
        max_distance = float(data.get('max_distance', 50))
        search_query = data.get('search', '').lower()
        service_filter = data.get('service', '').lower()
        sort_by = data.get('sort_by', 'distance')
        
        print(f"[DEBUG] Nearby merchants request: lat={user_lat}, lon={user_lon}, dist={max_distance}, search={search_query}, service={service_filter}")
        
        # Get all approved merchants with coordinates
        merchants = Merchant.query.filter(
            Merchant.application_status == 'approved',
            Merchant.latitude.isnot(None),
            Merchant.longitude.isnot(None)
        ).all()
        
        print(f"[DEBUG] Found {len(merchants)} approved merchants with coordinates")
        
        nearby_list = []
        from datetime import datetime
        
        for merchant in merchants:
            # Calculate road distance (more accurate than straight-line)
            distance = get_road_distance(
                user_lat, user_lon,
                float(merchant.latitude), float(merchant.longitude)
            )
            
            # Filter by max_distance
            if distance > max_distance:
                continue
            
            # Apply search filter
            if search_query:
                if not (search_query in merchant.business_name.lower() or
                        search_query in (merchant.city or '').lower()):
                    continue
            
            # Apply service filter
            if service_filter:
                services_str = ' '.join([s.lower() for s in (merchant.services_offered or [])])
                if service_filter not in services_str:
                    continue
            
            # Check if open using same logic as store_public
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
            
            # Default rating if no reviews
            avg_rating = 4.5
            review_count = 0
            
            # Extract min and max prices from service_pricing JSON
            min_price = 999999
            max_price = 0
            service_pricing = merchant.get_service_pricing()
            
            if service_pricing:
                # Handle new nested structure: service -> duration -> size -> price
                for service_name, service_data in service_pricing.items():
                    if isinstance(service_data, dict):
                        # Check for new nested structure (duration -> size -> price)
                        for duration_key, duration_data in service_data.items():
                            if isinstance(duration_data, dict):
                                # Could be size->price or other structure
                                for size_or_key, value in duration_data.items():
                                    if isinstance(value, (int, float)) and value > 0:
                                        min_price = min(min_price, value)
                                        max_price = max(max_price, value)
            
            # Reset to 0 if no prices found
            if min_price == 999999:
                min_price = 0
            
            merchant_data = {
                'id': merchant.id,
                'business_name': merchant.business_name,
                'business_category': merchant.business_category,
                'city': merchant.city,
                'province': merchant.province,
                'barangay': merchant.barangay or '',
                'contact_email': merchant.contact_email,
                'contact_phone': merchant.contact_phone,
                'services_offered': merchant.services_offered or [],
                'pets_accepted': merchant.pets_accepted or [],
                'min_price': int(min_price),
                'max_price': int(max_price),
                'opening_time': merchant.opening_time or '09:00',
                'closing_time': merchant.closing_time or '18:00',
                'is_open': is_open,
                'distance': round(distance, 1),
                'rating': round(avg_rating, 1),
                'reviews': review_count,
                'response_time': '2h',
                'completion_rate': 90,
                'latitude': float(merchant.latitude),
                'longitude': float(merchant.longitude),
                'service_pricing': service_pricing or {}
            }
            nearby_list.append(merchant_data)
        
        print(f"[DEBUG] After filtering: {len(nearby_list)} merchants within {max_distance}km")
        
        # Sort results
        if sort_by == 'distance':
            nearby_list.sort(key=lambda x: x['distance'])
        elif sort_by == 'rating':
            nearby_list.sort(key=lambda x: x['rating'], reverse=True)
        elif sort_by == 'name':
            nearby_list.sort(key=lambda x: x['business_name'])
        
        return jsonify({
            'success': True,
            'merchants': nearby_list,
            'count': len(nearby_list)
        })
        
    except Exception as e:
        print(f"[ERROR] get_nearby_merchants: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'merchants': []
        }), 500


@bp.route('/api/location/reverse-geocode', methods=['POST'])
@csrf.exempt
def reverse_geocode():
    """Reverse geocode coordinates to get human-readable location"""
    try:
        data = request.get_json() or {}
        
        lat = data.get('latitude')
        lon = data.get('longitude')
        
        if lat is None or lon is None:
            return jsonify({
                'success': False,
                'error': 'Missing latitude or longitude'
            }), 400
        
        # Call Nominatim API from backend to avoid CORS issues
        nominatim_url = f'https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1&zoom=10&limit=1'
        
        response = requests.get(nominatim_url, timeout=5, headers={
            'User-Agent': 'Petsona-App'
        })
        
        if response.status_code != 200:
            return jsonify({
                'success': False,
                'locationText': 'Your Location'
            }), 200
        
        data = response.json()
        address = data.get('address', {})
        
        # Build human-readable location - prioritize different address parts
        location_parts = []
        
        # For Philippines: barangay, city, province/region
        barangay = address.get('suburb') or address.get('hamlet') or address.get('neighbourhood') or address.get('village') or ''
        city = address.get('city') or address.get('town') or address.get('municipal_city') or ''
        province = address.get('state') or address.get('province') or address.get('region') or ''
        country = address.get('country') or ''
        
        # Build location string prioritizing the most relevant parts
        if barangay and barangay.strip():
            location_parts.append(barangay.strip())
        if city and city != barangay and city.strip():
            location_parts.append(city.strip())
        if province and province != city and province != barangay and province.strip():
            location_parts.append(province.strip())
        
        if location_parts:
            location_text = ', '.join(location_parts)
        elif city:
            location_text = city
        elif province:
            location_text = province
        else:
            location_text = country or 'Your Location'
        
        return jsonify({
            'success': True,
            'locationText': location_text
        }), 200
        
    except requests.Timeout:
        return jsonify({
            'success': False,
            'locationText': 'Your Location'
        }), 200
    except Exception as e:
        print(f"[ERROR] reverse_geocode: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'locationText': 'Your Location'
        }), 200


# ========== BOOKING ROUTES ==========

@bp.route('/bookings')
@login_required
@user_required
def my_bookings():
    """Display user's bookings"""
    from app.models.booking import Booking
    from app.utils.qr_generator import qr_generator
    
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    
    query = Booking.query.filter_by(user_id=current_user.id, deleted_at=None)
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    bookings = query.order_by(Booking.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    # Generate QR codes for each booking
    # Generate QR codes for each booking
    bookings_with_qr = []
    for booking in bookings.items:
        qr_url = qr_generator.generate_booking_qr(
            booking_id=booking.id,
            booking_number=booking.booking_number,
            confirmation_code=booking.confirmation_code,
            merchant_name=booking.merchant.business_name if booking.merchant else 'Unknown',
            appointment_date=booking.appointment_date.strftime('%b %d, %Y'),
            appointment_time=booking.appointment_time
        )
        booking.qr_code_url = qr_url
        bookings_with_qr.append(booking)
    
    bookings.items = bookings_with_qr
    
    return render_template('user/my_bookings.html', 
                         bookings=bookings,
                         status_filter=status_filter)


@bp.route('/booking/<int:booking_id>')
@login_required
@user_required
def booking_details(booking_id):
    """Display booking details"""
    from app.models.booking import Booking
    
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first()
    
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('user.my_bookings'))
    
    return render_template('user/booking_details.html', booking=booking)


@bp.route('/booking/<int:booking_id>/receipt')
@login_required
@user_required
def booking_receipt(booking_id):
    """Display booking receipt as digital receipt (can be printed/saved as PNG or PDF)"""
    from app.models.booking import Booking
    from app.utils.qr_generator import qr_generator
    
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first()
    
    if not booking:
        abort(404)
    
    # Generate QR code for receipt
    qr_url = qr_generator.generate_booking_qr(
        booking_id=booking.id,
        booking_number=booking.booking_number,
        confirmation_code=booking.confirmation_code,
        merchant_name=booking.merchant.business_name if booking.merchant else 'Unknown',
        appointment_date=booking.appointment_date.strftime('%b %d, %Y'),
        appointment_time=booking.appointment_time
    )
    booking.qr_code_url = qr_url
    
    return render_template('user/receipt.html', booking=booking)


@bp.route('/booking/<int:booking_id>/cancel', methods=['POST'])
@login_required
@user_required
def cancel_booking(booking_id):
    """Cancel a booking"""
    from app.models.booking import Booking
    from app.models.audit_log import AuditLog
    from datetime import datetime
    
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first()
    
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('user.my_bookings'))
    
    if not booking.can_be_cancelled:
        flash('This booking cannot be cancelled.', 'danger')
        return redirect(url_for('user.booking_details', booking_id=booking_id))
    
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"CANCELLING BOOKING {booking_id}")
        logger.info(f"{'='*60}")
        
        cancellation_reason = request.form.get('cancellation_reason', '').strip()
        
        # Step 1: Update booking status
        booking.status = 'cancelled'
        booking.cancellation_date = get_ph_datetime()
        booking.cancellation_reason = cancellation_reason
        
        db.session.commit()
        logger.info(f"[STEP 1] ✓ Booking status updated to 'cancelled'")
        
        # Step 2: Log the action
        audit_log = AuditLog(
            event='booking_cancelled_by_customer',
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=get_ph_datetime()
        )
        audit_log.set_details({
            'booking_id': booking.id,
            'booking_number': booking.booking_number,
            'cancelled_at': get_ph_datetime().isoformat()
        })
        db.session.add(audit_log)
        db.session.commit()
        logger.info(f"[STEP 2] ✓ Audit log created and committed")
        
        # Step 3: Send notification to merchant about booking cancellation
        logger.info(f"[STEP 3] Starting notification creation...")
        
        from app.models.merchant import Merchant
        merchant = Merchant.query.filter_by(id=booking.merchant_id).first()
        
        logger.info(f"[STEP 3a] Merchant lookup: booking.merchant_id={booking.merchant_id}")
        logger.info(f"[STEP 3b] Merchant found: {merchant}")
        
        if merchant:
            logger.info(f"[STEP 3c] Merchant ID: {merchant.id}, Merchant user_id: {merchant.user_id}")
            
            if merchant.user_id:
                logger.info(f"[STEP 3d] Creating notification for merchant user {merchant.user_id}...")
                
                result = NotificationManager.notify_booking_cancelled_by_customer(
                    user_id=merchant.user_id,
                    booking_number=booking.booking_number,
                    customer_name=booking.customer_name or current_user.email,
                    related_booking_id=booking.id,
                    from_user_id=current_user.id
                )
                
                if result:
                    logger.info(f"[STEP 3e] ✓ Notification created and committed - ID: {result.id}")
                else:
                    logger.error(f"[STEP 3e] ✗ NotificationManager returned None")
            else:
                logger.warning(f"[STEP 3d] ⚠️  Merchant user_id is NULL - Cannot notify merchant")
        else:
            logger.warning(f"[STEP 3c] ⚠️  Merchant not found for merchant_id {booking.merchant_id}")
        
        logger.info(f"[FINAL] ✓ Booking cancellation complete")
        logger.info(f"{'='*60}\n")
        
        flash('Booking cancelled successfully.', 'success')
    except Exception as e:
        logger.error(f"[ERROR] Exception during booking cancellation: {str(e)}", exc_info=True)
        db.session.rollback()
        flash(f'Error cancelling booking: {str(e)}', 'danger')
    
    return redirect(url_for('user.my_bookings'))

@bp.route('/booking/<int:booking_id>/appeal', methods=['POST'])
@login_required
@user_required
def appeal_no_show(booking_id):
    """Submit an appeal for a no-show booking status"""
    from app.models.booking import Booking
    from app.models.audit_log import AuditLog
    
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first()
    
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found'}), 404
    
    # Only allow appeal for no-show bookings
    if booking.status != 'no-show':
        return jsonify({'success': False, 'message': 'This booking cannot be appealed'}), 403
    
    # Check if appeal was already submitted
    if booking.appeal_submitted_at:
        return jsonify({'success': False, 'message': 'Appeal has already been submitted for this booking'}), 400
    
    try:
        data = request.get_json()
        appeal_reason = data.get('appeal_reason', '').strip()
        
        if not appeal_reason:
            return jsonify({'success': False, 'message': 'Appeal reason is required'}), 400
        
        # Save appeal
        booking.appeal_reason = appeal_reason
        booking.appeal_submitted_at = get_ph_datetime()
        
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            event='booking_no_show_appeal_submitted',
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=get_ph_datetime()
        )
        audit_log.set_details({
            'booking_id': booking.id,
            'booking_number': booking.booking_number,
            'merchant_id': booking.merchant_id,
            'appeal_submitted_at': get_ph_datetime().isoformat()
        })
        db.session.add(audit_log)
        db.session.commit()
        
        # TODO: Send notification to merchant about the appeal
        
        return jsonify({'success': True, 'message': 'Appeal submitted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error submitting appeal for booking {booking_id}: {str(e)}')
        return jsonify({'success': False, 'message': 'Error submitting appeal. Please try again.'}), 500


@bp.route('/booking/<int:booking_id>/delete', methods=['POST'])
@login_required
@user_required
def delete_booking(booking_id):
    """Soft delete a booking (for rejected or cancelled bookings)"""
    from app.models.booking import Booking
    from app.models.audit_log import AuditLog
    
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first()
    
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('user.my_bookings'))
    
    # Only allow deletion of rejected or cancelled bookings
    if booking.status not in ['rejected', 'cancelled']:
        flash('This booking cannot be deleted.', 'danger')
        return redirect(url_for('user.my_bookings'))
    
    try:
        booking.deleted_at = get_ph_datetime()
        
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            event='booking_deleted_by_customer',
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=get_ph_datetime()
        )
        audit_log.set_details({
            'booking_id': booking.id,
            'booking_number': booking.booking_number,
            'deleted_at': get_ph_datetime().isoformat()
        })
        db.session.add(audit_log)
        db.session.commit()
        
        flash('Booking deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting booking: {str(e)}', 'danger')
    
    return redirect(url_for('user.my_bookings'))

@bp.route('/booking/<int:booking_id>/download-receipt', methods=['GET'])
@login_required
@user_required
def download_receipt(booking_id):
    """Download digital receipt for confirmed or completed booking"""
    from app.models.booking import Booking
    from io import BytesIO
    from flask import make_response
    
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first()
    
    if not booking:
        flash('Booking not found', 'danger')
        return redirect(url_for('user.my_bookings'))
    
    # Allow for confirmed or completed bookings
    if booking.status not in ['confirmed', 'completed']:
        flash('Only confirmed or completed bookings can download receipts', 'danger')
        return redirect(url_for('user.my_bookings'))
    
    try:
        # Generate receipt text
        merchant_name = booking.merchant.business_name if booking.merchant else 'N/A'
        receipt_text = f"""
═══════════════════════════════════════════════════════
                    PETSONA RECEIPT
═══════════════════════════════════════════════════════

BOOKING NUMBER: {booking.booking_number}
CONFIRMATION CODE: {booking.confirmation_code}

═══════════════════════════════════════════════════════
MERCHANT DETAILS
═══════════════════════════════════════════════════════
Business: {merchant_name}

═══════════════════════════════════════════════════════
CUSTOMER DETAILS
═══════════════════════════════════════════════════════
Name: {booking.customer_name}
Email: {booking.customer_email}
Phone: {booking.customer_phone}

═══════════════════════════════════════════════════════
APPOINTMENT DETAILS
═══════════════════════════════════════════════════════
Date: {booking.appointment_date.strftime('%B %d, %Y')}
Time: {booking.appointment_time}
Total Pets: {booking.total_pets}

═══════════════════════════════════════════════════════
PRICING
═══════════════════════════════════════════════════════
Total Amount: ₱{booking.total_amount:,.2f}

Status: {booking.status.upper()}

═══════════════════════════════════════════════════════
Booking Date: {booking.created_at.strftime('%B %d, %Y at %I:%M %p')}
═══════════════════════════════════════════════════════

Thank you for choosing Petsona!
"""
        
        # Create response with text file
        response = make_response(receipt_text)
        response.headers['Content-Disposition'] = f'attachment; filename=receipt_{booking.booking_number}.txt'
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        
        # Log the download
        from app.models.audit_log import AuditLog
        audit_log = AuditLog(
            event='booking_receipt_downloaded',
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=get_ph_datetime()
        )
        audit_log.set_details({
            'booking_id': booking.id,
            'booking_number': booking.booking_number,
            'booking_status': booking.status
        })
        db.session.add(audit_log)
        db.session.commit()
        
        return response
        
    except Exception as e:
        logger.error(f'Error downloading receipt for booking {booking_id}: {str(e)}')
        flash('Error downloading receipt. Please try again.', 'danger')
        return redirect(url_for('user.my_bookings'))

