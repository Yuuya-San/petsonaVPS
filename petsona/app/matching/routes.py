from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from flask_login import current_user
from datetime import datetime
from app.models.breed import Breed
from app.models.species import Species
from app.utils.compatibility_engine import CompatibilityEngine
from app.utils.audit import log_event
from . import bp


# ---------------------------
# Quiz Page
# ---------------------------
@bp.route("/", methods=["GET", "POST"])
def quiz():
    if request.method == "POST":
        answers = {
            k: v.strip() if isinstance(v, str) else v
            for k, v in request.form.items()
            if v is not None and v != ""
        }

        session["quiz_answers"] = answers
        session.modified = True

        return redirect(url_for("matching.results"))

    return render_template("matching/quiz.html")


# ---------------------------
# Results Page
# ---------------------------
@bp.route("/results")
def results():
    answers = session.get("quiz_answers")

    if not isinstance(answers, dict) or not answers:
        session.pop("quiz_answers", None)
        return redirect(url_for("matching.quiz"))

    matches = CompatibilityEngine.find_top_matches(answers, limit=5) or []

    return render_template(
        "matching/results.html",
        matches=matches,
        user_answers=answers
    )


# ---------------------------
# Best Match
# ---------------------------
@bp.route("/match/top")
def match_top():
    answers = session.get("quiz_answers")

    if not isinstance(answers, dict) or not answers:
        return redirect(url_for("matching.quiz"))

    matches = CompatibilityEngine.find_top_matches(answers, limit=1) or []

    if not matches:
        return render_template("matching/no_match.html")

    match = matches[0]

    return render_template(
        "matching/specific_match.html",
        breed=match['breed'],
        score=match['score'],
        compatibility_level=match['level'],
        mismatches=match.get('mismatches', []),
        category_scores=match.get('details', {}).get('category_scores', {}),
        details=match.get('details', {})
    )


# ---------------------------
# Breed Analysis
# ---------------------------
@bp.route("/match/breed/<int:breed_id>")
def match_specific(breed_id):
    answers = session.get("quiz_answers")

    if not isinstance(answers, dict) or not answers:
        return redirect(url_for("matching.quiz"))

    breed = Breed.query.get_or_404(breed_id)

    match_data = CompatibilityEngine.calculate_match_score(answers, breed) or {}
    suggestions = CompatibilityEngine.get_improvement_suggestions(answers, breed) or {}

    return render_template(
        "matching/breed_analysis.html",
        breed=breed,
        score=match_data.get('score', 0),
        compatibility_level=match_data.get('compatibility_level', "Unknown"),
        mismatches=match_data.get('mismatches', []),
        category_scores=match_data.get('category_scores', {}),
        individual_scores=match_data.get('individual_scores', []),
        suggestions=suggestions.get('suggestions', []),
        strength_areas=suggestions.get('strength_areas', []),
    )


# ---------------------------
# API Match Score
# ---------------------------
@bp.route("/api/match-score/<int:breed_id>", methods=["POST"])
def api_match_score(breed_id):
    answers = session.get("quiz_answers")

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
# API Top Matches
# ---------------------------
@bp.route("/api/top-matches", methods=["GET"])
def api_top_matches():
    answers = session.get("quiz_answers")

    if not isinstance(answers, dict) or not answers:
        return jsonify({'error': 'No quiz answers in session'}), 400

    limit = request.args.get('limit', 5, type=int)
    limit = max(1, min(limit, 20))

    matches = CompatibilityEngine.find_top_matches(answers, limit=limit) or []

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
# API Breed Match
# ---------------------------
@bp.route("/api/breed-match", methods=["POST"])
def api_breed_match():
    try:
        data = request.get_json(silent=True) or {}

        breed_id = data.get("breed_id")
        answers = data.get("answers")

        if not isinstance(breed_id, int) or not isinstance(answers, dict):
            return jsonify({'error': 'Invalid breed_id or answers'}), 400

        breed = Breed.query.get_or_404(breed_id)

        match_data = CompatibilityEngine.calculate_match_score(answers, breed) or {}
        suggestions = CompatibilityEngine.get_improvement_suggestions(answers, breed) or {}

        return jsonify({
            'success': True,
            'breed_id': breed.id,
            'breed_name': breed.name,
            'score': match_data.get('score', 0),
            'level': match_data.get('compatibility_level', "Unknown"),
            'mismatches': match_data.get('mismatches', []),
            'suggestions': suggestions.get('suggestions', []),
            'strength_areas': suggestions.get('strength_areas', []),
            'improvement_areas': suggestions.get('improvement_areas', []),
            'category_scores': match_data.get('category_scores', {}),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ---------------------------
# API Quiz Submit
# ---------------------------
@bp.route("/api/quiz-submit", methods=["POST"])
def api_quiz_submit():
    try:
        data = request.get_json(silent=True) or {}

        if not isinstance(data, dict) or not data:
            return jsonify({'error': 'No quiz data provided'}), 400

        matches = CompatibilityEngine.find_top_matches(data, limit=5) or []

        enhanced = []
        for m in matches:
            breed = m['breed']
            suggestions = CompatibilityEngine.get_improvement_suggestions(data, breed) or {}

            enhanced.append({
                'breed': {
                    'id': breed.id,
                    'name': breed.name,
                    'image_url': breed.image_url,
                    'summary': breed.summary,
                    'species': {
                        'id': breed.species.id,
                        'name': breed.species.name,
                    }
                },
                'score': m['score'],
                'level': m['level'],
                'mismatches': m.get('mismatches', []),
                'suggestions': suggestions.get('suggestions', []),
                'strength_areas': suggestions.get('strength_areas', []),
                'category_scores': m.get('details', {}).get('category_scores', {}),
            })

        log_event(
            "pet_compatibility_quiz_completed",
            {
                "answers_count": len(data),
                "top_match_breed_id": enhanced[0]["breed"]["id"] if enhanced else None,
                "top_match_score": enhanced[0]["score"] if enhanced else None,
                "total_matches_generated": len(enhanced),
            }
        )

        return jsonify({
            "success": True,
            "matches": enhanced,
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ---------------------------
# Reset
# ---------------------------
@bp.route("/reset")
def reset_quiz():
    session.pop("quiz_answers", None)
    return redirect(url_for("matching.quiz"))
