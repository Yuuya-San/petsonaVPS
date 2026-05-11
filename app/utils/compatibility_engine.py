"""
Pet Compatibility Scoring Engine

A clean, modular system for calculating pet-owner compatibility.
Evaluates user answers against breed requirements across 8 dimensions.

Architecture:
1. Answer Normalization - Convert user answers to numeric scores (0-4)
2. Breed Value Normalization - Convert breed requirements to numeric scores
3. Question Scoring - Score individual questions with special case handling
4. Penalty Calculation - Apply penalties based on gaps between user and breed
5. Compatibility Calculation - Aggregate scores across all questions
6. Suggestions - Generate improvement recommendations
7. Match Reasons - Explain why user and pet matched
"""

from app.models.breed import Breed
from app.models.species import Species
from typing import Dict, List, Any, Optional


# ============================================================================
# ANSWER MAPPINGS - Convert user answers to numeric scores (0-4)
# ============================================================================

ANSWER_MAPPINGS = {
    # Lifestyle Questions
    'energy_level': {
        'I mostly relax at home': 4,
        'I move around sometimes': 3,
        'I am very active and always busy': 1,
    },
    'noise_level': {
        'I need it very quiet': 1,
        'Some noise is okay': 3,
        'Noise does not bother me': 4,
    },
    'social_needs': {
        'Just a little': 1,
        'A fair amount': 3,
        'A lot, I like bonding': 4,
    },
    'handling_tolerance': {
        'Very calm and quiet': 3,
        'Normal': 4,
        'Busy, noisy, and active': 1,
    },
    'exercise_needs': {
        'No, I\'m busy': 1,
        'Maybe, I\'m not sure': 2,
        'Yes, I can': 4,
    },
    
    # Experience & Training
    'experience_required': {
        'This is my first pet': 1,
        'I have had a few': 3,
        'I have a lot of experience': 4,
    },
    'trainability': {
        'Not very patient': 1,
        'Somewhat patient': 3,
        'Very patient': 4,
    },
    'temperament_tolerance': {
        'Not well': 1,
        'I can try': 3,
        'I handle them well': 4,
    },
    
    # Space & Environment
    'space_needs': {
        'Small apartment or room': 1,
        'Medium-sized home': 3,
        'Large home or house with space': 4,
    },
    'environment_complexity': {
        'No, I prefer simple pets': 1,
        'I can manage a little': 3,
        'Yes, I\'m okay with it': 4,
    },
    'min_enclosure_size': {
        'No': 0,
        'Small ones only': 3,
        'Large ones are okay': 4,
    },
    
    # Care & Time
    'daily_care_time': {
        'Less than 1 hour': 1,
        '1-2 hours': 2,
        '2-4 hours': 3,
        'More than 4 hours': 4,
    },
    
    # Financial
    'monthly_cost_level': {
        'Low budget': 1,
        'Medium budget': 3,
        'High budget': 4,
    },
    'emergency_care_risk': {
        'No, I cannot': 0,
        'Maybe, I am not sure': 2,
        'Yes, I can': 4,
    },
    
    # Household
    'child_friendly': {
        'Yes': 1,
        'No': 4,
    },
    'other_pets_friendly': {
        'None': 4,
        'Dogs': 1,
        'Cats': 1,
        'Small Pets': 1,
    },
    
    # Safety
    'prey_drive': {
        'No, I am not': 0,
        'Maybe, I am not sure': 2,
        'Yes, I am': 4,
    },
    'okay_fragile': {
        'No, I am not': 0,
        'Maybe, I am not sure': 2,
        'Yes, I am': 4,
    },
    'okay_special_vet': {
        'No, I cannot': 0,
        'Maybe, I am not sure': 2,
        'Yes, I can': 4,
    },
    
    # Pet Preference
    'pet_preference': {
        'Dogs': 'Dogs',
        'Cats': 'Cats',
        'Birds': 'Birds',
        'Fish': 'Fish',
        'Reptiles': 'Reptiles',
        'Amphibians': 'Amphibians',
        'Small Animals': 'Small Animals',
    },
    
    # Health
    'pet_allergies': {
        'Yes': 0,
        'No': 4,
    },
}

