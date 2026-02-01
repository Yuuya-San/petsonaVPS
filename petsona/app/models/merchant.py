from datetime import datetime
from app.extensions import db
from sqlalchemy.dialects.mysql import JSON, LONGTEXT


class Merchant(db.Model):
    """Merchant model for partner businesses applying to the platform"""
    __tablename__ = "merchants"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('merchant', uselist=False, cascade='all, delete-orphan'), primaryjoin='Merchant.user_id==User.id')
    
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Admin who reviewed
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], primaryjoin='Merchant.reviewed_by==User.id')

    # ========== SECTION 1: BUSINESS INFORMATION ==========
    business_name = db.Column(db.String(255), nullable=False)
    business_type = db.Column(db.String(50), nullable=False)  # Hotel, Boarding, Grooming, Vet, Trainer, Transport
    business_description = db.Column(LONGTEXT, nullable=True)
    years_in_operation = db.Column(db.Integer, nullable=True)

    # ========== SECTION 2: CONTACT PERSON ==========
    owner_manager_name = db.Column(db.String(128), nullable=False)
    contact_email = db.Column(db.String(255), nullable=False)
    contact_phone = db.Column(db.String(20), nullable=False)

    # ========== SECTION 3: LOCATION ==========
    full_address = db.Column(db.String(500), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(100), nullable=False)
    barangay = db.Column(db.String(100), nullable=True)
    postal_code = db.Column(db.String(10), nullable=True)
    google_maps_link = db.Column(db.String(500), nullable=True)
    
    # Coordinates for mapping and "nearest services" feature
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # ========== SECTION 4: SERVICES OFFERED (JSON array) ==========
    # Services: ['Pet Hotel', 'Pet Boarding', 'Pet Grooming', 'Pet Training', 'Pet Transport', 'Veterinary Clinic']
    services_offered = db.Column(JSON, nullable=False, default=[])

    # ========== SECTION 5: PETS ACCEPTED (JSON array) ==========
    # Pets: ['Dogs', 'Cats', 'Birds', 'Rabbits', 'Reptiles', 'Exotic Pets']
    pets_accepted = db.Column(JSON, nullable=False, default=[])

    # ========== SECTION 6: CAPACITY & PRICING ==========
    max_pets_per_day = db.Column(db.Integer, nullable=False)
    min_price_per_day = db.Column(db.Float, nullable=False)
    max_price_per_day = db.Column(db.Float, nullable=False)

    # ========== SECTION 7: OPERATING SCHEDULE ==========
    opening_time = db.Column(db.String(5), nullable=False)  # HH:MM format
    closing_time = db.Column(db.String(5), nullable=False)  # HH:MM format
    operating_days = db.Column(JSON, nullable=False, default=[])  # Array of days: ['Mon', 'Tue', ...]

    # ========== SECTION 8: POLICIES ==========
    cancellation_policy = db.Column(LONGTEXT, nullable=True)

    # ========== SECTION 9: VERIFICATION UPLOADS ==========
    # File paths stored in storage/uploads/merchants/{merchant_id}/
    logo_path = db.Column(db.String(255), nullable=True)  # Store logo file path
    government_id_path = db.Column(db.String(255), nullable=True)
    business_permit_path = db.Column(db.String(255), nullable=True)
    facility_photos_paths = db.Column(JSON, nullable=True, default=[])  # Array of file paths

    # ========== SECTION 10: SYSTEM FIELDS ==========
    application_status = db.Column(db.String(50), default='pending')  # pending, approved, rejected, under_review
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(LONGTEXT, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # For scalability: store searchable geospatial data
    # These will be indexed for quick "nearest services" queries
    is_verified = db.Column(db.Boolean, default=False)
    search_keywords = db.Column(db.String(500), nullable=True)  # Denormalized for search performance

    def __repr__(self):
        return f'<Merchant {self.business_name}>'

    @property
    def is_approved(self):
        return self.application_status == 'approved'

    @property
    def is_pending(self):
        return self.application_status == 'pending'

    @property
    def is_under_review(self):
        return self.application_status == 'under_review'

    @property
    def is_rejected(self):
        return self.application_status == 'rejected'

    def get_coordinates(self):
        """Returns coordinates as tuple (lat, lng)"""
        return (self.latitude, self.longitude)

    def set_coordinates(self, latitude, longitude):
        """Sets latitude and longitude"""
        self.latitude = float(latitude)
        self.longitude = float(longitude)

    def get_services_list(self):
        """Returns services as list"""
        return self.services_offered if isinstance(self.services_offered, list) else []

    def get_pets_list(self):
        """Returns accepted pets as list"""
        return self.pets_accepted if isinstance(self.pets_accepted, list) else []

    def get_operating_days(self):
        """Returns operating days as list of integers (0-6, Monday-Sunday)"""
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        if isinstance(self.operating_days, list):
            try:
                result = []
                for day in self.operating_days:
                    try:
                        # Try to treat as string day name first
                        if isinstance(day, str):
                            day_lower = day.strip().lower()
                            day_names_lower = [d.lower() for d in day_names]
                            if day_lower in day_names_lower:
                                result.append(day_names_lower.index(day_lower))
                        else:
                            # Try to treat as integer
                            day_int = int(day)
                            if 0 <= day_int <= 6:
                                result.append(day_int)
                    except (ValueError, TypeError, AttributeError):
                        continue
                return result if result else self.operating_days
            except Exception:
                pass
        return self.operating_days if isinstance(self.operating_days, list) else []

    def get_facility_photos(self):
        """Returns facility photos as list"""
        return self.facility_photos_paths if isinstance(self.facility_photos_paths, list) else []

    def get_logo_url(self):
        """Returns logo URL or placeholder"""
        from flask import url_for
        if self.logo_path:
            return url_for('static', filename=f'uploads/merchants/{self.id}/{self.logo_path}')
        # Return placeholder with business initials
        initials = ''.join([word[0].upper() for word in self.business_name.split()[:2]])
        return f"https://via.placeholder.com/300x300?text={initials}"

    def to_dict(self):
        """Converts merchant to dictionary for JSON response"""
        return {
            'id': self.id,
            'business_name': self.business_name,
            'business_type': self.business_type,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'full_address': self.full_address,
            'city': self.city,
            'province': self.province,
            'services_offered': self.get_services_list(),
            'pets_accepted': self.get_pets_list(),
            'contact_phone': self.contact_phone,
            'contact_email': self.contact_email,
            'min_price_per_day': self.min_price_per_day,
            'max_price_per_day': self.max_price_per_day,
            'application_status': self.application_status,
            'is_approved': self.is_approved
        }
