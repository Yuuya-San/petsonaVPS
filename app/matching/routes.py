from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from flask_login import current_user, login_required # pyright: ignore[reportMissingImports]
from datetime import datetime
import uuid
from app.extensions import db, csrf
from app.models.breed import Breed
from app.models.match_history import MatchHistory
from app.utils.compatibility_engine import (
    CompatibilityEngine,
    generate_suggestions,
    generate_match_reasons
)
from app.utils.audit import log_event
from . import bp
import pytz
from app.extensions import limiter

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


def normalize_quiz_answers(answers: dict) -> dict:
    """
    Normalize quiz answers for compatibility engine processing.
    
    Handles:
    - pet_preference vs pet_preffered naming mismatch
    - Multi-select answers (comma-separated strings)
    - other_pets_friendly multi-select (keep as comma-separated or single value)
    
    Args:
        answers: Raw quiz answers dict from frontend
    
    Returns:
        Normalized answers dict ready for CompatibilityEngine
    """
    if not answers or not isinstance(answers, dict):
        return {}
    
    normalized = {}
    
    for key, value in answers.items():
        if key == 'pet_preference':
            # Handle multi-select pet preferences
            if isinstance(value, str) and value:
                # If comma-separated, take just the first preference for filtering
                if ',' in value:
                    # Store the first preference for filtering
                    normalized[key] = value.split(',')[0].strip()
                else:
                    normalized[key] = value.strip()
            else:
                normalized[key] = value
        
        elif key == 'other_pets_friendly':
            # Handle other_pets_friendly - can be single or multi-select
            if isinstance(value, str) and value:
                # Keep as-is (can be comma-separated or single value)
                normalized[key] = value.strip()
            else:
                normalized[key] = value
        
        else:
            # All other answers pass through as-is
            normalized[key] = value
    
    return normalized


# --------------------------
# GLOBAL QUIZ PAGE (NEW)
# --------------------------
@bp.route("/", methods=["GET"])
@login_required
def quiz():
    """Display global quiz page accessible to all users"""
    # Clear any previous quiz data to ensure fresh session
    session.pop('last_answers', None)
    session.pop('last_matches', None)
    session.pop('quiz_session_id', None)
    session.pop('quiz_submission_timestamp', None)
    session.modified = True
    
    return render_template("matching/quiz.html")


# --------------------------
# BREED-SPECIFIC QUIZ PAGE (NEW)
# --------------------------
@bp.route("/quiz/specific/<int:breed_id>", methods=["GET"])
@login_required
def quiz_specific(breed_id):
    """Display breed-specific quiz for compatibility assessment"""
    breed = Breed.query.get_or_404(breed_id)
    
    # Clear any previous quiz data to ensure fresh session for this specific breed quiz
    session.pop('last_answers', None)
    session.pop('last_matches', None)
    session.pop('quiz_session_id', None)
    session.pop('quiz_submission_timestamp', None)
    session.modified = True
    
    return render_template("matching/quiz_specific.html", breed=breed)


# --------------------------
# GENERAL RESULTS PAGE (NEW)
# --------------------------
@bp.route("/results/general", methods=["GET"])
@login_required
def general_results():
    """Display top 5 breed matches from previous quiz submission"""
    # Get last stored matches from session
    matches = session.get('last_matches', [])
    answers = session.get('last_answers', {})
    
    # If no matches in session, check if user is authenticated and has history
    if not matches and current_user.is_authenticated:
        # Try to get the most recent match from history
        last_match = MatchHistory.query.filter_by(
            user_id=current_user.id,
            match_type='general'
        ).order_by(MatchHistory.created_at.desc()).first()
        
        if last_match and last_match.top_matches:
            # Reconstruct matches from history
            try:
                matches = []
                for match_data in last_match.top_matches:
                    breed = Breed.query.get(match_data.get('breed_id'))
                    if breed:
                        matches.append({
                            'breed': {
                                'id': breed.id,
                                'name': breed.name,
                                'image_url': breed.image_url,
                                'summary': breed.summary,
                                'species_id': breed.species_id,
                                'species': {'id': breed.species.id, 'name': breed.species.name}
                            },
                            'score': match_data.get('score', 0),
                            'level': match_data.get('level', 'Unknown'),
                            'strengths': [f"Matches your {breed.name} preferences"],
                            'mismatches': [],
                            'suggestions': []
                        })
                if matches:
                    session['last_matches'] = matches
                    session.modified = True
            except Exception as e:
                print(f"Error loading matches from history: {e}")
    
    # If still no matches, redirect back to quiz
    if not matches:
        return redirect(url_for('matching.quiz'))
    
    return render_template("matching/general_results.html", matches=matches)