# Question to Breed Attribute Mapping
QUESTION_TO_ATTRIBUTE = {
    'energy_level': ('energy_level', 'breed'),
    'exercise_needs': ('exercise_needs', 'breed'),
    'noise_level': ('noise_level', 'breed'),
    'social_needs': ('social_needs', 'breed'),
    'handling_tolerance': ('handling_tolerance', 'breed'),
    'experience_required': ('experience_required', 'breed'),
    'trainability': ('trainability', 'breed'),
    'temperament_tolerance': ('trainability', 'breed'),
    'space_needs': ('space_needs', 'breed'),
    'environment_complexity': ('environment_complexity', 'breed'),
    'min_enclosure_size': ('min_enclosure_size', 'breed'),
    'daily_care_time': ('time_commitment', 'breed'),
    'monthly_cost_level': ('monthly_cost_level', 'breed'),
    'emergency_care_risk': ('emergency_care_risk', 'breed'),
    'child_friendly': ('child_friendly', 'breed'),
    'other_pets_friendly': ('household_pets', 'breed'),
    'prey_drive': ('prey_drive', 'breed'),
    'pet_allergies': ('allergy_friendly', 'breed'),
    'okay_fragile': ('fragile_species', 'species'),
    'okay_special_vet': ('special_vet_required', 'species'),
}

# Question Weights (importance of each question)
QUESTION_WEIGHTS = {
    'energy_level': 0.95,
    'exercise_needs': 0.95,
    'noise_level': 0.80,
    'social_needs': 0.85,
    'handling_tolerance': 0.85,
    'experience_required': 1.00,
    'trainability': 0.95,
    'temperament_tolerance': 0.95,
    'space_needs': 1.00,
    'environment_complexity': 0.85,
    'min_enclosure_size': 0.85,
    'daily_care_time': 0.95,
    'monthly_cost_level': 1.00,
    'emergency_care_risk': 0.95,
    'child_friendly': 0.98,
    'other_pets_friendly': 0.95,
    'prey_drive': 0.98,
    'okay_fragile': 0.98,
    'okay_special_vet': 0.95,
    'pet_allergies': 1.00,
}

# Category Weights (importance of each category)
CATEGORY_WEIGHTS = {
    'safety': 1.60,
    'experience': 1.50,
    'household': 1.35,
    'space': 1.25,
    'lifestyle': 1.20,
    'health': 1.20,
    'financial': 1.10,
    'care': 1.05,
}

# Question to Category Mapping
QUESTION_CATEGORIES = {
    'energy_level': 'lifestyle',
    'exercise_needs': 'lifestyle',
    'noise_level': 'lifestyle',
    'social_needs': 'lifestyle',
    'handling_tolerance': 'lifestyle',
    'experience_required': 'experience',
    'trainability': 'experience',
    'temperament_tolerance': 'experience',
    'space_needs': 'space',
    'environment_complexity': 'space',
    'min_enclosure_size': 'space',
    'daily_care_time': 'care',
    'monthly_cost_level': 'financial',
    'emergency_care_risk': 'financial',
    'child_friendly': 'household',
    'other_pets_friendly': 'household',
    'prey_drive': 'safety',
    'okay_fragile': 'safety',
    'okay_special_vet': 'safety',
    'pet_allergies': 'health',
}


# ============================================================================
# NORMALIZATION FUNCTIONS
# ============================================================================

def normalize_answer(question_key: str, answer: str) -> Optional[int]:
    """
    Convert user answer to numeric score (0-4).
    
    Args:
        question_key: The question identifier
        answer: The user's answer text
    
    Returns:
        Numeric score (0-4) or None if answer not found
    """
    if not answer or question_key not in ANSWER_MAPPINGS:
        return None
    
    mapping = ANSWER_MAPPINGS[question_key]
    answer = str(answer).strip()
    return mapping.get(answer)


def normalize_breed_value(breed_value: Any) -> Optional[int]:
    """
    Convert breed requirement to numeric score (1-4).
    
    Args:
        breed_value: The breed's requirement value (boolean, string, int, etc.)
    
    Returns:
        Numeric score (1-4) or None if no value
    """
    if breed_value is None:
        return None
    
    # Handle booleans
    if isinstance(breed_value, bool):
        return 4 if breed_value else 1
    
    # Handle strings (Low/Medium/High/Very High)
    value_str = str(breed_value).strip().lower()
    
    mapping = {
        'low': 1,
        'medium': 2,
        'high': 3,
        'very high': 4,
    }
    return mapping.get(value_str)


