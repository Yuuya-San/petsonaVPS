from datetime import datetime
from app.extensions import db
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_now():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


class BackupCode(db.Model):
    __tablename__ = "backup_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)  # XXXX-XXXX-XXXX format (14 chars) + buffer
    is_used = db.Column(db.Boolean, default=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=get_ph_now)

    # Relationship
    user = db.relationship('User', backref=db.backref('backup_codes', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<BackupCode {self.id} for user {self.user_id}>'

    @staticmethod
    def generate_codes(count=10):
        """Generate backup codes in format XXXX-XXXX-XXXX"""
        import secrets
        codes = []
        for _ in range(count):
            # Generate 12 random bytes and convert to hex, then format
            code = secrets.token_hex(6).upper()
            # Format as XXXX-XXXX-XXXX
            formatted_code = f"{code[:4]}-{code[4:8]}-{code[8:12]}"
            codes.append(formatted_code)
        return codes

    @staticmethod
    def create_for_user(user_id, count=10):
        """Create backup codes for a user"""
        try:
            # Delete existing unused codes
            BackupCode.query.filter_by(user_id=user_id, is_used=False).delete()
            
            codes = BackupCode.generate_codes(count)
            for code in codes:
                backup_code = BackupCode(user_id=user_id, code=code)
                db.session.add(backup_code)
            
            db.session.commit()
            return codes
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def verify_code(user_id, code):
        """Verify and mark a backup code as used"""
        try:
            # Normalize the code (remove dashes, uppercase)
            normalized_input = code.replace('-', '').replace(' ', '').upper()
            
            # Get all unused backup codes for this user
            backup_codes = BackupCode.query.filter_by(
                user_id=user_id,
                is_used=False
            ).all()
            
            # Find matching code (comparing without dashes)
            matching_code = None
            for bc in backup_codes:
                stored_normalized = bc.code.replace('-', '').replace(' ', '').upper()
                if stored_normalized == normalized_input:
                    matching_code = bc
                    break
            
            if not matching_code:
                return False
            
            # Mark as used
            matching_code.is_used = True
            matching_code.used_at = get_ph_now()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

    @staticmethod
    def get_unused_count(user_id):
        """Get count of unused backup codes"""
        return BackupCode.query.filter_by(user_id=user_id, is_used=False).count()
