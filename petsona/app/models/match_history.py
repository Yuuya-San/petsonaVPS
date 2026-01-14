from datetime import datetime, timedelta
from app.extensions import db
import json
import pytz


class MatchHistory(db.Model):
    __tablename__ = "match_history"

    id = db.Column(db.Integer, primary_key=True)
    
    # User reference (optional - supports anonymous users)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    
    # Match type: 'general' for species/breed suggestions, 'breed' for specific breed matching
    match_type = db.Column(db.String(20), nullable=False, index=True)  # 'general' or 'breed'
    
    # Breed reference (only for breed-specific matching)
    breed_id = db.Column(db.Integer, db.ForeignKey('breed.id'), nullable=True, index=True)
    
    # Quiz answers stored as JSON
    quiz_answers = db.Column(db.JSON, nullable=False)
    
    # Results
    compatibility_score = db.Column(db.Float, nullable=False)  # 0-100
    compatibility_level = db.Column(db.String(50), nullable=False)  # Excellent, Good, Fair, Poor
    
    # Top 5 matches (for general matching)
    top_matches = db.Column(db.JSON, nullable=True)  # List of {breed_id, breed_name, score, level}
    
    # Detailed breakdown
    category_scores = db.Column(db.JSON, nullable=True)  # {lifestyle, experience, space, care, etc.}
    mismatches = db.Column(db.JSON, nullable=True)  # List of mismatch descriptions
    improvement_suggestions = db.Column(db.JSON, nullable=True)  # List of suggestion objects
    strength_areas = db.Column(db.JSON, nullable=True)  # List of strength descriptions
    
    # Device and session info
    device_type = db.Column(db.String(100), nullable=True)
    session_id = db.Column(db.String(100), nullable=True, index=True)
    source = db.Column(db.String(100), nullable=True)  # 'direct', 'species_page', 'breed_page'
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='match_histories')
    breed = db.relationship('Breed', backref='match_histories')
    
    @property
    def as_dict(self):
        """Convert to dictionary for JSON serialization"""
        try:
            breed_dict = None
            if self.breed:
                try:
                    breed_dict = {
                        'id': self.breed.id,
                        'name': self.breed.name,
                        'image_url': self.breed.image_url,
                        'species_id': self.breed.species_id,
                        'species_name': self.breed.species.name if self.breed.species else None,
                    }
                except Exception as e:
                    print(f"[ERROR] Failed to serialize breed: {e}")
                    breed_dict = None
            
            # Convert UTC timestamp to Philippines Time (UTC+8)
            created_at_pht = None
            if self.created_at:
                try:
                    utc_tz = pytz.UTC
                    pht_tz = pytz.timezone('Asia/Manila')
                    # Make created_at timezone-aware if it isn't already
                    if self.created_at.tzinfo is None:
                        created_at_utc = utc_tz.localize(self.created_at)
                    else:
                        created_at_utc = self.created_at
                    created_at_pht = created_at_utc.astimezone(pht_tz).isoformat()
                except Exception as e:
                    print(f"[ERROR] Failed to convert timestamp: {e}")
                    created_at_pht = self.created_at.isoformat() if self.created_at else None
            
            return {
                'id': self.id,
                'user_id': self.user_id,
                'match_type': self.match_type,
                'breed_id': self.breed_id,
                'breed': breed_dict,
                'compatibility_score': float(self.compatibility_score) if self.compatibility_score else 0,
                'compatibility_level': self.compatibility_level or 'Unknown',
                'top_matches': self.top_matches or [],
                'category_scores': self.category_scores or {},
                'mismatches': self.mismatches or [],
                'improvement_suggestions': self.improvement_suggestions or [],
                'strength_areas': self.strength_areas or [],
                'device_type': self.device_type,
                'source': self.source,
                'created_at': created_at_pht,
            }
        except Exception as e:
            print(f"[ERROR] Failed to convert match to dict: {e}")
            return {
                'id': self.id,
                'user_id': self.user_id,
                'match_type': self.match_type,
                'breed_id': self.breed_id,
                'breed': None,
                'compatibility_score': 0,
                'compatibility_level': 'Unknown',
                'top_matches': [],
                'category_scores': {},
                'mismatches': [],
                'improvement_suggestions': [],
                'strength_areas': [],
                'device_type': None,
                'source': None,
                'created_at': None,
            }
    
    def __repr__(self):
        return f"<MatchHistory {self.id} - {self.match_type} - {self.compatibility_score}%>"