# ============================================================================
# PENALTY FUNCTIONS
# ============================================================================

def calculate_penalty(gap: int) -> float:
    """
    Calculate penalty score based on gap between user and breed requirement.
    
    Scoring:
    - Gap 0: 1.0 (perfect match)
    - Gap 1: 0.75 (good match)
    - Gap 2: 0.45 (moderate match)
    - Gap 3: 0.15 (poor match)
    
    Args:
        gap: Difference between breed requirement and user capability
    
    Returns:
        Penalty score (0.0-1.0)
    """
    penalty_map = {
        0: 1.0,   # Perfect match
        1: 0.75,  # Small gap
        2: 0.45,  # Medium gap
        3: 0.15,  # Large gap
    }
    
    return penalty_map.get(gap, 0.0) if gap >= 0 else 1.0


# ============================================================================
# SPECIAL CASE SCORING FUNCTIONS
# ============================================================================

def score_space_and_household(question_key: str, user_score: int, breed_score: int) -> float:
    """
    Score space and household capacity questions.
    
    Logic: Having MORE capacity is always better. If user's capacity >= pet's 
    requirement, it's a perfect match.
    
    Args:
        question_key: The question identifier
        user_score: User's numeric score (1-4)
        breed_score: Breed's numeric requirement (1-4)
    
    Returns:
        Score (0.0-1.0)
    """
    if user_score >= breed_score:
        return 1.0
    
    gap = breed_score - user_score
    return calculate_penalty(gap)


def score_binary_safety(user_answer: str) -> float:
    """
    Score binary safety questions (okay_fragile, okay_special_vet).
    
    Logic: User must accept the risk or requirement.
    - Accept/Maybe → Perfect match (1.0)
    - Reject → Deal breaker (0.0)
    
    Args:
        user_answer: The user's answer text
    
    Returns:
        Score (0.0 or 1.0)
    """
    accept_answers = ['Yes', 'Yes, I am', 'Maybe, I am not sure', 'Yes, I can']
    reject_answers = ['No, I am not', 'No', 'No, I cannot']
    
    if user_answer in accept_answers:
        return 1.0
    elif user_answer in reject_answers:
        return 0.0
    
    return 0.5  # Uncertain


def score_child_friendly(user_answer: str, breed_value: Any) -> float:
    """
    Score child_friendly question with smart logic.
    
    Logic:
    - No children in household → Always perfect match (1.0) - no conflict
    - Has children → Need child-friendly pet (1.0 if breed is child-friendly, 0.0 if not)
    
    Args:
        user_answer: The user's answer text ("Yes" or "No")
        breed_value: Whether the breed is child-friendly (boolean, string, or int)
    
    Returns:
        Score (0.0 or 1.0)
    """
    user_has_children = user_answer.strip().lower() == 'yes'
    
    # No children in household = always compatible with any pet
    if not user_has_children:
        return 1.0
    
    # Has children = need to check if breed is child-friendly
    if breed_value is None:
        return 1.0  # Assume compatible if no data
    
    # Convert breed value to boolean
    if isinstance(breed_value, bool):
        breed_is_child_friendly = breed_value
    else:
        # Handle string values (True, "True", "Yes", etc.)
        breed_is_child_friendly = str(breed_value).lower() in ['true', 'yes', '1', 4]
    
    return 1.0 if breed_is_child_friendly else 0.0