# --------------------------
# API: GET RESULTS (NEW)
# --------------------------
@bp.route("/api/results/general", methods=["GET"])
@login_required
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
@login_required
def breed_match(breed_id):
    """Display compatibility assessment for specific breed"""
    breed = Breed.query.get_or_404(breed_id)
    
    # Get quiz answers from session
    answers = session.get('last_answers')
    
    # If no answers in session, try to get from authenticated user's history
    if not answers and current_user.is_authenticated:
        last_match = MatchHistory.query.filter_by(
            user_id=current_user.id
        ).order_by(MatchHistory.created_at.desc()).first()
        
        if last_match and last_match.quiz_answers:
            answers = last_match.quiz_answers
            session['last_answers'] = answers
            session.modified = True
    
    # If still no answers, redirect back to quiz
    if not answers or not isinstance(answers, dict):
        return redirect(url_for('matching.quiz'))
    
    # Calculate compatibility using exact same answers
    match_data = CompatibilityEngine.calculate_match_score(answers, breed)
    
    # Generate suggestions and reasons
    suggestions = generate_suggestions(answers, breed)
    reasons = generate_match_reasons(answers, breed)
    
    # Save to history if authenticated AND this is a breed-specific quiz (from breed page, not general quiz)
    # Only save if the route source is breed_page, not from general quiz redirects
    if current_user.is_authenticated and request.referrer and '/specific/' in request.referrer:
        try:
            match_record = MatchHistory(
                user_id=current_user.id,
                match_type='breed',
                breed_id=breed_id,
                quiz_answers=answers,
                compatibility_score=match_data.get('overall_score', 0),
                compatibility_level=match_data.get('compatibility_level', 'Unknown'),
                category_scores=match_data.get('category_scores', {}),
                mismatches=match_data.get('mismatches', []),
                strength_areas=match_data.get('strengths', []),
                improvement_suggestions=suggestions,
                device_type=request.user_agent.platform if request.user_agent else None,
                source='breed_page'
            )
            db.session.add(match_record)
            db.session.commit()
        except Exception as e:
            pass
    
    # Prepare category scores for display (calculate percentages if needed)
    category_display = {}
    for category, data in match_data.get('category_scores', {}).items():
        if isinstance(data, dict):
            category_display[category] = {
                'score': data.get('score', 0),
                'percentage': data.get('percentage', 0)
            }
    
    return render_template(
        "matching/breed_results.html",
        breed=breed,
        score=match_data.get('overall_score', 0),
        compatibility_level=match_data.get('compatibility_level', 'Unknown'),
        category_scores=category_display,
        strength_areas=match_data.get('strengths', []),
        question_scores=match_data.get('question_scores', []),
        matched_reasons=reasons.get('matched_reasons', []),
        mismatch_reasons=reasons.get('mismatch_reasons', []),
        suggestions=suggestions,
        total_questions=match_data.get('total_questions_answered', 0)
    )


