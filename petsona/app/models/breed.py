from datetime import datetime
from app.extensions import db


class Breed(db.Model):
    __tablename__ = 'breed'

    id = db.Column(db.Integer, primary_key=True)

    species_id = db.Column(db.Integer,db.ForeignKey('species.id'),nullable=False)
    name = db.Column(db.String(100), nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False)
    temperament = db.Column(db.String(255))
    image_url = db.Column(db.String(255), nullable=False)
    energy_level = db.Column(db.Enum('Low', 'Medium', 'High'),default='Medium')
    exercise_needs = db.Column(db.Enum('Low', 'Medium', 'High'),default='Medium')
    grooming_needs = db.Column(db.Enum('Low', 'Medium', 'High'),default='Medium')
    space_needs = db.Column(db.Enum('Small', 'Medium', 'Large'),default='Medium')
    trainability = db.Column(db.Enum('Easy', 'Moderate', 'Difficult'),default='Moderate')
    handling_tolerance = db.Column(db.Enum('Low', 'Medium', 'High'),default='Medium')
    noise_level = db.Column(db.Enum('Silent', 'Low', 'Moderate', 'Loud'),default='Low')
    social_needs = db.Column(db.Enum('Low', 'Medium', 'High'),default='Medium')
    prey_drive = db.Column(db.Enum('None', 'Low', 'Medium', 'High'),default='None',nullable=False)
    care_intensity = db.Column(db.Enum('Low', 'Medium', 'High'),default='Medium')
    time_commitment = db.Column(db.Enum('Low', 'Medium', 'High'),default='Medium')
    experience_required = db.Column(db.Enum('Beginner', 'Intermediate', 'Advanced'),default='Beginner')
    environment_complexity = db.Column(db.Enum('Simple', 'Moderate', 'Complex'),default='Simple')
    compatibility_risk = db.Column(db.Enum('Low', 'Medium', 'High'),default='Low')
    preventive_care_level = db.Column(db.Enum('Low', 'Medium', 'High'),default='Medium',comment="Frequency of vet visits, vaccines, parasite control")
    common_health_issues = db.Column(db.Text,comment="Breed-typical health issues vets warn about")
    emergency_care_risk = db.Column(db.Enum('Low', 'Medium', 'High'),default='Low',comment="Likelihood of emergency or sudden medical costs")
    stress_sensitivity = db.Column(db.Enum('Low', 'Medium', 'High'),default='Medium',comment="How easily the pet becomes stressed by change")
    monthly_cost_level = db.Column(db.Enum('Low', 'Medium', 'High'),default='Medium',comment="Food, grooming, routine care")
    lifetime_cost_level = db.Column(db.Enum('Low', 'Medium', 'High'),default='Medium',comment="Expected long-term financial commitment")
    care_cost = db.Column(db.Float)
    lifespan = db.Column(db.Integer)
    allergy_friendly = db.Column(db.Boolean,default=False,comment="Suitable for allergy-sensitive owners")
    child_friendly = db.Column(db.Boolean,default=True,comment="Safe and tolerant around children")
    senior_friendly = db.Column(db.Boolean,default=True,comment="Suitable for elderly owners")
    dog_friendly = db.Column(db.Boolean, default=True)
    cat_friendly = db.Column(db.Boolean, default=True)
    small_pet_friendly = db.Column(db.Boolean, default=True)
    min_enclosure_size = db.Column(db.Integer,nullable=True,comment="Tank or cage size depending on species")

    # --------------------------
    # Status & timestamps
    # --------------------------
    is_active = db.Column(db.Boolean, default=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def soft_delete(self):
        self.deleted_at = datetime.utcnow()
        self.is_active = False

    def ui_badges(self):
        return {
            "Energy": self.energy_level,
            "Care": self.care_intensity,
            "Space": self.space_needs,
            "Noise": self.noise_level,
            "Budget": self.monthly_cost_level,
            "Health Risk": self.emergency_care_risk
        }

    @property
    def as_dict(self):
        return {
            # --------------------------
            # Identity
            # --------------------------
            "id": self.id,
            "species_id": self.species_id,
            "name": self.name,
            "summary": self.summary,
            "temperament": self.temperament,
            "image_url": self.image_url,

            # --------------------------
            # Lifestyle & Behavior
            # --------------------------
            "energy_level": self.energy_level,
            "exercise_needs": self.exercise_needs,
            "grooming_needs": self.grooming_needs,
            "noise_level": self.noise_level,
            "social_needs": self.social_needs,
            "prey_drive": self.prey_drive,
            "handling_tolerance": self.handling_tolerance,

            # --------------------------
            # Space & Environment
            # --------------------------
            "space_needs": self.space_needs,
            "environment_complexity": self.environment_complexity,
            "min_enclosure_size": self.min_enclosure_size,

            # --------------------------
            # Experience & Time
            # --------------------------
            "care_intensity": self.care_intensity,
            "time_commitment": self.time_commitment,
            "experience_required": self.experience_required,
            "trainability": self.trainability,

            # --------------------------
            # Health & Veterinary Factors
            # --------------------------
            "preventive_care_level": self.preventive_care_level,
            "emergency_care_risk": self.emergency_care_risk,
            "stress_sensitivity": self.stress_sensitivity,
            "common_health_issues": self.common_health_issues,
            "lifespan": self.lifespan,

            # --------------------------
            # Financial Reality
            # --------------------------
            "monthly_cost_level": self.monthly_cost_level,
            "lifetime_cost_level": self.lifetime_cost_level,
            "estimated_care_cost": self.care_cost,

            # --------------------------
            # Household Compatibility
            # --------------------------
            "allergy_friendly": self.allergy_friendly,
            "child_friendly": self.child_friendly,
            "senior_friendly": self.senior_friendly,
            "dog_friendly": self.dog_friendly,
            "cat_friendly": self.cat_friendly,
            "small_pet_friendly": self.small_pet_friendly,

            # --------------------------
            # Risk & Responsibility
            # --------------------------
            "compatibility_risk": self.compatibility_risk,
            "is_active": self.is_active
        }

