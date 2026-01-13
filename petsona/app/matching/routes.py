from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from flask_login import current_user, login_required
from datetime import datetime
import uuid
from app.extensions import db
from app.models.breed import Breed
from app.models.match_history import MatchHistory
from app.utils.compatibility_engine import CompatibilityEngine
from app.utils.audit import log_event
from . import bp


# --------------------------
# GLOBAL QUIZ PAGE (NEW)
# --------------------------
@bp.route("/", methods=["GET"])
def quiz():
    """Display global quiz page accessible to all users"""
    return render_template("matching/quiz.html")


# --------------------------
# BREED-SPECIFIC QUIZ PAGE (NEW)
# --------------------------
@bp.route("/quiz/specific/<int:breed_id>", methods=["GET"])
def quiz_specific(breed_id):
    """Display breed-specific quiz for compatibility assessment"""
    breed = Breed.query.get_or_404(breed_id)
    return render_template("matching/quiz_specific.html", breed=breed)


# --------------------------
# GENERAL RESULTS PAGE (NEW)
# --------------------------
@bp.route("/results/general", methods=["GET"])
def general_results():
    """Display top 5 breed matches from previous quiz submission"""
    # Get last stored matches (from session or session_id param)
    session_id = request.args.get('session_id')
    
    # Check if we have match results in session
    if not session.get('last_matches'):
        return redirect(url_for('matching.quiz'))
    
    matches = session.get('last_matches', [])
    return render_template("matching/general_results.html", matches=matches)


# --------------------------
# API: GET RESULTS (NEW)
# --------------------------
@bp.route("/api/results/general", methods=["GET"])
def api_get_results():
    """Fetch results from session as JSON (for dashboard integration)"""
    matches = session.get('last_matches', [])
    
    if not matches:
        return jsonify({'error': 'No quiz results found', 'success': False}), 404
    
    return jsonify({
        'success': True,
        'matches': matches,
        'message': f'Found {len(matches)} great matches for you!'
    }), 200


# --------------------------
# BREED-SPECIFIC RESULTS PAGE (NEW)
# --------------------------
@bp.route("/results/breed/<int:breed_id>", methods=["GET"])
def breed_match(breed_id):
    """Display compatibility assessment for specific breed"""
    breed = Breed.query.get_or_404(breed_id)
    
    # Get quiz answers from session or request
    answers = session.get('last_answers')
    if not answers:
        return redirect(url_for('matching.quiz'))
    
    # Calculate compatibility
    match_data = CompatibilityEngine.calculate_match_score(answers, breed)
    
    return render_template(
        "matching/breed_results.html",
        breed=breed,
        score=match_data.get('score', 0),
        compatibility_level=match_data.get('compatibility_level', 'Unknown'),
        category_scores=match_data.get('category_scores', {}),
        strength_areas=match_data.get('strength_areas', []),
        mismatch_areas=match_data.get('mismatch_areas', []),
        suggestions=match_data.get('suggestions', []),
        improvements=match_data.get('improvement_suggestions', [])
    )


# --------------------------
# MATCH HISTORY PAGE (NEW)
# --------------------------
@bp.route("/history", methods=["GET"])
def history():
    """Display all match history for current user"""
    if not current_user.is_authenticated:
        # Show anonymous user results
        return redirect(url_for('matching.quiz'))
    
    matches = MatchHistory.query.filter_by(user_id=current_user.id).order_by(MatchHistory.created_at.desc()).all()
    return render_template("matching/history.html", matches=matches)


# --------------------------
# VIEW SPECIFIC RESULT (NEW)
# --------------------------
@bp.route("/results/<int:result_id>", methods=["GET"])
def view_result(result_id):
    """View a specific past match result"""
    match = MatchHistory.query.get_or_404(result_id)
    
    # Check authorization
    if match.user_id and match.user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for('matching.history'))
    
    return render_template("matching/result_detail.html", result=match)


