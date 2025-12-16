from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from .extensions import db, bcrypt
import json


# Utility function to create an admin user (call from shell or script)
from typing import Optional

def create_admin(email: str, password: str, photo_url: Optional[str] = None):
    """
    Creates an 'admin' user directly in the database.

    Commits the new user to the session, handling basic database errors.

    :param email: The user's email address (will be converted to lowercase).
    :param password: The plain-text password to be securely hashed.
    :param photo_url: An optional URL for the user's profile picture.
    :return: The created User object on success, or None on failure.
    """
    try:
        # 1. Create the User object
        admin = User(
            email=email.lower(),
            role='admin',
            photo_url=photo_url
        )

        # 2. Set the password (this should hash it internally)
        admin.set_password(password)

        # 3. Add to session and commit
        db.session.add(admin)
        db.session.commit()

        print(f"✅ Admin user '{email}' created successfully.")
        return admin

    except Exception as e:
        # Roll back the transaction in case of an error
        db.session.rollback()
        print(f"❌ Error creating admin user '{email}': {e}")
        return None

# --------------------------
# User model (existing)
# --------------------------
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(64), nullable=True)      
    last_name = db.Column(db.String(64), nullable=True)       
    photo_url = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Lockout support
    failed_login_attempts = db.Column(db.Integer, default=0)
    lockout_until = db.Column(db.DateTime, nullable=True)

    # Role-based access
    role = db.Column(db.String(32), default='user', nullable=False, index=True)  # 'user' or 'admin'

    # 2FA support
    totp_secret = db.Column(db.String(32), nullable=True)
    is_2fa_enabled = db.Column(db.Boolean, default=False)

    def set_password(self, password: str):
        """Hashes the password and stores it."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        """Verifies the password."""
        return bcrypt.check_password_hash(self.password_hash, password)

# --------------------------
# AuditLog model (existing)
# --------------------------
class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(128), nullable=False)          # e.g. 'user.login_success'
    actor_id = db.Column(db.Integer, nullable=True)            # user id if applicable
    actor_email = db.Column(db.String(255), nullable=True)     # email if applicable
    ip_address = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    details = db.Column(db.Text, nullable=True)                # JSON blob for extra context

    # --- NEW METHOD ---
    def set_details(self, data: dict):
        """Store extra information as JSON string."""
        try:
            self.details = json.dumps(data)
        except Exception:
            self.details = None

    def get_details(self) -> dict:
        """Retrieve extra information as dictionary."""
        if not self.details:
            return {}
        try:
            return json.loads(self.details)
        except Exception:
            return {}

    # ---------- BACKWARD COMPATIBILITY ----------
    def set_metadata(self, data: dict):
        """Alias for old code still using set_metadata()."""
        return self.set_details(data)

    def get_metadata(self) -> dict:
        """Alias for old code using get_metadata()."""
        return self.get_details()


# --------------------------
# Species model
# --------------------------
class Species(db.Model):
    __tablename__ = 'species'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    legal_status = db.Column(db.Enum('Allowed', 'Restricted', 'Permit Required'), default='Allowed')

    breeds = db.relationship('Breed', backref='species', lazy=True)

    def __repr__(self):
        return f"<Species {self.name}>"


# --------------------------
# Breed model
# --------------------------
class Breed(db.Model):
    __tablename__ = 'breed'
    id = db.Column(db.Integer, primary_key=True)
    species_id = db.Column(db.Integer, db.ForeignKey('species.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    summary = db.Column(db.Text, nullable=False)  # Single sentence description
    temperament = db.Column(db.String(50))
    energy_level = db.Column(db.Enum('Low', 'Medium', 'High'), default='Medium')
    exercise_needs = db.Column(db.String(100))
    grooming_needs = db.Column(db.Enum('Low', 'Medium', 'High'), default='Medium')
    space_needs = db.Column(db.Enum('Small', 'Medium', 'Large'), default='Medium')
    trainability = db.Column(db.Enum('Easy', 'Moderate', 'Difficult'), default='Moderate')
    health_issues = db.Column(db.Text)
    lifespan = db.Column(db.Integer)
    care_cost = db.Column(db.Float)  # Estimated monthly cost
    personality_traits = db.Column(db.JSON)  # e.g., ["loyal","playful"]
    allergy_friendly = db.Column(db.Boolean, default=False)
    image_url = db.Column(db.String(255))

    def __repr__(self):
        return f"<Breed {self.name}>"


# --------------------------
# Owner profile (for compatibility test)
# --------------------------
class OwnerProfile(db.Model):
    __tablename__ = 'owner_profile'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    age = db.Column(db.Integer)
    residence_size = db.Column(db.Enum('Small', 'Medium', 'Large'), default='Medium')
    activity_level = db.Column(db.Enum('Low', 'Medium', 'High'), default='Medium')
    experience = db.Column(db.Enum('Beginner', 'Intermediate', 'Advanced'), default='Beginner')
    budget = db.Column(db.Float)
    allergies = db.Column(db.Boolean, default=False)
    preferred_species = db.Column(db.JSON)  # e.g., ["Dog","Cat"]
    preferred_temperament = db.Column(db.JSON)  # e.g., ["Calm","Friendly"]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='owner_profile', lazy=True)

    def __repr__(self):
        return f"<OwnerProfile User:{self.user_id}>"


# --------------------------
# Compatibility score
# --------------------------
class CompatibilityScore(db.Model):
    __tablename__ = 'compatibility_score'
    id = db.Column(db.Integer, primary_key=True)
    owner_profile_id = db.Column(db.Integer, db.ForeignKey('owner_profile.id'), nullable=False)
    breed_id = db.Column(db.Integer, db.ForeignKey('breed.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)  # 0-100
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner_profile = db.relationship('OwnerProfile', backref='compatibility_scores')
    breed = db.relationship('Breed', backref='compatibility_scores')

    def __repr__(self):
        return f"<CompatibilityScore OwnerProfile:{self.owner_profile_id} Breed:{self.breed_id} Score:{self.score}>"
