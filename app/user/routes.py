from flask import render_template, flash, redirect, url_for, request, abort, jsonify, current_app, send_file, session
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]
from app.user import bp
from app.decorators import user_required
from werkzeug.utils import secure_filename
from app.models import Species, Breed, Merchant, MatchHistory, Vote, MyPet
from app.models.my_pet import validate_pet_name, validate_enum_field
from app import db
from app.extensions import csrf
from app.utils.notification_manager import NotificationManager
from app.utils.audit import log_event, log_action_with_changes, log_data_access
from app.utils.compatibility_engine import calculate_compatibility, QUESTION_WEIGHTS, CATEGORY_WEIGHTS
from app.utils.big_five_personality import (
    get_breed_big_five_scores,
    calculate_big_five_compatibility,
    integrate_big_five_into_compatibility,
    calculate_user_big_five_scores,
)
from app.utils.pet_owner_compatibility import calculate_pet_owner_compatibility as calc_pet_compatibility
from sqlalchemy import func # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta
import pytz
import logging
import qrcode
import io
import base64
from urllib.parse import quote_plus
from app.extensions import limiter

PH_TZ = pytz.timezone('Asia/Manila')

def _normalize_to_ph_time(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        try:
            return PH_TZ.localize(dt)
        except Exception:
            return dt.replace(tzinfo=PH_TZ)
    return dt.astimezone(PH_TZ)

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
@limiter.exempt
def dashboard():
    from app.models.breed import Breed
    from app.models.user import User
    from app.models.booking import Booking
    from datetime import datetime, timedelta
    
    # Log dashboard access
    log_data_access('user_dashboard', current_user.id, access_type='view')
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
    ).order_by(Species.heart_vote_count.desc()).limit(8).all()
    
    # ======================== TOP BREEDS SECTION ========================
    # Get top 3 breeds by vote count
    top_breeds = Breed.query.filter(
        Breed.deleted_at.is_(None)
    ).order_by(Breed.heart_vote_count.desc()).limit(8).all()
    
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

def _format_emv_tag(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def _normalize_ph_number(number: str) -> str:
    digits = ''.join(ch for ch in (number or '') if ch.isdigit())
    if digits.startswith('0'):
        return f"63{digits[1:]}"
    if digits.startswith('63'):
        return digits
    return digits


def _crc16_ccitt(data: str) -> str:
    crc = 0xFFFF
    polynomial = 0x1021
    for byte in data.encode('utf-8'):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ polynomial) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def _build_gcash_qr_text(plan: str, amount: float) -> str:
    gcash_raw = current_app.config.get('GCASH_PHONE') or '09977030323'
    gcash_number = _normalize_ph_number(gcash_raw)
    gcash_name = current_app.config.get('GCASH_NAME') or 'PetSona'

    merchant_info_value = (
        _format_emv_tag('00', 'A000000677010112') +
        _format_emv_tag('01', gcash_number)
    )

    payload = (
        _format_emv_tag('00', '01') +
        _format_emv_tag('01', '12') +
        _format_emv_tag('29', merchant_info_value) +
        _format_emv_tag('52', '0000') +
        _format_emv_tag('53', '608') +
        _format_emv_tag('54', f"{amount:.2f}") +
        _format_emv_tag('58', 'PH') +
        _format_emv_tag('59', gcash_name[:25].upper()) +
        _format_emv_tag('60', 'MANILA')
    )

    payload_with_crc_placeholder = payload + '6304'
    crc = _crc16_ccitt(payload_with_crc_placeholder)
    return payload_with_crc_placeholder + crc


def _generate_gcash_qr_png_bytes(plan: str, amount: float) -> bytes:
    qr_text = _build_gcash_qr_text(plan, amount)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#000000", back_color="white").convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def _generate_gcash_qr_data_url(plan: str, amount: float) -> str:
    encoded = base64.b64encode(_generate_gcash_qr_png_bytes(plan, amount)).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def _generate_gcash_deeplink(gcash_phone: str, amount: float, plan: str) -> str:
    normalized = _normalize_ph_number(gcash_phone)
    note = quote_plus(f"PetSona {plan.title()}")
    return f"gcash://pay?phone={normalized}&amount={amount:.2f}&currency=PHP&note={note}"

