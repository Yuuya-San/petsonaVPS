from datetime import datetime
from app.extensions import db
import pytz
from markupsafe import escape
import re

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    return datetime.now(PH_TZ)


def get_utc_now():
    return datetime.utcnow()


# Validation helpers
def validate_pet_name(name):
    """Validate pet name - max 120 chars, alphanumeric + common characters"""
    if not name or not isinstance(name, str):
        return False
    name = name.strip()
    if len(name) < 1 or len(name) > 120:
        return False
    # Allow letters, numbers, spaces, hyphens, apostrophes
    if not re.match(r"^[a-zA-Z0-9\s\-']+$", name):
        return False
    return True


def validate_enum_field(value, valid_options, default):
    """Validate enum field value"""
    if value and value.strip() in valid_options:
        return value.strip()
    return default


class MyPet(db.Model):
    __tablename__ = 'my_pet'

    id = db.Column(db.Integer, primary_key=True)
    # Reference the users table (User.__tablename__ == 'users')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    species = db.Column(db.String(120))
    breed = db.Column(db.String(120))
    age = db.Column(db.String(50))
    sex = db.Column(db.Enum('Male','Female','Unknown'), default='Unknown')
    weight = db.Column(db.String(50))
    photo_url = db.Column(db.String(255), nullable=True)

    activity_level = db.Column(db.Enum('Very calm','Moderately active','Very energetic'), default='Moderately active')
    animal_social_behavior = db.Column(db.Enum('Aggressive or territorial','Nervous or avoidant','Neutral','Friendly and playful'), default='Neutral')
    people_sociality = db.Column(db.Enum('Very shy','Selectively friendly','Friendly with most people','Extremely social'), default='Selectively friendly')
    independence_level = db.Column(db.Enum('Very dependent/clingy','Balanced','Very independent'), default='Balanced')
    adaptability = db.Column(db.Enum('Gets stressed easily','Needs time to adjust','Adapts quickly'), default='Needs time to adjust')
    affection_level = db.Column(db.Enum('Rarely affectionate','Occasionally affectionate','Very affectionate'), default='Occasionally affectionate')
    alone_behavior = db.Column(db.Enum('Gets anxious or destructive','Usually stays calm','Prefers being alone'), default='Usually stays calm')
    personality_type = db.Column(db.Enum('Calm and relaxed','Energetic and playful','Curious and adventurous','Protective and alert','Independent and reserved','Affectionate and clingy'), default='Calm and relaxed')
    trainability = db.Column(db.Enum('Difficult to train','Learns gradually','Learns quickly'), default='Learns gradually')
    companion_preference = db.Column(db.Enum('Probably not','Maybe','Most likely yes'), default='Maybe')

    # Big Five
    big_five_openness = db.Column(db.Integer, default=3)
    big_five_conscientiousness = db.Column(db.Integer, default=3)
    big_five_extraversion = db.Column(db.Integer, default=3)
    big_five_agreeableness = db.Column(db.Integer, default=3)
    big_five_neuroticism = db.Column(db.Integer, default=2)

    is_active = db.Column(db.Boolean, default=True, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=get_utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)

    def soft_delete(self):
        """Soft delete the pet record"""
        self.deleted_at = get_utc_now()
        self.is_active = False
        self.updated_at = get_utc_now()

    def update_from_dict(self, data):
        """Update pet record from dictionary with validation"""
        if 'name' in data and validate_pet_name(data['name']):
            self.name = data['name'].strip()
        
        if 'species' in data:
            self.species = str(escape(data['species'])).strip() if data['species'] else None
        
        if 'breed' in data:
            self.breed = str(escape(data['breed'])).strip() if data['breed'] else None
        
        if 'age' in data:
            self.age = str(escape(data['age'])).strip() if data['age'] else None
        
        if 'sex' in data:
            sex_options = ['Male', 'Female', 'Unknown']
            self.sex = validate_enum_field(data['sex'], sex_options, 'Unknown')
        
        if 'weight' in data:
            self.weight = str(escape(data['weight'])).strip() if data['weight'] else None
        
        # Behavior fields with validation
        if 'activity_level' in data:
            opts = ['Very calm', 'Moderately active', 'Very energetic']
            self.activity_level = validate_enum_field(data['activity_level'], opts, 'Moderately active')
        
        if 'animal_social_behavior' in data:
            opts = ['Aggressive or territorial', 'Nervous or avoidant', 'Neutral', 'Friendly and playful']
            self.animal_social_behavior = validate_enum_field(data['animal_social_behavior'], opts, 'Neutral')
        
        if 'people_sociality' in data:
            opts = ['Very shy', 'Selectively friendly', 'Friendly with most people', 'Extremely social']
            self.people_sociality = validate_enum_field(data['people_sociality'], opts, 'Selectively friendly')
        
        if 'independence_level' in data:
            opts = ['Very dependent/clingy', 'Balanced', 'Very independent']
            self.independence_level = validate_enum_field(data['independence_level'], opts, 'Balanced')
        
        if 'adaptability' in data:
            opts = ['Gets stressed easily', 'Needs time to adjust', 'Adapts quickly']
            self.adaptability = validate_enum_field(data['adaptability'], opts, 'Needs time to adjust')
        
        if 'affection_level' in data:
            opts = ['Rarely affectionate', 'Occasionally affectionate', 'Very affectionate']
            self.affection_level = validate_enum_field(data['affection_level'], opts, 'Occasionally affectionate')
        
        if 'alone_behavior' in data:
            opts = ['Gets anxious or destructive', 'Usually stays calm', 'Prefers being alone']
            self.alone_behavior = validate_enum_field(data['alone_behavior'], opts, 'Usually stays calm')
        
        if 'personality_type' in data:
            opts = ['Calm and relaxed', 'Energetic and playful', 'Curious and adventurous', 
                   'Protective and alert', 'Independent and reserved', 'Affectionate and clingy']
            self.personality_type = validate_enum_field(data['personality_type'], opts, 'Calm and relaxed')
        
        if 'trainability' in data:
            opts = ['Difficult to train', 'Learns gradually', 'Learns quickly']
            self.trainability = validate_enum_field(data['trainability'], opts, 'Learns gradually')
        
        if 'companion_preference' in data:
            opts = ['Probably not', 'Maybe', 'Most likely yes']
            self.companion_preference = validate_enum_field(data['companion_preference'], opts, 'Maybe')
        
        # Big Five personality (1-5 scale) with bounds checking
        if 'big_five_openness' in data:
            try:
                self.big_five_openness = max(1, min(5, int(data['big_five_openness'] or 3)))
            except (ValueError, TypeError):
                self.big_five_openness = 3
        
        if 'big_five_conscientiousness' in data:
            try:
                self.big_five_conscientiousness = max(1, min(5, int(data['big_five_conscientiousness'] or 3)))
            except (ValueError, TypeError):
                self.big_five_conscientiousness = 3
        
        if 'big_five_extraversion' in data:
            try:
                self.big_five_extraversion = max(1, min(5, int(data['big_five_extraversion'] or 3)))
            except (ValueError, TypeError):
                self.big_five_extraversion = 3
        
        if 'big_five_agreeableness' in data:
            try:
                self.big_five_agreeableness = max(1, min(5, int(data['big_five_agreeableness'] or 3)))
            except (ValueError, TypeError):
                self.big_five_agreeableness = 3
        
        if 'big_five_neuroticism' in data:
            try:
                self.big_five_neuroticism = max(1, min(5, int(data['big_five_neuroticism'] or 2)))
            except (ValueError, TypeError):
                self.big_five_neuroticism = 2
        
        self.updated_at = get_utc_now()

    @property
    def as_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name or '',
            'species': self.species or '',
            'breed': self.breed or '',
            'age': self.age or '',
            'sex': self.sex or '',
            'weight': self.weight or '',
            'photo_url': self.photo_url or '',
            'activity_level': self.activity_level or '',
            'animal_social_behavior': self.animal_social_behavior or '',
            'people_sociality': self.people_sociality or '',
            'independence_level': self.independence_level or '',
            'adaptability': self.adaptability or '',
            'affection_level': self.affection_level or '',
            'alone_behavior': self.alone_behavior or '',
            'personality_type': self.personality_type or '',
            'trainability': self.trainability or '',
            'companion_preference': self.companion_preference or '',
            'big_five_openness': self.big_five_openness or 3,
            'big_five_conscientiousness': self.big_five_conscientiousness or 3,
            'big_five_extraversion': self.big_five_extraversion or 3,
            'big_five_agreeableness': self.big_five_agreeableness or 3,
            'big_five_neuroticism': self.big_five_neuroticism or 2,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }
