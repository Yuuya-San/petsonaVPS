"""
Pet Compatibility Scoring Engine - ENHANCED VERSION

A sophisticated, modular system for calculating pet-owner compatibility.
Evaluates user answers against breed requirements with advanced accuracy.

Architecture:
1. Answer Normalization - Convert user answers to numeric scores (0-4) with case-insensitive matching
2. Breed Value Normalization - Convert breed requirements to numeric scores with multiple format support
3. Question Scoring - Score individual questions with special case handling and edge case management
4. Penalty Calculation - Non-linear penalty curve for accurate gap-based scoring
5. Filtering - STRICT filtering by pet type and size with fallback validation
6. Compatibility Calculation - Weighted category aggregation with importance-based prioritization
7. Suggestions - Generate improvement recommendations based on mismatches
8. Match Reasons - Explain why user and pet are (or aren't) compatible

IMPORTANCE GUIDE (Question Weights by Category):
============================================================================
Very Strong Importance (Weights: 1.40-1.50):
  - Personality / Temperament: trainability, temperament_tolerance
  - Energy / Activity Match: energy_level, exercise_needs
  - Lifestyle Compatibility: noise_level, social_needs, handling_tolerance
  - Safety: prey_drive, okay_fragile (primary safety concerns)

Strong Importance (Weights: 1.20-1.35):
  - Household Environment: child_friendly, other_pets_friendly, space_needs
  - Safety of User: okay_special_vet (secondary safety concerns)

Moderate-Strong Importance (Weights: 1.10-1.15):
  - Time Availability: daily_care_time
  - Pet Allergies / Health: pet_allergies (health concerns)

Moderate Importance (Weights: 0.85-0.95):
  - Experience Level: experience_required
  - Financial Capacity: monthly_cost_level, emergency_care_risk
  - Space/Environment: min_enclosure_size, environment_complexity

Weak-Moderate Importance (Weights: 0.65-0.70):
  - Appearance Preferences: pet_preference, pet_size_preference
  
KEY ENHANCEMENTS IN THIS VERSION:
============================================================================
✓ Non-linear Penalty Curve: Gap 1 = 70% (not 75%), Gap 2 = 40% (not 45%), 
                             Gap 3 = 10% (not 15%) - steeper penalties for larger gaps
✓ Accurate Filtering: STRICT breed matching on pet type AND size, with validation
✓ Enhanced Scoring: Question-specific logic with edge case handling
✓ Better Normalization: Case-insensitive answer matching with fallback validation
✓ Nuanced Safety: Binary safety questions allow "Maybe" option (0.70, not 1.0)
✓ Health Priority: Pet allergies score 0.40 (significant penalty) not 0.50
✓ Category Transparency: Category scores include weight values for clarity
✓ Minimum Threshold: Results filtered to exclude very poor matches (< 40%)
✓ Pet Compatibility: Enhanced pet type detection and compatibility checking
✓ Multi-preference Distribution: Intelligent result distribution across multiple pet types

PENALTY SCORING CURVE:
Gap 0 → 1.0 (100% match)
Gap 1 → 0.70 (70% match - acceptable)
Gap 2 → 0.40 (40% match - significant mismatch)
Gap 3 → 0.10 (10% match - critical mismatch)
Gap 4+ → 0.0 (0% match - complete dealbreaker)

This priority system ensures critical compatibility factors (personality, energy,
household safety) heavily influence the final score, while aesthetic preferences
(pet type, size preference) have minimal impact. This keeps pet welfare as the focus.
"""

from app.models.breed import Breed
from app.models.species import Species
from typing import Dict, List, Any, Optional


# ============================================================================
# PET PREFERENCE TO ICON MAPPING - For filtering recommendations
# ============================================================================
PET_PREFERENCE_TO_ICON = {
    'Dogs': 'fa-solid fa-dog',
    'Cats': 'fa-solid fa-cat',
    'Birds': 'fa-solid fa-dove',
    'Fish': 'fa-solid fa-fish',
    'Reptiles': 'fa-solid fa-dragon',
    'Amphibians': 'fa-solid fa-frog',
    'Small Mammals': 'fa-solid fa-otter',
    'Small Animals': 'fa-solid fa-otter',
}


