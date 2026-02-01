from flask import render_template, flash, redirect, url_for, request, abort
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]
from app.user import bp
from app.decorators import user_required
from app.models import Species, Breed, Merchant
from app import db
from app.extensions import csrf
from sqlalchemy import func # pyright: ignore[reportMissingImports]
from flask import Blueprint, request, jsonify
import math
import sys


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two coordinates using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    
    a = math.sin(dLat / 2) * math.sin(dLat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon / 2) * math.sin(dLon / 2)
    
    c = 2 * math.asin(math.sqrt(a))
    return R * c


@bp.route('/dashboard')
@login_required
@user_required
def dashboard():
    from app.models.breed import Breed
    from datetime import datetime, timedelta
    
    # Get top 3 species by vote count
    top_species = Species.query.filter(
        Species.deleted_at.is_(None)
    ).order_by(Species.heart_vote_count.desc()).limit(3).all()
    
    # Get top 8 breeds by vote count
    top_breeds = Breed.query.filter(
        Breed.deleted_at.is_(None)
    ).order_by(Breed.heart_vote_count.desc()).limit(8).all()
    
    # Get recently added species (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
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
        top_species=top_species,
        top_breeds=top_breeds,
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


@bp.route('/api/merchants/test', methods=['GET'])
@csrf.exempt
def test_merchants():
    """Test endpoint to check merchants in database"""
    try:
        print("\n[TEST] Starting test endpoint")
        all_merchants = Merchant.query.all()
        print(f"[TEST] Total merchants: {len(all_merchants)}")
        approved_merchants = Merchant.query.filter_by(
            application_status='approved',
            is_verified=True
        ).all()
        print(f"[TEST] Approved & verified: {len(approved_merchants)}\n")
        
        result = {
            'total_merchants': len(all_merchants),
            'approved_verified_count': len(approved_merchants),
            'approved_merchants': []
        }
        
        for m in approved_merchants:
            result['approved_merchants'].append({
                'id': m.id,
                'name': m.business_name,
                'status': m.application_status,
                'verified': m.is_verified,
                'lat': m.latitude,
                'lon': m.longitude,
                'city': m.city,
                'services': m.services_offered
            })
            print(f"[TEST] {m.business_name}: status={m.application_status}, verified={m.is_verified}, coords=({m.latitude}, {m.longitude})")
        
        print(f"[TEST] Returning result")
        return jsonify(result)
    except Exception as e:
        print(f"[ERROR] Test error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/merchants/nearby', methods=['POST'])
@csrf.exempt
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
        
        # Get all approved and verified merchants  
        merchants = Merchant.query.filter_by(
            application_status='approved',
            is_verified=True
        ).all()
        
        nearby_list = []
        from datetime import datetime
        
        for merchant in merchants:
            # Skip merchants without coordinates
            if not merchant.latitude or not merchant.longitude:
                continue
            
            # Calculate distance
            distance = haversine_distance(
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
            
            # Get merchant reviews for rating and count
            reviews = merchant.merchant_reviews if hasattr(merchant, 'merchant_reviews') else []
            if reviews:
                avg_rating = sum([r.rating for r in reviews]) / len(reviews)
                review_count = len(reviews)
            else:
                avg_rating = 4.5
                review_count = 0
            
            merchant_data = {
                'id': merchant.id,
                'business_name': merchant.business_name,
                'business_type': merchant.business_type,
                'city': merchant.city,
                'province': merchant.province,
                'barangay': merchant.barangay or '',
                'contact_email': merchant.contact_email,
                'contact_phone': merchant.contact_phone,
                'services_offered': merchant.services_offered or [],
                'pets_accepted': merchant.pets_accepted or [],
                'min_price': int(merchant.min_price_per_day) if merchant.min_price_per_day else 0,
                'max_price': int(merchant.max_price_per_day) if merchant.max_price_per_day else 0,
                'opening_time': merchant.opening_time or '09:00',
                'closing_time': merchant.closing_time or '18:00',
                'is_open': is_open,
                'distance': round(distance, 1),
                'rating': round(avg_rating, 1),
                'reviews': review_count,
                'response_time': '2h',
                'completion_rate': 90,
                'latitude': float(merchant.latitude),
                'longitude': float(merchant.longitude)
            }
            nearby_list.append(merchant_data)
        
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
