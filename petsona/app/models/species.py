from datetime import datetime
from app.extensions import db
from app.models.breed import Breed
from app.utils.icons import get_species_icon
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


class Species(db.Model):
    __tablename__ = "species"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(100),nullable=True,comment="Optional icon class for UI use")
    requires_exercise = db.Column(db.Boolean, default=False)
    requires_training = db.Column(db.Boolean, default=False)
    requires_grooming = db.Column(db.Boolean, default=False)
    requires_enclosure = db.Column(db.Boolean, default=False)
    predatory_species = db.Column(db.Boolean, default=False)
    fragile_species = db.Column(db.Boolean, default=False)
    beginner_friendly = db.Column(db.Boolean,default=True,comment="False if most breeds require advanced care")
    abandonment_risk_level = db.Column(db.Enum("Low", "Medium", "High"),default="Medium",comment="Species-level abandonment trends")
    ethical_notes = db.Column(db.Text,comment="Species-level welfare concerns")
    requires_permit = db.Column(db.Boolean,default=False,comment="Local permits may be required")
    special_vet_required = db.Column(db.Boolean,default=False,comment="Exotic or specialized vet care needed")
    heart_vote_count = db.Column(db.Integer, default=0, comment="Total heart votes from all users")

    deleted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=get_ph_datetime)
    updated_at = db.Column(db.DateTime, onupdate=get_ph_datetime)

    breeds = db.relationship("Breed", backref="species", lazy="dynamic")

    def soft_delete(self):
        self.deleted_at = get_ph_datetime()

    def update_breed_count(self):
        self.active_breeds_count = self.breeds.filter(
            Breed.deleted_at.is_(None),
            Breed.is_active.is_(True)
        ).count()

    @property
    def active_breed_count(self):
        return self.breeds.filter(
            Breed.deleted_at.is_(None),
            Breed.is_active.is_(True)
        ).count()

    def increment_heart_votes(self):
        """Increment heart vote count"""
        self.heart_vote_count = (self.heart_vote_count or 0) + 1
    
    def decrement_heart_votes(self):
        """Decrement heart vote count"""
        self.heart_vote_count = max(0, (self.heart_vote_count or 0) - 1)

    @property
    def display_icon(self):
        """Returns the icon to display: manual icon if set, otherwise auto-generated from species name"""
        if self.icon:
            return self.icon
        return get_species_icon(self.name)

    @property
    def as_dict(self):
        from markupsafe import escape
        return {
            "id": self.id,
            "name": escape(self.name) if self.name else "",
            "description": escape(self.description) if self.description else "",
            "image_url": escape(self.image_url) if self.image_url else "",
            "icon": escape(self.display_icon) if self.display_icon else "",

            "requires_exercise": self.requires_exercise,
            "requires_training": self.requires_training,
            "requires_grooming": self.requires_grooming,
            "requires_enclosure": self.requires_enclosure,

            "predatory_species": self.predatory_species,
            "fragile_species": self.fragile_species,

            "beginner_friendly": self.beginner_friendly,
            "abandonment_risk_level": escape(self.abandonment_risk_level) if self.abandonment_risk_level else "",

            "requires_permit": self.requires_permit,
            "special_vet_required": self.special_vet_required,

            "ethical_notes": escape(self.ethical_notes) if self.ethical_notes else "",
            
            "active_breed_count": self.active_breed_count
        }

    def __repr__(self):
        return f"<Species {self.name}>"
