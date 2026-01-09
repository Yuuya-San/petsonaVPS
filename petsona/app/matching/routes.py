from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from app.models.breed import Breed
from app.utils.compatibility_engine import CompatibilityEngine
from . import bp

# ---------------------------
# Quiz Page
# ---------------------------
@bp.route("/", methods=["GET", "POST"])
def quiz():
    """Display pet compatibility quiz"""
    if request.method == "POST":
        # Collect quiz answers
        answers = {k: request.form.get(k) for k in request.form}
        # Convert Yes/No to boolean for household compatibility questions
        for key in ["child_friendly", "dog_friendly", "cat_friendly", "small_pet_friendly",
                    "okay_fragile", "okay_permit", "okay_special_vet"]:
            if key in answers:
                answers[key] = answers[key] == "Yes"
        
        session["quiz_answers"] = answers
        return redirect(url_for("matching.results"))
    
    return render_template("matching/quiz.html")


# ---------------------------
# Results Page - Top 5 Matches
# ---------------------------
@bp.route("/results")
def results():
    """Display top 5 compatible pet matches"""
    answers = session.get("quiz_answers", {})
    
    if not answers:
        return redirect(url_for("matching.quiz"))
    
    # Get top 5 matches
    top_matches = CompatibilityEngine.find_top_matches(answers, limit=5)
    
    return render_template(
        "matching/results.html",
        matches=top_matches,
        user_answers=answers
    )


# ---------------------------
# Top Match Page (Random - Best Overall Match)
# ---------------------------
@bp.route("/match/top")
def match_top():
    """Show the single best compatible breed"""
    answers = session.get("quiz_answers", {})
    
    if not answers:
        return redirect(url_for("matching.quiz"))
    
    # Get top 1 match
    top_matches = CompatibilityEngine.find_top_matches(answers, limit=1)
    
    if not top_matches:
        return render_template("matching/no_match.html")
    
    match = top_matches[0]
    
    return render_template(
        "matching/specific_match.html",
        breed=match['breed'],
        score=match['score'],
        compatibility_level=match['level'],
        mismatches=match['mismatches'],
        details=match['details']
    )


# ---------------------------
# Specific Breed Match Analysis
# ---------------------------
@bp.route("/match/breed/<int:breed_id>")
def match_specific(breed_id):
    """Analyze compatibility with a specific breed and provide improvement suggestions"""
    answers = session.get("quiz_answers", {})
    
    if not answers:
        return redirect(url_for("matching.quiz"))
    
    breed = Breed.query.get_or_404(breed_id)
    
    # Calculate compatibility
    match_data = CompatibilityEngine.calculate_match_score(answers, breed)
    
    # Get improvement suggestions
    suggestions = CompatibilityEngine.get_improvement_suggestions(answers, breed)
    
    return render_template(
        "matching/breed_analysis.html",
        breed=breed,
        score=match_data['score'],
        compatibility_level=match_data['compatibility_level'],
        mismatches=match_data['mismatches'],
        individual_scores=match_data['individual_scores'],
        suggestions=suggestions['suggestions'],
        strength_areas=suggestions['strength_areas'],
    )


# ---------------------------
# API: Calculate Match Score
# ---------------------------
@bp.route("/api/match-score/<int:breed_id>", methods=["POST"])
def api_match_score(breed_id):
    """API endpoint to calculate match score for a breed"""
    answers = session.get("quiz_answers", {})
    
    if not answers:
        return jsonify({'error': 'No quiz answers in session'}), 400
    
    breed = Breed.query.get_or_404(breed_id)
    match_data = CompatibilityEngine.calculate_match_score(answers, breed)
    
    return jsonify({
        'breed_id': breed_id,
        'breed_name': breed.name,
        'score': match_data['score'],
        'level': match_data['compatibility_level'],
        'mismatches': match_data['mismatches'],
    })


# ---------------------------
# API: Get Top Matches
# ---------------------------
@bp.route("/api/top-matches", methods=["GET"])
def api_top_matches():
    """API endpoint to get top N matches"""
    answers = session.get("quiz_answers", {})
    
    if not answers:
        return jsonify({'error': 'No quiz answers in session'}), 400
    
    limit = request.args.get('limit', 5, type=int)
    limit = min(limit, 20)  # Cap at 20
    
    matches = CompatibilityEngine.find_top_matches(answers, limit=limit)
    
    return jsonify({
        'matches': [
            {
                'breed_id': m['breed'].id,
                'breed_name': m['breed'].name,
                'species_name': m['breed'].species.name,
                'score': m['score'],
                'level': m['level'],
                'image_url': m['breed'].image_url,
            }
            for m in matches
        ]
    })


# ---------------------------
# Reset Quiz Session
# ---------------------------
@bp.route("/reset")
def reset_quiz():
    """Clear quiz answers from session"""
    session.pop("quiz_answers", None)
    return redirect(url_for("matching.quiz"))
