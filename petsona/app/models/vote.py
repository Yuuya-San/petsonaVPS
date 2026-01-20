"""Vote model for tracking user votes on species and breeds"""
from datetime import datetime
from app.extensions import db


class Vote(db.Model):
    """Track which users have voted for which species and breeds"""
    __tablename__ = "votes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    species_id = db.Column(db.Integer, db.ForeignKey('species.id'), nullable=True, index=True)
    breed_id = db.Column(db.Integer, db.ForeignKey('breed.id'), nullable=True, index=True)
    
    # Ensure one vote per user per species and one vote per user per breed
    __table_args__ = (
        db.UniqueConstraint('user_id', 'species_id', name='unique_user_species_vote'),
        db.UniqueConstraint('user_id', 'breed_id', name='unique_user_breed_vote'),
    )
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('votes', cascade='all, delete-orphan', lazy='dynamic'))
    species = db.relationship('Species', backref=db.backref('votes', cascade='all, delete-orphan', lazy='dynamic'))
    breed = db.relationship('Breed', backref=db.backref('votes', cascade='all, delete-orphan', lazy='dynamic'))

    def __repr__(self):
        return f"<Vote user_id={self.user_id} species_id={self.species_id} breed_id={self.breed_id}>"
