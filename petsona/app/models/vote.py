"""Vote model for tracking user votes on species"""
from datetime import datetime
from app.extensions import db


class Vote(db.Model):
    """Track which users have voted for which species"""
    __tablename__ = "votes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    species_id = db.Column(db.Integer, db.ForeignKey('species.id'), nullable=False, index=True)
    
    # Ensure one vote per user per species
    __table_args__ = (db.UniqueConstraint('user_id', 'species_id', name='unique_user_species_vote'),)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('votes', cascade='all, delete-orphan', lazy='dynamic'))
    species = db.relationship('Species', backref=db.backref('votes', cascade='all, delete-orphan', lazy='dynamic'))

    def __repr__(self):
        return f"<Vote user_id={self.user_id} species_id={self.species_id}>"