def score_household_pets(user_answer: str, breed_value: Any) -> float:
    """
    Score household pets compatibility question.
    
    Logic: Check if breed is compatible with pets user has.
    - No pets → Always perfect (1.0)
    - Has pets → Check breed compatibility
    
    Args:
        user_answer: User's pets (comma-separated or single)
        breed_value: Breed object with pet compatibility attributes
    
    Returns:
        Score (0.0-1.0)
    """
    user_answer_str = str(user_answer).strip()
    
    # User has no pets = perfect for any breed
    if user_answer_str == 'None':
        return 1.0
    
    # No breed data = assume compatible
    if breed_value is None:
        return 1.0
    
    # Parse pets
    if ',' in user_answer_str:
        pets = [p.strip() for p in user_answer_str.split(',')]
        pets = [p for p in pets if p != 'None']
    else:
        pets = [user_answer_str] if user_answer_str else []
    
    if not pets:
        return 1.0
    
    # Check breed compatibility with each pet
    for pet in pets:
        compatible = False
        
        if pet == 'Dogs':
            compatible = getattr(breed_value, 'dog_friendly', True)
        elif pet == 'Cats':
            compatible = getattr(breed_value, 'cat_friendly', True)
        elif pet == 'Small Pets':
            compatible = getattr(breed_value, 'small_pet_friendly', True)
        
        if not compatible:
            return 0.0
    
    return 1.0


def score_pet_allergies(user_answer: str) -> float:
    """
    Score pet allergies question (informational, doesn't eliminate).
    
    Args:
        user_answer: "Yes" or "No"
    
    Returns:
        Score (0.5 if allergies, 1.0 if no allergies)
    """
    return 0.5 if user_answer == 'Yes' else 1.0


# ============================================================================
# MAIN QUESTION SCORING FUNCTION
# ============================================================================

def score_question(question_key: str, user_answer: str, breed_value: Any) -> float:
    """
    Score a single question by applying appropriate logic.
    
    Handles special cases and applies standard scoring for normal questions.
    
    Args:
        question_key: The question identifier
        user_answer: User's answer text
        breed_value: Breed's requirement value
    
    Returns:
        Score (0.0-1.0)
    """
    # Normalize answers
    user_score = normalize_answer(question_key, user_answer)
    breed_score = normalize_breed_value(breed_value)
    
    # Handle missing user answer
    if user_score is None:
        return 0.5
    
    # Handle missing breed data - assume perfect match
    if breed_score is None:
        return 1.0
    
    # ========================================================================
    # SPECIAL CASE HANDLERS
    # ========================================================================
    
    # Space and Household Capacity Questions
    if question_key in ['space_needs', 'min_enclosure_size', 'handling_tolerance']:
        return score_space_and_household(question_key, user_score, breed_score)
    
    # Environment Complexity - Special handling (willingness/capability, not capacity)
    if question_key == 'environment_complexity':
        # User willing to set up complex environments >= breed needs = perfect match
        if user_score >= breed_score:
            return 1.0
        # User unwilling = penalty based on gap
        gap = breed_score - user_score
        return calculate_penalty(gap)
    
    # Child Friendly Question (special logic)
    if question_key == 'child_friendly':
        return score_child_friendly(user_answer, breed_value)
    
    # Binary Safety Questions (fragile, special vet)
    if question_key in ['okay_fragile', 'okay_special_vet']:
        return score_binary_safety(user_answer)
    
    # Household Pets
    if question_key == 'other_pets_friendly':
        return score_household_pets(user_answer, breed_value)
    
    # Pet Allergies
    if question_key == 'pet_allergies':
        return score_pet_allergies(user_answer)
    
    # ========================================================================
    # STANDARD SCORING
    # ========================================================================
    
    if user_score >= breed_score:
        return 1.0
    
    gap = breed_score - user_score
    return calculate_penalty(gap)


# ============================================================================
# SCORE CALCULATION - Main logic
# ============================================================================