@bp.route('/subscription', methods=['GET', 'POST'])
@login_required
def subscription():
    """View and choose a subscription plan."""
    if current_user.is_admin:
        flash('Admins already have full access.', 'info')
        return redirect(url_for('user.dashboard'))

    payment_qr = None
    selected_plan = None
    payment_amount = None
    payment_due_text = None

    if current_user.is_pending_subscription:
        pending_due = _normalize_to_ph_time(current_user.subscription_payment_due)
        if pending_due and pending_due < get_ph_datetime():
            current_user.cancel_subscription()
            db.session.add(current_user)
            db.session.commit()
            flash('Your pending subscription request has expired. Please choose a plan again.', 'warning')
            return redirect(url_for('user.subscription'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'confirm_payment':
            if not current_user.is_pending_subscription:
                flash('There is no pending subscription to confirm.', 'danger')
                return redirect(url_for('user.subscription'))

            pending_due = _normalize_to_ph_time(current_user.subscription_payment_due)
            if pending_due and pending_due < get_ph_datetime():
                current_user.cancel_subscription()
                db.session.add(current_user)
                db.session.commit()
                flash('Your payment window has expired. Please choose a plan again.', 'warning')
                return redirect(url_for('user.subscription'))

            current_user.activate_pending_subscription()
            db.session.add(current_user)
            db.session.commit()
            flash('Payment confirmed. Your subscription is now active.', 'success')
            return redirect(url_for('user.dashboard'))

        if action == 'cancel_subscription':
            current_user.cancel_subscription()
            db.session.add(current_user)
            db.session.commit()
            flash('Your subscription request has been cancelled.', 'info')
            return redirect(url_for('user.dashboard'))

        selected_plan = (request.form.get('plan') or 'basic').lower()
        if selected_plan not in ['basic', 'premium', 'pro']:
            flash('Please choose a valid plan.', 'danger')
            return redirect(url_for('user.subscription'))

        if selected_plan == 'basic':
            current_user.set_free_basic()
            db.session.add(current_user)
            db.session.commit()
            flash('You are now on the Basic plan.', 'success')
            return redirect(url_for('user.dashboard'))

        payment_amount = 75.0 if selected_plan == 'premium' else 500.0
        current_user.set_pending_subscription(selected_plan, get_ph_datetime() + timedelta(days=1))
        db.session.add(current_user)
        db.session.commit()
        payment_qr = _generate_gcash_qr_data_url(selected_plan, payment_amount)
        gcash_pay_url = _generate_gcash_deeplink(current_app.config.get('GCASH_PHONE') or '09977030323', payment_amount, selected_plan)
        payment_due_text = current_user.subscription_payment_due.strftime('%B %d, %Y %I:%M %p')
        flash('Your subscription is pending payment. Complete payment within 1 day and confirm it below.', 'info')
    if current_user.is_pending_subscription and payment_qr is None:
        pending_plan = current_user.pending_subscription_plan
        payment_amount = 75.0 if pending_plan == 'premium' else 500.0
        payment_qr = _generate_gcash_qr_data_url(pending_plan, payment_amount)
        gcash_pay_url = _generate_gcash_deeplink(current_app.config.get('GCASH_PHONE') or '09977030323', payment_amount, pending_plan)
        payment_due_text = current_user.subscription_payment_due.strftime('%B %d, %Y %I:%M %p') if current_user.subscription_payment_due else None
        selected_plan = pending_plan

    if 'gcash_pay_url' not in locals():
        gcash_pay_url = None

    return render_template(
        'user/subscription.html',
        page_title='Subscription Plans',
        payment_qr=payment_qr,
        pending_plan=selected_plan,
        payment_amount=payment_amount,
        payment_due_text=payment_due_text,
        gcash_phone=current_app.config.get('GCASH_PHONE') or '09977030323',
        gcash_pay_url=gcash_pay_url
    )


@bp.route('/my-pets')
@login_required
def my_pets_index():
    pets = MyPet.query.filter_by(user_id=current_user.id, is_active=True).order_by(MyPet.created_at.desc()).all()
    return render_template('user/my_pets.html', page_title='My Pets', pets=pets)


@bp.route('/my-pets/upgrade-required')
@login_required
def my_pets_upgrade_required():
    """Check subscription and handle upgrade prompt for My Pets access"""
    if current_user.subscription_plan == 'basic':
        flash('Upgrade your plan to unlock all features and manage unlimited pets!', 'warning')
        return redirect(url_for('user.subscription'))
    return redirect(url_for('user.my_pets_index'))


@bp.route('/matching-quiz/upgrade-required')
@login_required
def matching_quiz_upgrade_required():
    """Check subscription and handle upgrade prompt for Find Me Pet access"""
    if current_user.subscription_plan == 'basic':
        flash('Upgrade your plan to use our intelligent pet matching system!', 'warning')
        return redirect(url_for('user.subscription'))
    return redirect(url_for('matching.quiz'))


@bp.route('/matching-quiz/breed/<int:breed_id>/upgrade-required')
@login_required
def matching_quiz_specific_upgrade_required(breed_id):
    """Check subscription and handle upgrade prompt for breed-specific matching"""
    if current_user.subscription_plan == 'basic':
        flash('Upgrade your plan to use our intelligent pet matching system!', 'warning')
        return redirect(url_for('user.subscription'))
    return redirect(url_for('matching.quiz_specific', breed_id=breed_id))


@bp.route('/api/my-pets', methods=['GET'])
@login_required
def api_my_pets():
    """API endpoint to get pets as JSON"""
    pets = MyPet.query.filter_by(user_id=current_user.id, is_active=True).order_by(MyPet.created_at.desc()).all()
    return jsonify({
        'success': True,
        'pets': [pet.as_dict for pet in pets]
    })


@bp.route('/my-pets/save', methods=['POST'])
@csrf.exempt
@login_required
def my_pets_save():
    """Save new or update existing pet - optimized and scalable."""
    try:
        pet_id = request.form.get('pet_id', '').strip()
        pet_name = request.form.get('name', '').strip()
        
        # Validate name
        if not pet_name or not validate_pet_name(pet_name):
            return jsonify({'success': False, 'message': 'Invalid pet name'}), 400
        
        # Get or create pet
        if pet_id:
            pet = MyPet.query.filter_by(id=pet_id, user_id=current_user.id, is_active=True).first()
            if not pet:
                return jsonify({'success': False, 'message': 'Pet not found'}), 404
            is_update = True
        else:
            pet = MyPet(user_id=current_user.id)
            is_update = False

        # Efficiently update all fields
        pet.name = pet_name
        pet.species = request.form.get('species', '').strip() or None
        pet.breed = request.form.get('breed', '').strip() or None
        pet.age = request.form.get('age', '').strip() or None
        pet.sex = validate_enum_field(request.form.get('sex', 'Unknown'), ['Male', 'Female', 'Unknown'], 'Unknown')
        pet.weight = request.form.get('weight', '').strip() or None
        
        # Behavior fields
        pet.activity_level = validate_enum_field(request.form.get('activity_level', 'Moderately active'), 
            ['Very calm', 'Moderately active', 'Very energetic'], 'Moderately active')
        pet.animal_social_behavior = validate_enum_field(request.form.get('animal_social_behavior', 'Neutral'),
            ['Aggressive or territorial', 'Nervous or avoidant', 'Neutral', 'Friendly and playful'], 'Neutral')
        pet.people_sociality = validate_enum_field(request.form.get('people_sociality', 'Selectively friendly'),
            ['Very shy', 'Selectively friendly', 'Friendly with most people', 'Extremely social'], 'Selectively friendly')
        pet.independence_level = validate_enum_field(request.form.get('independence_level', 'Balanced'),
            ['Very dependent/clingy', 'Balanced', 'Very independent'], 'Balanced')
        pet.adaptability = validate_enum_field(request.form.get('adaptability', 'Needs time to adjust'),
            ['Gets stressed easily', 'Needs time to adjust', 'Adapts quickly'], 'Needs time to adjust')
        pet.affection_level = validate_enum_field(request.form.get('affection_level', 'Occasionally affectionate'),
            ['Rarely affectionate', 'Occasionally affectionate', 'Very affectionate'], 'Occasionally affectionate')
        pet.alone_behavior = validate_enum_field(request.form.get('alone_behavior', 'Usually stays calm'),
            ['Gets anxious or destructive', 'Usually stays calm', 'Prefers being alone'], 'Usually stays calm')
        pet.personality_type = validate_enum_field(request.form.get('personality_type', 'Calm and relaxed'),
            ['Calm and relaxed', 'Energetic and playful', 'Curious and adventurous', 'Protective and alert', 'Independent and reserved', 'Affectionate and clingy'], 'Calm and relaxed')
        pet.trainability = validate_enum_field(request.form.get('trainability', 'Learns gradually'),
            ['Difficult to train', 'Learns gradually', 'Learns quickly'], 'Learns gradually')
        pet.companion_preference = validate_enum_field(request.form.get('companion_preference', 'Maybe'),
            ['Probably not', 'Maybe', 'Most likely yes'], 'Maybe')
        
        # Big Five (1-5 scale)
        try:
            pet.big_five_openness = max(1, min(5, int(request.form.get('big_five_openness', 3) or 3)))
            pet.big_five_conscientiousness = max(1, min(5, int(request.form.get('big_five_conscientiousness', 3) or 3)))
            pet.big_five_extraversion = max(1, min(5, int(request.form.get('big_five_extraversion', 3) or 3)))
            pet.big_five_agreeableness = max(1, min(5, int(request.form.get('big_five_agreeableness', 3) or 3)))
            pet.big_five_neuroticism = max(1, min(5, int(request.form.get('big_five_neuroticism', 2) or 2)))
        except (ValueError, TypeError):
            pass
        
        # Handle photo upload - FIXED to save properly
        file = request.files.get('photo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            if filename:
                timestamp = int(get_ph_datetime().timestamp())
                filename_with_ts = f"{timestamp}_{filename}"
                upload_dir = os.path.join(current_app.static_folder, 'uploads', 'pets')
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename_with_ts)
                try:
                    file.save(filepath)
                    pet.photo_url = f'uploads/pets/{filename_with_ts}'
                except Exception as e:
                    logger.warning(f'Photo upload error: {str(e)}')
        
        # Save to database
        db.session.add(pet)
        db.session.commit()
        
        # Log action
        log_action_with_changes('pet_' + ('updated' if is_update else 'created'), 
                              current_user.id, f'Pet: {pet.name}', {})
        
        # Flash message for page reload
        flash(f'✓ {pet.name} saved successfully!', 'success')
        
        return jsonify({
            'success': True,
            'message': f'✓ {pet.name} saved successfully!',
            'pet': pet.as_dict,
            'is_update': is_update
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Pet save error: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Failed to save pet'
        }), 500


@bp.route('/my-pets/<int:id>/delete', methods=['POST'])
@csrf.exempt
@login_required
def my_pets_delete(id):
    """Soft delete a pet (mark as inactive but keep data in database)."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    try:
        # Get pet and verify ownership
        pet = MyPet.query.filter_by(id=id, user_id=current_user.id, is_active=True).first()
        if not pet:
            error_msg = 'Pet not found.'
            if is_ajax:
                return jsonify({'success': False, 'message': error_msg}), 404
            flash(error_msg, 'danger')
            return redirect(url_for('user.my_pets_index'))
        
        # Soft delete the pet
        pet_name = pet.name
        pet.soft_delete()
        db.session.add(pet)
        db.session.commit()
        
        # Log the action
        log_action_with_changes('pet_deleted', current_user.id, f'Pet ID: {id}', {'name': pet_name})
        
        # Prepare response
        message = f'✓ {pet_name} removed successfully!'
        
        # Flash message for page reload (works for AJAX too)
        flash(message, 'warning')
        
        if is_ajax:
            return jsonify({'success': True, 'message': message}), 200
        
        return redirect(url_for('user.my_pets_index'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Pet delete error for user {current_user.id}: {str(e)}', exc_info=True)
        error_msg = 'Error removing pet. Please try again.'
        if is_ajax:
            return jsonify({'success': False, 'message': error_msg}), 500
        flash(error_msg, 'danger')
        return redirect(url_for('user.my_pets_index'))


@bp.route('/test/pet-form-diagnostics', methods=['GET'])
@login_required
def test_pet_form_diagnostics():
    """Diagnostic endpoint to test if pet form handler works"""
    try:
        # Test imports
        from app.models.my_pet import validate_pet_name, validate_enum_field, MyPet
        
        # Test validation functions
        name_valid = validate_pet_name("Fluffy")
        enum_valid = validate_enum_field('Moderately active', ['Very calm', 'Moderately active', 'Very energetic'], 'Moderately active')
        
        # Test model update
        test_pet = MyPet(user_id=current_user.id, name="DiagnosticTest")
        test_pet.update_from_dict({
            'name': 'TestPet',
            'species': 'Cat',
            'breed': 'Persian',
            'activity_level': 'Moderately active',
            'big_five_openness': 4
        })
        test_dict = test_pet.as_dict
        
        return jsonify({
            'success': True,
            'message': 'All pet form diagnostics passed ✓',
            'tests': {
                'validate_pet_name': name_valid,
                'validate_enum_field': enum_valid,
                'pet_update_from_dict': test_pet.name == 'TestPet',
                'as_dict_serializable': isinstance(test_dict, dict),
                'keys_in_response': len(test_dict) > 20
            }
        }), 200
    except Exception as e:
        import traceback
        logger.error(f'Diagnostic test failed: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'type': type(e).__name__,
            'details': traceback.format_exc()
        }), 500


@bp.route('/my-pets/<int:pet_id>/quiz', methods=['GET'])
@login_required
@user_required
def my_pets_quiz(pet_id):
    """Display quiz page for a specific pet."""
    pet = MyPet.query.filter_by(id=pet_id, user_id=current_user.id, is_active=True).first()
    if not pet:
        flash('Pet not found.', 'danger')
        return redirect(url_for('user.my_pets_index'))
    
    return render_template('user/my_pets_quiz.html', pet=pet)


@bp.route('/my-pets/quiz-submit', methods=['POST'])
@login_required
@user_required
def my_pets_quiz_submit():
    """Process pet owner compatibility quiz and save results."""
    from flask import session
    
    pet_id = request.form.get('pet_id')
    pet = MyPet.query.get(pet_id) if pet_id else None
    
    try:
        if not pet or pet.user_id != current_user.id:
            flash('Pet not found.', 'danger')
            return redirect(url_for('user.my_pets_index'))
        
        # Collect all user answers from form
        user_answers = {}
        for key, value in request.form.items():
            if key not in ['pet_id', 'csrf_token'] and value:
                user_answers[key] = value
        
        # Calculate Big Five scores from answers
        user_big_five = calculate_user_big_five_scores(user_answers)
        
        # NOTE: DO NOT modify pet's Big Five scores!
        # Pet already has its own Big Five scores set in the database
        # Only use them for compatibility calculation, do not overwrite
        
        # Calculate overall compatibility using new engine
        # Pet's existing Big Five scores are used from the database
        compatibility_result = calc_pet_compatibility(pet, user_answers)
        
        # Store in session for display on results page
        session[f'pet_{pet_id}_compatibility'] = compatibility_result
        session[f'pet_{pet_id}_answers'] = user_answers
        session.modified = True
        
        flash('✓ Quiz completed! Here\'s your compatibility analysis.', 'success')
        return redirect(url_for('user.my_pets_match_results', pet_id=pet_id))
        
    except ValueError as e:
        flash('Invalid answer format. Please try again.', 'warning')
        logger.error(f'ValueError in my_pets_quiz_submit: {str(e)}')
    except Exception as e:
        flash('Could not process your quiz. Please try again.', 'warning')
        logger.error(f'Error in my_pets_quiz_submit: {str(e)}')

    return redirect(url_for('user.my_pets_index'))


@bp.route('/my-pets/<int:pet_id>/match-results', methods=['GET'])
@login_required
@user_required
def my_pets_match_results(pet_id):
    """Display pet compatibility and matching results."""
    from flask import session
    from app.matching.routes import extract_big_five_from_answers
    
    pet = MyPet.query.filter_by(id=pet_id, user_id=current_user.id, is_active=True).first()
    if not pet:
        flash('Pet not found.', 'danger')
        return redirect(url_for('user.my_pets_index'))
    
    try:
        # Get compatibility result from session
        compatibility_result = session.get(f'pet_{pet_id}_compatibility')
        user_answers = session.get(f'pet_{pet_id}_answers', {})
        
        if not compatibility_result:
            # Fallback: Calculate using pet owner compatibility engine
            compatibility_result = calc_pet_compatibility(pet, user_answers) if user_answers else None
        
        if not compatibility_result:
            # If still no result, return basic pet info
            compatibility_result = {
                'overall_score': 70,
                'compatibility_level': 'Moderate',
                'compatibility_emoji': '🟠',
                'lifestyle_score': 70,
                'personality_score': 70,
                'strengths': ['Pet awaiting compatibility assessment'],
                'considerations': [],
                'recommendations': ['Complete the pet compatibility quiz for detailed insights'],
            }
        
        # Extract Big Five personality scores from user answers
        big_five_scores = extract_big_five_from_answers(user_answers) if user_answers else {}
        
        # Get scores directly from compatibility result (already calculated by pet_owner_compatibility)
        lifestyle_score = compatibility_result.get('lifestyle_score', 70)
        personality_score = compatibility_result.get('personality_score', 70)
        overall_score = compatibility_result.get('overall_score', 70)
        
        # Prepare result for template with proper structure
        result = {
            'pet_name': pet.name,
            'pet_species': pet.species,
            'pet_photo_url': pet.photo_url,
            'overall_score': overall_score,
            'compatibility_level': compatibility_result.get('compatibility_level', 'Moderate'),
            'compatibility_emoji': compatibility_result.get('compatibility_emoji', '🟠'),
            'lifestyle_score': lifestyle_score,
            'personality_score': personality_score,
            'category_breakdown': compatibility_result.get('category_breakdown', {}),
            # Nest insights for template compatibility
            'insights': {
                'strengths': compatibility_result.get('strengths', []),
                'considerations': compatibility_result.get('considerations', []),
                'recommendations': compatibility_result.get('recommendations', []),
            },
            'pet_big_five': {
                'Openness': pet.big_five_openness or 3,
                'Conscientiousness': pet.big_five_conscientiousness or 3,
                'Extraversion': pet.big_five_extraversion or 3,
                'Agreeableness': pet.big_five_agreeableness or 3,
                'Neuroticism': pet.big_five_neuroticism or 2,
            },
            'pet_traits': {
                'activity_level': pet.activity_level or 'N/A',
                'animal_social_behavior': pet.animal_social_behavior or 'N/A',
                'people_sociality': pet.people_sociality or 'N/A',
                'independence_level': pet.independence_level or 'N/A',
                'adaptability': pet.adaptability or 'N/A',
                'affection_level': pet.affection_level or 'N/A',
                'alone_behavior': pet.alone_behavior or 'N/A',
                'personality_type': pet.personality_type or 'N/A',
                'trainability': pet.trainability or 'N/A',
                'companion_preference': pet.companion_preference or 'N/A',
            },
            'big_five': big_five_scores,  # Add Big Five data to result for template
        }
        
        return render_template(
            'user/my_pets_match_results.html',
            pet=pet,
            result=result
        )
    
    except Exception as e:
        logger.error(f'Error displaying pet compatibility: {str(e)}', exc_info=True)
        flash('Error loading compatibility results.', 'danger')
        return redirect(url_for('user.my_pets_index'))


def calculate_pet_user_compatibility(pet):
    """Calculate overall compatibility score for a pet (0-100)."""
    # Base score on pet's behavioral traits
    scores = []
    
    # Evaluate each behavioral trait
    trait_evaluation = {
        'Moderately active': 80,
        'Friendly and playful': 85,
        'Selectively friendly': 75,
        'Balanced': 80,
        'Adaptable': 75,
        'Affectionate': 80,
        'Usually stays calm': 75,
        'Learns gradually': 70,
        'Maybe': 70,
    }
    
    traits = [
        pet.activity_level,
        pet.animal_social_behavior,
        pet.people_sociality,
        pet.independence_level,
        pet.adaptability,
        pet.affection_level,
        pet.alone_behavior,
        pet.trainability,
        pet.companion_preference,
    ]
    
    for trait in traits:
        if trait:
            score = trait_evaluation.get(trait, 70)
            scores.append(score)
    
    # Average the scores with Big Five adjustment
    base_score = sum(scores) / len(scores) if scores else 70
    
    # Adjust based on Big Five balance (more extreme = lower compatibility)
    big_five_average = (
        pet.big_five_openness +
        pet.big_five_conscientiousness +
        pet.big_five_extraversion +
        pet.big_five_agreeableness +
        (6 - pet.big_five_neuroticism)  # Lower neuroticism is better
    ) / 5
    
    # Normalize Big Five (1-5 scale to 0-1)
    big_five_factor = (big_five_average - 1) / 4
    adjusted_score = base_score * 0.7 + (big_five_factor * 100) * 0.3
    
    return round(max(40, min(100, adjusted_score)))


def get_pet_category_breakdown(pet):
    """Get compatibility breakdown by category."""
    return {
        'personality': {
            'name': 'Personality',
            'score': round((pet.big_five_extraversion + pet.big_five_agreeableness) / 2 * 20),
            'weight': CATEGORY_WEIGHTS.get('personality', 1.15),
            'status': 'good' if pet.big_five_agreeableness >= 3 else 'fair',
        },
        'energy': {
            'name': 'Energy & Activity',
            'score': calculate_energy_score(pet.activity_level),
            'weight': CATEGORY_WEIGHTS.get('lifestyle', 1.20),
            'status': 'good' if pet.activity_level in ['Moderately active', 'Very active'] else 'fair',
        },
        'social': {
            'name': 'Social Compatibility',
            'score': calculate_social_score(pet.people_sociality, pet.animal_social_behavior),
            'weight': CATEGORY_WEIGHTS.get('household', 1.35),
            'status': 'good' if pet.people_sociality in ['Friendly with most people', 'Extremely social'] else 'fair',
        },
        'adaptability': {
            'name': 'Adaptability',
            'score': calculate_adaptability_score(pet.adaptability),
            'weight': CATEGORY_WEIGHTS.get('experience', 1.50),
            'status': 'good' if pet.adaptability in ['Adapts quickly', 'Needs time to adjust'] else 'fair',
        },
        'care': {
            'name': 'Care Requirements',
            'score': calculate_care_score(pet.trainability),
            'weight': CATEGORY_WEIGHTS.get('care', 1.05),
            'status': 'good' if pet.trainability in ['Learns gradually', 'Learns quickly'] else 'fair',
        },
    }


def calculate_energy_score(activity_level):
    """Convert activity level to score."""
    mapping = {
        'Very calm': 40,
        'Moderately active': 75,
        'Very energetic': 65,
        'Very active': 80,
    }
    return mapping.get(activity_level, 60)


def calculate_social_score(people_sociality, animal_social):
    """Calculate social compatibility score."""
    social_mapping = {
        'Very shy': 30,
        'Selectively friendly': 65,
        'Friendly with most people': 85,
        'Extremely social': 95,
    }
    people_score = social_mapping.get(people_sociality, 60)
    return round(people_score * 0.7 + 60 * 0.3)  # Weight people more


def calculate_adaptability_score(adaptability):
    """Convert adaptability to score."""
    mapping = {
        'Gets stressed easily': 40,
        'Needs time to adjust': 70,
        'Adapts quickly': 90,
        'Adaptable': 80,
    }
    return mapping.get(adaptability, 65)


def calculate_care_score(trainability):
    """Convert trainability to care score."""
    mapping = {
        'Difficult to train': 50,
        'Learns gradually': 70,
        'Learns quickly': 85,
        'Intelligent': 85,
        'Very trainable': 90,
    }
    return mapping.get(trainability, 70)


def get_pet_insights(pet):
    """Generate insights about the pet."""
    insights = {
        'strengths': [],
        'considerations': [],
        'recommendations': [],
    }
    
    # Strengths
    if pet.affection_level in ['Affectionate', 'Very affectionate']:
        insights['strengths'].append('🤝 Very affectionate and bonding-oriented')
    if pet.trainability in ['Learns quickly', 'Very trainable']:
        insights['strengths'].append('🎓 Quick learner, easy to train')
    if pet.people_sociality in ['Friendly with most people', 'Extremely social']:
        insights['strengths'].append('👥 Great with people, social butterfly')
    if pet.adaptability in ['Adapts quickly']:
        insights['strengths'].append('🔄 Highly adaptable to changes')
    
    # Considerations
    if pet.activity_level == 'Very energetic':
        insights['considerations'].append('⚡ High energy - needs regular exercise')
    if pet.independence_level == 'Very independent':
        insights['considerations'].append('🐾 Independent nature - may not need constant attention')
    if pet.alone_behavior == 'Gets anxious or destructive':
        insights['considerations'].append('😟 May need companionship or alone training')
    if pet.big_five_neuroticism >= 4:
        insights['considerations'].append('💭 Emotionally sensitive - needs gentle handling')
    
    # Recommendations
    if pet.trainability in ['Learns gradually', 'Difficult to train']:
        insights['recommendations'].append('📚 Consider patience-based training methods')
    if pet.big_five_conscientiousness >= 4:
        insights['recommendations'].append('✅ Structured routines and schedules work best')
    if pet.big_five_extraversion >= 4:
        insights['recommendations'].append('🎉 Enjoys social activities and group settings')
    if pet.activity_level in ['Moderately active', 'Very active']:
        insights['recommendations'].append('🏃 Daily activities and playtime recommended')
    
    return insights


@bp.route('/api/gcash-subscription', methods=['GET', 'POST'])
@login_required
@user_required
@csrf.exempt
def api_gcash_subscription():
    """Create or retrieve GCash subscription payment details."""
    if current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admins already have full access.'}), 400

    if request.method == 'GET':
        if current_user.is_pending_subscription:
            plan = current_user.pending_subscription_plan
            amount = 75.0 if plan == 'premium' else 500.0 if plan == 'pro' else 0.0
            return jsonify({
                'success': True,
                'pending': True,
                'plan': plan,
                'amount': amount,
                'payment_due': current_user.subscription_payment_due.isoformat() if current_user.subscription_payment_due else None,
                'gcash_phone': current_app.config.get('GCASH_PHONE') or '09977030323',
                'payment_qr': _generate_gcash_qr_data_url(plan, amount),
                'gcash_pay_url': _generate_gcash_deeplink(current_app.config.get('GCASH_PHONE') or '09977030323', amount, plan)
            })

        return jsonify({
            'success': True,
            'pending': False,
            'message': 'No pending GCash payment. Use POST with plan to create payment details.'
        })

    data = request.get_json(silent=True) or request.form
    selected_plan = (data.get('plan') or 'basic').lower()
    if selected_plan not in ['basic', 'premium', 'pro']:
        return jsonify({'success': False, 'message': 'Invalid plan selected.'}), 400

    if selected_plan == 'basic':
        current_user.set_free_basic()
        db.session.add(current_user)
        db.session.commit()
        return jsonify({'success': True, 'plan': 'basic', 'message': 'Basic plan selected. No payment required.'})

    payment_amount = 75.0 if selected_plan == 'premium' else 500.0
    current_user.set_pending_subscription(selected_plan, get_ph_datetime() + timedelta(days=1))
    db.session.add(current_user)
    db.session.commit()

    return jsonify({
        'success': True,
        'pending': True,
        'plan': selected_plan,
        'amount': payment_amount,
        'payment_due': current_user.subscription_payment_due.isoformat(),
        'gcash_phone': current_app.config.get('GCASH_PHONE') or '09977030323',
        'payment_qr': _generate_gcash_qr_data_url(selected_plan, payment_amount),
        'gcash_pay_url': _generate_gcash_deeplink(current_app.config.get('GCASH_PHONE') or '09977030323', payment_amount, selected_plan),
        'message': 'GCash payment created. Scan the QR code and confirm payment within 1 day.'
    })

@bp.route('/api/gcash-subscription/confirm', methods=['POST'])
@login_required
@user_required
@csrf.exempt
def api_gcash_subscription_confirm():
    """Confirm the pending GCash subscription payment."""
    if not current_user.is_pending_subscription:
        return jsonify({'success': False, 'message': 'No pending subscription payment to confirm.'}), 400

    pending_due = _normalize_to_ph_time(current_user.subscription_payment_due)
    if pending_due and pending_due < get_ph_datetime():
        current_user.cancel_subscription()
        db.session.add(current_user)
        db.session.commit()
        return jsonify({'success': False, 'message': 'Payment window has expired. Please create a new payment request.'}), 400

    current_user.activate_pending_subscription()
    db.session.add(current_user)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Payment confirmed. Your subscription is now active.', 'plan': current_user.subscription_plan})

@bp.route('/subscription/qr.png')
@login_required
@user_required
def subscription_qr_download():
    if not current_user.is_pending_subscription:
        abort(404)

    pending_plan = current_user.pending_subscription_plan
    payment_amount = 75.0 if pending_plan == 'premium' else 500.0
    qr_bytes = _generate_gcash_qr_png_bytes(pending_plan, payment_amount)
    return send_file(
        io.BytesIO(qr_bytes),
        mimetype='image/png',
        as_attachment=True,
        download_name=f'PetSona-{pending_plan}-gcash-qr.png'
    )

@bp.route('/api/gcash-subscription/cancel', methods=['POST'])
@login_required
@user_required
@csrf.exempt
def api_gcash_subscription_cancel():
    """Cancel the pending GCash subscription payment."""
    if not current_user.is_pending_subscription:
        return jsonify({'success': False, 'message': 'No pending subscription payment to cancel.'}), 400

    current_user.cancel_subscription()
    db.session.add(current_user)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Pending subscription payment cancelled.'})

# ======================== PAYMONGO ENDPOINTS ========================

@bp.route('/api/paymongo/create-intent', methods=['POST'])
@login_required
@csrf.exempt
def paymongo_create_intent():
    """Create a PayMongo payment intent for subscription"""
    from app.utils.paymongo_manager import get_paymongo_manager
    
    if current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admins already have full access.'}), 400

    data = request.get_json(silent=True) or {}
    plan = (data.get('plan') or 'basic').lower()

    if plan not in ['premium', 'pro']:
        return jsonify({'success': False, 'message': 'Invalid plan. Use premium or pro.'}), 400

    if plan == 'basic':
        current_user.set_free_basic()
        db.session.add(current_user)
        db.session.commit()
        return jsonify({
            'success': True,
            'plan': 'basic',
            'message': 'Basic plan selected. No payment required.'
        })

    # Calculate amount in cents
    amount_cents = 7500 if plan == 'premium' else 50000  # ₱75.00 or ₱500.00
    payment_description = f"PetSona {plan.title()} Subscription - {current_user.email}"

    # Create payment intent
    pm = get_paymongo_manager()
    success, intent_data, error = pm.create_payment_intent(
        amount_cents=amount_cents,
        plan=plan,
        user_id=current_user.id,
        user_email=current_user.email,
        description=payment_description
    )

    if not success:
        logger.error(f"Failed to create PayMongo intent: {error}")
        return jsonify({
            'success': False,
            'message': 'Failed to create payment. Please try again.'
        }), 500

    # Store payment intent ID temporarily
    intent_id = intent_data.get('id', '')
    client_key = pm.create_client_key(intent_id)

    # Set pending subscription with PayMongo
    current_user.set_pending_subscription(plan, get_ph_datetime() + timedelta(days=1))
    current_user.paymongo_intent_id = intent_id
    db.session.add(current_user)
    db.session.commit()

    return jsonify({
        'success': True,
        'intent_id': intent_id,
        'client_key': client_key,
        'public_key': pm.public_key,
        'amount': amount_cents,
        'currency': 'PHP',
        'plan': plan,
        'payment_due': current_user.subscription_payment_due.isoformat(),
        'message': f'Payment intent created. Total: ₱{amount_cents/100:.2f}'
    })

@bp.route('/api/paymongo/confirm-payment', methods=['POST'])
@login_required
@csrf.exempt
def paymongo_confirm_payment():
    """Confirm a PayMongo payment and activate subscription"""
    from app.utils.paymongo_manager import get_paymongo_manager
    
    if not current_user.is_pending_subscription:
        return jsonify({'success': False, 'message': 'No pending subscription.'}), 400

    data = request.get_json(silent=True) or {}
    payment_id = data.get('payment_id', '')
    intent_id = data.get('intent_id', '') or current_user.paymongo_intent_id

    if not payment_id or not intent_id:
        return jsonify({'success': False, 'message': 'Missing payment information.'}), 400

    # Check payment status
    pm = get_paymongo_manager()
    
    # For test mode, check simulated state
    if pm.mode == 'test':
        status_data = pm.get_simulated_payment_status(intent_id)
        status = status_data.get('attributes', {}).get('status', 'unknown')
    else:
        success, intent_data, error = pm.retrieve_payment_intent(intent_id)
        if not success:
            logger.error(f"Failed to retrieve payment intent: {error}")
            return jsonify({
                'success': False,
                'message': 'Failed to verify payment status.'
            }), 500
        status = intent_data.get('attributes', {}).get('status', 'unknown')

    if status != 'succeeded':
        return jsonify({
            'success': False,
            'status': status,
            'message': f'Payment is {status}. Please wait or try again.'
        }), 400

    # Update user payment details and activate subscription
    current_user.set_paymongo_payment(payment_id, intent_id, 'card')
    current_user.update_paymongo_status('succeeded')
    current_user.activate_pending_subscription()
    db.session.add(current_user)
    db.session.commit()

    # Log the action
    log_action_with_changes(
        current_user.id,
        'subscription_activated',
        'Payment confirmed via PayMongo (Test Mode)',
        {'plan': current_user.subscription_plan, 'payment_id': payment_id}
    )

    return jsonify({
        'success': True,
        'plan': current_user.subscription_plan,
        'renewal_date': current_user.subscription_renewal_date.isoformat(),
        'message': f'Payment confirmed! Your {current_user.subscription_plan.title()} subscription is now active.'
    })

@bp.route('/api/paymongo/payment-status', methods=['GET'])
@login_required
@csrf.exempt
def paymongo_payment_status():
    """Check real-time PayMongo payment status (for polling) - Supports realistic simulation"""
    from app.utils.paymongo_manager import get_paymongo_manager
    
    intent_id = request.args.get('intent_id', '') or current_user.paymongo_intent_id

    if not intent_id:
        return jsonify({
            'success': False,
            'pending': False,
            'message': 'No payment intent found.'
        })

    pm = get_paymongo_manager()
    
    # For test mode, check simulated state
    if pm.mode == 'test':
        status_data = pm.get_simulated_payment_status(intent_id)
        status = status_data.get('attributes', {}).get('status', 'unknown')
        amount = status_data.get('attributes', {}).get('amount', 0)
        payments = status_data.get('attributes', {}).get('payments', [])
    else:
        success, intent_data, error = pm.retrieve_payment_intent(intent_id)
        if not success:
            return jsonify({
                'success': False,
                'status': 'error',
                'message': 'Failed to retrieve payment status.'
            })
        status = intent_data.get('attributes', {}).get('status', 'unknown')
        amount = intent_data.get('attributes', {}).get('amount', 0)
        payments = intent_data.get('attributes', {}).get('payments', [])

    return jsonify({
        'success': True,
        'status': status,
        'amount': amount,
        'currency': 'PHP',
        'payments': payments,
        'is_pending': status in ['processing', 'awaiting_payment_method'],
        'is_succeeded': status == 'succeeded',
        'is_failed': status == 'failed',
        'message': f'Payment status: {status}'
    })

@bp.route('/api/paymongo/simulate-payment', methods=['POST'])
@login_required
@csrf.exempt
def paymongo_simulate_payment():
    """
    Simulate a realistic payment transaction (TEST MODE ONLY)
    Mimics real-world payment processing with 2-4 second delay
    Status starts as 'processing' and transitions to 'succeeded'
    """
    from app.utils.paymongo_manager import get_paymongo_manager
    
    if not current_user.paymongo_intent_id:
        return jsonify({'success': False, 'message': 'No active payment intent.'}), 400

    pm = get_paymongo_manager()
    
    if pm.mode != 'test':
        return jsonify({
            'success': False,
            'message': 'Payment simulation only available in test mode.'
        }), 403

    intent_id = current_user.paymongo_intent_id

    # Simulate payment processing with realistic delay
    simulated_response = pm.simulate_successful_payment(intent_id)
    
    # Update user payment status to 'processing' (not succeeded yet)
    current_user.set_paymongo_payment(f"payment_sim_{intent_id}", intent_id, 'card')
    current_user.update_paymongo_status('processing')
    db.session.add(current_user)
    db.session.commit()

    # Return initial response showing payment is processing
    return jsonify({
        'success': True,
        'status': 'processing',
        'message': 'Processing payment... Please wait.',
        'payment_id': f"payment_sim_{intent_id}",
        'intent_id': intent_id,
        'amount': simulated_response.get('attributes', {}).get('amount', 0),
        'currency': 'PHP',
        'simulated': True,
        'polling_needed': True,  # Frontend should poll status
        'polling_interval': 500  # Check every 500ms
    })

@bp.route('/species')
@login_required
@user_required
def species_index():
    # Log species list access
    log_data_access('species_list', current_user.id, access_type='view')
    
    page = request.args.get('page', 1, type=int)

    # Paginate active species
    pagination = Species.query.filter(
        Species.deleted_at.is_(None)
    ).order_by(Species.name.asc()).paginate(
        page=page, per_page=1000, error_out=False
    )

    species_list = pagination.items
    voted_species_ids = set()
    if species_list:
        species_ids = [species.id for species in species_list]
        user_votes = Vote.query.filter(
            Vote.user_id == current_user.id,
            Vote.species_id.in_(species_ids)
        ).all()
        voted_species_ids = {vote.species_id for vote in user_votes}

    return render_template(
        'user/species_index.html',
        species_list=species_list,
        pagination=pagination,
        voted_species_ids=voted_species_ids,
        page_title="Pet Species"
    )

@bp.route('/species/<int:id>')
@login_required
@user_required
def view_species(id):
    # Log species detail access
    log_data_access('species_detail', id, access_type='view')
    
    species = Species.query.get_or_404(id)

    # Only fetch active breeds (not soft-deleted)
    breeds = Breed.query.filter_by(
        species_id=species.id,
        is_active=True   
    ).order_by(Breed.name.asc()).all()

    voted_breed_ids = set()
    if breeds:
        breed_ids = [breed.id for breed in breeds]
        user_votes = Vote.query.filter(
            Vote.user_id == current_user.id,
            Vote.breed_id.in_(breed_ids)
        ).all()
        voted_breed_ids = {vote.breed_id for vote in user_votes}

    return render_template(
        'user/view_species.html',
        species=species,
        breeds=breeds,
        voted_breed_ids=voted_breed_ids,
        page_title=f"{species.name} Breeds"
    )

@bp.route('/nearby-services')
@login_required
@user_required
def nearby_services():
    """Display nearby pet services based on user location"""
    # Log nearby services access
    log_data_access('nearby_services', current_user.id, access_type='view')
    
    return render_template(
        'user/nearby_services.html',
        page_title='Nearby Pet Services'
    )


@bp.route('/location-picker')
@login_required
@user_required
def location_picker():
    """Allow user to pick a location using OpenStreetMap"""
    # Log location picker access
    log_event('location_picker.opened', details={'user_id': current_user.id})
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
        
        # Log merchant search access
        log_data_access('merchant_search', current_user.id, access_type='search')
        
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
            
            # Use actual approved review data for merchant ratings
            from app.models.review import Review

            rating_stats = db.session.query(
                func.count(Review.id),
                func.avg(Review.overall_rating)
            ).filter(
                Review.merchant_id == merchant.id,
                Review.is_approved == True,
                Review.deleted_at == None
            ).first()

            review_count = int(rating_stats[0] or 0)
            avg_rating = round(float(rating_stats[1]), 1) if rating_stats[1] else 0.0
            merchant.average_rating = avg_rating
            merchant.total_reviews = review_count
            rating_html = merchant.get_rating_stars_html() if review_count > 0 else ''

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
                'rating': avg_rating,
                'reviews': review_count,
                'rating_html': rating_html,
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
        
        # Log location access if user is authenticated
        if current_user.is_authenticated:
            log_data_access('location_reverse_geocode', current_user.id, access_type='geocode')
        
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
    from sqlalchemy import or_
    
    log_data_access('user_bookings', current_user.id, access_type='view')
    
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    search = request.args.get('search', '', type=str).strip()
    
    # Auto-cancel pending bookings whose appointment date/time have already passed
    try:
        expired_pending_bookings = Booking.query.filter_by(
            user_id=current_user.id,
            status='pending',
            deleted_at=None
        ).all()
        auto_cancelled_bookings = []

        for pending_booking in expired_pending_bookings:
            if pending_booking.auto_cancel_if_expired():
                auto_cancelled_bookings.append(pending_booking)

        if auto_cancelled_bookings:
            db.session.commit()
            for pending_booking in auto_cancelled_bookings:
                NotificationManager.notify_booking_auto_cancelled_customer(
                    user_id=current_user.id,
                    booking_number=pending_booking.booking_number,
                    merchant_name=(pending_booking.merchant.business_name if pending_booking.merchant else 'the merchant'),
                    related_booking_id=pending_booking.id
                )
                if pending_booking.merchant and pending_booking.merchant.user_id:
                    NotificationManager.notify_booking_auto_cancelled_merchant(
                        user_id=pending_booking.merchant.user_id,
                        booking_number=pending_booking.booking_number,
                        customer_name=(pending_booking.customer_name or current_user.email),
                        related_booking_id=pending_booking.id
                    )
    except Exception as e:
        logger.error(f"Failed to auto-cancel expired pending bookings: {str(e)}", exc_info=True)
        db.session.rollback()

    query = Booking.query.filter_by(user_id=current_user.id, deleted_at=None)
    
    # Apply search filter if specified - search across booking number and merchant name
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Booking.booking_number.ilike(search_term),
                Booking.merchant_id.in_(
                    db.session.query(Merchant.id).filter(
                        Merchant.business_name.ilike(search_term)
                    )
                )
            )
        )
    
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
            booking_status=booking.status,
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
                         status_filter=status_filter,
                         search=search)


@bp.route('/booking/<int:booking_id>')
@login_required
@user_required
def booking_details(booking_id):
    """Display booking details"""
    log_data_access('booking_details', booking_id, access_type='view')
    from app.models.booking import Booking
    
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first()
    
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('user.my_bookings'))

    if booking.auto_cancel_if_expired():
        try:
            db.session.commit()
            NotificationManager.notify_booking_auto_cancelled_customer(
                user_id=current_user.id,
                booking_number=booking.booking_number,
                merchant_name=(booking.merchant.business_name if booking.merchant else 'the merchant'),
                related_booking_id=booking.id
            )
            if booking.merchant and booking.merchant.user_id:
                NotificationManager.notify_booking_auto_cancelled_merchant(
                    user_id=booking.merchant.user_id,
                    booking_number=booking.booking_number,
                    customer_name=(booking.customer_name or current_user.email),
                    related_booking_id=booking.id
                )
            flash('This booking was automatically cancelled because the appointment date and time have already passed.', 'warning')
        except Exception as e:
            logger.error(f"Failed to auto-cancel booking {booking.id} on detail view: {str(e)}", exc_info=True)
            db.session.rollback()
    
    return render_template('user/booking_details.html', booking=booking)


@bp.route('/booking/<int:booking_id>/receipt')
@login_required
@user_required
def booking_receipt(booking_id):
    """Display booking receipt as digital receipt (can be printed/saved as PNG or PDF)"""
    from app.models.booking import Booking
    from app.utils.qr_generator import qr_generator
    
    # Log receipt access
    log_data_access('booking_receipt', booking_id, access_type='view')
    
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first()
    
    if not booking:
        abort(404)
    
    # Generate QR code for receipt
    qr_url = qr_generator.generate_booking_qr(
        booking_id=booking.id,
        booking_number=booking.booking_number,
        booking_status=booking.status,
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
        return redirect(url_for('user.my_bookings'))
    
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
        
        # Step 2: Log the action using audit utility
        log_action_with_changes(
            event_name='booking.cancelled_by_customer',
            entity_id=booking.id,
            new_values={'status': 'cancelled', 'cancellation_reason': cancellation_reason},
            entity_type='booking',
            metadata={
                'booking_number': booking.booking_number,
                'merchant_id': booking.merchant_id
            }
        )
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
    
    # Log appeal submission
    log_event('booking.appeal_submitted', details={'booking_id': booking_id})
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
        
        # Log the action using audit utility
        log_event('booking.no_show_appeal_submitted', details={
            'booking_id': booking.id,
            'booking_number': booking.booking_number,
            'merchant_id': booking.merchant_id,
            'appeal_reason': appeal_reason
        })
        
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
        
        # Log booking deletion
        log_event('booking.deleted_by_customer', details={
            'booking_id': booking.id,
            'booking_number': booking.booking_number,
            'previous_status': booking.status
        })
        
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
    
    # Log receipt download
    log_event('booking_receipt.downloaded', details={'booking_id': booking_id})
    
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
        log_event('booking.receipt_downloaded', details={
            'booking_id': booking.id,
            'booking_number': booking.booking_number,
            'booking_status': booking.status
        })
        
        return response
        
    except Exception as e:
        logger.error(f'Error downloading receipt for booking {booking_id}: {str(e)}')
        flash('Error downloading receipt. Please try again.', 'danger')
        return redirect(url_for('user.my_bookings'))


# ========== REVIEW ROUTES ==========
@bp.route('/booking/<int:booking_id>/review', methods=['GET'])
@login_required
@user_required
def get_review_form(booking_id):
    """Get review form for a completed booking"""
    from app.models.booking import Booking
    
    # Log review form access
    log_event('booking_review.form_accessed', details={'booking_id': booking_id})
    
    try:
        booking = Booking.query.filter_by(
            id=booking_id,
            user_id=current_user.id,
            deleted_at=None
        ).first()
        
        if not booking:
            return jsonify({'success': False, 'error': 'Booking not found'}), 404
        
        if booking.status != 'completed':
            return jsonify({'success': False, 'error': 'Only completed bookings can be reviewed'}), 400
        
        # Check if review already exists
        from app.models.review import Review
        existing_review = Review.query.filter_by(booking_id=booking_id, deleted_at=None).first()
        if existing_review:
            return jsonify({'success': False, 'error': 'Review already exists for this booking'}), 400
        
        return jsonify({
            'success': True,
            'booking': {
                'id': booking.id,
                'booking_number': booking.booking_number,
                'merchant_name': booking.merchant.business_name,
                'appointment_date': booking.appointment_date.strftime('%B %d, %Y'),
                'service_type': booking.service_type,
                'total_amount': f"{booking.total_amount:.2f}"
            }
        })
    except Exception as e:
        logger.error(f'Error fetching review form: {str(e)}')
        return jsonify({'success': False, 'error': 'Error fetching review form'}), 500


@bp.route('/booking/<int:booking_id>/review', methods=['POST'])
@login_required
@user_required
def submit_review(booking_id):
    """Submit a review for a completed booking"""
    from app.models.booking import Booking
    from app.models.review import Review
    
    # Log review submission
    log_event('booking_review.submitted', details={'booking_id': booking_id})
    
    try:
        booking = Booking.query.filter_by(
            id=booking_id,
            user_id=current_user.id,
            deleted_at=None
        ).first()
        
        if not booking:
            return jsonify({'success': False, 'error': 'Booking not found'}), 404
        
        if booking.status != 'completed':
            return jsonify({'success': False, 'error': 'Only completed bookings can be reviewed'}), 400
        
        # Check if review already exists
        existing_review = Review.query.filter_by(booking_id=booking_id, deleted_at=None).first()
        if existing_review:
            return jsonify({'success': False, 'error': 'Review already exists for this booking'}), 400
        
        data = request.get_json()
        
        # Validate input
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Validate ratings
        overall_rating = float(data.get('overall_rating', 0))
        if not (1 <= overall_rating <= 5):
            return jsonify({'success': False, 'error': 'Overall rating must be between 1 and 5'}), 400
        
        service_quality = int(data.get('service_quality_rating', 5))
        cleanliness = int(data.get('cleanliness_rating', 5))
        staff_friendliness = int(data.get('staff_friendliness_rating', 5))
        value_for_money = int(data.get('value_for_money_rating', 5))
        
        for rating in [service_quality, cleanliness, staff_friendliness, value_for_money]:
            if not (1 <= rating <= 5):
                return jsonify({'success': False, 'error': 'All aspect ratings must be between 1 and 5'}), 400
        
        title = data.get('title', '').strip()
        if not title or len(title) < 5:
            return jsonify({'success': False, 'error': 'Review title must be at least 5 characters'}), 400
        
        if len(title) > 200:
            return jsonify({'success': False, 'error': 'Review title must not exceed 200 characters'}), 400
        
        comment = data.get('comment', '').strip()
        if comment and len(comment) > 5000:
            return jsonify({'success': False, 'error': 'Review comment must not exceed 5000 characters'}), 400
        
        highlights = data.get('highlights', [])
        if not isinstance(highlights, list):
            highlights = []
        highlights = highlights[:5]  # Max 5 highlights
        
        # Create review
        review = Review(
            booking_id=booking_id,
            user_id=current_user.id,
            merchant_id=booking.merchant_id,
            overall_rating=overall_rating,
            service_quality_rating=service_quality,
            cleanliness_rating=cleanliness,
            staff_friendliness_rating=staff_friendliness,
            value_for_money_rating=value_for_money,
            title=title,
            comment=comment or None,
            highlights=highlights,
            is_verified_purchase=True,
            is_approved=True
        )
        
        db.session.add(review)
        db.session.flush()  # Flush to get the review ID
        
        # Update merchant ratings
        booking.merchant.update_ratings_from_reviews()
        
        db.session.commit()
        
        # Log review submission
        log_event('booking.review_submitted', details={
            'review_id': review.id,
            'booking_id': booking_id,
            'merchant_id': booking.merchant_id,
            'rating': overall_rating
        })
        
        # Notify: Alert merchant that they received a new review
        NotificationManager.notify_review_received(
            merchant_user_id=booking.merchant.user_id,
            reviewer_name=current_user.first_name,
            rating=overall_rating,
            related_booking_id=booking_id
        )
        
        flash('Review submitted successfully! Thank you for your feedback.', 'success')
        
        return jsonify({
            'success': True,
            'message': 'Review submitted successfully',
            'review_id': review.id,
            'merchant_rating': booking.merchant.get_rating_display()
        })
    
    except ValueError as e:
        logger.error(f'Validation error submitting review: {str(e)}')
        return jsonify({'success': False, 'error': 'Invalid input data'}), 400
    except Exception as e:
        logger.error(f'Error submitting review for booking {booking_id}: {str(e)}')
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Error submitting review. Please try again.'}), 500


@bp.route('/booking/<int:booking_id>/review', methods=['DELETE'])
@login_required
@user_required
def delete_review(booking_id):
    """Delete a review (soft delete)"""
    from app.models.booking import Booking
    from app.models.review import Review
    
    # Log review deletion
    log_event('booking_review.deleted', details={'booking_id': booking_id})
    
    try:
        booking = Booking.query.filter_by(
            id=booking_id,
            user_id=current_user.id,
            deleted_at=None
        ).first()
        
        if not booking:
            return jsonify({'success': False, 'error': 'Booking not found'}), 404
        
        review = Review.query.filter_by(
            booking_id=booking_id,
            user_id=current_user.id,
            deleted_at=None
        ).first()
        
        if not review:
            return jsonify({'success': False, 'error': 'Review not found'}), 404
        
        # Soft delete
        review.deleted_at = get_ph_datetime()
        
        # Update merchant ratings
        booking.merchant.update_ratings_from_reviews()
        
        db.session.commit()
        
        flash('Review deleted successfully.', 'success')
        
        return jsonify({
            'success': True,
            'message': 'Review deleted successfully',
            'merchant_rating': booking.merchant.get_rating_display()
        })
    
    except Exception as e:
        logger.error(f'Error deleting review for booking {booking_id}: {str(e)}')
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Error deleting review. Please try again.'}), 500


@bp.route('/merchant/<int:merchant_id>/reviews', methods=['GET'])
@login_required
@user_required
def get_merchant_reviews(merchant_id):
    """Get all reviews for a merchant"""
    # Log merchant reviews access
    log_data_access('merchant_reviews', merchant_id, access_type='view')
    from app.models.merchant import Merchant
    from app.models.review import Review
    
    try:
        merchant = Merchant.query.filter_by(id=merchant_id, deleted_at=None).first()
        
        if not merchant:
            return jsonify({'success': False, 'error': 'Merchant not found'}), 404
        
        # Get pagination params
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Get reviews
        reviews_query = Review.query.filter_by(
            merchant_id=merchant_id,
            is_approved=True,
            deleted_at=None
        ).order_by(Review.created_at.desc())
        
        reviews_paginated = reviews_query.paginate(page=page, per_page=per_page)
        
        reviews_data = [review.to_dict() for review in reviews_paginated.items]
        
        return jsonify({
            'success': True,
            'merchant': {
                'id': merchant.id,
                'business_name': merchant.business_name,
                'average_rating': merchant.average_rating,
                'total_reviews': merchant.total_reviews,
                'rating_display': merchant.get_rating_display(),
                'five_star_count': merchant.five_star_count,
                'four_star_count': merchant.four_star_count,
                'three_star_count': merchant.three_star_count,
                'two_star_count': merchant.two_star_count,
                'one_star_count': merchant.one_star_count,
                'avg_service_quality': merchant.avg_service_quality,
                'avg_cleanliness': merchant.avg_cleanliness,
                'avg_staff_friendliness': merchant.avg_staff_friendliness,
                'avg_value_for_money': merchant.avg_value_for_money,
            },
            'reviews': reviews_data,
            'pagination': {
                'page': reviews_paginated.page,
                'per_page': reviews_paginated.per_page,
                'total': reviews_paginated.total,
                'pages': reviews_paginated.pages,
                'has_prev': reviews_paginated.has_prev,
                'has_next': reviews_paginated.has_next
            }
        })
    
    except Exception as e:
        logger.error(f'Error fetching merchant reviews: {str(e)}')
        return jsonify({'success': False, 'error': 'Error fetching reviews'}), 500



# ======================== PET MANAGEMENT ROUTES ========================

@bp.route('/pets', methods=['GET'])
@login_required
@user_required
def my_pets():
    """Display user's pet collection"""
    from app.models import MyPet
    
    page = request.args.get('page', 1, type=int)
    
    # Get user's pets with pagination
    pets = MyPet.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(MyPet.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    
    log_event('pet_collection_viewed', details={'user_id': current_user.id, 'pet_count': pets.total})
    
    return render_template('user/my_pets.html', pets=pets)


@bp.route('/api/pets', methods=['GET'])
@login_required
@user_required
@csrf.exempt
def api_get_pets():
    """Get user's pets as JSON"""
    from app.models import MyPet
    
    pets = MyPet.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(MyPet.created_at.desc()).all()
    
    return jsonify({
        'success': True,
        'pets': [pet.as_dict for pet in pets],
        'total': len(pets)
    })


@bp.route('/api/pets/<int:pet_id>', methods=['GET'])
@login_required
@user_required
@csrf.exempt
def api_get_pet(pet_id):
    """Get single pet details"""
    from app.models import MyPet
    
    pet = MyPet.query.filter_by(
        id=pet_id,
        user_id=current_user.id
    ).first()
    
    if not pet:
        return jsonify({'success': False, 'error': 'Pet not found'}), 404
    
    return jsonify({
        'success': True,
        'pet': pet.as_dict
    })


ALLOWED_PET_PHOTO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_pet_photo(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_PET_PHOTO_EXTENSIONS

def save_pet_photo(file, pet_id):
    """Save pet photo and return the relative path"""
    if not file or file.filename == '':
        return None
    
    if not allowed_pet_photo(file.filename):
        return None
    
    try:
        # Create upload directory if it doesn't exist
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
        pet_upload_dir = os.path.join(upload_dir, 'pets')
        os.makedirs(pet_upload_dir, exist_ok=True)
        
        # Generate secure filename
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = f"{timestamp}{pet_id}_{filename}"
        
        filepath = os.path.join(pet_upload_dir, filename)
        file.save(filepath)
        
        # Return relative path for database storage
        return f"uploads/pets/{filename}"
    except Exception as e:
        print(f"Error saving pet photo: {e}")
        return None


@bp.route('/api/pets/create', methods=['POST'])
@login_required
@user_required
@csrf.exempt
def api_create_pet():
    """Create a new pet"""
    from app.models import MyPet
    
    try:
        data = request.form.to_dict()
        
        # Validate required fields
        if not data.get('name') or not data.get('species'):
            return jsonify({'success': False, 'error': 'Name and species are required'}), 400
        
        # Create new pet
        pet = MyPet(
            user_id=current_user.id,
            name=data.get('name'),
            species=data.get('species'),
            breed=data.get('breed'),
            age=data.get('age'),
            sex=data.get('sex') or 'Unknown',
            weight=data.get('weight'),
            energy_level=data.get('energy_level') or 'Medium',
            exercise_frequency=data.get('exercise_frequency') or 'Medium',
            grooming_frequency=data.get('grooming_frequency') or 'Medium',
            space_requirement=data.get('space_requirement') or 'Medium',
            training_difficulty=data.get('training_difficulty') or 'Moderate',
            handling_difficulty=data.get('handling_difficulty') or 'Medium',
            noise_level=data.get('noise_level') or 'Low',
            bonding_needs=data.get('bonding_needs') or 'Medium',
            child_friendly=data.get('child_friendly') or 'Medium',
            pet_friendly=data.get('pet_friendly') or 'Medium',
            care_intensity=data.get('care_intensity') or 'Medium',
            time_commitment=data.get('time_commitment') or 'Medium',
            experience_required=data.get('experience_required') or 'Beginner',
            environment_complexity=data.get('environment_complexity') or 'Simple',
            preventive_care=data.get('preventive_care') or 'Medium',
            emergency_risk=data.get('emergency_risk') or 'Low',
            stress_sensitivity=data.get('stress_sensitivity') or 'Medium',
            lifetime_cost_level=data.get('lifetime_cost_level') or 'Medium',
            big_five_openness=int(data.get('big_five_openness', 3)),
            big_five_conscientiousness=int(data.get('big_five_conscientiousness', 3)),
            big_five_extraversion=int(data.get('big_five_extraversion', 3)),
            big_five_agreeableness=int(data.get('big_five_agreeableness', 3)),
            big_five_neuroticism=int(data.get('big_five_neuroticism', 2))
        )
        
        db.session.add(pet)
        db.session.flush()
        
        # Handle photo upload
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and allowed_pet_photo(photo.filename):
                photo_path = save_pet_photo(photo, pet.id)
                if photo_path:
                    pet.photo_url = photo_path
        
        db.session.commit()
        
        log_event('pet_created', details={
            'user_id': current_user.id,
            'pet_id': pet.id,
            'pet_name': pet.name
        })
        
        return jsonify({
            'success': True,
            'pet': pet.as_dict,
            'message': f'{pet.name} has been added to your pets!'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating pet: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/pets/<int:pet_id>/update', methods=['POST'])
@login_required
@user_required
@csrf.exempt
def api_update_pet(pet_id):
    """Update an existing pet"""
    from app.models import MyPet
    
    try:
        pet = MyPet.query.filter_by(
            id=pet_id,
            user_id=current_user.id
        ).first()
        
        if not pet:
            return jsonify({'success': False, 'error': 'Pet not found'}), 404
        
        data = request.form.to_dict()
        
        # Update basic info
        pet.name = data.get('name', pet.name)
        pet.species = data.get('species', pet.species)
        pet.breed = data.get('breed', pet.breed)
        pet.age = data.get('age', pet.age)
        pet.weight = data.get('weight', pet.weight)
        pet.sex = data.get('sex', pet.sex)
        
        # Update care and behavioral traits
        pet.energy_level = data.get('energy_level', pet.energy_level)
        pet.exercise_frequency = data.get('exercise_frequency', pet.exercise_frequency)
        pet.grooming_frequency = data.get('grooming_frequency', pet.grooming_frequency)
        pet.space_requirement = data.get('space_requirement', pet.space_requirement)
        pet.training_difficulty = data.get('training_difficulty', pet.training_difficulty)
        pet.handling_difficulty = data.get('handling_difficulty', pet.handling_difficulty)
        pet.noise_level = data.get('noise_level', pet.noise_level)
        pet.bonding_needs = data.get('bonding_needs', pet.bonding_needs)
        pet.child_friendly = data.get('child_friendly', pet.child_friendly)
        pet.pet_friendly = data.get('pet_friendly', pet.pet_friendly)
        pet.care_intensity = data.get('care_intensity', pet.care_intensity)
        pet.time_commitment = data.get('time_commitment', pet.time_commitment)
        pet.experience_required = data.get('experience_required', pet.experience_required)
        pet.environment_complexity = data.get('environment_complexity', pet.environment_complexity)
        pet.preventive_care = data.get('preventive_care', pet.preventive_care)
        pet.emergency_risk = data.get('emergency_risk', pet.emergency_risk)
        pet.stress_sensitivity = data.get('stress_sensitivity', pet.stress_sensitivity)
        pet.lifetime_cost_level = data.get('lifetime_cost_level', pet.lifetime_cost_level)
        
        # Update Big Five traits
        pet.big_five_openness = int(data.get('big_five_openness', pet.big_five_openness))
        pet.big_five_conscientiousness = int(data.get('big_five_conscientiousness', pet.big_five_conscientiousness))
        pet.big_five_extraversion = int(data.get('big_five_extraversion', pet.big_five_extraversion))
        pet.big_five_agreeableness = int(data.get('big_five_agreeableness', pet.big_five_agreeableness))
        pet.big_five_neuroticism = int(data.get('big_five_neuroticism', pet.big_five_neuroticism))
        
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and allowed_pet_photo(photo.filename):
                photo_path = save_pet_photo(photo, pet.id)
                if photo_path:
                    pet.photo_url = photo_path
        
        pet.updated_at = datetime.utcnow()
        db.session.commit()
        
        log_event('pet_updated', details={
            'user_id': current_user.id,
            'pet_id': pet.id,
            'pet_name': pet.name
        })
        
        return jsonify({
            'success': True,
            'pet': pet.as_dict,
            'message': f'{pet.name} has been updated!'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating pet: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/pets/<int:pet_id>/delete', methods=['POST'])
@login_required
@user_required
@csrf.exempt
def api_delete_pet(pet_id):
    """Delete a pet (soft delete)"""
    from app.models import MyPet
    
    try:
        pet = MyPet.query.filter_by(
            id=pet_id,
            user_id=current_user.id
        ).first()
        
        if not pet:
            return jsonify({'success': False, 'error': 'Pet not found'}), 404
        
        pet_name = pet.name
        pet.is_active = False
        pet.updated_at = datetime.utcnow()
        db.session.commit()
        
        log_event('pet_deleted', details={
            'user_id': current_user.id,
            'pet_id': pet.id,
            'pet_name': pet_name
        })
        
        return jsonify({
            'success': True,
            'message': f'{pet_name} has been removed from your pets.'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting pet: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

        return jsonify({'success': False, 'error': str(e)}), 500