# ============================================================================
# PET SIZE PREFERENCE TO BREED SIZE CATEGORY MAPPING - For filtering by size
# ============================================================================
# Maps quiz answer options to breed.size_category enum values
PET_SIZE_PREFERENCE_TO_CATEGORY = {
    'Toy / Extra Small': 'Toy / Extra Small',
    'Small': 'Small',
    'Medium': 'Medium',
    'Large': 'Large',
    'Giant': 'Giant',
}



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
    
    # Pet Preference
    'pet_preference': {
        'Dogs': 'Dogs',
        'Cats': 'Cats',
        'Birds': 'Birds',
        'Fish': 'Fish',
        'Reptiles': 'Reptiles',
        'Amphibians': 'Amphibians',
        'Small Animals': 'Small Animals',
        'Small Mammals': 'Small Mammals',
    },
    
    # Pet Size Preference (maps to breed.size_category)
    'pet_size_preference': {
        'Toy / Extra Small': 'Toy / Extra Small',
        'Small': 'Small',
        'Medium': 'Medium',
        'Large': 'Large',
        'Giant': 'Giant',
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

# Question Weights (importance of each question, based on compatibility guide)
# See top comment for importance guide
QUESTION_WEIGHTS = {
    # Very Strong Importance (Personality / Temperament & Energy Match)
    'trainability': 1.50,                    # Personality/Temperament - Very Strong
    'temperament_tolerance': 1.50,           # Personality/Temperament - Very Strong
    'energy_level': 1.45,                    # Energy/Activity Match + Lifestyle - Very Strong
    'exercise_needs': 1.45,                  # Energy/Activity Match + Lifestyle - Very Strong
    
    # Strong Importance (Lifestyle & Household Environment & Safety)
    'noise_level': 1.35,                     # Lifestyle - Strong
    'social_needs': 1.35,                    # Lifestyle - Strong
    'handling_tolerance': 1.35,              # Personality/Lifestyle + Household - Strong
    'child_friendly': 1.30,                  # Household Environment - Strong
    'other_pets_friendly': 1.30,             # Household Environment - Strong
    'space_needs': 1.25,                     # Household + Space - Strong
    'prey_drive': 1.40,                      # Safety of User - Strong/Moderate-Strong
    'okay_fragile': 1.40,                    # Safety of User - Strong/Moderate-Strong
    'okay_special_vet': 1.35,                # Safety of User - Moderate-Strong
    
    # Moderate-Strong Importance (Time & Health)
    'pet_allergies': 1.25,                   # Health - Moderate-Strong
    'daily_care_time': 1.10,                 # Time Availability - Moderate-Strong
    
    # Moderate Importance (Experience & Financial)
    'experience_required': 0.90,              # Experience Level - Moderate
    'monthly_cost_level': 0.85,              # Financial Capacity - Moderate
    'emergency_care_risk': 0.85,             # Financial Capacity - Moderate
    'environment_complexity': 0.90,          # Space/Environment - Moderate
    'min_enclosure_size': 0.85,              # Space/Environment - Moderate
    
    # Weak-Moderate Importance (Appearance Preferences)
    'pet_preference': 0.65,                  # Appearance Preferences - Weak-Moderate
    'pet_size_preference': 0.65,             # Appearance Preferences - Weak-Moderate
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
    'pet_preference': 'lifestyle',  # Appearance preferences in lifestyle category
    'pet_size_preference': 'lifestyle',  # Appearance preferences in lifestyle category
}


# ============================================================================
# NORMALIZATION FUNCTIONS
# ============================================================================

def normalize_answer(question_key: str, answer: str) -> Optional[int]:
    """
    Convert user answer to numeric score (0-4) with validation.
    
    Enhanced features:
    - Case-insensitive matching
    - Whitespace trimming
    - Returns None for unmapped answers (safe fallback)
    
    Args:
        question_key: The question identifier
        answer: The user's answer text
    
    Returns:
        Numeric score (0-4) or None if answer not found or invalid
    """
    if not answer or not isinstance(answer, str):
        return None
    
    if question_key not in ANSWER_MAPPINGS:
        return None
    
    # Normalize the answer for matching
    mapping = ANSWER_MAPPINGS[question_key]
    answer_normalized = str(answer).strip()
    
    # Try exact match first
    if answer_normalized in mapping:
        return mapping[answer_normalized]
    
    # Try case-insensitive match as fallback
    for key, value in mapping.items():
        if key.lower() == answer_normalized.lower():
            return value
    
    # No match found
    return None


def normalize_breed_value(breed_value: Any) -> Optional[int]:
    """
    Convert breed requirement to numeric score (1-4) with enhanced handling.
    
    Supports:
    - Boolean values (True=4, False=1)
    - String levels (Low/Medium/High/Very High)
    - Numeric values (1-4 range)
    - Case-insensitive matching
    
    Args:
        breed_value: The breed's requirement value (boolean, string, int, etc.)
    
    Returns:
        Numeric score (1-4) or None if no valid value found
    """
    if breed_value is None:
        return None
    
    # Handle booleans
    if isinstance(breed_value, bool):
        return 4 if breed_value else 1
    
    # Handle numeric values directly
    if isinstance(breed_value, int):
        if 1 <= breed_value <= 4:
            return breed_value
    
    # Handle string values (Low/Medium/High/Very High)
    value_str = str(breed_value).strip().lower()
    
    # Map common string representations
    mapping = {
        'low': 1,
        'medium': 2,
        'high': 3,
        'very high': 4,
        'very_high': 4,
        'true': 4,
        'false': 1,
        'yes': 4,
        'no': 1,
    }
    
    return mapping.get(value_str)


# ============================================================================
# PENALTY FUNCTIONS
# ============================================================================

def calculate_penalty(gap: int) -> float:
    """
    Calculate penalty score based on gap between user and breed requirement.
    
    Uses non-linear scoring curve for better accuracy:
    - Gap 0: 1.0 (perfect match - 100%)
    - Gap 1: 0.70 (acceptable gap - 70%)
    - Gap 2: 0.40 (significant gap - 40%)
    - Gap 3+: 0.10 (critical gap - 10%)
    
    Non-linear curve emphasizes importance of small gaps while penalizing large ones.
    
    Args:
        gap: Difference between breed requirement and user capability (non-negative)
    
    Returns:
        Penalty score (0.0-1.0)
    """
    if gap < 0:
        return 1.0  # User exceeds requirement (perfect match)
    
    # Non-linear penalty curve: steeper for larger gaps
    if gap == 0:
        return 1.0
    elif gap == 1:
        return 0.70  # 30% penalty for small gap
    elif gap == 2:
        return 0.40  # 60% penalty for medium gap
    elif gap == 3:
        return 0.10  # 90% penalty for large gap
    else:
        return 0.0  # Complete mismatch for gap >= 4


# ============================================================================
# SPECIAL CASE SCORING FUNCTIONS
# ============================================================================

def score_space_and_household(question_key: str, user_score: int, breed_score: int) -> float:
    """
    Score space and household capacity questions with threshold logic.
    
    Logic: Having MORE capacity is always better. Uses graduated scoring:
    - If user's capacity >= pet's requirement: Perfect match (1.0)
    - If user's capacity meets minimum threshold (requirement - 1): Good match (0.70)
    - If user's capacity is below threshold: Apply graduated penalty
    
    Args:
        question_key: The question identifier
        user_score: User's numeric score (1-4)
        breed_score: Breed's numeric requirement (1-4)
    
    Returns:
        Score (0.0-1.0)
    """
    # Perfect match: user has >= capacity than required
    if user_score >= breed_score:
        return 1.0
    
    # Calculate gap
    gap = breed_score - user_score
    
    # Use penalty curve for graduated scoring
    return calculate_penalty(gap)


def score_binary_safety(user_answer: str) -> float:
    """
    Score binary safety questions (okay_fragile, okay_special_vet) with nuance.
    
    Logic: User must accept the risk/requirement with graduated scoring:
    - Definite acceptance ('Yes, I am', 'Yes, I can'): Perfect match (1.0)
    - Uncertain but open ('Maybe, I am not sure'): Good match (0.70)
    - Rejection ('No, I am not', 'No', 'No, I cannot'): Deal breaker (0.0)
    
    This allows for uncertainty rather than binary on/off scoring.
    
    Args:
        user_answer: The user's answer text
    
    Returns:
        Score (0.0, 0.70, or 1.0)
    """
    user_answer = str(user_answer).strip().lower()
    
    # Definite acceptance
    if user_answer in ['yes', 'yes, i am', 'yes, i can']:
        return 1.0
    
    # Uncertain but open to it
    if user_answer in ['maybe', 'maybe, i am not sure', 'maybe, i am not sure']:
        return 0.70  # Allows for flexibility while penalizing uncertainty
    
    # Rejection
    if user_answer in ['no', 'no, i am not', 'no, i cannot']:
        return 0.0
    
    # Unknown answer - treat as uncertain
    return 0.5


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
    Score household pets compatibility with enhanced logic.
    
    Logic: Check if breed is compatible with pets user currently has
    - No pets → Always perfect (1.0)
    - Has pets → Check breed compatibility with each pet type
    - Missing compatibility data → Assume compatible (1.0)
    - Pet incompatible → Significant penalty (0.0)
    
    Args:
        user_answer: User's pets (comma-separated or single value, "None" for no pets)
        breed_value: Breed object with pet compatibility attributes
    
    Returns:
        Score (0.0-1.0)
    """
    user_answer_str = str(user_answer).strip()
    
    # User has no pets - always compatible
    if user_answer_str.lower() == 'none':
        return 1.0
    
    # No breed data to check - assume compatible
    if breed_value is None:
        return 1.0
    
    # Parse user's current pets (handle both comma-separated and single values)
    if ',' in user_answer_str:
        pets = [p.strip() for p in user_answer_str.split(',')]
        pets = [p for p in pets if p.lower() != 'none']
    else:
        pets = [user_answer_str] if user_answer_str else []
    
    # No pets listed
    if not pets or len(pets) == 0:
        return 1.0
    
    # Check breed compatibility with each pet type
    for pet in pets:
        pet_lower = pet.lower().strip()
        compatible = True
        
        # Check breed attributes for specific pet types
        if 'dog' in pet_lower:
            # Check dog_friendly attribute if it exists
            compatible = getattr(breed_value, 'dog_friendly', True)
        elif 'cat' in pet_lower:
            # Check cat_friendly attribute if it exists
            compatible = getattr(breed_value, 'cat_friendly', True)
        elif 'bird' in pet_lower or 'small' in pet_lower:
            # Check small pet/bird compatibility
            compatible = getattr(breed_value, 'small_pet_friendly', True)
        elif 'rodent' in pet_lower or 'hamster' in pet_lower or 'mouse' in pet_lower:
            # Check rodent compatibility
            compatible = getattr(breed_value, 'small_pet_friendly', True)
        
        # If any pet is incompatible, return failure
        if not compatible:
            return 0.0
    
    # All pets are compatible
    return 1.0


def score_pet_allergies(user_answer: str) -> float:
    """
    Score pet allergies question with health prioritization.
    
    Logic: Pet allergies are health-related and more serious than other preferences
    - No allergies: Perfect match (1.0)
    - Has allergies: Caution flag (0.40) - not a deal breaker but requires management
    
    This allows users with allergies to find pets they can still live with,
    but prioritizes allergy-free options.
    
    Args:
        user_answer: "Yes" or "No"
    
    Returns:
        Score (0.40 if allergies, 1.0 if no allergies)
    """
    user_answer_norm = str(user_answer).strip().lower()
    
    # User has allergies - significant score reduction
    if user_answer_norm == 'yes':
        return 0.40  # 60% penalty but not a complete dealbreaker
    
    # No allergies - perfect match
    if user_answer_norm == 'no':
        return 1.0
    
    # Unknown/unclear
    return 0.5


# ============================================================================
# MAIN QUESTION SCORING FUNCTION
# ============================================================================

def score_question(question_key: str, user_answer: str, breed_value: Any) -> float:
    """
    Score a single question by applying appropriate logic.
    
    Enhanced scoring with:
    - Question-specific handling for edge cases
    - Special case handlers for critical questions
    - Standard scoring with gap analysis for others
    - Better handling of missing data
    
    Args:
        question_key: The question identifier
        user_answer: User's answer text
        breed_value: Breed's requirement value
    
    Returns:
        Score (0.0-1.0)
    """
    # Skip pet preference/size preference questions - they're filtered, not scored
    if question_key in ['pet_preference', 'pet_size_preference']:
        return 1.0  # Auto-pass if breed made it through filtering
    
    # Normalize answers
    user_score = normalize_answer(question_key, user_answer)
    breed_score = normalize_breed_value(breed_value)
    
    # Handle missing user answer
    if user_score is None:
        return 0.5  # Penalize missing answers
    
    # Handle missing breed data - assume perfect match
    if breed_score is None:
        return 1.0
    
    # ========================================================================
    # SPECIAL CASE HANDLERS
    # ========================================================================

    # Space capacity questions - more capacity is always better
    if question_key in ['space_needs', 'min_enclosure_size', 'handling_tolerance']:
        return score_space_and_household(question_key, user_score, breed_score)
    
    # Environment Complexity - willingness/capability, not capacity
    if question_key == 'environment_complexity':
        # User willing to set up complex environments >= breed needs = perfect match
        if user_score >= breed_score:
            return 1.0
        # User unwilling = penalty based on gap
        gap = breed_score - user_score
        return calculate_penalty(gap)
    
    # Child Friendly Question (special logic - household composition matters)
    if question_key == 'child_friendly':
        return score_child_friendly(user_answer, breed_value)
    
    # Binary Safety Questions (fragile, special vet) - nuanced scoring
    if question_key in ['okay_fragile', 'okay_special_vet']:
        return score_binary_safety(user_answer)
    
    # Household Pets - compatibility check
    if question_key == 'other_pets_friendly':
        return score_household_pets(user_answer, breed_value)
    
    # Pet Allergies - informational, doesn't eliminate
    if question_key == 'pet_allergies':
        return score_pet_allergies(user_answer)
    
    # ========================================================================
    # STANDARD SCORING WITH GRADUATED PENALTIES
    # ========================================================================
    
    # Perfect match: user meets or exceeds requirement
    if user_score >= breed_score:
        return 1.0
    
    # Mismatch: use gap-based penalty
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
    
    # Calculate category scores with enhanced weighting
    category_scores = {}
    total_weighted = 0
    total_weight = 0
    
    for category, data in category_data.items():
        if data['weight_sum'] > 0:
            # Raw score is weighted average for this category
            raw_score = sum(data['scores']) / data['weight_sum']
            
            # Apply category weight (importance of this category type)
            cat_weight = CATEGORY_WEIGHTS.get(category, 1.0)
            weighted_score = raw_score * cat_weight
            
            category_scores[category] = {
                'score': round(raw_score, 2),
                'percentage': round(raw_score * 100, 1),
                'weight': round(cat_weight, 2),  # Add weight for transparency
            }
            
            total_weighted += weighted_score
            total_weight += cat_weight
    
    # Calculate final overall score with better scaling
    if total_weight > 0:
        # Scale to 0-100 range
        overall_score = (total_weighted / total_weight * 100)
    else:
        overall_score = 0
    
    # Clamp to valid range
    overall_score = max(0, min(100, overall_score))
    
    # Determine compatibility level with refined thresholds
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

def generate_suggestions(answers: Dict, breed) -> List[Dict[str, str]]:
    """
    Generate actionable suggestions to address compatibility concerns.
    
    Provides specific, actionable steps to address each mismatch and improve
    compatibility between user and pet. Suggestions are prioritized by concern
    severity and provide concrete actions the user can take.
    
    Args:
        answers: Dictionary of user answers
        breed: Breed object
    
    Returns:
        List of suggestion dictionaries with:
        - question_key: Question being addressed
        - concern_area: What needs to be addressed
        - suggestion: Specific actionable recommendation
        - priority: High/Medium/Low based on impact
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
            suggestion_detail = {
                'question_key': question_key,
                'concern_area': 'Compatibility Issue',
                'suggestion': suggestion_map[question_key],
                'priority': 'Medium',
                'score': round(score, 2),
            }
            suggestions.append(suggestion_detail)
    
    # Sort by concern severity
    priority_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
    suggestions.sort(key=lambda x: (priority_order.get(x.get('priority', 'Medium'), 4), -x['score']))
    
    return suggestions


# ============================================================================
# CONCERNS - Explain specific compatibility concerns
# ============================================================================

def generate_concerns(answers: Dict, breed) -> List[Dict[str, str]]:
    """
    Generate specific concerns about compatibility based on question mismatches.
    
    Organizes concerns by severity and provides:
    - The specific concern
    - Why it's a concern for this pet and owner
    - Severity level (Critical, Important, Moderate)
    
    Args:
        answers: Dictionary of user answers
        breed: Breed object
    
    Returns:
        List of concern dictionaries with:
        - question_key: The question that has a concern
        - concern: The specific concern
        - reason: Why this is a concern
        - severity: Critical/Important/Moderate
    """
    concerns = []
    
    if not answers or not breed:
        return concerns
    
    concern_map = {
        'prey_drive': {
            'concern': 'Strong Prey Drive Safety Risk',
            'reason': 'This pet has a strong natural hunting instinct that could pose a safety risk to small animals or fast-moving objects in your home.',
            'severity': 'Critical',
        },
        'okay_fragile': {
            'concern': 'Delicate Species Handling',
            'reason': 'This pet is physically delicate and requires gentle handling. Without proper care and technique, the pet could be easily injured.',
            'severity': 'Critical',
        },
        'okay_special_vet': {
            'concern': 'Specialized Veterinary Care Required',
            'reason': 'This pet needs specialized veterinary care that may not be available in all areas or may require higher expertise and costs.',
            'severity': 'Important',
        },
        'child_friendly': {
            'concern': 'Child Safety and Pet Welfare',
            'reason': 'This pet may not be suitable for households with children, risking harm to the pet or creating stress for the animal.',
            'severity': 'Critical',
        },
        'other_pets_friendly': {
            'concern': 'Compatibility with Existing Pets',
            'reason': 'This pet may not be compatible with the pets you currently have, potentially leading to stress, injuries, or behavioral issues.',
            'severity': 'Important',
        },
        'energy_level': {
            'concern': 'Activity Level Mismatch',
            'reason': 'Your activity level differs significantly from what this pet needs. Under-stimulation can lead to behavioral problems and reduced wellbeing.',
            'severity': 'Important',
        },
        'exercise_needs': {
            'concern': 'Insufficient Exercise Capability',
            'reason': 'This pet requires regular exercise that you may not be able to provide, which can lead to obesity, frustration, and behavioral issues.',
            'severity': 'Important',
        },
        'pet_allergies': {
            'concern': 'Pet Allergy Health Risk',
            'reason': 'You have pet allergies, which could affect your health and comfort living with this pet long-term.',
            'severity': 'Moderate',
        },
        'noise_level': {
            'concern': 'Noise Tolerance Mismatch',
            'reason': 'This pet can be vocal or noisy, which may conflict with your need for a quiet environment.',
            'severity': 'Moderate',
        },
        'handling_tolerance': {
            'concern': 'Stressful Environment Sensitivity',
            'reason': 'This pet is sensitive to noise and activity. Your busy or loud household may cause chronic stress to the animal.',
            'severity': 'Important',
        },
        'space_needs': {
            'concern': 'Insufficient Living Space',
            'reason': 'Your living space is smaller than what this pet ideally needs, which could impact their physical health and comfort.',
            'severity': 'Important',
        },
        'min_enclosure_size': {
            'concern': 'Inadequate Enclosure Size',
            'reason': 'This pet requires a larger enclosure than you can provide, which could limit their movement and natural behaviors.',
            'severity': 'Important',
        },
        'environment_complexity': {
            'concern': 'Limited Environmental Enrichment',
            'reason': 'This pet needs a complex, enriched environment. A simple setup may lead to boredom, stress, and behavioral problems.',
            'severity': 'Moderate',
        },
        'daily_care_time': {
            'concern': 'Insufficient Daily Care Time',
            'reason': 'This pet requires more daily care time than you can dedicate, which could affect their health and your ability to maintain consistent care.',
            'severity': 'Important',
        },
        'experience_required': {
            'concern': 'Lack of Required Experience',
            'reason': 'This pet requires more experience than you have, which could lead to mistakes in care, training, or handling.',
            'severity': 'Moderate',
        },
        'trainability': {
            'concern': 'Training Patience Requirements',
            'reason': 'This pet requires more patience during training than you may have available, which could lead to frustration on both sides.',
            'severity': 'Moderate',
        },
        'temperament_tolerance': {
            'concern': 'Personality Type Compatibility',
            'reason': 'This pet has a personality type you may not be equipped to handle, which could lead to behavioral or management challenges.',
            'severity': 'Moderate',
        },
        'monthly_cost_level': {
            'concern': 'Budget-to-Cost Mismatch',
            'reason': 'This pet has higher ongoing costs than your budget allows, which could cause financial stress over time.',
            'severity': 'Moderate',
        },
        'emergency_care_risk': {
            'concern': 'Limited Emergency Care Preparedness',
            'reason': 'Unexpected veterinary emergencies can be costly. Your budget limitations might prevent you from providing emergency care if needed.',
            'severity': 'Moderate',
        },
        'social_needs': {
            'concern': 'Socialization Needs Mismatch',
            'reason': 'This pet has social needs that dont match your available interaction time, which could lead to loneliness or behavioral issues.',
            'severity': 'Moderate',
        },
    }
    
    # Analyze each question for concerns
    for question_key, user_answer in answers.items():
        if user_answer is None or question_key not in QUESTION_TO_ATTRIBUTE:
            continue
        
        # Skip preference questions - no concerns
        if question_key in ['pet_preference', 'pet_size_preference']:
            continue
        
        attr_name, attr_source = QUESTION_TO_ATTRIBUTE[question_key]
        breed_value = getattr(breed.species, attr_name, None) if attr_source == 'species' and breed.species else getattr(breed, attr_name, None)
        
        score = score_question(question_key, user_answer, breed_value)
        
        # Only add concerns for mismatches (score < 0.50)
        if score < 0.50 and question_key in concern_map:
            concerns.append({
                'question_key': question_key,
                'concern': concern_map[question_key]['concern'],
                'reason': concern_map[question_key]['reason'],
                'severity': concern_map[question_key]['severity'],
                'score': round(score, 2),
                'score_percentage': round(score * 100, 1),
            })
    
    # Sort by severity (Critical > Important > Moderate)
    severity_order = {'Critical': 0, 'Important': 1, 'Moderate': 2}
    concerns.sort(key=lambda x: (severity_order.get(x['severity'], 3), -x['score']))
    
    return concerns


# ============================================================================
# MATCH REASONS - Explain compatibility by category
# ============================================================================

def generate_match_reasons(answers: Dict, breed) -> Dict[str, Any]:
    """
    Generate detailed match reasons organized by category.
    
    Organizes matches and mismatches by category (Lifestyle, Safety, Household, etc.)
    providing category-level summary and question-by-question details.
    
    Args:
        answers: Dictionary of user answers
        breed: Breed object
    
    Returns:
        Dictionary with:
        - by_category: Matches organized by category with reasons
        - strengths: Top compatibility areas (score >= 0.95)
        - areas_of_concern: Weak compatibility areas (score < 0.50)
    """
    by_category = {}
    strengths = []
    areas_of_concern = []
    
    if not answers or not breed:
        return {
            'by_category': by_category,
            'strengths': strengths,
            'areas_of_concern': areas_of_concern,
        }
    
    reason_map = {
        'energy_level': {
            'match': "Your relaxed home routine is perfect for this pet's moderate energy needs.",
            'mismatch': "This pet needs an active lifestyle that differs from your routine.",
        },
        'pet_allergies': {
            'match': "Great news! You don't have allergies, so this pet is a good fit for your health.",
            'mismatch': "Your pet allergies may make living with this pet challenging long-term.",
        },
        'exercise_needs': {
            'match': "Perfect! Your available time for exercise matches what this pet needs.",
            'mismatch': "This pet requires regular exercise that you may struggle to provide.",
        },
        'noise_level': {
            'match': "Excellent! Your noise tolerance is well-matched to this pet's vocal tendencies.",
            'mismatch': "This pet can be noisy, which may conflict with your quiet living preference.",
        },
        'social_needs': {
            'match': "Great match! Your interaction style suits this pet's social requirements.",
            'mismatch': "This pet's social needs may require more interaction than you can provide.",
        },
        'handling_tolerance': {
            'match': "Perfect! Your calm household is ideal for this pet's comfort.",
            'mismatch': "This pet's sensitivity to activity doesn't match your household environment.",
        },
        'daily_care_time': {
            'match': "Excellent! You have sufficient time for this pet's daily care routine.",
            'mismatch': "This pet requires more daily care time than you currently have available.",
        },
        'experience_required': {
            'match': "Perfect! Your experience level is ideal for caring for this pet.",
            'mismatch': "This pet would benefit from more experience than you currently have.",
        },
        'trainability': {
            'match': "Great! You have the patience needed for this pet's training.",
            'mismatch': "Training this pet requires more patience than you indicated you have.",
        },
        'temperament_tolerance': {
            'match': "Excellent! You can handle this pet's personality traits well.",
            'mismatch': "This pet's personality requires understanding and skills you may need to develop.",
        },
        'space_needs': {
            'match': "Perfect! Your living space meets this pet's requirements.",
            'mismatch': "Your living space is smaller than what this pet ideally needs.",
        },
        'environment_complexity': {
            'match': "Great! Your home can provide the environmental complexity this pet enjoys.",
            'mismatch': "This pet thrives with complex environments that you're not set up for.",
        },
        'min_enclosure_size': {
            'match': "Excellent! You can provide an appropriately sized enclosure.",
            'mismatch': "This pet needs a larger enclosure than you can accommodate.",
        },
        'monthly_cost_level': {
            'match': "Perfect! Your budget accommodates this pet's ongoing costs.",
            'mismatch': "This pet's monthly costs exceed your current budget.",
        },
        'emergency_care_risk': {
            'match': "Great! You're financially prepared for unexpected veterinary needs.",
            'mismatch': "You may face financial strain if unexpected veterinary care is needed.",
        },
        'child_friendly': {
            'match': "Excellent! This pet is suitable for your household composition.",
            'mismatch': "This pet's temperament may not be suitable for your household with children.",
        },
        'other_pets_friendly': {
            'match': "Perfect! This pet should integrate well with your other pets.",
            'mismatch': "This pet may not be compatible with the pets you already have.",
        },
        'prey_drive': {
            'match': "Great! This pet's prey drive is manageable in your household.",
            'mismatch': "This pet's strong prey drive poses potential safety risks in your home.",
        },
        'okay_fragile': {
            'match': "Good! You're comfortable with the care needs of delicate species.",
            'mismatch': "This delicate pet requires careful handling you may not be equipped for.",
        },
        'okay_special_vet': {
            'match': "Excellent! You're prepared for this pet's specialized veterinary needs.",
            'mismatch': "This pet requires specialized veterinary care you may not have access to.",
        },
    }
    
    # Initialize categories
    categories = [
        'lifestyle', 'safety', 'experience', 'household', 'space', 'care', 'financial', 'health'
    ]
    for cat in categories:
        by_category[cat] = {
            'category_name': cat.capitalize(),
            'questions': [],
            'overall_match': True,
            'summary': '',
        }
    
    # Analyze each question
    for question_key, user_answer in answers.items():
        if user_answer is None or question_key not in QUESTION_TO_ATTRIBUTE:
            continue
        
        # Skip preference questions
        if question_key in ['pet_preference', 'pet_size_preference']:
            continue
        
        attr_name, attr_source = QUESTION_TO_ATTRIBUTE[question_key]
        breed_value = getattr(breed.species, attr_name, None) if attr_source == 'species' and breed.species else getattr(breed, attr_name, None)
        
        score = score_question(question_key, user_answer, breed_value)
        category = QUESTION_CATEGORIES.get(question_key, 'lifestyle')
        
        # Determine if match or mismatch
        is_match = score >= 0.85
        reason = reason_map.get(question_key, {})
        reason_text = reason.get('match') if is_match else reason.get('mismatch')
        
        if reason_text:
            question_detail = {
                'question_key': question_key,
                'is_match': is_match,
                'score': round(score, 2),
                'score_percentage': round(score * 100, 1),
                'reason': reason_text,
            }
            by_category[category]['questions'].append(question_detail)
            
            # Track overall category match
            if not is_match and score < 0.85:
                by_category[category]['overall_match'] = False
            
            # Track strengths and areas of concern
            if score >= 0.95:
                strengths.append({
                    'question_key': question_key,
                    'category': category,
                    'reason': reason_text,
                })
            elif score < 0.50:
                areas_of_concern.append({
                    'question_key': question_key,
                    'category': category,
                    'reason': reason_text,
                    'score': round(score, 2),
                })
    
    # Generate category summaries
    category_summaries = {
        'lifestyle': 'How well your daily habits match the pet\'s needs',
        'safety': 'Potential safety concerns and risk factors',
        'experience': 'Your expertise level for this pet type',
        'household': 'Compatibility with your family and existing pets',
        'space': 'Whether you have adequate space and environment setup',
        'care': 'Your available time for daily care',
        'financial': 'Your budget alignment with pet costs',
        'health': 'Health-related compatibility factors',
    }
    
    for cat in categories:
        if by_category[cat]['questions']:
            by_category[cat]['summary'] = category_summaries.get(cat, '')
    
    return {
        'by_category': by_category,
        'strengths': strengths,
        'areas_of_concern': areas_of_concern,
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
    
    Enhanced Filtering Logic:
    - Pet Preference (pet_preference): STRICT - only breeds with matching species icon
    - Pet Size Preference (pet_size_preference): STRICT - only breeds with matching size categories
    - If no filters specified, scores all active breeds
    - Scoring emphasizes personality, energy, household safety over appearance
    
    Multi-preference Logic:
    - If user selected 2+ pet preferences, distribute results intelligently
    - More than 5 preferences: Top 5 overall by score
    - Exactly 2 preferences: Top 2 per preference + 1 from 3rd highest across all
    - 3-5 preferences: Distribute slots evenly + fill with 3rd highest
    
    Scoring includes:
    - Weighted category scores (safety, experience, household weighted highest)
    - Question-specific importance (personality/energy heavily weighted)
    - Penalty curve for gaps (steeper for larger mismatches)
    
    Args:
        answers: Dictionary of user answers {question_key: answer_value}
        limit: Number of breeds to return (default 5)
    
    Returns:
        List of breed matches sorted by compatibility score (highest first)
    """
    if not answers or not isinstance(answers, dict):
        return []
    
    # Extract and validate pet preference from answers
    pet_preference_str = answers.get('pet_preference', '').strip()
    preferences = []
    preferred_icons = {}
    
    if pet_preference_str:
        # Parse comma-separated preferences and validate against known mappings
        preferences = [p.strip() for p in pet_preference_str.split(',') if p.strip()]
        for pref in preferences:
            pref_normalized = pref.strip()
            icon = PET_PREFERENCE_TO_ICON.get(pref_normalized)
            if icon:
                preferred_icons[icon] = pref_normalized
    
    # Extract and validate pet size preference from answers
    pet_size_preference_str = answers.get('pet_size_preference', '').strip()
    size_preferences = []
    
    if pet_size_preference_str:
        # Parse comma-separated size preferences and map to breed categories
        sizes = [s.strip() for s in pet_size_preference_str.split(',') if s.strip()]
        for size in sizes:
            size_normalized = size.strip()
            # First try exact match
            if size_normalized in PET_SIZE_PREFERENCE_TO_CATEGORY:
                size_preferences.append(PET_SIZE_PREFERENCE_TO_CATEGORY[size_normalized])
            else:
                # Try partial match (handle with/without weight ranges)
                for key, val in PET_SIZE_PREFERENCE_TO_CATEGORY.items():
                    if size_normalized.lower() in key.lower() or key.lower() in size_normalized.lower():
                        if val not in size_preferences:
                            size_preferences.append(val)
                        break
    
    # Get all active breeds
    breeds = Breed.query.filter(
        Breed.is_active == True,
        Breed.deleted_at.is_(None)
    ).all()
    
    if not breeds:
        return []
    
    # If multiple pet preferences (2+), use intelligent distribution
    if len(preferences) >= 2:
        return _find_top_matches_multipreference(answers, breeds, preferred_icons, limit, preferences, size_preferences)
    
    # Single or no preference: use standard filtering
    matches = []
    
    for breed in breeds:
        # STRICT FILTER: if user specified pet_preference, breed MUST match
        if preferred_icons:
            if not breed.species:
                continue  # Skip breeds without species
            
            species_icon = (breed.species.icon or '').strip()
            if not species_icon or species_icon not in preferred_icons:
                continue  # Skip non-matching species
        
        # STRICT FILTER: if user specified pet_size_preference, breed MUST match
        if size_preferences:
            breed_size = (breed.size_category or '').strip()
            if not breed_size or breed_size not in size_preferences:
                continue  # Skip non-matching sizes
        
        # Calculate compatibility for this breed
        score_data = calculate_compatibility(answers, breed)
        suggestions = generate_suggestions(answers, breed)
        reasons = generate_match_reasons(answers, breed)
        
        # Only include if score meets minimum threshold (40+)
        # This filters out very poor matches
        if score_data.get('overall_score', 0) >= 40:
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
    
    # Return top N results
    return matches[:limit]


def _find_top_matches_multipreference(answers: Dict, all_breeds: List, preferred_icons: Dict, limit: int, preferences: List, size_preferences: List = None) -> List[Dict]:
    """
    Find top matches when user has 2+ pet preferences.
    
    Enhanced Features:
    - Validates pet preference and size filtering
    - Applies both filters when specified
    - Uses improved scoring with penalty curve
    - Filters results by minimum threshold (40+ score)
    - Intelligent result distribution across preferences
    
    Distribution logic:
    - More than 5 preferences: Top 5 overall by score (winner takes all)
    - Exactly 2 preferences: Top 2 per preference + 1 from 3rd highest
    - 3-5 preferences: Distribute slots evenly + fill with 3rd highest
    
    Args:
        answers: User answers dict
        all_breeds: All breed objects to score
        preferred_icons: Dict mapping icons to pet type names
        limit: Number of results to return (default 5)
        preferences: List of selected pet preference names
        size_preferences: List of selected size category values (optional)
    
    Returns:
        List of breed matches sorted by compatibility score (highest first)
    """
    if size_preferences is None:
        size_preferences = []
    
    # Group and validate breeds by their species icon
    breeds_by_icon = {}
    
    for breed in all_breeds:
        # Validate breed has required data
        if not breed.species or not breed.species.icon:
            continue
        
        species_icon = (breed.species.icon or '').strip()
        
        # Apply pet preference filter
        if species_icon not in preferred_icons:
            continue
        
        # Apply size preference filter if specified
        if size_preferences:
            breed_size = (breed.size_category or '').strip()
            if not breed_size or breed_size not in size_preferences:
                continue
        
        # Group breed by icon
        if species_icon not in breeds_by_icon:
            breeds_by_icon[species_icon] = []
        breeds_by_icon[species_icon].append(breed)
    
    # Score all breeds and group by icon
    scored_breeds_by_icon = {}
    
    for icon, breeds_list in breeds_by_icon.items():
        scored_breeds_by_icon[icon] = []
        
        for breed in breeds_list:
            score_data = calculate_compatibility(answers, breed)
            
            # Filter out very poor matches (below 40% threshold)
            if score_data.get('overall_score', 0) < 40:
                continue
            
            suggestions = generate_suggestions(answers, breed)
            reasons = generate_match_reasons(answers, breed)
            
            breed_result = {
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
                'icon': icon,
            }
            scored_breeds_by_icon[icon].append(breed_result)
        
        # Sort by score (highest first) for this icon group
        scored_breeds_by_icon[icon].sort(key=lambda x: x['score'], reverse=True)
    
    # Distribution logic based on number of preferences
    matches = []
    num_prefs = len(preferences)
    
    if num_prefs > 5:
        # More than 5 preferences: Top 5 overall by score (winner takes all)
        all_scored = []
        for icon_list in scored_breeds_by_icon.values():
            all_scored.extend(icon_list)
        all_scored.sort(key=lambda x: x['score'], reverse=True)
        matches = all_scored[:limit]
    
    elif num_prefs == 2:
        # 2 preferences: 2 per preference + 1 from 3rd highest
        for icon in list(preferred_icons.keys())[:2]:
            breeds_for_icon = scored_breeds_by_icon.get(icon, [])
            # Take top 2 from each preference
            matches.extend(breeds_for_icon[:2])
        
        # Fill 5th slot with 3rd highest from each preference
        if len(matches) < limit:
            third_place_candidates = []
            for icon in preferred_icons.keys():
                breeds_for_icon = scored_breeds_by_icon.get(icon, [])
                if len(breeds_for_icon) > 2:
                    third_place_candidates.append(breeds_for_icon[2])
            
            # Sort third place candidates by score and add top one
            third_place_candidates.sort(key=lambda x: x['score'], reverse=True)
            if third_place_candidates:
                matches.append(third_place_candidates[0])
    
    else:
        # 3-5 preferences: Distribute slots evenly, then fill with 3rd highest
        breeds_per_pref = limit // num_prefs
        remainder = limit % num_prefs
        
        # First pass: distribute main slots
        for i, icon in enumerate(list(preferred_icons.keys())[:num_prefs]):
            breeds_for_icon = scored_breeds_by_icon.get(icon, [])
            # Determine how many to take from this preference
            num_to_take = breeds_per_pref + (1 if i < remainder else 0)
            matches.extend(breeds_for_icon[:num_to_take])
        
        # Second pass: fill remaining slots with 3rd highest from each preference
        if len(matches) < limit:
            third_place_candidates = []
            for icon in preferred_icons.keys():
                breeds_for_icon = scored_breeds_by_icon.get(icon, [])
                if len(breeds_for_icon) > breeds_per_pref:
                    # Collect 3rd highest and beyond from each preference
                    for j in range(breeds_per_pref, len(breeds_for_icon)):
                        third_place_candidates.append(breeds_for_icon[j])
            
            # Sort by score and fill remaining slots
            third_place_candidates.sort(key=lambda x: x['score'], reverse=True)
            for candidate in third_place_candidates:
                if len(matches) < limit:
                    matches.append(candidate)
                else:
                    break
    
    # Final sort by score to ensure top performers are shown
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    return matches[:limit]
    
    # Score all breeds and group by icon
    scored_breeds_by_icon = {}
    for icon, breeds_list in breeds_by_icon.items():
        scored_breeds_by_icon[icon] = []
        for breed in breeds_list:
            score_data = calculate_compatibility(answers, breed)
            suggestions = generate_suggestions(answers, breed)
            reasons = generate_match_reasons(answers, breed)
            
            breed_result = {
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
                'icon': icon,
            }
            scored_breeds_by_icon[icon].append(breed_result)
        
        # Sort by score (highest first)
        scored_breeds_by_icon[icon].sort(key=lambda x: x['score'], reverse=True)
    
    # Distribution logic based on number of preferences
    matches = []
    num_prefs = len(preferences)
    
    if num_prefs > 5:
        # More than 5 preferences: Top 5 overall by score (winner takes all)
        all_scored = []
        for icon_list in scored_breeds_by_icon.values():
            all_scored.extend(icon_list)
        all_scored.sort(key=lambda x: x['score'], reverse=True)
        matches = all_scored[:limit]
    
    elif num_prefs == 2:
        # 2 preferences: 2 per preference + 1 from 3rd highest
        for icon in list(preferred_icons.keys())[:2]:
            breeds_for_icon = scored_breeds_by_icon.get(icon, [])
            # Take top 2 from each preference
            matches.extend(breeds_for_icon[:2])
        
        # Fill 5th slot with 3rd highest from each preference
        if len(matches) < limit:
            third_place_candidates = []
            for icon in preferred_icons.keys():
                breeds_for_icon = scored_breeds_by_icon.get(icon, [])
                if len(breeds_for_icon) > 2:
                    third_place_candidates.append(breeds_for_icon[2])
            
            # Sort third place candidates by score and add top one
            third_place_candidates.sort(key=lambda x: x['score'], reverse=True)
            if third_place_candidates:
                matches.append(third_place_candidates[0])
    
    else:
        # 3-5 preferences: Distribute slots evenly, then fill with 3rd highest
        breeds_per_pref = limit // num_prefs
        remainder = limit % num_prefs
        
        # First pass: distribute main slots
        for i, icon in enumerate(list(preferred_icons.keys())[:num_prefs]):
            breeds_for_icon = scored_breeds_by_icon.get(icon, [])
            # Determine how many to take from this preference
            num_to_take = breeds_per_pref + (1 if i < remainder else 0)
            matches.extend(breeds_for_icon[:num_to_take])
        
        # Second pass: fill remaining slots with 3rd highest from each preference
        if len(matches) < limit:
            third_place_candidates = []
            for icon in preferred_icons.keys():
                breeds_for_icon = scored_breeds_by_icon.get(icon, [])
                if len(breeds_for_icon) > breeds_per_pref:
                    # Collect 3rd highest and beyond from each preference
                    for j in range(breeds_per_pref, len(breeds_for_icon)):
                        third_place_candidates.append(breeds_for_icon[j])
            
            # Sort by score and fill remaining slots
            third_place_candidates.sort(key=lambda x: x['score'], reverse=True)
            for candidate in third_place_candidates:
                if len(matches) < limit:
                    matches.append(candidate)
                else:
                    break
    
    # Final sort by score to ensure top performers are shown
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