def calculate_compatibility(answers: Dict, breed) -> Dict[str, Any]:
    """
    Calculate overall compatibility score between user and breed.
    
    Args:
        answers: Dictionary of user answers {question_key: user_answer}
        breed: Breed object with requirements
    
    Returns:
        Dictionary with:
        - overall_score: Final compatibility percentage (0-100)
        - compatibility_level: Rating (Excellent/Good/Moderate/Low/Poor)
        - question_scores: Score breakdown for each question
        - category_scores: Score breakdown for each category
        - strengths: Questions where match is strong (score >= 0.95)
        - mismatches: Questions where match is weak (score < 0.50)
    """
    if not answers or not breed:
        return _error_response()
    
    # Initialize tracking structures
    category_data = {
        'lifestyle': {'scores': [], 'weight_sum': 0},
        'experience': {'scores': [], 'weight_sum': 0},
        'space': {'scores': [], 'weight_sum': 0},
        'care': {'scores': [], 'weight_sum': 0},
        'household': {'scores': [], 'weight_sum': 0},
        'financial': {'scores': [], 'weight_sum': 0},
        'health': {'scores': [], 'weight_sum': 0},
        'safety': {'scores': [], 'weight_sum': 0},
    }
    
    question_scores = []
    mismatches = []
    strengths = []
    
    # Score each question
    for question_key, user_answer in answers.items():
        if user_answer is None:
            continue
        
        # Skip if question not in mapping
        if question_key not in QUESTION_TO_ATTRIBUTE:
            continue
        
        # Get breed requirement
        attr_name, attr_source = QUESTION_TO_ATTRIBUTE[question_key]
        
        if attr_source == 'species':
            breed_value = getattr(breed.species, attr_name, None) if breed.species else None
        else:
            breed_value = getattr(breed, attr_name, None)
        
        # Score the question
        score = score_question(question_key, user_answer, breed_value)
        
        # Get metadata
        category = QUESTION_CATEGORIES.get(question_key, 'lifestyle')
        weight = QUESTION_WEIGHTS.get(question_key, 0.85)
        
        # Store question score
        question_scores.append({
            'question_key': question_key,
            'user_answer': user_answer,
            'breed_requirement': str(breed_value) if breed_value else 'N/A',
            'score': round(score, 2),
            'score_percentage': round(score * 100, 1),
            'category': category,
        })
        
        # Accumulate for category calculation
        category_data[category]['scores'].append(score * weight)
        category_data[category]['weight_sum'] += weight
        
        # Track strengths and mismatches
        if score >= 0.95:
            strengths.append(question_key)
        elif score < 0.50:
            mismatches.append(question_key)
    
    # Calculate category scores
    category_scores = {}
    total_weighted = 0
    total_weight = 0
    
    for category, data in category_data.items():
        if data['weight_sum'] > 0:
            raw_score = sum(data['scores']) / data['weight_sum']
            cat_weight = CATEGORY_WEIGHTS.get(category, 1.0)
            weighted_score = raw_score * cat_weight
            
            category_scores[category] = {
                'score': round(raw_score, 2),
                'percentage': round(raw_score * 100, 1),
            }
            
            total_weighted += weighted_score
            total_weight += cat_weight
    
    # Calculate final overall score
    overall_score = (total_weighted / total_weight * 100) if total_weight > 0 else 0
    overall_score = max(0, min(100, overall_score))
    
    # Determine compatibility level
    if overall_score >= 85:
        level = 'Excellent'
    elif overall_score >= 70:
        level = 'Good'
    elif overall_score >= 55:
        level = 'Moderate'
    elif overall_score >= 40:
        level = 'Low'
    else:
        level = 'Poor'
    
    return {
        'overall_score': round(overall_score, 1),
        'compatibility_level': level,
        'percentage': round(overall_score, 1),
        'question_scores': question_scores,
        'category_scores': category_scores,
        'strengths': strengths,
        'mismatches': mismatches,
        'total_questions_answered': len(question_scores),
    }


# ============================================================================
# SUGGESTIONS - Improvement recommendations
# ============================================================================

