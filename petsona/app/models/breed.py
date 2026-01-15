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
    care_cost = db.Column(db.String(255),comment="Estimated average annual care cost")
    lifespan = db.Column(db.String(50),comment="Average life expectancy")
    allergy_friendly = db.Column(db.Boolean,default=False,comment="Suitable for allergy-sensitive owners")
    child_friendly = db.Column(db.Boolean,default=True,comment="Safe and tolerant around children")
    senior_friendly = db.Column(db.Boolean,default=True,comment="Suitable for elderly owners")
    dog_friendly = db.Column(db.Boolean, default=True)
    cat_friendly = db.Column(db.Boolean, default=True)
    small_pet_friendly = db.Column(db.Boolean, default=True)
    min_enclosure_size = db.Column(db.String(100),comment="Minimum recommended enclosure size for the breed")

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
        from markupsafe import escape
        return {
            # --------------------------
            # Identity
            # --------------------------
            "id": self.id,
            "species_id": self.species_id,
            "name": escape(self.name) if self.name else "",
            "summary": escape(self.summary) if self.summary else "",
            "temperament": escape(self.temperament) if self.temperament else "",
            "image_url": escape(self.image_url) if self.image_url else "",

            # --------------------------
            # Lifestyle & Behavior
            # --------------------------
            "energy_level": escape(self.energy_level) if self.energy_level else "",
            "exercise_needs": escape(self.exercise_needs) if self.exercise_needs else "",
            "grooming_needs": escape(self.grooming_needs) if self.grooming_needs else "",
            "noise_level": escape(self.noise_level) if self.noise_level else "",
            "social_needs": escape(self.social_needs) if self.social_needs else "",
            "prey_drive": escape(self.prey_drive) if self.prey_drive else "",
            "handling_tolerance": escape(self.handling_tolerance) if self.handling_tolerance else "",

            # --------------------------
            # Space & Environment
            # --------------------------
            "space_needs": escape(self.space_needs) if self.space_needs else "",
            "environment_complexity": escape(self.environment_complexity) if self.environment_complexity else "",
            "min_enclosure_size": escape(self.min_enclosure_size) if self.min_enclosure_size else "",

            # --------------------------
            # Experience & Time
            # --------------------------
            "care_intensity": escape(self.care_intensity) if self.care_intensity else "",
            "time_commitment": escape(self.time_commitment) if self.time_commitment else "",
            "experience_required": escape(self.experience_required) if self.experience_required else "",
            "trainability": escape(self.trainability) if self.trainability else "",

            # --------------------------
            # Health & Veterinary Factors
            # --------------------------
            "preventive_care_level": escape(self.preventive_care_level) if self.preventive_care_level else "",
            "emergency_care_risk": escape(self.emergency_care_risk) if self.emergency_care_risk else "",
            "stress_sensitivity": escape(self.stress_sensitivity) if self.stress_sensitivity else "",
            "common_health_issues": escape(self.common_health_issues) if self.common_health_issues else "",
            "lifespan": escape(self.lifespan) if self.lifespan else "",

            # --------------------------
            # Financial Reality
            # --------------------------
            "monthly_cost_level": escape(self.monthly_cost_level) if self.monthly_cost_level else "",
            "lifetime_cost_level": escape(self.lifetime_cost_level) if self.lifetime_cost_level else "",
            "estimated_care_cost": escape(self.care_cost) if self.care_cost else "",
            "care_cost": escape(self.care_cost) if self.care_cost else "",

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
            "compatibility_risk": escape(self.compatibility_risk) if self.compatibility_risk else "",
            "is_active": self.is_active
        }

