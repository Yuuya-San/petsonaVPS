"""Booking model for online reservations at merchant services"""
from datetime import datetime
from app.extensions import db
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


class Booking(db.Model):
    """
    Booking model for appointment-based pet service reservations.
    Aligned with booking.html form - appointment-based pricing by pet SIZE category.
    Handles reservations WITHOUT real money transactions.
    """
    __tablename__ = "bookings"

    # ========== SECTION 1: PRIMARY & FOREIGN KEYS ==========
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('bookings', cascade='all, delete-orphan', lazy='dynamic'))
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False, index=True)
    merchant = db.relationship('Merchant', foreign_keys=[merchant_id], backref=db.backref('bookings', cascade='all, delete-orphan', lazy='dynamic'))

    # ========== SECTION 2: BOOKING IDENTIFICATION ==========
    booking_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    confirmation_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, default='pending', index=True)

    # ========== SECTION 3: CUSTOMER INFO (From booking.html form) ==========
    customer_name = db.Column(db.String(128), nullable=False)
    customer_email = db.Column(db.String(255), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)

    # ========== SECTION 4: PETS (From booking.html multi-pet form) ==========
    # Each pet: { pet_name, species, breed, age, weight, medical_conditions }
    pets_booked = db.Column(JSON, nullable=False, default=[])
    total_pets = db.Column(db.Integer, default=1, nullable=False)
    pet_special_notes = db.Column(LONGTEXT, nullable=True)

    # ========== SECTION 5: APPOINTMENT DATE & TIME (Single appointment, not multi-day) ==========
    appointment_date = db.Column(db.DateTime, nullable=False, index=True)  # Date of appointment
    appointment_time = db.Column(db.String(5), nullable=False)  # HH:MM format

    # ========== SECTION 6: PRICING (Based on pet SIZE categories) ==========
    # Price breakdown by size category:
    # { "small": {"count": 1, "price": 500}, "medium": {"count": 2, "price": 1000}, ... }
    price_breakdown = db.Column(JSON, nullable=True, default={})
    
    # Total cost based on all pets' sizes and service type
    total_amount = db.Column(db.Float, nullable=False, default=0.0)

    # ========== SECTION 7: SERVICE TYPE & DURATION ==========
    # Depends on business category:
    # - Pet Hotel/Boarding: "Per Night"
    # - Pet Daycare: "Full Day" or "Half Day"
    service_type = db.Column(db.String(100), nullable=True)  # e.g., "Per Night", "Full Day"
    business_category = db.Column(db.String(100), nullable=True)  # e.g., "Pet Hotel", "Pet Daycare"

    # ========== SECTION 8: MERCHANT CONFIRMATION (Workflow) ==========
    merchant_confirmed = db.Column(db.Boolean, default=False)
    merchant_confirmed_at = db.Column(db.DateTime, nullable=True)

    # ========== SECTION 9: ADDITIONAL NOTES (From booking.html form) ==========
    special_requests = db.Column(LONGTEXT, nullable=True)

    # ========== SECTION 10: TIMESTAMPS & TRACKING ==========
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('booking_number', name='unique_booking_number'),
        db.UniqueConstraint('confirmation_code', name='unique_confirmation_code'),
        db.Index('idx_user_merchant_appointment', 'user_id', 'merchant_id', 'appointment_date'),
        db.Index('idx_booking_status', 'status', 'created_at'),
    )

    def __repr__(self):
        return f'<Booking {self.booking_number} - {self.customer_name}>'

    # ========== PROPERTIES ==========
    @property
    def is_pending(self):
        """Check if booking is awaiting merchant confirmation"""
        return self.status == 'pending' and not self.merchant_confirmed

    @property
    def is_confirmed(self):
        """Check if booking is confirmed by merchant"""
        return self.status == 'confirmed' or self.merchant_confirmed

    @property
    def is_completed(self):
        """Check if booking service was completed"""
        return self.status == 'completed'

    @property
    def is_cancelled(self):
        """Check if booking was cancelled"""
        return self.status == 'cancelled'

    @property
    def is_active(self):
        """Check if appointment is today or in the future and confirmed"""
        now = get_ph_datetime()
        return self.is_confirmed and self.appointment_date.date() >= now.date()

    @property
    def is_upcoming(self):
        """Check if appointment is scheduled for the future"""
        appt_dt = self.appointment_date
        if appt_dt.tzinfo is None:
            appt_dt = appt_dt.replace(tzinfo=PH_TZ)
        return self.is_confirmed and appt_dt > get_ph_datetime()

    @property
    def is_past(self):
        """Check if appointment date has passed"""
        appt_dt = self.appointment_date
        if appt_dt.tzinfo is None:
            appt_dt = appt_dt.replace(tzinfo=PH_TZ)
        return get_ph_datetime() > appt_dt

    @property
    def can_be_cancelled(self):
        """Check if booking can still be cancelled"""
        appt_dt = self.appointment_date
        if appt_dt.tzinfo is None:
            appt_dt = appt_dt.replace(tzinfo=PH_TZ)
        return not self.is_cancelled and not self.is_completed and get_ph_datetime() < appt_dt

    @property
    def total_pets_count(self):
        """Get total count of pets in booking"""
        return self.total_pets or (len(self.pets_booked) if isinstance(self.pets_booked, list) else 0)

    # ========== METHODS ==========
    def get_status_display(self):
        """Get human-readable status for UI display"""
        status_map = {
            'pending': 'Awaiting Merchant Confirmation',
            'confirmed': 'Confirmed',
            'completed': 'Completed',
            'cancelled': 'Cancelled',
        }
        return status_map.get(self.status, self.status)

    def get_status_badge_color(self):
        """Get Tailwind color class for status badge"""
        color_map = {
            'pending': 'yellow',
            'confirmed': 'green',
            'completed': 'blue',
            'cancelled': 'red',
        }
        return color_map.get(self.status, 'gray')

    def get_pets_summary(self):
        """Returns formatted pet information from JSON"""
        if self.pets_booked:
            if isinstance(self.pets_booked, list):
                return self.pets_booked
            elif isinstance(self.pets_booked, dict):
                return [self.pets_booked]
        return []

    def get_booking_duration_text(self):
        """Get human-readable appointment info"""
        if self.appointment_date:
            date_str = self.appointment_date.strftime('%b %d, %Y')
            time_str = self.appointment_time
            service_str = self.service_type or 'Appointment'
            return f"{service_str} on {date_str} at {time_str}"
        return "Appointment scheduled"

    def to_dict(self):
        """Convert booking to dictionary for JSON responses"""
        return {
            'id': self.id,
            'booking_number': self.booking_number,
            'confirmation_code': self.confirmation_code,
            'status': self.status,
            'status_display': self.get_status_display(),
            'customer_name': self.customer_name,
            'customer_email': self.customer_email,
            'customer_phone': self.customer_phone,
            'merchant_name': self.merchant.business_name if self.merchant else None,
            'pets_booked': self.get_pets_summary(),
            'total_pets': self.total_pets_count,
            'appointment_date': self.appointment_date.isoformat() if self.appointment_date else None,
            'appointment_time': self.appointment_time,
            'service_type': self.service_type,
            'business_category': self.business_category,
            'price_breakdown': self.price_breakdown or {},
            'total_amount': self.total_amount,
            'special_requests': self.special_requests,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
            'is_upcoming': self.is_upcoming,
            'can_be_cancelled': self.can_be_cancelled,
        }

    def to_dict_detailed(self):
        """Convert booking to detailed dictionary with all fields"""
        return {
            'id': self.id,
            'booking_number': self.booking_number,
            'confirmation_code': self.confirmation_code,
            'status': self.status,
            'status_display': self.get_status_display(),
            'status_color': self.get_status_badge_color(),
            
            'customer': {
                'name': self.customer_name,
                'email': self.customer_email,
                'phone': self.customer_phone,
            },
            
            'merchant': {
                'id': self.merchant_id,
                'name': self.merchant.business_name if self.merchant else None,
                'category': self.merchant.business_category if self.merchant else None,
            },
            
            'pets': {
                'list': self.get_pets_summary(),
                'total_count': self.total_pets_count,
                'special_notes': self.pet_special_notes,
            },
            
            'appointment': {
                'appointment_date': self.appointment_date.isoformat() if self.appointment_date else None,
                'appointment_time': self.appointment_time,
                'service_type': self.service_type,
                'business_category': self.business_category,
                'duration_text': self.get_booking_duration_text(),
            },
            
            'pricing': {
                'price_breakdown': self.price_breakdown or {},
                'total_amount': self.total_amount,
            },
            
            'confirmation': {
                'merchant_confirmed': self.merchant_confirmed,
                'confirmed_at': self.merchant_confirmed_at.isoformat() if self.merchant_confirmed_at else None,
            },
            
            'notes': {
                'special_requests': self.special_requests,
            },
            
            'timestamps': {
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            },
            
            'status_flags': {
                'is_pending': self.is_pending,
                'is_confirmed': self.is_confirmed,
                'is_completed': self.is_completed,
                'is_cancelled': self.is_cancelled,
                'is_active': self.is_active,
                'is_upcoming': self.is_upcoming,
                'is_past': self.is_past,
                'can_be_cancelled': self.can_be_cancelled,
            }
        }