def generate_suggestions(answers: Dict, breed) -> List[str]:
    """
    Generate suggestions to improve compatibility score.
    
    Analyzes low-scoring questions and provides actionable recommendations.
    
    Args:
        answers: Dictionary of user answers
        breed: Breed object
    
    Returns:
        List of suggestion strings (max 5)
    """
    suggestions = []
    
    if not answers or not breed:
        return suggestions
    
    # Score all questions to find problem areas
    problem_questions = []
    
    for question_key, user_answer in answers.items():
        if user_answer is None or question_key not in QUESTION_TO_ATTRIBUTE:
            continue
        
        attr_name, attr_source = QUESTION_TO_ATTRIBUTE[question_key]
        breed_value = getattr(breed.species, attr_name, None) if attr_source == 'species' and breed.species else getattr(breed, attr_name, None)
        
        score = score_question(question_key, user_answer, breed_value)
        
        if score < 0.70:
            problem_questions.append((question_key, score, user_answer, breed_value))
    
    # Generate suggestions based on problem areas
    suggestion_map = {
        'energy_level': "This pet may have a different energy level than your routine—adjusting activity or adding enrichment could help balance things out.",

        'pet_allergies': "This pet may trigger sensitivities—exploring hypoallergenic options or managing exposure could help you stay comfortable.",

        'exercise_needs': "This pet thrives with regular activity—finding small ways to add playtime or walks could make a big difference.",
        
        'noise_level': "This pet can be a bit vocal at times—consider how that fits with your living environment and daily routine.",
        
        'social_needs': "This pet benefits from regular interaction—setting aside quality time can help build a strong and healthy bond.",
        
        'handling_tolerance': "This pet may prefer a calmer environment—creating quiet, low-stress spaces can help them feel more secure.",
        
        'daily_care_time': "Caring for this pet may take a bit more time each day, so planning a flexible routine could help you stay consistent.",
        
        'experience_required': "This pet may benefit from more experience—learning through guides, training resources, or expert advice can help you prepare.",
        
        'trainability': "Training may take a little extra patience, but with consistency, it can be a rewarding experience.",
        
        'temperament_tolerance': "This pet has unique personality traits—understanding their behavior and adjusting expectations can improve your experience.",
        
        'space_needs': "A slightly more spacious or enriched environment would help this pet feel more comfortable and relaxed.",
        
        'environment_complexity': "This pet benefits from a stimulating environment—adding toys, structures, or variety can improve their wellbeing.",
        
        'min_enclosure_size': "Providing a larger or more enriched enclosure can greatly improve this pet’s wellbeing.",
        
        'monthly_cost_level': "This pet may come with higher ongoing costs, so a bit of budgeting ahead can help you feel more prepared.",
        
        'emergency_care_risk': "Unexpected vet visits can happen, so having a small emergency fund could give you peace of mind.",
        
        'child_friendly': "This pet may need gentle and supervised interactions around children to feel safe and comfortable.",
        
        'other_pets_friendly': "Introducing this pet to others may take time and careful management to ensure a smooth adjustment.",
        
        'prey_drive': "This pet has natural hunting instincts—providing supervision and safe boundaries can help prevent unwanted situations.",
        
        'okay_fragile': "This pet is more delicate than most, so gentle handling and a calm environment will help keep it safe.",
        
        'okay_special_vet': "This pet may benefit from specialized veterinary care, so checking availability in your area is a good idea.",
    }
    
    for question_key, score, user_answer, breed_value in problem_questions:
        if question_key in suggestion_map:
            suggestions.append(suggestion_map[question_key])
    
    return suggestions


# ============================================================================
# MATCH REASONS - Explain compatibility
# ============================================================================

