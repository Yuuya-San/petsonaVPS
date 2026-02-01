"""Booking model for online reservations at merchant services"""
from datetime import datetime
from app.extensions import db
from sqlalchemy.dialects.mysql import JSON, LONGTEXT


class Booking(db.Model):
    """
    Booking model for managing online reservations at merchant services.
    Inspired by e-commerce platforms like Grab, Shopee, Lazada, and Panda.
    Handles reservations WITHOUT real money transactions.
    """
    __tablename__ = "bookings"

    # ========== SECTION 1: PRIMARY & FOREIGN KEYS ==========
    id = db.Column(db.Integer, primary_key=True)
    
    # Customer (User who made the booking)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('bookings', cascade='all, delete-orphan', lazy='dynamic'))
    
    # Merchant (Service provider)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False, index=True)
    merchant = db.relationship('Merchant', foreign_keys=[merchant_id], backref=db.backref('bookings', cascade='all, delete-orphan', lazy='dynamic'))

    # ========== SECTION 2: BOOKING IDENTIFICATION ==========
    booking_number = db.Column(db.String(50), unique=True, nullable=False, index=True)  # e.g., BK-2026-001234
    status = db.Column(db.String(50), nullable=False, default='pending', index=True)  # pending, confirmed, completed, cancelled, no-show
    
    # ========== SECTION 3: CUSTOMER CONTACT INFO ==========
    customer_name = db.Column(db.String(128), nullable=False)
    customer_email = db.Column(db.String(255), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    special_requests = db.Column(LONGTEXT, nullable=True)  # Additional customer notes/requests

    # ========== SECTION 4: SERVICE DETAILS ==========
    # Services selected from merchant.services_offered
    services_booked = db.Column(JSON, nullable=False, default=[])  # Array of service names
    service_description = db.Column(LONGTEXT, nullable=True)  # Detailed description of services

    # ========== SECTION 5: PET INFORMATION ==========
    # Can book multiple pets
    pets_booked = db.Column(JSON, nullable=False, default=[])  # Array of {pet_id, pet_name, species, breed, age, special_needs}
    total_pets = db.Column(db.Integer, default=1, nullable=False)
    pet_special_notes = db.Column(LONGTEXT, nullable=True)  # Dietary, behavioral, medical notes

    # ========== SECTION 6: RESERVATION DATES & TIMES ==========
    check_in_date = db.Column(db.DateTime, nullable=False, index=True)
    check_out_date = db.Column(db.DateTime, nullable=False, index=True)
    check_in_time = db.Column(db.String(5), nullable=False)  # HH:MM format
    check_out_time = db.Column(db.String(5), nullable=False)  # HH:MM format
    duration_days = db.Column(db.Integer, nullable=False)  # Calculated days
    
    # ========== SECTION 7: PICKUP & DELIVERY (OPTIONAL) ==========
    requires_pickup = db.Column(db.Boolean, default=False)
    requires_delivery = db.Column(db.Boolean, default=False)
    pickup_location = db.Column(db.String(500), nullable=True)  # Customer pickup address
    pickup_time = db.Column(db.String(5), nullable=True)  # HH:MM
    delivery_location = db.Column(db.String(500), nullable=True)  # Return delivery address
    delivery_time = db.Column(db.String(5), nullable=True)  # HH:MM

    # ========== SECTION 8: PRICING & REVENUE SIMULATION ==========
    # No real payment processing, but tracks revenue for analytics
    base_price_per_day = db.Column(db.Float, nullable=False)  # Price per day from merchant
    total_service_cost = db.Column(db.Float, nullable=False)  # Base cost (days * price_per_day * pets)
    
    # Additional charges (optional)
    pickup_fee = db.Column(db.Float, default=0)
    delivery_fee = db.Column(db.Float, default=0)
    additional_services_fee = db.Column(db.Float, default=0)  # Extra services like grooming, training, etc.
    
    # Discounts (promo codes, loyalty, etc.)
    discount_amount = db.Column(db.Float, default=0)
    discount_code = db.Column(db.String(50), nullable=True)  # Promo code used
    
    # Final totals
    subtotal = db.Column(db.Float, nullable=False)  # service_cost + additional fees
    total_amount = db.Column(db.Float, nullable=False)  # subtotal - discount_amount (FINAL PRICE)
    
    # Revenue tracking (for merchant stats/analytics)
    merchant_commission_rate = db.Column(db.Float, default=0.85)  # e.g., 85% to merchant, 15% to platform
    merchant_receives = db.Column(db.Float, nullable=False)  # Amount merchant receives (for stats only)
    platform_fee = db.Column(db.Float, nullable=False)  # Amount platform keeps (for stats only)

    # ========== SECTION 9: PAYMENT SIMULATION (NO REAL TRANSACTIONS) ==========
    payment_method = db.Column(db.String(50), default='simulated', nullable=False)  # 'simulated', 'wallet', 'credit_card', etc.
    payment_status = db.Column(db.String(50), default='pending', nullable=False)  # pending, completed, failed, refunded
    payment_date = db.Column(db.DateTime, nullable=True)  # When payment was "completed"
    
    # Cancellation & Refund Simulation
    cancellation_reason = db.Column(LONGTEXT, nullable=True)  # Why booking was cancelled
    cancellation_date = db.Column(db.DateTime, nullable=True)
    refund_amount = db.Column(db.Float, default=0)  # Simulated refund (based on cancellation policy)
    refund_date = db.Column(db.DateTime, nullable=True)
    refund_status = db.Column(db.String(50), nullable=True)  # pending, completed, denied

    # ========== SECTION 10: BOOKING CONFIRMATION & COMMUNICATION ==========
    confirmation_code = db.Column(db.String(50), unique=True, nullable=False, index=True)  # Like Grab/Shopee
    merchant_confirmation_required = db.Column(db.Boolean, default=True)
    merchant_confirmed_at = db.Column(db.DateTime, nullable=True)
    merchant_confirmation_notes = db.Column(LONGTEXT, nullable=True)

    # ========== SECTION 11: COMPLETION & RATINGS ==========
    completed_at = db.Column(db.DateTime, nullable=True)
    customer_rating = db.Column(db.Float, nullable=True)  # 1-5 stars
    customer_review = db.Column(LONGTEXT, nullable=True)
    merchant_rating_to_customer = db.Column(db.Float, nullable=True)  # Merchant rate customer
    merchant_notes_on_customer = db.Column(LONGTEXT, nullable=True)

    # ========== SECTION 12: NO-SHOW & PENALTY TRACKING ==========
    no_show = db.Column(db.Boolean, default=False)
    no_show_reason = db.Column(LONGTEXT, nullable=True)
    customer_no_show_penalty = db.Column(db.Float, default=0)  # Penalty for no-show (for analytics)

    # ========== SECTION 13: DOCUMENTS & ATTACHMENTS ==========
    # File paths for receipts, invoices, etc.
    receipt_path = db.Column(db.String(255), nullable=True)
    invoice_path = db.Column(db.String(255), nullable=True)
    additional_documents = db.Column(JSON, nullable=True, default=[])  # Array of file paths

    # ========== SECTION 14: METADATA & TIMESTAMPS ==========
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)  # Soft delete

    # ========== SECTION 15: ANALYTICS & TRACKING ==========
    source = db.Column(db.String(100), nullable=True)  # 'web', 'mobile', 'app'
    notes = db.Column(LONGTEXT, nullable=True)  # Internal notes
    
    # Unique constraint to prevent duplicate bookings for same customer at same merchant for overlapping dates
    __table_args__ = (
        db.UniqueConstraint('booking_number', name='unique_booking_number'),
        db.UniqueConstraint('confirmation_code', name='unique_confirmation_code'),
        db.Index('idx_user_merchant_dates', 'user_id', 'merchant_id', 'check_in_date', 'check_out_date'),
    )

    def __repr__(self):
        return f'<Booking {self.booking_number} - {self.customer_name}>'

    # ========== PROPERTIES & HELPER METHODS ==========
    
    @property
    def is_pending(self):
        """Check if booking is pending confirmation"""
        return self.status == 'pending'

    @property
    def is_confirmed(self):
        """Check if booking is confirmed"""
        return self.status == 'confirmed'

    @property
    def is_completed(self):
        """Check if booking is completed"""
        return self.status == 'completed'

    @property
    def is_cancelled(self):
        """Check if booking is cancelled"""
        return self.status == 'cancelled'

    @property
    def is_no_show(self):
        """Check if customer didn't show up"""
        return self.no_show

    @property
    def is_active(self):
        """Check if booking is currently active (confirmed and within date range)"""
        now = datetime.utcnow()
        return self.is_confirmed and self.check_in_date <= now <= self.check_out_date

    @property
    def is_upcoming(self):
        """Check if booking is in the future"""
        return self.is_confirmed and datetime.utcnow() < self.check_in_date

    @property
    def can_be_cancelled(self):
        """Check if booking can still be cancelled (before check-in)"""
        return self.is_pending or (self.is_confirmed and datetime.utcnow() < self.check_in_date)

    @property
    def payment_complete(self):
        """Check if payment is simulated as complete"""
        return self.payment_status == 'completed'

    def calculate_merchant_split(self):
        """Calculate and update merchant commission and platform fee"""
        self.merchant_receives = round(self.total_amount * self.merchant_commission_rate, 2)
        self.platform_fee = round(self.total_amount - self.merchant_receives, 2)

    def calculate_refund(self, cancellation_policy_percentage=50):
        """
        Simulate refund based on cancellation policy and when booking was cancelled.
        Different platforms have different policies.
        
        Args:
            cancellation_policy_percentage: % of amount to refund (e.g., 50%, 75%, 100%)
        """
        if self.payment_status == 'completed':
            self.refund_amount = round(self.total_amount * (cancellation_policy_percentage / 100), 2)
            self.refund_status = 'pending'

    def get_pets_summary(self):
        """Returns formatted pet information"""
        if isinstance(self.pets_booked, list):
            return self.pets_booked
        return []

    def get_services_summary(self):
        """Returns formatted services information"""
        if isinstance(self.services_booked, list):
            return self.services_booked
        return []

    def to_dict(self):
        """Convert booking to dictionary for JSON responses"""
        return {
            'id': self.id,
            'booking_number': self.booking_number,
            'confirmation_code': self.confirmation_code,
            'status': self.status,
            'customer_name': self.customer_name,
            'customer_email': self.customer_email,
            'customer_phone': self.customer_phone,
            'merchant_name': self.merchant.business_name if self.merchant else None,
            'services_booked': self.get_services_summary(),
            'pets_booked': self.get_pets_summary(),
            'check_in_date': self.check_in_date.isoformat() if self.check_in_date else None,
            'check_out_date': self.check_out_date.isoformat() if self.check_out_date else None,
            'duration_days': self.duration_days,
            'total_amount': self.total_amount,
            'payment_status': self.payment_status,
            'customer_rating': self.customer_rating,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
            'is_upcoming': self.is_upcoming,
            'can_be_cancelled': self.can_be_cancelled,
        }

    def to_dict_detailed(self):
        """Convert booking to detailed dictionary with all fields for JSON responses"""
        return {
            'id': self.id,
            'booking_number': self.booking_number,
            'confirmation_code': self.confirmation_code,
            'status': self.status,
            'customer': {
                'name': self.customer_name,
                'email': self.customer_email,
                'phone': self.customer_phone,
            },
            'merchant': {
                'id': self.merchant_id,
                'name': self.merchant.business_name if self.merchant else None,
                'type': self.merchant.business_type if self.merchant else None,
            },
            'services': self.get_services_summary(),
            'pets': self.get_pets_summary(),
            'reservation': {
                'check_in_date': self.check_in_date.isoformat() if self.check_in_date else None,
                'check_in_time': self.check_in_time,
                'check_out_date': self.check_out_date.isoformat() if self.check_out_date else None,
                'check_out_time': self.check_out_time,
                'duration_days': self.duration_days,
            },
            'pricing': {
                'base_price_per_day': self.base_price_per_day,
                'subtotal': self.subtotal,
                'pickup_fee': self.pickup_fee,
                'delivery_fee': self.delivery_fee,
                'additional_services_fee': self.additional_services_fee,
                'discount_amount': self.discount_amount,
                'discount_code': self.discount_code,
                'total_amount': self.total_amount,
            },
            'payment': {
                'method': self.payment_method,
                'status': self.payment_status,
                'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            },
            'merchant_split': {
                'merchant_receives': self.merchant_receives,
                'platform_fee': self.platform_fee,
                'commission_rate': self.merchant_commission_rate,
            },
            'ratings': {
                'customer_rating': self.customer_rating,
                'customer_review': self.customer_review,
                'merchant_rating': self.merchant_rating_to_customer,
            },
            'cancellation': {
                'cancelled': self.is_cancelled,
                'cancellation_date': self.cancellation_date.isoformat() if self.cancellation_date else None,
                'cancellation_reason': self.cancellation_reason,
                'refund_amount': self.refund_amount,
                'refund_status': self.refund_status,
            },
            'no_show': {
                'is_no_show': self.no_show,
                'reason': self.no_show_reason,
                'penalty': self.customer_no_show_penalty,
            },
            'timestamps': {
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
                'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            },
            'status_flags': {
                'is_pending': self.is_pending,
                'is_confirmed': self.is_confirmed,
                'is_completed': self.is_completed,
                'is_cancelled': self.is_cancelled,
                'is_active': self.is_active,
                'is_upcoming': self.is_upcoming,
                'can_be_cancelled': self.can_be_cancelled,
            }
        }