# --------------------------
# MATCH HISTORY PAGE (NEW)
# --------------------------
@bp.route("/history", methods=["GET"])
@limiter.exempt
@login_required
def history():
    """Display all match history for current user"""
    if not current_user.is_authenticated:
        # Show anonymous user results
        return redirect(url_for('matching.quiz'))
    
    try:
        matches = MatchHistory.query.filter_by(user_id=current_user.id).order_by(MatchHistory.created_at.desc()).all()
        print(f"[HISTORY] Found {len(matches)} matches for user {current_user.id}")
        
        matches_data = []
        for match in matches:
            try:
                match_dict = match.as_dict
                matches_data.append(match_dict)
            except Exception as e:
                print(f"[HISTORY ERROR] Failed to convert match {match.id}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"[HISTORY] Returning {len(matches_data)} matches to template")
        return render_template("matching/history.html", matches=matches_data)
    except Exception as e:
        print(f"[HISTORY ERROR] Exception in history route: {e}")
        import traceback
        traceback.print_exc()
        return render_template("matching/history.html", matches=[])


# --------------------------
# VIEW SPECIFIC RESULT (NEW)
# --------------------------
@bp.route("/results/<int:result_id>", methods=["GET"])
@login_required
def view_result(result_id):
    """View a specific past match result from history"""
    match = MatchHistory.query.get_or_404(result_id)

    # Check authorization
    if match.user_id and match.user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for('matching.history'))

    # Handle based on match type
    if match.match_type == 'general' and match.top_matches:
        # For general matches, reconstruct matches array from top_matches
        try:
            matches = []
            for match_data in match.top_matches:
                # If match_data has breed_id, fetch breed from database
                if isinstance(match_data, dict) and 'breed_id' in match_data:
                    breed = Breed.query.get(match_data.get('breed_id'))
                    if breed:
                        matches.append({
                            'breed': {
                                'id': breed.id,
                                'name': breed.name,
                                'image_url': breed.image_url,
                                'summary': breed.summary,
                                'species_id': breed.species_id,
                                'species': {'id': breed.species.id, 'name': breed.species.name}
                            },
                            'score': match_data.get('score', 0),
                            'level': match_data.get('level', 'Unknown'),
                            'strengths': [f"Matches your preferences"],
                            'mismatches': [],
                            'suggestions': []
                        })
            
            if matches:
                # Store in session for general_results template
                session['last_matches'] = matches
                session['last_answers'] = match.quiz_answers
                session.modified = True
                return redirect(url_for('matching.general_results'))
        except Exception as e:
            print(f"Error reconstructing general matches: {e}")
            pass
        
        # Fallback if reconstruction fails
        return redirect(url_for('matching.history'))
    
    elif match.match_type == 'breed' and match.breed:
        # For breed matches, reconstruct data and render directly
        try:
            # Calculate compatibility using stored answers
            answers = match.quiz_answers if match.quiz_answers else {}
            match_data = CompatibilityEngine.calculate_match_score(answers, match.breed)
            
            # Use stored data if calculation fails
            if not match_data.get('overall_score'):
                match_data = {
                    'overall_score': match.compatibility_score,
                    'compatibility_level': match.compatibility_level,
                    'category_scores': match.category_scores or {},
                    'strengths': match.strength_areas or [],
                    'mismatches': match.mismatches or []
                }
            
            # Generate suggestions and reasons
            suggestions = generate_suggestions(answers, match.breed) if answers else (match.improvement_suggestions or [])
            reasons = generate_match_reasons(answers, match.breed) if answers else {
                'matched_reasons': [],
                'mismatch_reasons': []
            }
            
            # Prepare category scores for display
            category_display = {}
            for category, data in match_data.get('category_scores', {}).items():
                if isinstance(data, dict):
                    category_display[category] = {
                        'score': data.get('score', 0),
                        'percentage': data.get('percentage', 0)
                    }
            
            return render_template(
                "matching/breed_results.html",
                breed=match.breed,
                score=match_data.get('overall_score', 0),
                compatibility_level=match_data.get('compatibility_level', 'Unknown'),
                category_scores=category_display,
                strength_areas=match_data.get('strengths', []),
                question_scores=match_data.get('question_scores', []),
                matched_reasons=reasons.get('matched_reasons', []),
                mismatch_reasons=reasons.get('mismatch_reasons', []),
                suggestions=suggestions,
                total_questions=1,
                from_history=True
            )
        except Exception as e:
            print(f"Error rendering breed results: {e}")
            return redirect(url_for('matching.history'))
    
    else:
        # No valid match data, redirect to history
        return redirect(url_for('matching.history'))