def generate_match_reasons(answers: Dict, breed) -> Dict[str, List[str]]:
    """
    Generate reasons explaining why user and pet are (or aren't) compatible.
    
    Args:
        answers: Dictionary of user answers
        breed: Breed object
    
    Returns:
        Dictionary with:
        - matched_reasons: Why they ARE compatible
        - mismatch_reasons: Why they AREN'T compatible
    """
    matched_reasons = []
    mismatch_reasons = []
    
    if not answers or not breed:
        return {'matched_reasons': matched_reasons, 'mismatch_reasons': mismatch_reasons}
    
    reason_map = {
        'energy_level': {
            'match': "Great! Your activity level matches well with this pet's energy requirements.",
            'mismatch': "This pet's energy level differs from your lifestyle—consider if you can adapt your routine or find ways to keep the pet stimulated.",
        },
        'pet_allergies': {
            'match': "Excellent! This pet is a great fit for your health considerations.",
            'mismatch': "This pet may not be the best fit for your health needs—consider if there are ways to manage allergies or other concerns.",
        },
        'exercise_needs': {
            'match': "Perfect! You're well-equipped to provide the exercise this pet needs.",
            'mismatch': "This pet thrives with regular activity—finding small ways to add playtime or walks could make a big difference.",
        },
        'noise_level': {
            'match': "Excellent! Your noise tolerance aligns well with this pet's vocalizations.",
            'mismatch': "This pet can be a bit vocal at times—consider how that fits with your living environment and daily routine.",
        },
        'social_needs': {
            'match': "Great match! Your socialization style suits this pet's needs.",
            'mismatch': "This pet has specific social needs—dedicating quality interaction time could strengthen your bond.",
        },
        'handling_tolerance': {
            'match': "Perfect! Your household environment is ideal for this pet's comfort.",
            'mismatch': "This pet may be sensitive to your current household activity level—creating calm spaces could help.",
        },
        'daily_care_time': {
            'match': "Excellent! You have the time to provide proper daily care.",
            'mismatch': "Caring for this pet may take a bit more time each day, so planning a flexible routine could help you stay consistent.",
        },
        'experience_required': {
            'match': "Perfect! Your experience level is ideal for this pet.",
            'mismatch': "This pet may benefit from more specialized knowledge—consider resources or mentorship to support your care.",
        },
        'trainability': {
            'match': "Great! You're well-suited to handle this pet's training needs.",
            'mismatch': "Training may take a little extra patience, but with consistency, it can be a rewarding experience.",
        },
        'temperament_tolerance': {
            'match': "Excellent! You can handle this pet's temperament traits well.",
            'mismatch': "This pet's personality type may require extra understanding—learning about their behavior could help.",
        },
        'space_needs': {
            'match': "Perfect! Your living space is well-suited for this pet.",
            'mismatch': "A slightly more spacious or enriched environment would help this pet feel more comfortable and relaxed.",
        },
        'environment_complexity': {
            'match': "Great! Your home environment matches this pet's complexity needs.",
            'mismatch': "This pet benefits from environmental enrichment—adding variety to their space could improve wellbeing.",
        },
        'min_enclosure_size': {
            'match': "Excellent! You can provide the enclosure size this pet requires.",
            'mismatch': "Providing a larger or more enriched enclosure can greatly improve this pet's wellbeing.",
        },
        'monthly_cost_level': {
            'match': "Perfect! Your budget aligns well with this pet's costs.",
            'mismatch': "This pet may come with higher ongoing costs, so a bit of budgeting ahead can help you feel more prepared.",
        },
        'emergency_care_risk': {
            'match': "Great! You're prepared for potential emergency care needs.",
            'mismatch': "Unexpected vet visits can happen, so having a small emergency fund could give you peace of mind.",
        },
        'child_friendly': {
            'match': "Excellent! This pet fits perfectly with your household situation.",
            'mismatch': "This pet may need gentle and supervised interactions around children to feel safe and comfortable.",
        },
        'other_pets_friendly': {
            'match': "Perfect! This pet should integrate well with your other pets.",
            'mismatch': "Introducing this pet to others may take time and careful management to ensure a smooth adjustment.",
        },
        'prey_drive': {
            'match': "Great! This pet's prey drive aligns well with your household.",
            'mismatch': "This pet has a strong prey drive—extra caution and management will be important for safety.",
        },
        'okay_fragile': {
            'match': "Good! You're comfortable handling delicate species.",
            'mismatch': "This pet is more delicate than most, so gentle handling and a calm environment will help keep it safe.",
        },
        'okay_special_vet': {
            'match': "Excellent! You're prepared for specialized veterinary care.",
            'mismatch': "This pet may benefit from specialized veterinary care, so checking availability in your area is a good idea.",
        },
    }
    
    # Analyze each question
    for question_key, user_answer in answers.items():
        if user_answer is None or question_key not in QUESTION_TO_ATTRIBUTE:
            continue
        
        attr_name, attr_source = QUESTION_TO_ATTRIBUTE[question_key]
        breed_value = getattr(breed.species, attr_name, None) if attr_source == 'species' and breed.species else getattr(breed, attr_name, None)
        
        score = score_question(question_key, user_answer, breed_value)
        
        if question_key in reason_map:
            if score >= 0.85:
                matched_reasons.append(reason_map[question_key]['match'])
            elif score < 0.50:
                mismatch_reasons.append(reason_map[question_key]['mismatch'])
    
    return {
        'matched_reasons': matched_reasons,
        'mismatch_reasons': mismatch_reasons,
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _error_response() -> Dict[str, Any]:
    """Return error response structure"""
    return {
        'overall_score': 0.0,
        'compatibility_level': 'Unknown',
        'percentage': 0.0,
        'question_scores': [],
        'category_scores': {},
        'strengths': [],
        'mismatches': [],
        'total_questions_answered': 0,
        'error': 'Unable to calculate compatibility',
    }


# ============================================================================
# BREED MATCHING - Find top matching breeds
# ============================================================================

def find_top_matches(answers: Dict, limit: int = 5) -> List[Dict]:
    """
    Find the top N most compatible breeds for user answers.
    
    Args:
        answers: Dictionary of user answers
        limit: Number of breeds to return (default 5)
    
    Returns:
        List of breed matches with scores
    """
    if not answers or not isinstance(answers, dict):
        return []
    
    # Get all active breeds
    breeds = Breed.query.filter(
        Breed.is_active == True,
        Breed.deleted_at.is_(None)
    ).all()
    
    if not breeds:
        return []
    
    # Score each breed
    matches = []
    for breed in breeds:
        score_data = calculate_compatibility(answers, breed)
        suggestions = generate_suggestions(answers, breed)
        reasons = generate_match_reasons(answers, breed)
        
        matches.append({
            'breed': {
                'id': breed.id,
                'name': breed.name,
                'summary': breed.summary,
                'image_url': breed.image_url,
                'species_id': breed.species_id,
                'species': {
                    'id': breed.species.id,
                    'name': breed.species.name,
                } if breed.species else {}
            },
            'score': score_data.get('overall_score', 0),
            'level': score_data.get('compatibility_level', 'Unknown'),
            'suggestions': suggestions,
            'matched_reasons': reasons.get('matched_reasons', []),
            'mismatch_reasons': reasons.get('mismatch_reasons', []),
        })
    
    # Sort by score (highest first)
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    return matches[:limit]


# ============================================================================
# BACKWARD COMPATIBILITY WRAPPER CLASS
# ============================================================================

class CompatibilityEngine:
    """
    Backward compatibility wrapper for the modular functions.
    
    All methods delegate to the standalone functions above.
    This allows existing code that uses CompatibilityEngine.method()
    to work without any changes.
    """
    
    @classmethod
    def calculate_match_score(cls, answers: Dict, breed) -> Dict[str, Any]:
        """Wrapper for calculate_compatibility()"""
        return calculate_compatibility(answers, breed)
    
    @classmethod
    def find_top_matches(cls, answers: Dict, limit: int = 5) -> List[Dict]:
        """Wrapper for find_top_matches()"""
        return find_top_matches(answers, limit)
    
    @classmethod
    def get_question_scores(cls, answers: Dict, breed) -> List[Dict]:
        """Get question scores for a specific breed"""
        if not answers or not breed:
            return []
        
        # Calculate compatibility to get question scores
        score_data = calculate_compatibility(answers, breed)
        question_scores = score_data.get('question_scores', [])
        
        # Format for API response
        result = []
        for q_score in question_scores:
            result.append({
                'question_key': q_score.get('question_key'),
                'section': cls._get_question_section(q_score.get('question_key', '')),
                'user_answer': q_score.get('user_answer'),
                'score': q_score.get('score', 0),
                'score_percentage': q_score.get('score_percentage', 0),
                'category': q_score.get('category'),
                'weight': QUESTION_WEIGHTS.get(q_score.get('question_key'), 0.85),
            })
        
        return result
    
    @staticmethod
    def _get_question_section(question_key: str) -> str:
        """Get display section for question"""
        sections = {
            'pet_preference': 'About You',
            'pet_allergies': 'About You',
            'energy_level': 'About You',
            'noise_level': 'About You',
            'social_needs': 'About You',
            'handling_tolerance': 'About You',
            'daily_care_time': 'Time & Care',
            'exercise_needs': 'Time & Care',
            'environment_complexity': 'Time & Care',
            'experience_required': 'Experience',
            'trainability': 'Experience',
            'temperament_tolerance': 'Experience',
            'space_needs': 'Home & Space',
            'min_enclosure_size': 'Home & Space',
            'monthly_cost_level': 'Budget & Costs',
            'emergency_care_risk': 'Budget & Costs',
            'child_friendly': 'Household',
            'other_pets_friendly': 'Household',
            'prey_drive': 'Species & Safety',
            'okay_fragile': 'Species & Safety',
            'okay_special_vet': 'Species & Safety',
        }
        return sections.get(question_key, 'Other')
