from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required
from app.extensions import db, csrf
from app.models import Species, Breed, Vote
import json

votes_bp = Blueprint('votes', __name__, url_prefix='/api/votes')


@csrf.exempt  # Exempt API endpoint from CSRF protection
@votes_bp.route('/heart/<int:species_id>', methods=['POST'])
@login_required
def toggle_heart_vote(species_id):
    """Toggle a heart vote for a species - persisted in database"""
    try:
        species = Species.query.get_or_404(species_id)
        
        # Check if user already voted for this species
        existing_vote = Vote.query.filter_by(
            user_id=current_user.id,
            species_id=species_id
        ).first()
        
        if existing_vote:
            # User already voted → remove vote (unvote)
            db.session.delete(existing_vote)
            species.decrement_heart_votes()
            voted = False
        else:
            # User hasn't voted → create vote
            new_vote = Vote(user_id=current_user.id, species_id=species_id)
            db.session.add(new_vote)
            species.increment_heart_votes()
            voted = True
        
        # Commit all database changes
        db.session.commit()
        
        # Broadcast vote update via Socket.IO to all connected clients
        from app.socket_events import broadcast_vote_update
        broadcast_vote_update(species_id, species.heart_vote_count)
        
        return jsonify({
            'success': True,
            'species_id': species_id,
            'voted': voted,
            'total_votes': species.heart_vote_count
        }), 200
    
    except Exception as e:
        print(f"Error in toggle_heart_vote: {str(e)}")  # Server-side logging
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@csrf.exempt  # Exempt API endpoint from CSRF protection
@votes_bp.route('/heart/<int:species_id>/count', methods=['GET'])
@login_required
def get_heart_count(species_id):
    """Get the heart vote count for a species and user's vote status"""
    try:
        species = Species.query.get_or_404(species_id)
        
        # Check if user has voted for this species
        user_vote = Vote.query.filter_by(
            user_id=current_user.id,
            species_id=species_id
        ).first()
        
        return jsonify({
            'success': True,
            'species_id': species_id,
            'total_votes': species.heart_vote_count,
            'user_voted': user_vote is not None
        }), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@csrf.exempt  # Exempt API endpoint from CSRF protection
@votes_bp.route('/heart/check-votes', methods=['POST'])
@login_required
def check_votes():
    """Check votes for multiple species - queries database for persistence"""
    try:
        data = request.get_json()
        species_ids = data.get('species_ids', [])
        
        # Get all votes for current user for these species
        user_votes = Vote.query.filter(
            Vote.user_id == current_user.id,
            Vote.species_id.in_(species_ids)
        ).all()
        
        # Create set of voted species for fast lookup
        voted_species_ids = {vote.species_id for vote in user_votes}
        
        votes_data = {}
        for species_id in species_ids:
            species = Species.query.get(species_id)
            if species:
                # Check if user has voted for this species
                user_voted = species_id in voted_species_ids
                votes_data[str(species_id)] = {
                    'total_votes': species.heart_vote_count or 0,
                    'user_voted': user_voted
                }
        
        return jsonify({
            'success': True,
            'votes': votes_data
        }), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== BREED VOTING ENDPOINTS ====================

@csrf.exempt
@votes_bp.route('/breed/<int:breed_id>', methods=['POST'])
@login_required
def toggle_breed_heart_vote(breed_id):
    """Toggle a heart vote for a breed"""
    try:
        breed = Breed.query.get_or_404(breed_id)
        
        # Check if user already voted for this breed
        existing_vote = Vote.query.filter_by(
            user_id=current_user.id,
            breed_id=breed_id
        ).first()
        
        if existing_vote:
            # User already voted → remove vote
            db.session.delete(existing_vote)
            breed.heart_vote_count = max(0, (breed.heart_vote_count or 0) - 1)
            voted = False
        else:
            # User hasn't voted → create vote
            new_vote = Vote(user_id=current_user.id, breed_id=breed_id)
            db.session.add(new_vote)
            breed.heart_vote_count = (breed.heart_vote_count or 0) + 1
            voted = True
        
        db.session.commit()
        
        # Broadcast breed vote update via Socket.IO to all connected clients
        from app.socket_events import broadcast_breed_vote_update
        broadcast_breed_vote_update(breed_id, breed.heart_vote_count, voted, current_user.id)
        
        return jsonify({
            'success': True,
            'breed_id': breed_id,
            'voted': voted,
            'total_votes': breed.heart_vote_count
        }), 200
    
    except Exception as e:
        print(f"Error in toggle_breed_heart_vote: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@csrf.exempt
@votes_bp.route('/breed/check-votes', methods=['POST'])
@login_required
def check_breed_votes():
    """Check votes for multiple breeds"""
    try:
        data = request.get_json()
        breed_ids = data.get('breed_ids', [])
        
        # Get all votes for current user for these breeds
        user_votes = Vote.query.filter(
            Vote.user_id == current_user.id,
            Vote.breed_id.in_(breed_ids)
        ).all()
        
        # Create set of voted breeds for fast lookup
        voted_breed_ids = {vote.breed_id for vote in user_votes}
        
        votes_data = {}
        for breed_id in breed_ids:
            breed = Breed.query.get(breed_id)
            if breed:
                user_voted = breed_id in voted_breed_ids
                votes_data[str(breed_id)] = {
                    'total_votes': breed.heart_vote_count or 0,
                    'user_voted': user_voted
                }
        
        return jsonify({
            'success': True,
            'votes': votes_data
        }), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
