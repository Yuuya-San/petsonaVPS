"""
Big Five Personality Traits Assessment & Compatibility Engine

Implements the Big Five personality model (also known as OCEAN) to provide
psychological depth to pet-owner compatibility matching. Based on established
psychological research, the Big Five model measures five fundamental dimensions
of human personality.

Theory:
--------
The Big Five model (Costa & McCrae) measures personality across five dimensions:
1. Openness (O) - Creativity, curiosity, adaptability, openness to experience
2. Conscientiousness (C) - Organization, discipline, responsibility, structure
3. Extraversion (E) - Sociability, energy levels, assertiveness, activity
4. Agreeableness (A) - Kindness, cooperation, empathy, compassion
5. Neuroticism (N) - Emotional sensitivity, anxiety, stress response

Application to Pet Compatibility:
----------------------------------
Each breed has inherent personality characteristics that align better with certain
human personality types. For example:
- High-energy, social dogs match extraverted owners
- Calm, independent cats match introverted owners
- High-maintenance breeds match conscientious owners
- Routine-dependent pets match low-openness owners
- Emotionally sensitive pets match low-neuroticism owners

Scoring System:
---------------
User traits: Calculated from questionnaire responses (1-5 scale)
- Questions are designed to measure each of the five traits
- Multiple questions per trait ensure reliability
- Scoring converts answers to 1-5 numeric values
- Composite scores normalize to 1-100 percentile scale

Breed traits: Assigned by experts/data based on breed characteristics (1-5 scale)
- Breed data reflects inherent tendencies and needs
- Flexibility rating indicates variability within breed
- More flexible breeds work with wider personality ranges

Compatibility Scoring:
- Euclidean distance metric in 5D personality space
- Penalizes large personality mismatches while allowing flexibility
- Weighted by breed flexibility rating
- Integrated into overall compatibility calculation with 20% weight

IMPORTANT: This is a SUPPORTING factor, not the primary determinant.
Pet welfare, safety, and practical constraints (space, time, budget) remain
the highest priority in compatibility calculations.
"""

from typing import Dict, List, Any, Optional, Tuple
import math


# ============================================================================
# BIG FIVE PERSONALITY ASSESSMENT QUESTIONS
# ============================================================================

