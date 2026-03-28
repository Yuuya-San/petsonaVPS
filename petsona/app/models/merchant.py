from datetime import datetime
from app.extensions import db
from sqlalchemy.dialects.mysql import JSON, LONGTEXT


class Merchant(db.Model):
    """Merchant model for partner businesses applying to the platform"""
    __tablename__ = "merchants"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('merchant', uselist=False, cascade='all, delete-orphan'), primaryjoin='Merchant.user_id==User.id')
    
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], primaryjoin='Merchant.reviewed_by==User.id')

    # ========== SECTION 1: BUSINESS INFORMATION ==========
    business_name = db.Column(db.String(255), nullable=False)

    business_category = db.Column(db.String(50), nullable=False)

    business_description = db.Column(LONGTEXT, nullable=True)

    # ========== SECTION 2: CONTACT PERSON ==========
    owner_manager_name = db.Column(db.String(128), nullable=False)
    contact_email = db.Column(db.String(255), nullable=False)
    contact_phone = db.Column(db.String(20), nullable=False)

    # ========== SECTION 3: LOCATION ==========
    full_address = db.Column(db.String(500), nullable=False)
    region = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(100), nullable=False)
    barangay = db.Column(db.String(100), nullable=False, default='')
    postal_code = db.Column(db.String(10), nullable=True)
    google_maps_link = db.Column(db.String(500), nullable=True)
    
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # ========== SECTION 5: PETS ACCEPTED (Checkboxes) ==========
    pets_accepted = db.Column(JSON, nullable=False, default=[])

    service_pricing = db.Column(JSON, nullable=True)

    # ========== SECTION 7: OPERATING SCHEDULE ==========
    is_24h = db.Column(db.Boolean, default=False)  # True if operating 24/7
    opening_time = db.Column(db.String(5), nullable=True)  # HH:MM
    closing_time = db.Column(db.String(5), nullable=True)
    operating_days = db.Column(JSON, nullable=True, default=[])

    # ========== SECTION 8: POLICIES ==========
    cancellation_policy = db.Column(LONGTEXT, nullable=True)

    # ========== SECTION 9: VERIFICATION UPLOADS ==========
    logo_path = db.Column(db.String(255), nullable=True)
    government_id_path = db.Column(db.String(255), nullable=True)
    business_permit_path = db.Column(db.String(255), nullable=True)
    facility_photos_paths = db.Column(JSON, nullable=True, default=[])

    # ========== SECTION 10: SYSTEM FIELDS ==========
    application_status = db.Column(db.String(50), default='pending')  # pending, approved, rejected, under_review
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(LONGTEXT, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    is_verified = db.Column(db.Boolean, default=False)
    is_open = db.Column(db.Boolean, default=True)  # Store open/closed status

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

    @property
    def services_offered(self):
        """Return currently configured services based on service pricing."""
        if isinstance(self.service_pricing, dict):
            return list(self.service_pricing.keys())
        return []

    @services_offered.setter
    def services_offered(self, services):
        """Persist a list of offered services by ensuring they exist in service_pricing."""
        if not isinstance(services, list):
            return
        pricing = self.get_service_pricing()
        for service in services:
            if service not in pricing:
                pricing[service] = {}
        self.service_pricing = pricing

    def get_services_list(self):
        """Returns service names as a list based on pricing configuration"""
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

    def get_service_pricing(self):
        """Returns service pricing configuration"""
        return self.service_pricing if isinstance(self.service_pricing, dict) else {}

    def get_price_for_service(self, service_name, size=None, duration=None):
        """
        Get price range for a specific service with optional size/duration
        Returns dict with 'min' and 'max' keys or None
        """
        pricing = self.get_service_pricing()
        if service_name not in pricing:
            return None
        
        config = pricing[service_name]
        
        if config.get('type') == 'flat':
            return {
                'min': config.get('min_price'),
                'max': config.get('max_price'),
                'unit': config.get('unit', 'services')
            }
        elif config.get('type') == 'size' and size:
            size_data = config.get('by_size', {}).get(size, {})
            if size_data:
                return {
                    'min': size_data.get('min_price'),
                    'max': size_data.get('max_price'),
                    'unit': config.get('unit', 'services'),
                    'size': size
                }
        elif config.get('type') == 'duration' and duration:
            duration_data = config.get('by_duration', {}).get(duration, {})
            if duration_data:
                return {
                    'min': duration_data.get('min_price'),
                    'max': duration_data.get('max_price'),
                    'unit': duration,
                }
        elif config.get('type') == 'duration+size' and duration and size:
            duration_data = config.get('by_duration_and_size', {}).get(duration, {})
            if duration_data:
                size_data = duration_data.get('by_size', {}).get(size, {})
                if size_data:
                    return {
                        'min': size_data.get('min_price'),
                        'max': size_data.get('max_price'),
                        'duration': duration,
                        'size': size,
                    }
        return None

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
            'business_category': self.business_category,  

            'latitude': self.latitude,
            'longitude': self.longitude,

            'full_address': self.full_address,
            'region': self.region,
            'city': self.city,
            'province': self.province,
            'barangay': self.barangay,

            'services_offered': self.get_services_list(),
            'pets_accepted': self.get_pets_list(),

            'contact_phone': self.contact_phone,
            'contact_email': self.contact_email,

            'min_price': self.min_price,
            'max_price': self.max_price,

            'opening_time': self.opening_time,
            'closing_time': self.closing_time,
            'operating_days': self.get_operating_days(),

            'application_status': self.application_status,
            'is_verified': self.is_verified,
            'is_approved': self.is_approved,
        }