# --------------------------
# DELETE HISTORY RECORD (NEW)
# --------------------------
@bp.route("/history/delete", methods=["DELETE"])
@csrf.exempt
@login_required
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
@csrf.exempt
@login_required
def api_quiz_submit():
    """
    Submit quiz answers and get top 5 matches.
    Accessible to all users (authenticated and unauthenticated).
    Saves match history if user is authenticated.
    """
    try:
        data = request.get_json(silent=True) or {}

        if not isinstance(data, dict) or not data:
            return jsonify({'error': 'No quiz data provided', 'success': False}), 400

        # Normalize quiz answers for compatibility engine
        normalized_data = normalize_quiz_answers(data)

        # Find top 5 matches
        matches = CompatibilityEngine.find_top_matches(normalized_data, limit=5) or []

        # Enhance matches with detailed information (store all details for each top match)
        enhanced_matches = []
        for match in matches:
            breed = match['breed']
            enhanced_match = {
                'breed': {
                    'id': breed['id'],
                    'name': breed['name'],
                    'image_url': breed.get('image_url', ''),
                    'summary': breed.get('summary', ''),
                    'species_id': breed.get('species_id', ''),
                    'species': breed.get('species', {})
                },
                'score': match.get('score', 0),
                'level': match.get('level', 'Unknown'),
                'strengths': match.get('strengths', []),
                'mismatches': match.get('mismatches', []),
                'suggestions': match.get('suggestions', []),
                'category_scores': match.get('category_scores', {}),
            }
            enhanced_matches.append(enhanced_match)

        # Store EXACT normalized answers and matches in session for result page
        session['last_answers'] = normalized_data
        session['last_matches'] = enhanced_matches
        session.modified = True
        
        # For unauthenticated users, also store a unique session ID
        if not current_user.is_authenticated:
            session['quiz_session_id'] = str(uuid.uuid4())
            session.modified = True

        # Save to database if authenticated (only as general, never as breed for top 5)
        if current_user.is_authenticated and enhanced_matches:
            try:
                match_record = MatchHistory(
                    user_id=current_user.id,
                    match_type='general',
                    quiz_answers=normalized_data,
                    compatibility_score=enhanced_matches[0]['score'],
                    compatibility_level=enhanced_matches[0]['level'],
                    top_matches=[{
                        'breed_id': m['breed']['id'],
                        'breed_name': m['breed']['name'],
                        'score': m['score'],
                        'level': m['level'],
                        'strengths': m.get('strengths', []),
                        'mismatches': m.get('mismatches', []),
                        'image_url': m['breed'].get('image_url', ''),
                        'category_scores': m.get('category_scores', {}),
                    } for m in enhanced_matches],
                    category_scores=enhanced_matches[0].get('category_scores', {}),
                    mismatches=enhanced_matches[0].get('mismatches', []),
                    strength_areas=enhanced_matches[0].get('strengths', []),
                    improvement_suggestions=[],
                    device_type=request.user_agent.platform if request.user_agent else None,
                    source='quiz_page'
                )
                db.session.add(match_record)
                db.session.commit()
            except Exception as e:
                pass

        log_event(
            "pet_compatibility_quiz_completed",
            {
                "answers_count": len(data),
                "top_match_breed_id": enhanced_matches[0]["breed"]["id"] if enhanced_matches else None,
                "top_match_score": enhanced_matches[0]["score"] if enhanced_matches else None,
                "total_matches_generated": len(enhanced_matches),
                "user_id": current_user.id if current_user.is_authenticated else None,
                "is_authenticated": current_user.is_authenticated
            }
        )

        return jsonify({
            "success": True,
            "matches": enhanced_matches,
            "message": f"Found {len(enhanced_matches)} great matches for you!",
            "timestamp": get_ph_datetime().isoformat()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


# ---------------------------
# API: BREED-SPECIFIC MATCH (UPDATED)
# ---------------------------
@bp.route("/api/breed-match", methods=["POST"])
@csrf.exempt
@login_required
def api_breed_match():
    """
    Calculate compatibility for a specific breed.
    Expects breed_id and quiz answers in request body.
    """
    try:
        data = request.get_json(silent=True) or {}

        breed_id = data.get("breed_id")
        answers = data.get("answers")

        if not breed_id:
            return jsonify({'error': 'Missing breed_id', 'success': False}), 400
        
        if not answers or len(answers) == 0:
            return jsonify({'error': 'No quiz answers provided', 'success': False}), 400

        breed = Breed.query.get_or_404(breed_id)

        # Normalize quiz answers for compatibility engine
        normalized_answers = normalize_quiz_answers(answers)

        # Calculate match score
        try:
            match_data = CompatibilityEngine.calculate_match_score(normalized_answers, breed)
        except Exception as calc_error:
            return jsonify({'error': f'Calculation error: {str(calc_error)}', 'success': False}), 500
        
        # Store normalized answers in session for breed_match route
        session['last_answers'] = normalized_answers
        session.modified = True
        
        # Only save to history if this is a breed-specific quiz (from /quiz/specific/ route)
        # Do NOT save if this is just a user clicking on a breed from the general results page
        # Check if the API call came from a breed-specific quiz (indicated by API source param)
        save_as_breed = request.args.get('from_breed_quiz', 'false').lower() == 'true'
        
        if current_user.is_authenticated and save_as_breed:
            try:
                match_record = MatchHistory(
                    user_id=current_user.id,
                    match_type='breed',
                    breed_id=breed_id,
                    quiz_answers=normalized_answers,
                    compatibility_score=match_data.get('overall_score', 0),
                    compatibility_level=match_data.get('compatibility_level', 'Unknown'),
                    category_scores=match_data.get('category_scores', {}),
                    mismatches=match_data.get('mismatches', []),
                    strength_areas=match_data.get('strengths', []),
                    improvement_suggestions=[],
                    device_type=request.user_agent.platform if request.user_agent else None,
                    source='breed_page'
                )
                db.session.add(match_record)
                db.session.commit()
            except Exception as e:
                print(f"Error saving match history: {str(e)}")
                pass

        return jsonify({
            'success': True,
            'breed_id': breed.id,
            'breed_name': breed.name,
            'score': match_data.get('overall_score', 0),
            'level': match_data.get('compatibility_level', 'Unknown'),
            'strength_areas': match_data.get('strengths', []),
            'mismatch_areas': match_data.get('mismatches', []),
            'category_scores': match_data.get('category_scores', {}),
            'suggestions': match_data.get('mismatches', [])
        }), 200

    except Exception as e:
        print(f"Breed match error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'success': False}), 500


# --------------------------
# API: Match Score
# --------------------------
@bp.route("/api/match-score/<int:breed_id>", methods=["POST"])
@login_required
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


# --------------------------
# API: Question Scores (NEW)
# --------------------------
@bp.route("/api/question-scores/<int:breed_id>", methods=["POST"])
@csrf.exempt
@login_required
def api_question_scores(breed_id):
    """
    Get detailed per-question scores for a specific breed.
    Can use session answers or provided answers in request body.
    
    Returns:
        - question_scores: List of dicts with score for each question
        - breed_name: Name of breed being evaluated
        - overall_score: Overall compatibility score
    """
    try:
        breed = Breed.query.get_or_404(breed_id)
        
        # Try to get answers from request body first, then from session
        data = request.get_json(silent=True) or {}
        answers = data.get('answers') or session.get('last_answers')
        
        if not isinstance(answers, dict) or not answers:
            return jsonify({'error': 'No quiz answers provided', 'success': False}), 400
        
        # Normalize answers before processing
        normalized_answers = normalize_quiz_answers(answers)
        
        # Get per-question scores
        question_scores = CompatibilityEngine.get_question_scores(normalized_answers, breed)
        
        # Get overall score
        overall_result = CompatibilityEngine.calculate_match_score(normalized_answers, breed)
        
        return jsonify({
            'success': True,
            'breed_id': breed.id,
            'breed_name': breed.name,
            'overall_score': overall_result.get('overall_score', 0),
            'compatibility_level': overall_result.get('compatibility_level', 'Unknown'),
            'question_scores': question_scores,
            'total_questions': len(question_scores),
        }), 200
    
    except Exception as e:
        print(f"Question scores error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'success': False}), 500


# --------------------------
# API: Analytics
# ---------------------------
@bp.route("/api/analytics/stats")
@login_required
def api_analytics_stats():
    """Get matching system statistics."""
    try:
        # Get basic stats
        total_matches = MatchHistory.query.count()
        general_matches = MatchHistory.query.filter_by(match_type='general').count()
        breed_matches = MatchHistory.query.filter_by(match_type='breed').count()
        
        # Get top breeds
        from sqlalchemy import func # pyright: ignore[reportMissingImports]
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

