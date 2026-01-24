from flask import render_template, flash, redirect, url_for, request, abort
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]
from app.user import bp
from app.decorators import user_required
from app.models import Species, Breed
from app import db
from sqlalchemy import func # pyright: ignore[reportMissingImports]
from flask import Blueprint, request, jsonify


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
    
    # TODO: Replace with real database query and distance calculation
    # Real implementation would:
    # 1. Get user's current location (from request or saved location)
    # 2. Query merchants with: 
    #    Merchant.query.filter_by(application_status='approved').all()
    # 3. Calculate distance using haversine formula with latitude/longitude
    # 4. Filter by distance radius (e.g., 5km)
    # 5. Sort by distance
    
    # Mock data - scalable structure for real merchant data
    nearby_merchants = [
        {
            'id': 1,
            'business_name': 'PawsCare Pet Services',
            'rating': 4.8,
            'reviews': 156,
            'distance': 0.8,  # km
            'city': 'Manila',
            'contact_phone': '+63 912 345 6789',
            'contact_email': 'contact@pawscare.com',
            'services_offered': ['Pet Grooming', 'Pet Boarding', 'Veterinary'],
            'pets_accepted': ['Dogs', 'Cats', 'Birds'],
            'min_price': 500,
            'max_price': 2500,
            'opening_time': '09:00',
            'closing_time': '18:00',
            'is_open': True,
            'response_time': '1h',
            'completion_rate': 94
        },
        {
            'id': 2,
            'business_name': 'Furry Friends Pet Hotel',
            'rating': 4.6,
            'reviews': 89,
            'distance': 1.2,
            'city': 'Manila',
            'contact_phone': '+63 923 456 7890',
            'contact_email': 'hello@furryfriends.com',
            'services_offered': ['Pet Boarding', 'Pet Sitting', 'Pet Transport'],
            'pets_accepted': ['Dogs', 'Cats', 'Rabbits'],
            'min_price': 400,
            'max_price': 2000,
            'opening_time': '08:00',
            'closing_time': '20:00',
            'is_open': True,
            'response_time': '2h',
            'completion_rate': 91
        },
        {
            'id': 3,
            'business_name': 'Pet Haven Clinic',
            'rating': 4.9,
            'reviews': 234,
            'distance': 1.5,
            'city': 'Manila',
            'contact_phone': '+63 934 567 8901',
            'contact_email': 'vet@pethaven.com',
            'services_offered': ['Veterinary Clinic', 'Pet Grooming', 'Pet Training'],
            'pets_accepted': ['Dogs', 'Cats', 'Birds', 'Reptiles'],
            'min_price': 300,
            'max_price': 5000,
            'opening_time': '07:00',
            'closing_time': '19:00',
            'is_open': True,
            'response_time': '30m',
            'completion_rate': 98
        },
        {
            'id': 4,
            'business_name': 'Paws Training Academy',
            'rating': 4.7,
            'reviews': 102,
            'distance': 2.1,
            'city': 'Makati',
            'contact_phone': '+63 945 678 9012',
            'contact_email': 'trainer@pawsacademy.com',
            'services_offered': ['Pet Training', 'Behavioral Coaching', 'Pet Grooming'],
            'pets_accepted': ['Dogs', 'Cats'],
            'min_price': 600,
            'max_price': 3000,
            'opening_time': '10:00',
            'closing_time': '17:00',
            'is_open': True,
            'response_time': '3h',
            'completion_rate': 89
        },
        {
            'id': 5,
            'business_name': 'Cozy Paws Grooming',
            'rating': 4.5,
            'reviews': 67,
            'distance': 2.3,
            'city': 'Quezon City',
            'contact_phone': '+63 956 789 0123',
            'contact_email': 'groom@cozypaws.com',
            'services_offered': ['Pet Grooming', 'Pet Spa', 'Pet Care'],
            'pets_accepted': ['Dogs', 'Cats'],
            'min_price': 350,
            'max_price': 1500,
            'opening_time': '09:00',
            'closing_time': '18:00',
            'is_open': False,
            'response_time': '4h',
            'completion_rate': 85
        },
        {
            'id': 6,
            'business_name': 'Happy Paws Transport',
            'rating': 4.4,
            'reviews': 45,
            'distance': 2.8,
            'city': 'Pasig',
            'contact_phone': '+63 967 890 1234',
            'contact_email': 'transport@happypaws.com',
            'services_offered': ['Pet Transport', 'Pet Delivery', 'Pet Sitting'],
            'pets_accepted': ['Dogs', 'Cats', 'Small Animals'],
            'min_price': 200,
            'max_price': 1000,
            'opening_time': '06:00',
            'closing_time': '22:00',
            'is_open': True,
            'response_time': '15m',
            'completion_rate': 92
        }
    ]
    
    return render_template(
        'user/nearby_services.html',
        nearby_merchants=nearby_merchants,
        page_title='Nearby Pet Services'
    )
