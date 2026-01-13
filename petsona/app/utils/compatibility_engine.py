from app.models.breed import Breed
from app.models.species import Species
import re
from typing import Dict, List, Any, Optional, Tuple


class CompatibilityEngine:
    """
    Professional Pet Compatibility Matching Engine with Veterinary-Grade Scoring
    
    Evaluates compatibility across 8 key dimensions using a 1-4 numerical scale:
    - Lifestyle & Activity: Energy levels, exercise, noise tolerance
    - Experience & Training: Required expertise, trainability, temperament match
    - Space & Environment: Housing needs, enclosure complexity
    - Care & Grooming: Time commitment, grooming requirements
    - Household Compatibility: Safety with children, dogs, cats, small pets
    - Financial Reality: Monthly costs, emergency care, lifetime expenses
    - Health & Wellness: Preventive care, stress sensitivity, health issues, lifespan
    - Species-Specific Safety: Prey drive, fragility, permits, veterinary needs
    
    Scoring Philosophy:
    - Score >= Breed Requirement: Full/high points (excellent match)
    - Score < Breed Requirement: Graduated penalty (potential mismatch)
    - Binary safety items: Pass/fail with no middle ground
    - All mappings based on actual quiz.html answer choices
    
    Professional tone emphasizes veterinary best practices and animal welfare.
    """
    
    # Question-to-Breed Attribute Mapping
    ATTRIBUTE_MAPPING = {
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
        'grooming_needs': ('grooming_needs', 'breed'),
        'child_friendly': ('child_friendly', 'breed'),
        'dog_friendly': ('dog_friendly', 'breed'),
        'cat_friendly': ('cat_friendly', 'breed'),
        'small_pet_friendly': ('small_pet_friendly', 'breed'),
        'monthly_cost_level': ('monthly_cost_level', 'breed'),
        'emergency_care_risk': ('emergency_care_risk', 'breed'),
        'lifetime_cost_level': ('lifetime_cost_level', 'breed'),
        'care_cost': ('care_cost', 'breed'),
        'preventive_care_level': ('preventive_care_level', 'breed'),
        'stress_sensitivity': ('stress_sensitivity', 'breed'),
        'common_health_issues': ('common_health_issues', 'breed'),
        'lifespan': ('lifespan', 'breed'),
        'prey_drive': ('prey_drive', 'breed'),
        'okay_fragile': ('fragile_species', 'species'),
        'okay_permit': ('requires_permit', 'species'),
        'okay_special_vet': ('special_vet_required', 'species'),
    }
    
    # Quiz Answer Choices (from quiz.html) -> 1-4 Scale Mappings
    QUIZ_ANSWER_MAPPINGS = {
        'energy_level': {
            'I mostly relax at home': 1,
            'I move around sometimes': 2,
            'I am very active and always busy': 4,
        },
        'noise_level': {
            'I need it very quiet': 1,
            'Some noise is okay': 3,
            'Noise does not bother me': 4,
        },
        'social_needs': {
            'Just a little': 1,
            'A fair amount': 2,
            'A lot, I like bonding': 4,
        },
        'handling_tolerance': {
            'Very calm and quiet': 1,
            'Normal': 2,
            'Busy, noisy, and active': 4,
        },
        'daily_care_time': {
            'Less than 1 hour': 1,
            '1-2 hours': 2,
            '2-4 hours': 3,
            'More than 4 hours': 4,
        },
        'grooming_needs': {
            'Rarely': 1,
            'About once a week': 2,
            'Very often': 4,
        },
        'exercise_needs': {
            'No': 1,
            'Sometimes': 2,
            'Yes, every day': 4,
        },
        'environment_complexity': {
            'No, I prefer simple pets': 1,
            'I can manage a little': 2,
            'Yes, I\'m okay with it': 4,
        },
        'experience_required': {
            'This is my first pet': 1,
            'I have had a few': 2,
            'I have a lot of experience': 4,
        },
        'trainability': {
            'Not very patient': 1,
            'Somewhat patient': 2,
            'Very patient': 4,
        },
        'temperament_tolerance': {
            'Not well': 1,
            'I can try': 2,
            'I handle them well': 4,
        },
        'space_needs': {
            'Small apartment or room': 1,
            'Medium-sized home': 2,
            'Large home or house with space': 4,
        },
        'min_enclosure_size': {
            'No': 1,
            'Small ones only': 2,
            'Large ones are okay': 4,
        },
        'monthly_cost_level': {
            'Low budget': 1,
            'Medium budget': 2,
            'High budget': 4,
        },
        'emergency_care_risk': {
            'No': 1,
            'Maybe': 2,
            'Yes': 4,
        },
        'lifetime_cost_level': {
            'Not really': 1,
            'Somewhat': 2,
            'Yes, I\'m prepared': 4,
        },
        'child_friendly': {
            'No': 0,
            'Yes': 1,
        },
        'dog_friendly': {
            'No': 0,
            'Yes': 1,
        },
        'cat_friendly': {
            'No': 0,
            'Yes': 1,
        },
        'small_pet_friendly': {
            'No': 0,
            'Yes': 1,
        },
        'prey_drive': {
            'No': 1,
            'Maybe': 2,
            'Yes': 4,
        },
        'okay_fragile': {
            'No': 0,
            'Yes': 1,
        },
        'okay_permit': {
            'No': 0,
            'Yes': 1,
        },
        'okay_special_vet': {
            'No': 0,
            'Yes': 1,
        },
    }
    
    # Category Weights (emphasis on critical factors)
    CATEGORY_WEIGHTS = {
        'lifestyle': 1.15,      # Core activity alignment
        'experience': 1.40,     # Critical for pet welfare
        'space': 1.15,          # Essential for health
        'care': 1.10,           # Daily commitment
        'household': 1.25,      # Safety critical
        'financial': 1.10,      # Sustainability important
        'health': 1.20,         # Long-term wellness
        'safety': 1.30,         # Most critical (permits, vet care, prey drive)
    }
    
    # Question-Level Weights (relative importance within categories)
    QUESTION_WEIGHTS = {
        'energy_level': 0.95,
        'exercise_needs': 0.95,
        'noise_level': 0.80,
        'social_needs': 0.85,
        'handling_tolerance': 0.85,
        'experience_required': 1.00,
        'trainability': 0.95,
        'temperament_tolerance': 0.95,
        'space_needs': 0.90,
        'environment_complexity': 0.85,
        'min_enclosure_size': 0.85,
        'daily_care_time': 0.95,
        'grooming_needs': 0.95,
        'child_friendly': 0.98,        # Safety
        'dog_friendly': 0.95,
        'cat_friendly': 0.95,
        'small_pet_friendly': 0.95,
        'monthly_cost_level': 0.85,
        'emergency_care_risk': 0.95,
        'lifetime_cost_level': 0.85,
        'care_cost': 0.80,
        'preventive_care_level': 0.95,
        'stress_sensitivity': 0.90,
        'common_health_issues': 0.85,
        'lifespan': 0.90,
        'prey_drive': 0.98,            # Safety critical
        'okay_fragile': 0.98,          # Safety critical
        'okay_permit': 0.95,           # Legal requirement
        'okay_special_vet': 0.95,      # Health access critical
    }
    
    # Breed Value Mappings (convert breed DB values to 1-4 scale)
    BREED_VALUE_MAPPINGS = {
        'Low': 1,
        'Medium': 2,
        'High': 3,
        'Very High': 4,
        'low': 1,
        'medium': 2,
        'high': 3,
        'very high': 4,
    }
    
    # =====================================================================
    # UNIFIED MAPPING SYSTEM
    # =====================================================================
    
    @classmethod
    def normalize_answer_value(cls, question_key: str, answer: Any) -> Optional[int]:
        """
        Normalize a user answer to 1-4 scale using quiz.html answer choices.
        
        Returns:
            int: 1-4 scale value, or None if answer is invalid
        """
        if answer is None:
            return None
        
        # Convert answer to string and trim
        answer_str = str(answer).strip()
        
        # Look up in quiz answer mappings
        if question_key in cls.QUIZ_ANSWER_MAPPINGS:
            return cls.QUIZ_ANSWER_MAPPINGS[question_key].get(answer_str)
        
        # Fallback: return None (invalid answer)
        return None
    
    @classmethod
    def normalize_breed_value(cls, breed_value: Any) -> Optional[int]:
        """
        Normalize a breed value to 1-4 scale.
        Handles various input formats: strings, integers, booleans.
        
        Returns:
            int: 1-4 scale value, or None if normalization fails
        """
        if breed_value is None:
            return None
        
        # Handle boolean values
        if isinstance(breed_value, bool):
            return 4 if breed_value else 1
        
        # Convert to string and normalize
        value_str = str(breed_value).strip()
        
        # Try direct mapping (Low/Medium/High/Very High)
        if value_str in cls.BREED_VALUE_MAPPINGS:
            return cls.BREED_VALUE_MAPPINGS[value_str]
        
        # Case-insensitive attempt
        value_lower = value_str.lower()
        for key, val in cls.BREED_VALUE_MAPPINGS.items():
            if key.lower() == value_lower:
                return val
        
        # No valid mapping found
        return None
    
    @staticmethod
    def calculate_penalty_score(user_level: int, requirement: int, scoring_type: str = 'capability') -> float:
        """
        Calculate a normalized score (0.0-1.0) based on gap between user capability and breed requirement.
        
        Scoring Types:
        - 'capability': User must meet/exceed requirement (e.g., exercise ability, experience)
        - 'tolerance': User tolerance must be >= breed requirement (e.g., noise tolerance, calm home)
        
        Args:
            user_level: User's capability/tolerance level (1-4 scale)
            requirement: Breed's requirement level (1-4 scale)
            scoring_type: Type of scoring logic to apply
        
        Returns:
            float: Score from 0.0 (poor match) to 1.0 (excellent match)
        """
        if user_level is None or requirement is None:
            return 0.5  # Neutral score
        
        # Perfect match or user exceeds requirement
        if user_level >= requirement:
            return 1.0
        
        # Calculate gap
        gap = requirement - user_level
        
        # Apply graduated penalties based on gap size
        if scoring_type == 'capability':
            # Higher penalties for capability mismatches (safety/welfare critical)
            penalties = {
                1: 0.75,  # Gap of 1: 75% compatible
                2: 0.45,  # Gap of 2: 45% compatible
                3: 0.15,  # Gap of 3: 15% compatible
            }
        else:  # tolerance
            # Slightly higher tolerance penalties for tolerance mismatches
            penalties = {
                1: 0.75,
                2: 0.50,
                3: 0.20,
            }
        
        return max(0.0, penalties.get(gap, 0.0))
    
    @staticmethod
    def _get_category_for_question(question_key: str) -> str:
        """Map question to category dimension"""
        categories = {
            'lifestyle': ['energy_level', 'exercise_needs', 'noise_level', 'social_needs', 'handling_tolerance'],
            'experience': ['experience_required', 'trainability', 'temperament_tolerance'],
            'space': ['space_needs', 'environment_complexity', 'min_enclosure_size'],
            'care': ['daily_care_time', 'grooming_needs'],
            'household': ['child_friendly', 'dog_friendly', 'cat_friendly', 'small_pet_friendly'],
            'financial': ['monthly_cost_level', 'emergency_care_risk', 'lifetime_cost_level', 'care_cost'],
            'health': ['preventive_care_level', 'stress_sensitivity', 'common_health_issues', 'lifespan'],
            'safety': ['prey_drive', 'okay_fragile', 'okay_permit', 'okay_special_vet'],
        }
        for category, questions in categories.items():
            if question_key in questions:
                return category
        return 'lifestyle'
    
    @staticmethod
    def _get_compatibility_level(score: float) -> str:
        """Convert score to professional compatibility level"""
        if score >= 85:
            return 'Excellent'
        elif score >= 70:
            return 'Good'
        elif score >= 55:
            return 'Moderate'
        elif score >= 40:
            return 'Low'
        else:
            return 'Poor'
    
    @classmethod
    def calculate_match_score(cls, answers: Dict, breed) -> Dict[str, Any]:
        """Calculate comprehensive compatibility score"""
        category_scores = {
            'lifestyle': {'total': 0, 'weight_sum': 0},
            'experience': {'total': 0, 'weight_sum': 0},
            'space': {'total': 0, 'weight_sum': 0},
            'care': {'total': 0, 'weight_sum': 0},
            'household': {'total': 0, 'weight_sum': 0},
            'financial': {'total': 0, 'weight_sum': 0},
            'health': {'total': 0, 'weight_sum': 0},
            'safety': {'total': 0, 'weight_sum': 0},
        }
        
        individual_scores = []
        mismatches = []
        strengths = []
        
        for question_key, (attr_name, attr_source) in cls.ATTRIBUTE_MAPPING.items():
            user_answer = answers.get(question_key)
            if user_answer is None:
                continue
            
            category = cls._get_category_for_question(question_key)
            q_weight = cls.QUESTION_WEIGHTS.get(question_key, 0.85)
            
            if attr_source == 'species':
                breed_value = getattr(breed.species, attr_name, None) if breed.species else None
            else:
                breed_value = getattr(breed, attr_name, None)
            
            score = cls._calculate_question_score(question_key, user_answer, breed_value, breed)
            
            # Get normalized values for improvement logic
            user_normalized = cls.normalize_answer_value(question_key, user_answer)
            breed_normalized = cls.normalize_breed_value(breed_value)
            
            if score >= 0.95:
                strength = cls._generate_strength_description(question_key, user_answer, breed)
                if strength:
                    strengths.append(strength)
            elif score < 0.50:
                mismatch = cls._generate_mismatch_description(question_key, user_answer, breed_value, breed)
                if mismatch:
                    mismatches.append(mismatch)
            
            category_scores[category]['total'] += score * q_weight
            category_scores[category]['weight_sum'] += q_weight
            
            individual_scores.append({
                'question': question_key,
                'category': category,
                'user_answer': user_answer,
                'breed_value': breed_value,
                'score': round(score, 2),
                'weight': q_weight,
                'user_normalized': user_normalized,
                'breed_normalized': breed_normalized,
            })
        
        total_weighted = 0
        total_weight = 0
        category_results = {}
        
        for category, data in category_scores.items():
            if data['weight_sum'] > 0:
                normalized = data['total'] / data['weight_sum']
                cat_weight = cls.CATEGORY_WEIGHTS.get(category, 1.0)
                weighted = normalized * cat_weight
                
                category_results[category] = {
                    'raw_score': round(normalized, 3),
                    'weighted_score': round(weighted, 3),
                }
                
                total_weighted += weighted
                total_weight += cat_weight
        
        final_score = (total_weighted / total_weight * 100) if total_weight > 0 else 0
        final_score = max(0, min(100, final_score))
        
        # Generate improvement suggestions with priorities
        improvements = cls._generate_improvement_suggestions(answers, breed, individual_scores, final_score)
        
        return {
            'score': round(final_score, 1),
            'compatibility_level': cls._get_compatibility_level(final_score),
            'category_scores': category_results,
            'individual_scores': individual_scores,
            'mismatches': mismatches[:5],
            'strengths': strengths[:5],
            'mismatch_areas': mismatches[:5],
            'strength_areas': strengths[:5],
            'suggestions': mismatches[:3],
            'improvement_suggestions': improvements,
            'total_questions_answered': len(individual_scores),
        }
    
    @classmethod
    def _calculate_question_score(cls, question_key: str, user_answer: Any, breed_value: Any, breed) -> float:
        """
        Calculate normalized score (0.0-1.0) for a single compatibility question.
        
        Handles all question types with proper normalization, fallbacks, and edge cases.
        
        Args:
            question_key: The quiz question identifier
            user_answer: The user's answer (from quiz)
            breed_value: The breed's requirement value (from database)
            breed: The breed object for context
        
        Returns:
            float: Score from 0.0 (poor match) to 1.0 (excellent match)
        """
        
        # Normalize user answer
        user_normalized = cls.normalize_answer_value(question_key, user_answer)
        if user_normalized is None:
            return 0.5  # Neutral fallback
        
        # Normalize breed value
        breed_normalized = cls.normalize_breed_value(breed_value)
        
        # =====================================================================
        # BINARY SAFETY QUESTIONS (pass/fail)
        # =====================================================================
        
        if question_key == 'okay_fragile':
            """User must be okay with fragile species if breed is fragile"""
            user_okay = user_answer == 'Yes'
            breed_fragile = breed.species.fragile_species if breed.species else False
            if breed_fragile and not user_okay:
                return 0.0  # Deal breaker
            return 1.0  # Match
        
        if question_key == 'okay_permit':
            """User must be okay with permits if breed requires them"""
            user_okay = user_answer == 'Yes'
            breed_permit = breed.species.requires_permit if breed.species else False
            if breed_permit and not user_okay:
                return 0.0  # Deal breaker
            return 1.0  # Match
        
        if question_key == 'okay_special_vet':
            """User should be able to access special vet if breed needs it"""
            user_okay = user_answer == 'Yes'
            breed_vet = breed.species.special_vet_required if breed.species else False
            if breed_vet and not user_okay:
                return 0.5  # Significant concern but not automatic fail
            return 1.0  # Match
        
        # =====================================================================
        # HOUSEHOLD BINARY QUESTIONS (presence of children/pets)
        # =====================================================================
        
        if question_key in ['child_friendly', 'dog_friendly', 'cat_friendly', 'small_pet_friendly']:
            """
            Score household compatibility based on presence vs. breed friendliness.
            If user HAS children/pets, breed MUST be compatible.
            If user DOESN'T have them, no penalty.
            """
            user_has = user_answer == 'Yes'
            breed_attr_map = {
                'child_friendly': 'child_friendly',
                'dog_friendly': 'dog_friendly',
                'cat_friendly': 'cat_friendly',
                'small_pet_friendly': 'small_pet_friendly',
            }
            breed_compatible = getattr(breed, breed_attr_map[question_key], True)
            
            if user_has and not breed_compatible:
                return 0.0  # Deal breaker - user has child/pet but breed not compatible
            return 1.0  # Safe match
        
        # =====================================================================
        # PREY DRIVE SPECIAL CASE
        # =====================================================================
        
        if question_key == 'prey_drive':
            """User must be okay with prey drive if breed has it"""
            # user_normalized: No=1, Maybe=2, Yes=4
            # breed_value: Low/Medium/High (from breed table)
            user_okay = user_normalized >= 2  # User is okay with 'Maybe' or 'Yes'
            
            if breed_value and breed_value.lower() in ['high', 'very high']:
                if not user_okay:
                    return 0.2  # Very unlikely match
            elif breed_value and breed_value.lower() in ['medium']:
                if user_normalized == 1:  # User said "No"
                    return 0.5  # Moderate concern
            
            return cls.calculate_penalty_score(user_normalized, 2, 'capability')
        
        # =====================================================================
        # STANDARD CAPABILITY QUESTIONS
        # (User ability must meet breed requirement)
        # =====================================================================
        
        capability_questions = [
            'energy_level', 'exercise_needs', 'daily_care_time', 'grooming_needs',
            'experience_required', 'space_needs', 'environment_complexity',
            'min_enclosure_size', 'monthly_cost_level', 'emergency_care_risk',
            'lifetime_cost_level', 'care_cost', 'preventive_care_level'
        ]
        
        if question_key in capability_questions:
            if breed_normalized is None:
                return 0.5  # Can't determine breed requirement
            return cls.calculate_penalty_score(user_normalized, breed_normalized, 'capability')
        
        # =====================================================================
        # TOLERANCE QUESTIONS
        # (User tolerance must meet breed production/requirement)
        # =====================================================================
        
        tolerance_questions = [
            'noise_level', 'handling_tolerance', 'social_needs', 'stress_sensitivity'
        ]
        
        if question_key in tolerance_questions:
            if breed_normalized is None:
                return 0.5  # Can't determine breed requirement
            return cls.calculate_penalty_score(user_normalized, breed_normalized, 'tolerance')
        
        # =====================================================================
        # TRAINING/TEMPERAMENT PATIENCE QUESTIONS
        # =====================================================================
        
        if question_key == 'trainability':
            """User patience must match breed training difficulty"""
            # trainability maps user patience to 1-4 scale
            if breed_normalized is None:
                return 0.5
            return cls.calculate_penalty_score(user_normalized, breed_normalized, 'capability')
        
        if question_key == 'temperament_tolerance':
            """User ability to handle temperament issues"""
            if breed_normalized is None:
                return 0.5
            return cls.calculate_penalty_score(user_normalized, breed_normalized, 'capability')
        
        # =====================================================================
        # LIFESPAN MATCHING
        # =====================================================================
        
        if question_key == 'lifespan':
            """User lifetime commitment vs. breed lifespan"""
            try:
                # Extract numeric values
                if isinstance(user_answer, str):
                    user_years = int(re.search(r'\d+', user_answer).group()) if re.search(r'\d+', user_answer) else 10
                else:
                    user_years = int(user_answer) if user_answer else 10
                
                if isinstance(breed_value, str):
                    match = re.search(r'(\d+)', breed_value)
                    breed_years = int(match.group(1)) if match else 10
                else:
                    breed_years = int(breed_value) if breed_value else 10
                
                # Score based on lifespan match
                if user_years >= breed_years:
                    return 1.0
                elif user_years >= breed_years - 2:
                    return 0.8
                else:
                    return max(0.3, user_years / breed_years)
            except (ValueError, TypeError):
                return 0.5  # Neutral fallback
        
        # =====================================================================
        # HEALTH ISSUES
        # =====================================================================
        
        if question_key == 'common_health_issues':
            """User readiness for breed health challenges"""
            if not breed_value or str(breed_value).lower() in ['none', 'minimal']:
                return 1.0  # No health issues
            
            user_aware = user_answer in ['Yes', 'Ready', 'Prepared', 'High', 'Yes']
            return 0.85 if user_aware else 0.55
        
        # =====================================================================
        # DEFAULT FALLBACK
        # =====================================================================
        
        return 0.5
    
    @staticmethod
    def _generate_strength_description(question_key: str, user_answer: str, breed) -> Optional[str]:
        """
        Generate professional strength descriptions highlighting excellent compatibility.
        
        Returns detailed, veterinary-tone messages that reinforce positive matches.
        """
        strengths_map = {
            'energy_level': f"Excellent activity alignment: Your lifestyle perfectly matches {breed.name}'s energy requirements for optimal physical and mental health",
            'exercise_needs': f"Strong exercise commitment: You can provide the daily physical activity {breed.name} requires to maintain muscle tone and cardiovascular wellness",
            'daily_care_time': f"Well-aligned time availability: Your daily schedule accommodates all of {breed.name}'s essential care needs",
            'grooming_needs': f"Ideal grooming dedication: Your grooming commitment ensures {breed.name} maintains optimal coat health and skin condition",
            'space_needs': f"Optimal living environment: Your home provides adequate space for {breed.name} to exhibit natural behaviors and maintain physical well-being",
            'experience_required': f"Perfect experience match: Your background provides the expertise necessary for {breed.name}'s successful care and behavioral development",
            'monthly_cost_level': f"Sustainable financial alignment: Your budget adequately supports {breed.name}'s monthly care and nutrition requirements",
            'noise_level': f"Excellent noise tolerance: Your home environment suits {breed.name}'s natural vocalization patterns",
            'social_needs': f"Strong social compatibility: You can provide the regular interaction and companionship {breed.name} requires for psychological well-being",
            'child_friendly': f"Family-safe compatibility: {breed.name}'s gentle temperament makes it an excellent match for your household with children",
            'dog_friendly': f"Multi-dog compatibility: {breed.name}'s sociable nature allows for positive coexistence with your dog(s)",
            'cat_friendly': f"Cat-compatible household: {breed.name} has demonstrated ability to safely coexist with cats",
            'small_pet_friendly': f"Small pet safe: {breed.name}'s prey drive is minimal, enabling safe interaction with smaller household animals",
            'preventive_care_level': f"Health-conscious approach: Your commitment to preventive veterinary care supports {breed.name}'s long-term health and wellness",
            'stress_sensitivity': f"Stable household environment: Your calm, stable home is ideal for {breed.name}'s psychological well-being and stress management",
            'lifespan': f"Lifetime commitment ready: You're prepared to provide {breed.name} with a permanent, stable home throughout its entire lifespan",
            'trainability': f"Patient training approach: Your patience and training commitment matches {breed.name}'s learning style and behavioral development needs",
            'temperament_tolerance': f"Behavioral flexibility: You're well-equipped to manage {breed.name}'s personality traits and behavioral tendencies",
            'space_needs': f"Adequate living space: Your home environment meets {breed.name}'s spatial requirements for natural behavior expression",
            'environment_complexity': f"Capable of specialized care: You can manage {breed.name}'s specific habitat or environmental setup requirements",
            'emergency_care_risk': f"Emergency preparedness: You're financially prepared for unexpected veterinary emergencies",
            'lifetime_cost_level': f"Long-term financial commitment: You understand and are prepared for {breed.name}'s lifetime care costs",
            'okay_fragile': f"Gentle handling capability: You can provide the careful, gentle handling this delicate breed requires",
            'okay_permit': f"Legal compliance ready: You're prepared to obtain and manage any required permits for this species",
            'okay_special_vet': f"Specialized veterinary access: You can access exotic or specialist veterinarians this breed may require",
            'prey_drive': f"Prey drive compatibility: You're comfortable with {breed.name}'s natural hunting instincts and predatory behaviors",
        }
        return strengths_map.get(question_key)
    
    @staticmethod
    def _generate_mismatch_description(question_key: str, user_answer: str, breed_value: Any, breed) -> Optional[str]:
        """
        Generate professional mismatch descriptions highlighting compatibility concerns.
        
        Returns detailed, clinically-toned messages with specific veterinary guidance.
        """
        mismatches_map = {
            'energy_level': f"Activity mismatch: {breed.name} has higher energy requirements than your {user_answer.lower()} activity level can sustain, potentially leading to behavioral issues or obesity",
            'exercise_needs': f"Exercise deficit: {breed.name} requires {breed_value} daily exercise, but your '{user_answer}' schedule may lead to unmet activity needs",
            'noise_level': f"Noise environment concern: {breed.name}'s {breed_value} vocalizations may conflict with your need for a quiet living space",
            'grooming_needs': f"Grooming commitment gap: {breed.name} requires {breed_value} grooming while you prefer {user_answer.lower()}, potentially resulting in coat/skin health issues",
            'space_needs': f"Space limitation: {breed.name} needs {breed_value} space; your {user_answer.lower()} environment may restrict natural behaviors and wellness",
            'experience_required': f"Experience concern: {breed.name} is recommended for {breed_value} owners; your {user_answer.lower()} experience may present challenges in care or training",
            'daily_care_time': f"Time commitment gap: {breed.name} needs {breed_value} daily care, but you have {user_answer} available, risking inadequate care",
            'monthly_cost_level': f"Budget concern: {breed.name}'s {breed_value} monthly costs may exceed your {user_answer.lower()} budget, causing financial strain",
            'preventive_care_level': f"Veterinary care gap: {breed.name} requires {breed_value} preventive care, but your {user_answer.lower()} commitment may leave health issues undetected",
            'stress_sensitivity': f"Household stability concern: {breed.name} is sensitive to environmental stress; your {user_answer.lower()} home may cause behavioral or health problems",
            'lifespan': f"Lifetime commitment concern: {breed.name} lives {breed_value}; ensure you can provide consistent care for this duration",
            'emergency_care_risk': f"Emergency preparedness gap: {breed.name} may require urgent veterinary care; your '{user_answer}' financial readiness may be insufficient",
            'trainability': f"Training patience mismatch: {breed.name} requires {breed_value} training input, but your '{user_answer}' patience level may prove inadequate",
            'temperament_tolerance': f"Behavioral complexity: {breed.name} may present behavioral challenges that exceed your '{user_answer}' ability to manage",
            'environment_complexity': f"Setup capability gap: {breed.name} needs {breed_value} environmental setup, but your '{user_answer}' willingness to accommodate this may be limiting",
            'okay_fragile': f"Handling concern: This breed is delicate and fragile; careful, gentle handling is essential for health and safety",
            'okay_permit': f"Legal requirement: This species requires special permits in many jurisdictions; ensure you can obtain and maintain compliance",
            'okay_special_vet': f"Specialized veterinary care: This breed may require exotic animal specialists; verify you can access appropriate veterinary care",
            'prey_drive': f"Prey drive concern: {breed.name} has {breed_value} prey drive; your '{user_answer}' acceptance of hunting behaviors may be mismatched",
            'child_friendly': f"Child safety concern: {breed.name} may not be suitable for households with children; temperament and size present safety considerations",
            'dog_friendly': f"Multi-dog compatibility issue: {breed.name} may have difficulty coexisting with other dogs in your household",
            'cat_friendly': f"Cat compatibility concern: {breed.name} may not be safe to house with cats due to prey drive or predatory instinct",
            'small_pet_friendly': f"Small pet safety: {breed.name} may pose a risk to smaller animals; prey drive and predatory instinct are safety considerations",
            'common_health_issues': f"Health complexity: {breed.name} is prone to specific health issues requiring attentive monitoring and management",
        }
        return mismatches_map.get(question_key)
    
    @classmethod
    def _generate_improvement_suggestions(cls, answers: Dict, breed, individual_scores: List, final_score: float) -> List[Dict]:
        """
        Generate structured improvement suggestions with priority levels.
        ONLY flag areas where user capability is LESS than required.
        If user meets or exceeds requirement, it's a strength, not an improvement area.
        
        Returns list of improvement items with:
        - title: Area of concern
        - current: User's current situation
        - ideal: What's ideal for this breed
        - action: Specific action to improve
        - priority: 'High', 'Medium', or 'Low'
        """
        improvements = []
        
        # Questions that are binary or special-case - don't flag these as areas to improve
        # Binary questions return 0/1 or pass/fail logic that shouldn't be "improved"
        skip_improvement_questions = {
            # Deal breaker questions (binary Yes/No - either compatible or not)
            'okay_fragile', 'okay_permit', 'okay_special_vet',
            # Household compatibility (binary presence - either compatible or not)
            'child_friendly', 'dog_friendly', 'cat_friendly', 'small_pet_friendly',
            # Special cases that need custom handling
            'lifespan',  # Text parsing, not comparable on 1-4 scale
            'common_health_issues',  # Informational, not a capability mismatch
            'care_cost',  # String field, not normalizable to 1-4 scale
            'min_enclosure_size',  # Categorical text, special handling needed
        }
        
        # Group scores by area for priority determination
        for score_item in individual_scores:
            question_key = score_item['question']
            score = score_item['score']
            user_answer = score_item['user_answer']
            breed_value = score_item['breed_value']
            user_normalized = score_item.get('user_normalized')
            breed_normalized = score_item.get('breed_normalized')
            
            # SAFETY: Skip special questions that don't fit standard improvement logic
            if question_key in skip_improvement_questions:
                continue
            
            # CRITICAL: Only flag as improvement if BOTH conditions are true:
            # 1. Score is poor (< 0.6)
            # 2. User actually has LESS capability/tolerance than required
            if score < 0.6:
                # SAFETY: Only flag if we can properly compare normalized values
                if user_normalized is None or breed_normalized is None:
                    # Can't reliably compare - skip to avoid false positives
                    continue
                
                # If user meets or exceeds requirement, SKIP (it's a strength, not an improvement area)
                if user_normalized >= breed_normalized:
                    continue
                
                priority = 'High' if score < 0.3 else 'Medium'
                
                # Generate specific improvement guidance
                improvement = cls._create_improvement_item(
                    question_key, user_answer, breed_value, breed, priority
                )
                if improvement:
                    improvements.append(improvement)
        
        # Sort by priority (High first, then Medium, then Low)
        priority_order = {'High': 0, 'Medium': 1, 'Low': 2}
        improvements.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return improvements[:6]  # Return top 6 improvement areas
    
    @staticmethod
    def _create_improvement_item(question_key: str, user_answer: str, breed_value: Any, breed, priority: str) -> Optional[Dict]:
        """Create a structured improvement suggestion item"""
        
        improvement_map = {
            'energy_level': {
                'title': 'Increase Daily Activity',
                'current': f"Your lifestyle: {user_answer}",
                'ideal': f"{breed.name} requires: High activity level",
                'action': 'Establish a daily routine with structured exercise, outdoor activities, and playtime to match the breed\'s energy requirements. Consider walking, running, agility training, or interactive games.'
            },
            'exercise_needs': {
                'title': 'Enhance Exercise Commitment',
                'current': f"Your exercise availability: {user_answer}",
                'ideal': f"{breed.name} needs: Daily, dedicated exercise",
                'action': 'Plan for at least 1-2 hours of daily dedicated exercise. Explore activities like fetch, swimming, running, or training sessions that engage both body and mind.'
            },
            'daily_care_time': {
                'title': 'Allocate More Daily Care Time',
                'current': f"Your available time: {user_answer}",
                'ideal': f"{breed.name} requires: {breed_value} daily commitment",
                'action': 'Restructure your schedule to dedicate adequate time for feeding, grooming, training, play, and medical care. Consider assistance from family members or professional services.'
            },
            'grooming_needs': {
                'title': 'Increase Grooming Frequency',
                'current': f"Your grooming commitment: {user_answer}",
                'ideal': f"{breed.name} requires: {breed_value} grooming",
                'action': 'Establish a regular grooming schedule. Professional grooming services can help, along with daily brushing and hygiene maintenance to prevent health issues.'
            },
            'space_needs': {
                'title': 'Optimize Living Space',
                'current': f"Your home size: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value} space",
                'action': 'Ensure your home provides adequate room for the breed to move, exercise, and exhibit natural behaviors. If space is limited, increase outdoor time or explore alternative housing options.'
            },
            'experience_required': {
                'title': 'Build Expertise & Knowledge',
                'current': f"Your experience level: {user_answer}",
                'ideal': f"{breed.name} requires: {breed_value} prior experience",
                'action': 'Take breed-specific courses, connect with experienced owners, read breed guides, and consider mentoring from breed clubs. Attend training classes and veterinary consultations.'
            },
            'monthly_cost_level': {
                'title': 'Prepare Financial Resources',
                'current': f"Your budget: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value} monthly costs",
                'action': 'Build financial reserves for food, veterinary care, grooming, and supplies. Create a monthly budget specifically for pet expenses and consider pet health insurance.'
            },
            'emergency_care_risk': {
                'title': 'Establish Emergency Financial Backup',
                'current': f"Your emergency preparedness: {user_answer}",
                'ideal': f"{breed.name} may require: Significant emergency care funding",
                'action': 'Build an emergency fund for unexpected veterinary expenses (recommended $2,000-$5,000). Explore pet insurance options and identify 24/7 emergency veterinary clinics.'
            },
            'lifetime_cost_level': {
                'title': 'Plan Long-Term Financial Commitment',
                'current': f"Your long-term financial readiness: {user_answer}",
                'ideal': f"{breed.name} lifetime costs: {breed_value}",
                'action': 'Calculate total lifetime costs for this breed (food, medical, grooming, supplies over their lifespan). Ensure financial stability and discuss with family members.'
            },
            'trainability': {
                'title': 'Develop Training Patience',
                'current': f"Your patience level: {user_answer}",
                'ideal': f"{breed.name} training needs: {breed_value} attention",
                'action': 'Enroll in professional training courses, practice positive reinforcement methods, and allocate consistent training time. Consider hiring a professional trainer if needed.'
            },
            'temperament_tolerance': {
                'title': 'Prepare for Behavioral Challenges',
                'current': f"Your behavioral management skills: {user_answer}",
                'ideal': f"{breed.name} may require: Advanced behavioral understanding",
                'action': 'Learn breed-specific behaviors and potential issues. Consult with professional animal behaviorists and trainers. Develop patience and management strategies.'
            },
            'noise_level': {
                'title': 'Adapt to Noise Levels',
                'current': f"Your noise tolerance: {user_answer}",
                'ideal': f"{breed.name} noise output: {breed_value}",
                'action': 'Soundproof areas of your home if possible. Consider whether your living situation can accommodate a more vocal pet. Discuss with neighbors if in shared housing.'
            },
            'social_needs': {
                'title': 'Increase Social Interaction',
                'current': f"Your attention availability: {user_answer}",
                'ideal': f"{breed.name} social needs: {breed_value}",
                'action': 'Plan for regular, quality interaction time. Schedule playdates, training sessions, and companionship activities. Consider your work schedule and availability.'
            },
            'environment_complexity': {
                'title': 'Set Up Specialized Environment',
                'current': f"Your setup capability: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value} environmental setup",
                'action': 'Research and prepare specialized habitat, tank, cage, or enclosure requirements. Ensure proper temperature, humidity, lighting, and enrichment elements.'
            },
            'child_friendly': {
                'title': 'Ensure Child Safety Compatibility',
                'current': f"Your household: Has children",
                'ideal': f"{breed.name}: Must be child-safe",
                'action': 'If this breed is not child-friendly, consider waiting until children are older, or explore more child-compatible breeds. Consult with breed specialists.'
            },
            'dog_friendly': {
                'title': 'Prepare for Multi-Dog Dynamics',
                'current': f"Your household: Has existing dog(s)",
                'ideal': f"{breed.name}: Must coexist with dogs",
                'action': 'Consult with a professional behaviorist for introduction strategies. Ensure proper separation spaces and gradual socialization protocols.'
            },
            'cat_friendly': {
                'title': 'Manage Cat Coexistence',
                'current': f"Your household: Has cat(s)",
                'ideal': f"{breed.name}: Must be cat-safe",
                'action': 'Work with a behaviorist if attempting introduction. Provide separate spaces. Monitor closely for prey drive behaviors. Consider the breed\'s safety around cats.'
            },
            'small_pet_friendly': {
                'title': 'Ensure Small Pet Safety',
                'current': f"Your household: Has small pets",
                'ideal': f"{breed.name}: Must be small-pet safe",
                'action': 'Secure separate enclosures for small pets. Never leave unsupervised. Monitor prey drive carefully. Consult with breed experts on safety protocols.'
            },
            'okay_fragile': {
                'title': 'Learn Gentle Handling Techniques',
                'current': f"Your handling approach: Standard",
                'ideal': f"This breed requires: Very gentle, careful handling",
                'action': 'Learn proper handling techniques for delicate species. Take classes on gentle handling and care. Always supervise interactions, especially with children.'
            },
            'okay_permit': {
                'title': 'Obtain Required Special Permits',
                'current': f"Your legal readiness: Not prepared",
                'ideal': f"This species requires: Legal permits",
                'action': 'Research permit requirements in your local jurisdiction. Contact relevant authorities, obtain necessary permits, and maintain compliance with all regulations.'
            },
            'okay_special_vet': {
                'title': 'Locate Specialized Veterinary Care',
                'current': f"Your vet access: Standard veterinarians only",
                'ideal': f"This breed needs: Exotic/specialized veterinarians",
                'action': 'Research and identify exotic or specialist veterinarians in your area. Establish relationships before acquiring the animal. Know their hours and emergency protocols.'
            },
            'preventive_care_level': {
                'title': 'Commit to Preventive Veterinary Care',
                'current': f"Your preventive care: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value} preventive care",
                'action': 'Schedule regular veterinary checkups (at least annually or as recommended). Stay current with vaccinations, parasite prevention, dental care, and health screenings.'
            },
            'stress_sensitivity': {
                'title': 'Create a Calm Home Environment',
                'current': f"Your home environment: {user_answer}",
                'ideal': f"{breed.name} needs: Calm, stable environment",
                'action': 'Minimize loud noises, sudden changes, and household stress. Establish predictable routines. Provide quiet spaces and calming enrichment to reduce anxiety.'
            },
            'lifespan': {
                'title': 'Prepare for Long-Term Commitment',
                'current': f"Your commitment horizon: {user_answer}",
                'ideal': f"{breed.name} lifespan: {breed_value} years",
                'action': 'Ensure your life plans include this breed for their entire lifespan. Consider your career, relocation, and lifestyle changes that might affect your ability to provide care.'
            },
            'prey_drive': {
                'title': 'Accept or Manage Prey Drive',
                'current': f"Your prey drive acceptance: {user_answer}",
                'ideal': f"{breed.name} prey drive: {breed_value}",
                'action': 'Understand natural hunting behaviors and design appropriate outlets. Use secure enclosures and supervised interactions. Consult behaviorists on enrichment strategies.'
            },
        }
        
        if question_key in improvement_map:
            item = improvement_map[question_key].copy()
            item['priority'] = priority
            return item
        
        return None
    
    @classmethod
    def find_top_matches(cls, answers: Dict, limit: int = 5) -> List[Dict]:
        """Find top N most compatible breeds"""
        matches = []
        breeds = Breed.query.filter(
            Breed.is_active == True,
            Breed.deleted_at.is_(None)
        ).all()
        
        for breed in breeds:
            result = cls.calculate_match_score(answers, breed)
            matches.append({
                'breed': breed,
                'score': result['score'],
                'level': result['compatibility_level'],
                'mismatches': result['mismatches'],
                'strengths': result['strengths'],
                'details': result,
                'scores': {'raw_score': result['score']}
            })
        
        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches[:limit]
    
    @classmethod
    def get_breed_compatibility_percentage(cls, answers: Dict, breed) -> Dict[str, Any]:
        """Get detailed compatibility percentage"""
        result = cls.calculate_match_score(answers, breed)
        return {
            'overall_score': result['score'],
            'compatibility_level': result['compatibility_level'],
            'percentage': round(result['score'], 1),
            'category_scores': {k: round(v.get('raw_score', 0) * 100, 1) for k, v in result['category_scores'].items()},
            'is_good_match': result['score'] >= 70,
            'key_strengths': result['strengths'][:3],
            'key_challenges': result['mismatches'][:3],
            'total_score_breakdown': result['score'],
        }
    
    @classmethod
    def get_improvement_suggestions(cls, answers: Dict, breed) -> Dict[str, Any]:
        """Generate professional improvement suggestions"""
        result = cls.calculate_match_score(answers, breed)
        return {
            'breed_name': breed.name,
            'current_score': result['score'],
            'compatibility_level': result['compatibility_level'],
            'strengths': result['strengths'],
            'challenges': result['mismatches'],
            'improvement_suggestions': [],
        }