# --------------------------
# DELETE HISTORY RECORD (NEW)
# --------------------------
@bp.route("/history/delete", methods=["DELETE"])
def delete_history():
    """Delete a match history record"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    match_id = request.args.get('match_id', type=int)
    match = MatchHistory.query.get_or_404(match_id)
    
    if match.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(match)
    db.session.commit()
    
    return jsonify({'success': True}), 200


# ---------------------------
# API: QUIZ SUBMISSION (UPDATED)
# ---------------------------
@bp.route("/api/quiz-submit", methods=["POST"])
def api_quiz_submit():
    """
    Submit quiz answers and get top 5 matches.
    Saves match history if user is authenticated.
    """
    try:
        data = request.get_json(silent=True) or {}

        if not isinstance(data, dict) or not data:
            return jsonify({'error': 'No quiz data provided'}), 400

        # Find top 5 matches
        matches = CompatibilityEngine.find_top_matches(data, limit=5) or []

        # Enhance matches with detailed information
        enhanced_matches = []
        for match in matches:
            breed = match['breed']
            match_data = match.get('details', {})
            
            enhanced_match = {
                'breed': {
                    'id': breed.id,
                    'name': breed.name,
                    'image_url': breed.image_url,
                    'summary': breed.summary,
                    'species_id': breed.species_id,
                    'species': {
                        'id': breed.species.id,
                        'name': breed.species.name,
                    }
                },
                'score': match.get('score', 0),
                'level': match.get('level', 'Unknown'),
                'mismatches': match.get('mismatches', []),
                'suggestions': match.get('suggestions', []),
                'details': match_data
            }
            enhanced_matches.append(enhanced_match)

        # Store answers and matches in session for result page
        session['last_answers'] = data
        session['last_matches'] = enhanced_matches
        session.modified = True

        # Save to database if authenticated
        if current_user.is_authenticated and enhanced_matches:
            try:
                match_record = MatchHistory(
                    user_id=current_user.id,
                    match_type='general',
                    quiz_answers=data,
                    compatibility_score=enhanced_matches[0]['score'],
                    compatibility_level=enhanced_matches[0]['level'],
                    top_matches=[{
                        'breed_id': m['breed']['id'],
                        'breed_name': m['breed']['name'],
                        'score': m['score'],
                        'level': m['level']
                    } for m in enhanced_matches],
                    category_scores=enhanced_matches[0]['details'].get('category_scores', {}),
                    mismatches=enhanced_matches[0]['details'].get('mismatches', []),
                    improvement_suggestions=enhanced_matches[0].get('suggestions', []),
                    device_type=request.user_agent.platform if request.user_agent else None,
                    source='quiz_page'
                )
                db.session.add(match_record)
                db.session.commit()
            except Exception as e:
                print(f"Error saving match history: {e}")

        log_event(
            "pet_compatibility_quiz_completed",
            {
                "answers_count": len(data),
                "top_match_breed_id": enhanced_matches[0]["breed"]["id"] if enhanced_matches else None,
                "top_match_score": enhanced_matches[0]["score"] if enhanced_matches else None,
                "total_matches_generated": len(enhanced_matches),
                "user_id": current_user.id if current_user.is_authenticated else None,
            }
        )

        return jsonify({
            "success": True,
            "matches": enhanced_matches,
            "message": f"Found {len(enhanced_matches)} great matches for you!",
            "timestamp": datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


# ---------------------------
# API: BREED-SPECIFIC MATCH (UPDATED)
# ---------------------------
@bp.route("/api/breed-match", methods=["POST"])
def api_breed_match():
    """
    Calculate compatibility for a specific breed.
    Expects breed_id and quiz answers in request body.
    """
    try:
        data = request.get_json(silent=True) or {}

        breed_id = data.get("breed_id")
        answers = data.get("answers")

        if not breed_id or not answers:
            return jsonify({'error': 'Missing breed_id or answers'}), 400

        breed = Breed.query.get_or_404(breed_id)

        # Calculate match score
        match_data = CompatibilityEngine.calculate_match_score(answers, breed)
        
        # Store answers in session for breed_match route
        session['last_answers'] = answers
        session.modified = True
        
        # Save to history if authenticated
        if current_user.is_authenticated:
            try:
                match_record = MatchHistory(
                    user_id=current_user.id,
                    match_type='breed',
                    breed_id=breed_id,
                    quiz_answers=answers,
                    compatibility_score=match_data.get('score', 0),
                    compatibility_level=match_data.get('compatibility_level', 'Unknown'),
                    category_scores=match_data.get('category_scores', {}),
                    mismatches=match_data.get('mismatches', []),
                    device_type=request.user_agent.platform if request.user_agent else None,
                    source='breed_page'
                )
                db.session.add(match_record)
                db.session.commit()
            except Exception as e:
                print(f"Error saving match history: {e}")

        return jsonify({
            'success': True,
            'breed_id': breed.id,
            'breed_name': breed.name,
            'score': match_data.get('score', 0),
            'level': match_data.get('compatibility_level', 'Unknown'),
            'strength_areas': match_data.get('strength_areas', []),
            'mismatch_areas': match_data.get('mismatch_areas', []),
            'category_scores': match_data.get('category_scores', {}),
            'suggestions': match_data.get('suggestions', [])
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


# --------------------------
# API: Match Score
# --------------------------
@bp.route("/api/match-score/<int:breed_id>", methods=["POST"])
def api_match_score(breed_id):
    """Get match score for a specific breed based on session answers"""
    answers = session.get("last_answers")

    if not isinstance(answers, dict) or not answers:
        return jsonify({'error': 'No quiz answers in session'}), 400

    breed = Breed.query.get_or_404(breed_id)
    match_data = CompatibilityEngine.calculate_match_score(answers, breed) or {}

    return jsonify({
        'breed_id': breed.id,
        'breed_name': breed.name,
        'score': match_data.get('score', 0),
        'level': match_data.get('compatibility_level', "Unknown"),
        'mismatches': match_data.get('mismatches', []),
        'category_scores': match_data.get('category_scores', {}),
    })


# ---------------------------
# API: Analytics
# ---------------------------
@bp.route("/api/analytics/stats")
def api_analytics_stats():
    """Get matching system statistics."""
    try:
        # Get basic stats
        total_matches = MatchHistory.query.count()
        general_matches = MatchHistory.query.filter_by(match_type='general').count()
        breed_matches = MatchHistory.query.filter_by(match_type='breed').count()
        
        # Get top breeds
        from sqlalchemy import func
        top_breeds = db.session.query(
            MatchHistory.breed_id,
            func.count(MatchHistory.id).label('match_count')
        ).filter(MatchHistory.breed_id.isnot(None)).group_by(
            MatchHistory.breed_id
        ).order_by(func.count(MatchHistory.id).desc()).limit(10).all()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_matches': total_matches,
                'general_matches': general_matches,
                'breed_matches': breed_matches,
            },
            'top_breeds': [
                {
                    'breed_id': b[0],
                    'matches': b[1],
                }
                for b in top_breeds
            ]
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

