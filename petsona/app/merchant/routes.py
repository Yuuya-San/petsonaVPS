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
from app.extensions import db, csrf
from app.merchant.forms import MerchantApplicationForm
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