BIG_FIVE_QUESTIONS = [
    # ========================================================================
    # OPENNESS - Creativity, curiosity, adaptability (3 questions - OPTIMIZED)
    # ========================================================================
    {
        'name': 'big_five_open_1',
        'section': 'Your Personality',
        'trait': 'Openness',
        'question': 'I like trying new things and exploring different activities.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },
    {
        'name': 'big_five_open_2',
        'section': 'Your Personality',
        'trait': 'Openness',
        'question': 'Unusual or different ideas excite me.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },
    {
        'name': 'big_five_open_3',
        'section': 'Your Personality',
        'trait': 'Openness',
        'question': 'When things change unexpectedly, I adapt pretty well.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },

    # ========================================================================
    # CONSCIENTIOUSNESS - Organization, discipline, responsibility (3 questions - OPTIMIZED)
    # ========================================================================
    {
        'name': 'big_five_cons_1',
        'section': 'Your Personality',
        'trait': 'Conscientiousness',
        'question': 'My space is usually clean and organized.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },
    {
        'name': 'big_five_cons_2',
        'section': 'Your Personality',
        'trait': 'Conscientiousness',
        'question': 'I stick to a routine for daily tasks.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },
    {
        'name': 'big_five_cons_3',
        'section': 'Your Personality',
        'trait': 'Conscientiousness',
        'question': 'People can count on me to follow through.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },

    # ========================================================================
    # EXTRAVERSION - Sociability, energy, assertiveness (3 questions - OPTIMIZED)
    # ========================================================================
    {
        'name': 'big_five_extr_1',
        'section': 'Your Personality',
        'trait': 'Extraversion',
        'question': 'I\'m comfortable meeting and talking to new people.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },
    {
        'name': 'big_five_extr_2',
        'section': 'Your Personality',
        'trait': 'Extraversion',
        'question': 'I have lots of energy and I\'m always doing something.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },
    {
        'name': 'big_five_extr_3',
        'section': 'Your Personality',
        'trait': 'Extraversion',
        'question': 'I have fun at social gatherings.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },

    # ========================================================================
    # AGREEABLENESS - Kindness, cooperation, empathy (3 questions - OPTIMIZED)
    # ========================================================================
    {
        'name': 'big_five_agre_1',
        'section': 'Your Personality',
        'trait': 'Agreeableness',
        'question': 'I genuinely care about others\' feelings.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },
    {
        'name': 'big_five_agre_2',
        'section': 'Your Personality',
        'trait': 'Agreeableness',
        'question': 'I like helping people and making them happy.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },
    {
        'name': 'big_five_agre_3',
        'section': 'Your Personality',
        'trait': 'Agreeableness',
        'question': 'When people make mistakes, I\'m understanding.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },

    # ========================================================================
    # NEUROTICISM (Emotional Stability) - Emotional sensitivity, stress response (3 questions - OPTIMIZED)
    # ========================================================================
    {
        'name': 'big_five_neur_1',
        'section': 'Your Personality',
        'trait': 'Neuroticism',
        'question': 'I tend to worry about things more than I should.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },
    {
        'name': 'big_five_neur_2',
        'section': 'Your Personality',
        'trait': 'Neuroticism',
        'question': 'I stay calm when things get stressful.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': True,
    },
    {
        'name': 'big_five_neur_3',
        'section': 'Your Personality',
        'trait': 'Neuroticism',
        'question': 'Small problems can really bother me.',
        'options': ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
        'reverse': False,
    },
]


# ============================================================================
# ANSWER MAPPING - Convert Likert scale to numeric scores
# ============================================================================

LIKERT_ANSWER_MAPPING = {
    'Strongly Disagree': 1,
    'Disagree': 2,
    'Neutral': 3,
    'Agree': 4,
    'Strongly Agree': 5,
}


# ============================================================================
# BIG FIVE TRAIT DESCRIPTIONS & RANGES
# ============================================================================

TRAIT_DESCRIPTIONS = {
    'Openness': {
        'description': 'Creativity, curiosity, adaptability, and openness to new experiences',
        'low': 'Prefers routine, traditional, familiar experiences',
        'high': 'Creative, curious, adaptable, enjoys novelty and change',
    },
    'Conscientiousness': {
        'description': 'Organization, discipline, responsibility, and attention to detail',
        'low': 'Spontaneous, flexible, casual about rules and schedules',
        'high': 'Organized, disciplined, responsible, detail-oriented',
    },
    'Extraversion': {
        'description': 'Sociability, energy levels, and assertiveness in social situations',
        'low': 'Introverted, reserved, recharges through alone time',
        'high': 'Outgoing, high-energy, social, enjoys being with others',
    },
    'Agreeableness': {
        'description': 'Kindness, cooperation, empathy, and compassion',
        'low': 'Competitive, independent, critical',
        'high': 'Compassionate, cooperative, empathetic, warm',
    },
    'Neuroticism': {
        'description': 'Emotional sensitivity, anxiety, and stress response',
        'low': 'Calm, confident, emotionally stable',
        'high': 'Emotionally sensitive, anxious, affected by stress',
    },
}


# ============================================================================
# FUNCTIONS: ASSESSMENT & SCORING
# ============================================================================

def calculate_user_big_five_scores(answers: Dict[str, str]) -> Dict[str, float]:
    """
    Calculate user's Big Five personality scores from questionnaire answers.
    
    IMPROVED PROCESS:
    1. Extract answers for each Big Five question
    2. Convert Likert scale responses to numeric scores (1-5)
    3. Apply reverse scoring where needed (big_five_neur_2: "I stay calm" reversed)
    4. Calculate mean score for each trait (3 questions per trait)
    5. Validate all answers exist and are in valid range
    6. Return 1-5 scale scores
    
    Args:
        answers: Dictionary of user answers {question_key: answer_text}
    
    Returns:
        Dictionary with trait scores (1-5 scale):
        {
            'Openness': 3.5,
            'Conscientiousness': 4.0,
            'Extraversion': 2.8,
            'Agreeableness': 4.2,
            'Neuroticism': 2.1,
        }
    """
    trait_scores = {
        'Openness': [],
        'Conscientiousness': [],
        'Extraversion': [],
        'Agreeableness': [],
        'Neuroticism': [],
    }
    
    # Process each Big Five question
    for question in BIG_FIVE_QUESTIONS:
        question_key = question['name']
        trait = question['trait']
        
        # Get user's answer - validate it exists
        if question_key not in answers:
            # Skip missing answers, don't default
            continue
        
        user_answer = answers[question_key]
        if user_answer is None or user_answer == '':
            # Skip empty answers
            continue
        
        # Convert to numeric score - validate it's a valid Likert response
        user_answer_str = str(user_answer).strip()
        if user_answer_str not in LIKERT_ANSWER_MAPPING:
            # Skip invalid answers
            continue
        
        numeric_score = LIKERT_ANSWER_MAPPING[user_answer_str]
        
        # Apply reverse scoring if needed
        # Example: big_five_neur_2 "I stay calm when things get stressful" should be reversed
        # High calm = low neuroticism, so reverse the score
        if question.get('reverse', False):
            numeric_score = 6 - numeric_score  # 5→1, 4→2, 3→3, 2→4, 1→5
        
        # Ensure score is in valid range
        numeric_score = max(1, min(5, numeric_score))
        
        # Accumulate in trait scores
        trait_scores[trait].append(numeric_score)
    
    # Calculate mean score for each trait
    final_scores = {}
    for trait, scores in trait_scores.items():
        if scores and len(scores) > 0:
            mean_score = sum(scores) / len(scores)
            # Round to 2 decimal places for precision, ensure 1-5 range
            final_scores[trait] = max(1.0, min(5.0, round(mean_score, 2)))
        else:
            # If no valid answers for this trait, default to neutral (3.0)
            final_scores[trait] = 3.0
    
    return final_scores


def get_breed_big_five_scores(breed) -> Dict[str, int]:
    """
    Get breed's Big Five personality requirement scores.
    
    These are predefined by experts and stored in the breed database.
    Each score on 1-5 scale represents the breed's inherent traits.
    
    Args:
        breed: Breed object with Big Five attributes
    
    Returns:
        Dictionary with trait scores:
        {
            'Openness': 4,
            'Conscientiousness': 2,
            'Extraversion': 4,
            'Agreeableness': 4,
            'Neuroticism': 1,
        }
    """
    return {
        'Openness': getattr(breed, 'big_five_openness', 3),
        'Conscientiousness': getattr(breed, 'big_five_conscientiousness', 3),
        'Extraversion': getattr(breed, 'big_five_extraversion', 3),
        'Agreeableness': getattr(breed, 'big_five_agreeableness', 3),
        'Neuroticism': getattr(breed, 'big_five_neuroticism', 2),
    }


def calculate_big_five_compatibility(
    user_scores: Dict[str, float],
    breed_scores: Dict[str, int],
    breed_flexibility: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculate personality compatibility score using Big Five traits.
    
    IMPROVED ALGORITHM:
    1. Calculate absolute trait gaps for each dimension
    2. Use gap-based scoring: perfect match (gap 0) = 100%, max gap (4) = 0%
    3. Average across all 5 traits
    4. Apply flexibility bonus (modest, only 5-10%)
    5. Individual trait gap analysis for detailed feedback
    
    Key Fix: Uses direct gap-to-percentage conversion instead of Euclidean distance
    This ensures opposite answers (1 vs 5, gap=4) = 0% compatibility
    
    Args:
        user_scores: User's Big Five scores {trait: 1-5 value}
        breed_scores: Breed's Big Five requirements {trait: 1-5 value}
        breed_flexibility: Optional float (0-1) indicating breed's adaptability
    
    Returns:
        Dictionary with:
        - overall_compatibility: 0-1 score (1 = perfect match)
        - compatibility_percentage: 0-100 percentage
        - compatibility_level: 'Excellent'|'Good'|'Moderate'|'Low'|'Poor'
        - trait_gaps: Dict showing mismatches per trait (for feedback)
        - personality_match_reason: Text explanation
    """
    if not user_scores or not breed_scores:
        return {
            'overall_compatibility': 0.5,
            'compatibility_percentage': 50,
            'compatibility_level': 'Unknown',
            'trait_gaps': {},
            'personality_match_reason': 'Unable to calculate personality compatibility.',
        }
    
    traits = ['Openness', 'Conscientiousness', 'Extraversion', 'Agreeableness', 'Neuroticism']
    
    # Calculate gap-based compatibility for each trait
    trait_compatibilities = []
    trait_gaps = {}
    
    for trait in traits:
        user_val = user_scores.get(trait, 3.0)
        breed_val = breed_scores.get(trait, 3)
        
        # Ensure both values are in 1-5 range
        user_val = max(1.0, min(5.0, float(user_val)))
        breed_val = max(1, min(5, int(breed_val)))
        
        # Calculate gap (0-4 range since scale is 1-5)
        gap = abs(user_val - breed_val)
        
        # Convert gap to compatibility percentage
        # gap 0 = 100%, gap 0.5 = 87.5%, gap 1 = 75%, gap 2 = 50%, gap 3 = 25%, gap 4 = 0%
        trait_compat = max(0, (1 - (gap / 4.0)) * 100)
        trait_compatibilities.append(trait_compat)
        
        trait_gaps[trait] = {
            'user': round(user_val, 2),
            'breed': breed_val,
            'gap': round(gap, 2),
            'compatibility': round(trait_compat, 1),
            'match_quality': _get_trait_match_quality(gap),
        }
    
    # Calculate average compatibility across all traits
    avg_compatibility = sum(trait_compatibilities) / len(trait_compatibilities) if trait_compatibilities else 50
    compatibility_percentage = max(0, min(100, avg_compatibility))
    
    # Apply flexibility bonus (modest: only 5% for highly flexible breeds)
    if breed_flexibility and breed_flexibility > 0.7:
        compatibility_percentage *= 1.05  # 5% bonus only
        compatibility_percentage = min(100, compatibility_percentage)
    
    compatibility_score = compatibility_percentage / 100.0
    
    # Determine compatibility level
    if compatibility_percentage >= 85:
        level = 'Excellent'
    elif compatibility_percentage >= 70:
        level = 'Good'
    elif compatibility_percentage >= 55:
        level = 'Moderate'
    elif compatibility_percentage >= 40:
        level = 'Low'
    else:
        level = 'Poor'
    
    # Generate explanation
    explanation = _generate_personality_explanation(user_scores, breed_scores, trait_gaps)
    
    return {
        'overall_compatibility': round(compatibility_score, 3),
        'compatibility_percentage': round(compatibility_percentage, 1),
        'compatibility_level': level,
        'trait_gaps': trait_gaps,
        'personality_match_reason': explanation,
        'trait_compatibilities': {t: trait_gaps[t]['compatibility'] for t in traits},
    }


def _get_trait_match_quality(gap: float) -> str:
    """
    Convert trait gap to quality descriptor.
    
    Args:
        gap: Absolute difference between user and breed trait (0-4 scale)
    
    Returns:
        Quality descriptor string
    """
    if gap < 0.5:
        return 'Perfect Match'
    elif gap < 1.0:
        return 'Excellent Match'
    elif gap < 1.5:
        return 'Good Match'
    elif gap < 2.0:
        return 'Moderate Match'
    elif gap < 2.5:
        return 'Fair Match'
    else:
        return 'Poor Match'


def _generate_personality_explanation(
    user_scores: Dict[str, float],
    breed_scores: Dict[str, int],
    trait_gaps: Dict[str, Dict],
) -> str:
    """
    Generate human-readable explanation of personality compatibility.
    
    Args:
        user_scores: User's Big Five scores
        breed_scores: Breed's Big Five scores
        trait_gaps: Calculated trait gaps
    
    Returns:
        Explanatory text
    """
    # Find the best and worst matching traits
    gaps_sorted = sorted(
        [(trait, data['gap']) for trait, data in trait_gaps.items()],
        key=lambda x: x[1]
    )
    
    best_trait = gaps_sorted[0][0]
    worst_trait = gaps_sorted[-1][0]
    
    explanations = {
        'Openness': f"Your {'creative and adventurous' if user_scores.get('Openness', 3) > 3.5 else 'traditional and routine-oriented'} nature",
        'Conscientiousness': f"Your {'organized and disciplined' if user_scores.get('Conscientiousness', 3) > 3.5 else 'flexible and spontaneous'} approach",
        'Extraversion': f"Your {'outgoing and social' if user_scores.get('Extraversion', 3) > 3.5 else 'introverted and reserved'} personality",
        'Agreeableness': f"Your {'compassionate and cooperative' if user_scores.get('Agreeableness', 3) > 3.5 else 'independent and analytical'} nature",
        'Neuroticism': f"Your {'emotionally sensitive' if user_scores.get('Neuroticism', 3) > 3.5 else 'calm and stable'} temperament",
    }
    
    explanation = f"Personality-wise, {explanations.get(best_trait, 'your personality')} aligns perfectly with this breed. "
    
    if gaps_sorted[-1][1] > 1.5:
        explanation += f"However, {explanations.get(worst_trait, 'your personality')} differs from what this breed typically needs."
    
    return explanation


def get_big_five_recommendations(
    user_scores: Dict[str, float],
    breed_scores: Dict[str, int],
) -> List[str]:
    """
    Generate recommendations for improving personality compatibility.
    
    Args:
        user_scores: User's Big Five scores
        breed_scores: Breed's Big Five requirements
    
    Returns:
        List of actionable recommendations
    """
    recommendations = []
    traits = ['Openness', 'Conscientiousness', 'Extraversion', 'Agreeableness', 'Neuroticism']
    
    recommendation_map = {
        'Openness': {
            'low': 'This pet benefits from routine—creating a predictable daily schedule will help it feel secure.',
            'high': 'This pet thrives on variety and enrichment—plan new activities and environmental changes regularly.',
        },
        'Conscientiousness': {
            'low': 'This pet requires structured care—consider setting reminders for feeding, exercise, and vet appointments.',
            'high': 'This pet appreciates consistency—maintain regular routines for feeding, exercise, and training.',
        },
        'Extraversion': {
            'low': 'This pet prefers calm, quiet environments—create peaceful spaces where it can rest undisturbed.',
            'high': 'This pet needs social interaction and activity—plan daily engagement and social time.',
        },
        'Agreeableness': {
            'low': 'This pet may be independent—respect its boundaries and avoid forcing excessive interaction.',
            'high': 'This pet thrives on bonding—invest time in building a strong relationship through gentle interaction.',
        },
        'Neuroticism': {
            'low': 'This pet is resilient—you can handle occasional changes or stressful situations together.',
            'high': 'This pet is sensitive to stress—minimize sudden changes and create a calm, supportive environment.',
        },
    }
    
    for trait in traits:
        user_val = user_scores.get(trait, 3.0)
        breed_val = breed_scores.get(trait, 3)
        gap = abs(user_val - breed_val)
        
        # Only recommend for significant mismatches (gap > 1.0)
        if gap > 1.0:
            # Determine if user is too low or too high compared to breed
            key = 'low' if user_val < breed_val else 'high'
            recommendation = recommendation_map.get(trait, {}).get(key)
            if recommendation:
                recommendations.append(recommendation)
    
    return recommendations


# ============================================================================
# INTEGRATION WITH COMPATIBILITY ENGINE
# ============================================================================

def integrate_big_five_into_compatibility(
    base_compatibility_score: float,
    big_five_compatibility_score: float,
    big_five_weight: float = 0.20,
) -> float:
    """
    Integrate Big Five personality compatibility into overall compatibility score.
    
    The Big Five personality compatibility is a supporting factor, not the
    primary determinant. It should be weighted at approximately 20% of the
    overall compatibility score.
    
    Formula:
    Final Score = (Base Score * (1 - Weight)) + (Big Five Score * Weight)
    
    Args:
        base_compatibility_score: Original compatibility score (0-100)
        big_five_compatibility_score: Big Five compatibility (0-100)
        big_five_weight: Weight to give Big Five (default 0.20 = 20%)
    
    Returns:
        Adjusted compatibility score (0-100)
    """
    # Normalize scores to 0-1 range if needed
    base_norm = base_compatibility_score / 100 if base_compatibility_score > 1 else base_compatibility_score
    big_five_norm = big_five_compatibility_score / 100 if big_five_compatibility_score > 1 else big_five_compatibility_score
    
    # Calculate weighted average
    adjusted_score = (base_norm * (1 - big_five_weight)) + (big_five_norm * big_five_weight)
    
    # Return as percentage (0-100)
    return adjusted_score * 100
