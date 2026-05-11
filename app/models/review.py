"""Review model for customer reviews of merchant services"""
from datetime import datetime
from app.extensions import db
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


class Review(db.Model):
    """
    Review model for customer reviews of pet service merchants.
    Inspired by Shopee's review system with star ratings and comments.
    """
    __tablename__ = "reviews"

    # ========== PRIMARY & FOREIGN KEYS ==========
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    booking = db.relationship('Booking', foreign_keys=[booking_id], backref=db.backref('review', uselist=False, cascade='all, delete-orphan'))
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('reviews', cascade='all, delete-orphan', lazy='dynamic'))
    
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False, index=True)
    merchant = db.relationship('Merchant', foreign_keys=[merchant_id], backref=db.backref('reviews', cascade='all, delete-orphan', lazy='dynamic'))

    # ========== REVIEW RATINGS (Shopee-inspired 5-star system) ==========
    # Overall rating from 1-5 stars
    overall_rating = db.Column(db.Float, nullable=False)  # Range: 1.0 to 5.0
    
    # Detailed ratings for different aspects
    service_quality_rating = db.Column(db.Integer, nullable=False, default=5)  # 1-5
    cleanliness_rating = db.Column(db.Integer, nullable=False, default=5)  # 1-5
    staff_friendliness_rating = db.Column(db.Integer, nullable=False, default=5)  # 1-5
    value_for_money_rating = db.Column(db.Integer, nullable=False, default=5)  # 1-5

    # ========== REVIEW CONTENT ==========
    title = db.Column(db.String(200), nullable=False)  # Short review title
    comment = db.Column(LONGTEXT, nullable=True)  # Full review comment
    
    # Tags/highlights for quick review summary (e.g., ['Great Service', 'Clean', 'Affordable'])
    highlights = db.Column(db.JSON, nullable=True, default=list)

    # ========== REVIEW METADATA ==========
    is_verified_purchase = db.Column(db.Boolean, default=True)  # Is this from completed booking
    is_helpful = db.Column(db.Boolean, nullable=True)  # Merchant response status
    
    # For handling review moderation
    is_approved = db.Column(db.Boolean, default=True)  # Admin approval (for moderation)
    rejection_reason = db.Column(LONGTEXT, nullable=True)  # Why review was rejected

    # ========== MERCHANT RESPONSE ==========
    merchant_response = db.Column(LONGTEXT, nullable=True)  # Merchant's response to review
    merchant_response_at = db.Column(db.DateTime, nullable=True)  # When merchant replied
    
    # ========== TIMESTAMPS ==========
    created_at = db.Column(db.DateTime, default=get_ph_datetime, index=True)
    updated_at = db.Column(db.DateTime, default=get_ph_datetime, onupdate=get_ph_datetime)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (
        db.Index('idx_merchant_rating', 'merchant_id', 'overall_rating'),
        db.Index('idx_user_merchant', 'user_id', 'merchant_id'),
        db.Index('idx_created_at', 'created_at'),
    )

    def __repr__(self):
        return f'<Review {self.id} - Rating: {self.overall_rating}/5 - Merchant: {self.merchant_id}>'

    @property
    def rating_as_stars(self):
        """Return rating as visual stars string"""
        full_stars = int(self.overall_rating)
        has_half_star = (self.overall_rating % 1) >= 0.5
        
        stars = '★' * full_stars
        if has_half_star and full_stars < 5:
            stars += '⯨'
        stars += '☆' * (5 - full_stars - (1 if has_half_star else 0))
        return stars

    @property
    def average_aspect_rating(self):
        """Calculate average of all aspect ratings"""
        total = (self.service_quality_rating + 
                self.cleanliness_rating + 
                self.staff_friendliness_rating + 
                self.value_for_money_rating)
        return total / 4.0

    @property
    def has_merchant_response(self):
        """Check if merchant has replied to this review"""
        return self.merchant_response is not None

    def get_highlight_badges(self):
        """Get highlights as list"""
        return self.highlights if isinstance(self.highlights, list) else []

    def set_highlights(self, highlights_list):
        """Set highlights from a list"""
        if isinstance(highlights_list, list):
            self.highlights = highlights_list[:5]  # Max 5 highlights
        return self

    def mark_helpful(self):
        """Mark review as helpful"""
        self.is_helpful = True
        self.updated_at = get_ph_datetime()

    def add_merchant_response(self, response_text):
        """Add merchant response to review"""
        self.merchant_response = response_text
        self.merchant_response_at = get_ph_datetime()
        self.updated_at = get_ph_datetime()

    def to_dict(self):
        """Convert review to dictionary for API responses"""
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'user': {
                'id': self.user_id,
                'name': f"{self.user.first_name} {self.user.last_name}" if self.user else 'Anonymous',
                'photo': self.user.photo_url if self.user else None,
            },
            'merchant_id': self.merchant_id,
            'overall_rating': self.overall_rating,
            'rating_as_stars': self.rating_as_stars,
            'service_quality_rating': self.service_quality_rating,
            'cleanliness_rating': self.cleanliness_rating,
            'staff_friendliness_rating': self.staff_friendliness_rating,
            'value_for_money_rating': self.value_for_money_rating,
            'title': self.title,
            'comment': self.comment,
            'highlights': self.highlights,
            'is_verified_purchase': self.is_verified_purchase,
            'is_helpful': self.is_helpful,
            'merchant_response': self.merchant_response,
            'merchant_response_at': self.merchant_response_at.isoformat() if self.merchant_response_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
