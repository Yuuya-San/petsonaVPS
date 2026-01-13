from app.models.breed import Breed
from app.models.species import Species
import re
from typing import Dict, List, Any, Optional, Tuple


class CompatibilityEngine:
    """
    Advanced pet compatibility matching engine using a weighted multi-dimensional scoring system.
    
    Evaluates compatibility across 7 key dimensions:
    - Lifestyle & Activity: Energy levels, exercise, noise tolerance
    - Experience & Training: Required expertise, trainability, temperament match
    - Space & Environment: Housing needs, enclosure complexity
    - Care & Grooming: Time commitment, grooming requirements
    - Household Compatibility: Safety with children, dogs, cats, small pets
    - Financial Reality: Monthly costs, emergency care, lifetime expenses
    - Species-Specific Safety: Prey drive, fragility, permits, veterinary needs
    
    Uses configurable weights to prioritize safety and experience to prevent
    adoption failures and ensure responsible pet ownership.
    """
    
    # =====================================================================
    # COMPREHENSIVE ATTRIBUTE MAPPING
    # Maps all 24 quiz questions to breed/species attributes
    # =====================================================================
    ATTRIBUTE_MAPPING = {
        # ---- LIFESTYLE & ACTIVITY (5 questions) ----
        'energy_level': ('energy_level', 'breed'),
        'exercise_needs': ('exercise_needs', 'breed'),
        'noise_level': ('noise_level', 'breed'),
        'social_needs': ('social_needs', 'breed'),
        'handling_tolerance': ('handling_tolerance', 'breed'),
        
        # ---- EXPERIENCE & TRAINING (3 questions) ----
        'experience_required': ('experience_required', 'breed'),
        'trainability': ('trainability', 'breed'),
        'temperament_tolerance': ('trainability', 'breed'),  # Proxy
        
        # ---- SPACE & ENVIRONMENT (3 questions) ----
        'space_needs': ('space_needs', 'breed'),
        'environment_complexity': ('environment_complexity', 'breed'),
        'min_enclosure_size': ('min_enclosure_size', 'breed'),
        
        # ---- CARE & TIME (2 questions) ----
        'daily_care_time': ('time_commitment', 'breed'),
        'grooming_needs': ('grooming_needs', 'breed'),
        
        # ---- HOUSEHOLD COMPATIBILITY (4 questions) ----
        'child_friendly': ('child_friendly', 'breed'),
        'dog_friendly': ('dog_friendly', 'breed'),
        'cat_friendly': ('cat_friendly', 'breed'),
        'small_pet_friendly': ('small_pet_friendly', 'breed'),
        
        # ---- FINANCIAL REALITY (4 questions) ----
        'monthly_cost_level': ('monthly_cost_level', 'breed'),
        'emergency_care_risk': ('emergency_care_risk', 'breed'),
        'lifetime_cost_level': ('lifetime_cost_level', 'breed'),
        'care_cost': ('care_cost', 'breed'),  # Actual care cost estimate
        
        # ---- HEALTH & WELLNESS (4 questions) ----
        'preventive_care_level': ('preventive_care_level', 'breed'),
        'stress_sensitivity': ('stress_sensitivity', 'breed'),
        'common_health_issues': ('common_health_issues', 'breed'),
        'lifespan': ('lifespan', 'breed'),
        
        # ---- SPECIES-SPECIFIC SAFETY (4 questions) ----
        'prey_drive': ('prey_drive', 'breed'),
        'okay_fragile': ('fragile_species', 'species'),
        'okay_permit': ('requires_permit', 'species'),
        'okay_special_vet': ('special_vet_required', 'species'),
    }
    
    # =====================================================================
    # CATEGORY WEIGHTS
    # Higher weights = more critical for overall compatibility
    # =====================================================================
    CATEGORY_WEIGHTS = {
        'lifestyle': 1.15,       # Important for daily satisfaction
        'experience': 1.35,      # CRITICAL - prevents abandonment
        'space': 1.10,           # Important for quality of life
        'care': 1.05,            # Standard importance
        'household': 1.20,       # Very important for safety & success
        'financial': 1.10,       # Important - affects commitment and pet welfare
        'health': 1.15,          # CRITICAL - affects pet longevity and wellbeing
        'safety': 1.25,          # CRITICAL - legal/ethical responsibility
    }
    
    # =====================================================================
    # QUESTION-LEVEL WEIGHTS
    # Fine-tuning within each category (0.0-1.0)
    # =====================================================================
    QUESTION_WEIGHTS = {
        # Lifestyle
        'energy_level': 0.95,
        'exercise_needs': 0.95,
        'noise_level': 0.80,
        'social_needs': 0.85,
        'handling_tolerance': 0.85,
        
        # Experience (all weighted heavily)
        'experience_required': 1.00,
        'trainability': 0.95,
        'temperament_tolerance': 0.95,
        
        # Space
        'space_needs': 0.90,
        'environment_complexity': 0.85,
        'min_enclosure_size': 0.85,
        
        # Care
        'daily_care_time': 0.90,
        'grooming_needs': 0.90,
        
        # Household (all weighted heavily for safety)
        'child_friendly': 0.95,
        'dog_friendly': 0.90,
        'cat_friendly': 0.90,
        'small_pet_friendly': 0.90,
        
        # Financial
        'monthly_cost_level': 0.85,
        'emergency_care_risk': 0.90,
        'lifetime_cost_level': 0.85,
        'care_cost': 0.80,
        
        # Health & Wellness (all weighted heavily - affects pet longevity)
        'preventive_care_level': 0.90,
        'stress_sensitivity': 0.85,
        'common_health_issues': 0.85,
        'lifespan': 0.85,
        
        # Safety (all weighted heavily)
        'prey_drive': 0.95,
        'okay_fragile': 0.95,
        'okay_permit': 0.90,
        'okay_special_vet': 0.85,
    }
    
    # =====================================================================
    # MAPPING HELPERS
    # =====================================================================
    @staticmethod
    def map_care_time(user_value):
        """Map user's daily care time response to breed's time_commitment"""
        mapping = {
            'Less than 1 hour': 'Low',
            '1-2 hours': 'Medium',
            '2-4 hours': 'High',
            'More than 4 hours': 'High',
        }
        return mapping.get(user_value, 'Medium')
    
    @staticmethod
    def map_noise_tolerance(user_answer):
        """Map user's noise tolerance to numeric scale for comparison"""
        mapping = {
            'I need it very quiet': 1,      # Low tolerance
            'Some noise is okay': 2,         # Medium tolerance
            'Noise does not bother me': 3,   # High tolerance
        }
        return mapping.get(user_answer, 2)
    
    @staticmethod
    def map_noise_level(breed_value):
        """Map breed's noise level to numeric scale"""
        mapping = {
            'Silent': 1,
            'Low': 2,
            'Moderate': 2.5,
            'Loud': 3,
        }
        return mapping.get(breed_value, 2)
    
    @staticmethod
    def map_energy_tolerance(user_answer):
        """Map user's energy preference to numeric scale"""
        mapping = {
            'Low energy': 1,
            'Moderate energy': 2,
            'High energy': 3,
        }
        return mapping.get(user_answer, 2)
    
    @staticmethod
    def map_energy_level(breed_value):
        """Map breed's energy level to numeric scale"""
        mapping = {
            'Low': 1,
            'Medium': 2,
            'High': 3,
        }
        return mapping.get(breed_value, 2)
    
    @staticmethod
    def map_exercise_response(user_value):
        """Map exercise frequency response to needs level"""
        mapping = {
            'No': 'Low',
            'Sometimes': 'Medium',
            'Yes, every day': 'High',
        }
        return mapping.get(user_value, 'Medium')
    
    @staticmethod
    def map_exercise_numeric(user_answer):
        """Map exercise frequency to numeric scale (1-3)"""
        mapping = {
            'No': 1,
            'Sometimes': 2,
            'Yes, every day': 3,
        }
        return mapping.get(user_answer, 2)
    
    @staticmethod
    def map_grooming_response(user_value):
        """Map grooming frequency to needs level"""
        mapping = {
            'Rarely': 'Low',
            'About once a week': 'Medium',
            'Very often': 'High',
        }
        return mapping.get(user_value, 'Medium')
    
    @staticmethod
    def map_grooming_numeric(user_answer):
        """Map grooming frequency to numeric scale (1-3)"""
        mapping = {
            'Rarely': 1,
            'About once a week': 2,
            'Very often': 3,
        }
        return mapping.get(user_answer, 2)
    
    @staticmethod
    def map_care_time_numeric(user_value):
        """Map daily care time to numeric scale (1-3)"""
        mapping = {
            'Less than 1 hour': 1,
            '1-2 hours': 2,
            '2-4 hours': 3,
            'More than 4 hours': 3,
        }
        return mapping.get(user_value, 2)
    
    @staticmethod
    def map_space_numeric(user_answer):
        """Map space/living situation to numeric scale (1-3)"""
        mapping = {
            'Small': 1,
            'Medium': 2,
            'Large': 3,
        }
        return mapping.get(user_answer, 2)
    
    @staticmethod
    def map_temperament_tolerance(user_value):
        """Map patience level to trainability tolerance"""
        mapping = {
            'Not well': 'Difficult',
            'I can try': 'Moderate',
            'I handle them well': 'Easy',
        }
        return mapping.get(user_value, 'Moderate')
    
    @staticmethod
    def map_boolean_yes_no(user_value):
        """Convert Yes/No to boolean"""
        return user_value == 'Yes'
    
    @classmethod
    def calculate_match_score(cls, answers, breed):
        """
        Calculate comprehensive compatibility score between user and breed.
        
        Performs multi-dimensional analysis of 24 quiz questions mapped to breed attributes,
        applying category-level and question-level weights to produce a normalized 0-100 score.
        
        Args:
            answers (dict): User quiz responses mapped to question keys
            breed (Breed): Breed model instance with all attribute data
            
        Returns:
            dict: Comprehensive scoring result with:
                - score (float): Final compatibility score (0-100)
                - compatibility_level (str): Human-readable level (Excellent/Good/Moderate/Low/Poor)
                - category_scores (dict): Detailed scores for each dimension
                - individual_scores (list): Per-question breakdown with weights
                - mismatches (list): Human-readable mismatch descriptions
                - total_questions_answered (int): Number of valid answers processed
        """
        category_scores = {
            'lifestyle': 0,
            'experience': 0,
            'space': 0,
            'care': 0,
            'household': 0,
            'financial': 0,
            'safety': 0,
        }
        category_totals = {k: 0 for k in category_scores}
        category_weights_total = {k: 0 for k in category_scores}
        
        individual_scores = []
        mismatches = []
        
        # Process each quiz question
        for question_key, (attr_name, attr_source) in cls.ATTRIBUTE_MAPPING.items():
            user_answer = answers.get(question_key)
            
            if user_answer is None:
                continue
            
            # Determine which category this question belongs to
            category = cls._get_category_for_question(question_key)
            
            # Get question weight
            q_weight = cls.QUESTION_WEIGHTS.get(question_key, 0.8)
            
            # Get breed or species attribute value
            if attr_source == 'species':
                breed_value = getattr(breed.species, attr_name, None)
            else:
                breed_value = getattr(breed, attr_name, None)
            
            # Calculate match score for this question (0-1 scale)
            score = cls._calculate_question_match_score(
                question_key, user_answer, attr_name, breed_value, breed
            )
            
            # Track mismatch if score is low
            if score < 0.5:
                mismatch = cls._generate_mismatch_description(
                    question_key, user_answer, breed_value, breed
                )
                if mismatch:
                    mismatches.append(mismatch)
            
            # Accumulate weighted scores by category
            category_scores[category] += score * q_weight
            category_weights_total[category] += q_weight
            
            individual_scores.append({
                'question': question_key,
                'category': category,
                'user_answer': user_answer,
                'breed_value': breed_value,
                'score': round(score, 2),
                'weight': q_weight,
            })
        
        # Calculate category scores and apply category weights
        total_weighted_score = 0
        total_category_weight = 0
        category_results = {}
        
        for category in category_scores:
            if category_weights_total[category] > 0:
                # Normalize category score to 0-1
                normalized_score = category_scores[category] / category_weights_total[category]
                # Apply category weight multiplier
                cat_weight = cls.CATEGORY_WEIGHTS.get(category, 1.0)
                weighted_score = normalized_score * cat_weight
                
                category_results[category] = {
                    'raw_score': round(normalized_score, 3),
                    'weighted_score': round(weighted_score, 3),
                    'weight': cat_weight,
                }
                
                total_weighted_score += weighted_score
                total_category_weight += cat_weight
        
        # Convert to 0-100 scale
        final_score = (total_weighted_score / total_category_weight * 100) if total_category_weight > 0 else 0
        final_score = max(0, min(100, final_score))  # Clamp to 0-100
        
        return {
            'score': round(final_score, 1),
            'compatibility_level': cls._get_compatibility_level(final_score),
            'category_scores': category_results,
            'individual_scores': individual_scores,
            'mismatches': mismatches,
            'total_questions_answered': len(individual_scores),
        }
    
    @staticmethod
    def _get_category_for_question(question_key):
        """
        Map a quiz question to its category dimension.
        
        Args:
            question_key (str): Question identifier
            
        Returns:
            str: Category name (lifestyle/experience/space/care/household/financial/health/safety)
        """
        categories_map = {
            'lifestyle': ['energy_level', 'exercise_needs', 'noise_level', 'social_needs', 'handling_tolerance'],
            'experience': ['experience_required', 'trainability', 'temperament_tolerance'],
            'space': ['space_needs', 'environment_complexity', 'min_enclosure_size'],
            'care': ['daily_care_time', 'grooming_needs'],
            'household': ['child_friendly', 'dog_friendly', 'cat_friendly', 'small_pet_friendly'],
            'financial': ['monthly_cost_level', 'emergency_care_risk', 'lifetime_cost_level', 'care_cost'],
            'health': ['preventive_care_level', 'stress_sensitivity', 'common_health_issues', 'lifespan'],
            'safety': ['prey_drive', 'okay_fragile', 'okay_permit', 'okay_special_vet'],
        }
        
        for category, questions in categories_map.items():
            if question_key in questions:
                return category
        
        return 'lifestyle'  # Default
    
    @classmethod
    def _calculate_question_match_score(cls, question_key, user_answer, attr_name, breed_value, breed):
        """
        Calculate normalized match score (0-1.0) for a specific question.
        
        Implements special logic for questions requiring nuanced matching beyond
        simple string comparison. Handles scenario-specific rules:
        - Safety concerns (permits, fragility) have binary/penalty logic
        - Capability questions reward exceeding requirements
        - Temperament matching uses patience levels
        - Boolean attributes use asymmetric logic
        
        Args:
            question_key (str): Question identifier for routing to special cases
            user_answer (str/int): User's response value
            attr_name (str): Breed attribute name (unused, kept for clarity)
            breed_value (any): Breed attribute value for comparison
            breed (Breed): Full breed model for accessing nested attributes
            
        Returns:
            float: Normalized score in range [0.0, 1.0]
                - 1.0: Perfect match
                - 0.5: Unknown or neutral
                - 0.0-1.0: Graduated penalty based on mismatch severity
        """
        
        # ---- SPECIAL CASE: SAFETY (FRAGILE/PERMIT/VET) ----
        if question_key in ['okay_fragile', 'okay_permit', 'okay_special_vet']:
            user_okay = user_answer == 'Yes'
            
            # Determine if breed has this requirement
            if question_key == 'okay_fragile':
                breed_has_requirement = breed.species.fragile_species if hasattr(breed.species, 'fragile_species') else False
            elif question_key == 'okay_permit':
                breed_has_requirement = breed.species.requires_permit if hasattr(breed.species, 'requires_permit') else False
            else:  # okay_special_vet
                breed_has_requirement = breed.species.special_vet_required if hasattr(breed.species, 'special_vet_required') else False
            
            # Perfect match: either user is ready and breed needs it, or breed doesn't need it
            if user_okay or not breed_has_requirement:
                return 1.0
            # Mismatch: user not ready but breed requires it
            else:
                return 0.0 if question_key == 'okay_fragile' or question_key == 'okay_permit' else 0.5
        
        # ---- SPECIAL CASE: DAILY CARE TIME ----
        if question_key == 'daily_care_time':
            """
            User's available care time must meet breed's needs.
            If user has 4+ hours available (3), perfect match with any breed.
            """
            user_time = cls.map_care_time_numeric(user_answer)
            breed_time_requirement = {'Low': 1, 'Medium': 2, 'High': 3}.get(breed.time_commitment, 2)
            
            # If user has 4+ hours available, perfect match with any breed's care needs
            if user_time == 3:
                return 1.0
            # Perfect match or user has more time
            elif user_time >= breed_time_requirement:
                return 1.0
            else:
                shortfall = breed_time_requirement - user_time
                return max(0.0, 1.0 - (shortfall * 0.35))
        
        # ---- SPECIAL CASE: GROOMING NEEDS ----
        if question_key == 'grooming_needs':
            """
            User's grooming commitment must meet breed's grooming needs.
            If user willing to groom very often (3), perfect match with any breed.
            """
            user_grooming = cls.map_grooming_numeric(user_answer)
            breed_grooming_requirement = {'Low': 1, 'Medium': 2, 'High': 3}.get(breed.grooming_needs, 2)
            
            # If user willing to groom very often, perfect match with any breed's grooming needs
            if user_grooming == 3:
                return 1.0
            # Perfect match or user willing to groom more
            elif user_grooming >= breed_grooming_requirement:
                return 1.0
            else:
                shortfall = breed_grooming_requirement - user_grooming
                return max(0.0, 1.0 - (shortfall * 0.35))
        
        # ---- SPECIAL CASE: EXERCISE CAPABILITY ----
        if question_key == 'exercise_needs':
            """
            User's exercise capability must meet breed's exercise needs.
            If user exercises daily (3), perfect match with any breed.
            """
            user_exercise = cls.map_exercise_numeric(user_answer)
            breed_exercise_requirement = {'Low': 1, 'Medium': 2, 'High': 3}.get(breed.exercise_needs, 2)
            
            # If user exercises daily, perfect match with any breed's exercise need
            if user_exercise == 3:
                return 1.0
            # Perfect match or user can provide more exercise
            elif user_exercise >= breed_exercise_requirement:
                return 1.0
            else:
                shortfall = breed_exercise_requirement - user_exercise
                return max(0.0, 1.0 - (shortfall * 0.35))
        
        # ---- SPECIAL CASE: TEMPERAMENT TOLERANCE (TRAINABILITY) ----
        if question_key == 'temperament_tolerance':
            """
            User's patience/ability to train must match breed's trainability needs.
            If user "handles them well" (3), perfect match with any breed difficulty.
            """
            # Map user patience to numeric scale
            patience_levels = {'Not well': 1, 'I can try': 2, 'I handle them well': 3}
            user_patience = patience_levels.get(user_answer, 2) if user_answer else 2
            
            # Map breed trainability to numeric scale (difficulty)
            trainability_levels = {'Easy': 1, 'Moderate': 2, 'Difficult': 3}
            breed_difficulty = trainability_levels.get(breed.trainability, 2)
            
            # If user handles them well, perfect match with any breed difficulty
            if user_patience == 3:
                return 1.0
            # User patience must meet or exceed breed difficulty
            elif user_patience >= breed_difficulty:
                return 1.0
            else:
                shortfall = breed_difficulty - user_patience
                return max(0.0, 1.0 - (shortfall * 0.4))
        
        # ---- SPECIAL CASE: MIN ENCLOSURE SIZE ----
        if question_key == 'min_enclosure_size':
            """
            Enclosure size matching with graduated penalty:
            - No penalty if either party has no requirement
            - Perfect score if user capacity >= breed requirement
            - Graduated penalty (0.4 per unit shortfall) if insufficient
            - Perfect match if user capacity is significantly larger (>50% more)
            """
            try:
                user_capacity = int(user_answer) if isinstance(user_answer, str) else user_answer
                breed_requirement = breed.min_enclosure_size or 0
                
                if breed_requirement == 0:
                    return 1.0  # No enclosure needed
                # If user capacity is at least 50% more than requirement, perfect match
                if user_capacity >= breed_requirement * 1.5:
                    return 1.0  # User can provide abundant space
                elif user_capacity >= breed_requirement:
                    return 1.0  # User can provide what's needed
                else:
                    # User's capacity is insufficient - apply graduated penalty
                    shortfall = breed_requirement - user_capacity
                    return max(0.0, 1.0 - shortfall * 0.4)
            except (ValueError, TypeError):
                # Invalid enclosure size data - return neutral score
                return 0.5
        
        # ---- SPECIAL CASE: BOOLEAN COMPARISONS (Household) ----
        if isinstance(breed_value, bool):
            user_bool = user_answer == 'Yes'
            
            # If user specifically wants this trait and breed has it = perfect match
            if user_bool and breed_value:
                return 1.0
            # If user doesn't care (says No) and breed is safe = acceptable (0.4)
            elif not user_bool and not breed_value:
                return 1.0  # User doesn't have it, breed is also safe
            # If user wants it but breed doesn't have it = mismatch (0.0)
            elif user_bool and not breed_value:
                return 0.0  # Critical - user has the animal but breed isn't compatible
            # If user doesn't want it but breed has it = okay (0.4)
            else:
                return 0.4  # Breed is friendly but user doesn't have that animal
        
        # ---- SPECIAL CASE: PREVENTIVE CARE LEVEL ----
        if question_key == 'preventive_care_level':
            """
            User's willingness to handle vet visits must match breed's needs.
            If user has high vet commitment (3), perfect match with any breed.
            """
            care_levels = {'Low': 1, 'Medium': 2, 'High': 3}
            user_level = care_levels.get(user_answer, 2)
            breed_level = care_levels.get(breed_value, 2)
            
            # If user has high vet commitment, perfect match with any breed's care needs
            if user_level == 3:
                return 1.0
            elif user_level >= breed_level:
                return 1.0  # User can handle the care level
            elif user_level == breed_level - 1:
                return 0.7  # User is slightly under-equipped
            else:
                return 0.3  # User can't handle breed's vet needs
        
        # ---- SPECIAL CASE: STRESS SENSITIVITY ----
        if question_key == 'stress_sensitivity':
            """
            User's lifestyle stability should match breed's stress sensitivity.
            If user has very stable home (1), perfect match with any sensitivity.
            """
            sensitivity_levels = {'Low': 1, 'Medium': 2, 'High': 3}
            user_stability = sensitivity_levels.get(user_answer, 2)
            breed_sensitivity = sensitivity_levels.get(breed_value, 2)
            
            # If user has very stable home, perfect match with any breed's sensitivity
            if user_stability == 1:
                return 1.0  # User's very stable home works for any breed
            elif breed_sensitivity <= 2:  # Low or Medium sensitivity - flexible
                return 1.0
            else:  # High sensitivity - needs stable home
                return 0.7 if user_stability == 2 else 0.3
        
        # ---- SPECIAL CASE: COMMON HEALTH ISSUES ----
        if question_key == 'common_health_issues':
            """
            Presence of common health issues affects score based on user preparation
            """
            if not breed_value:  # No common health issues - perfect
                return 1.0
            # If breed has health issues, assume user can handle (user willing to learn)
            # Score based on whether user answered they're ready for health challenges
            user_ready = user_answer in ['Yes', 'High', 'I can manage']
            return 0.8 if user_ready else 0.6
        
        # ---- SPECIAL CASE: LIFESPAN ----
        if question_key == 'lifespan':
            """
            User's expected lifespan commitment should align with breed's life expectancy.
            If user expects 20+ years, perfect match with any breed lifespan.
            """
            # Parse lifespan range if available (e.g., "10-15 years" or "10")
            if breed_value:
                try:
                    if isinstance(breed_value, str):
                        # Extract numbers from range like "10-15 years"
                        import re
                        numbers = re.findall(r'\d+', breed_value)
                        if numbers:
                            breed_years = int(numbers[-1])  # Take the upper bound
                        else:
                            breed_years = 10  # Default estimate
                    else:
                        breed_years = int(breed_value)
                except (ValueError, TypeError):
                    breed_years = 10  # Default estimate
                
                # User's expected years
                try:
                    if isinstance(user_answer, str):
                        import re
                        numbers = re.findall(r'\d+', user_answer)
                        if numbers:
                            user_years = int(numbers[-1])
                        else:
                            user_years = 10
                    else:
                        user_years = int(user_answer)
                except (ValueError, TypeError):
                    return 0.5  # Unknown user expectation
                
                # If user expects very long commitment (20+ years), perfect match
                if user_years >= 20:
                    return 1.0  # User is committed long-term
                # Score based on alignment
                elif user_years >= breed_years:
                    return 1.0  # User can commit long enough
                elif user_years >= breed_years - 2:
                    return 0.8  # Close match
                else:
                    return 0.5  # Significant mismatch
            return 1.0  # No lifespan data available
        
        # ---- SPECIAL CASE: MONTHLY COST LEVEL ----
        if question_key == 'monthly_cost_level':
            """
            User's budget should align with breed's estimated monthly cost.
            If user has no budget constraints, perfect match with any breed cost.
            """
            # User answer could be: 'Budget-conscious', 'Moderate budget', 'No budget constraints'
            if user_answer in ['No budget constraints', 'High budget', 'Unlimited']:
                return 1.0  # User can afford any breed's monthly costs
            
            # For others, check if they can handle the breed's cost level
            cost_levels = {'Low': 1, 'Medium': 2, 'High': 3}
            user_budget = cost_levels.get(user_answer, 2) if user_answer else 2
            breed_cost = cost_levels.get(breed_value, 2)
            
            if user_budget >= breed_cost:
                return 1.0
            else:
                return 0.5 if user_budget == breed_cost - 1 else 0.2
        
        # ---- SPECIAL CASE: NOISE LEVEL ----
        if question_key == 'noise_level':
            """
            User's noise tolerance must accommodate breed's noise production.
            
            Scoring logic:
            - If user doesn't mind noise at all (tolerance=3): Perfect score (1.0) regardless of breed noise
            - If user is okay with some noise (tolerance=2): Score well with low-moderate noise, penalty for loud
            - If user needs quiet (tolerance=1): Must match with quiet/low noise breeds
            """
            user_tolerance = cls.map_noise_tolerance(user_answer)
            breed_noise = cls.map_noise_level(breed_value)
            
            # If user says "noise doesn't bother me" - they're perfectly fine with ANY noise level
            if user_tolerance == 3:
                return 1.0
            
            # For less tolerant users: Perfect match if user tolerance >= breed noise level
            if user_tolerance >= breed_noise:
                return 1.0
            # User can't handle breed's noise level - apply graduated penalty
            else:
                shortfall = breed_noise - user_tolerance
                # Graduated penalty: each step down is -0.35
                return max(0.0, 1.0 - (shortfall * 0.35))
        
        # ---- SPECIAL CASE: ENERGY LEVEL ----
        if question_key == 'energy_level':
            """
            User's energy level should match breed's energy needs.
            If user has high energy (3), they're perfect with any breed energy level.
            """
            user_energy = cls.map_energy_tolerance(user_answer) if user_answer else 2
            breed_energy = cls.map_energy_level(breed_value)
            
            # If user has high energy, perfect match with any breed
            if user_energy == 3:
                return 1.0
            # Perfect match if both are aligned
            elif user_energy == breed_energy:
                return 1.0
            # User has more energy than breed needs - still good (0.85)
            elif user_energy > breed_energy:
                return 0.85
            # User has less energy than breed needs - problematic
            else:
                shortfall = breed_energy - user_energy
                return max(0.0, 1.0 - (shortfall * 0.4))
        
        # ---- SPECIAL CASE: SOCIAL NEEDS ----
        if question_key == 'social_needs':
            """
            User's ability to provide attention should match breed's social needs.
            If user has high availability (3), perfect match with any breed.
            """
            social_levels = {'Low': 1, 'Medium': 2, 'High': 3}
            user_availability = social_levels.get(user_answer, 2) if user_answer else 2
            breed_social = social_levels.get(breed_value, 2)
            
            # If user has high availability, perfect match with any breed's social needs
            if user_availability == 3:
                return 1.0
            elif user_availability >= breed_social:
                return 1.0
            else:
                shortfall = breed_social - user_availability
                return max(0.0, 1.0 - (shortfall * 0.35))
        
        # ---- SPECIAL CASE: HANDLING TOLERANCE ----
        if question_key == 'handling_tolerance':
            """
            User's home environment should match breed's handling requirements.
            If user has busy/active home (3), perfect match with any breed.
            """
            home_styles = {'Very calm and quiet': 1, 'Normal': 2, 'Busy, noisy, and active': 3}
            user_home = home_styles.get(user_answer, 2) if user_answer else 2
            breed_tolerance = home_styles.get(breed_value, 2)
            
            # If user has busy/active home, perfect match with any breed's handling needs
            if user_home == 3:
                return 1.0
            # User with adequate home environment = good match
            elif user_home >= breed_tolerance:
                return 1.0
            else:
                shortfall = breed_tolerance - user_home
                return max(0.0, 1.0 - (shortfall * 0.35))
        
        # ---- SPECIAL CASE: SPACE NEEDS ----
        if question_key == 'space_needs':
            """
            User's living space must accommodate breed's space requirements.
            If user has large space (3), perfect match with any breed.
            """
            space_levels = {'Small': 1, 'Medium': 2, 'Large': 3}
            user_space = space_levels.get(user_answer, 2) if user_answer else 2
            breed_space_need = space_levels.get(breed_value, 2)
            
            # If user has large space, perfect match with any breed's space needs
            if user_space == 3:
                return 1.0
            # User space >= breed need = good match
            elif user_space >= breed_space_need:
                return 1.0
            else:
                shortfall = breed_space_need - user_space
                return max(0.0, 1.0 - (shortfall * 0.35))
        
        # ---- SPECIAL CASE: EXPERIENCE REQUIRED ----
        if question_key == 'experience_required':
            """
            User's experience level must meet breed's requirement.
            If user is advanced (3), perfect match with any breed.
            """
            experience_levels = {'Beginner': 1, 'Intermediate': 2, 'Advanced': 3}
            user_experience = experience_levels.get(user_answer, 2) if user_answer else 2
            breed_experience_need = experience_levels.get(breed_value, 2)
            
            # If user is advanced, perfect match with any breed's experience needs
            if user_experience == 3:
                return 1.0
            # User experience >= breed need = good match
            elif user_experience >= breed_experience_need:
                return 1.0
            else:
                shortfall = breed_experience_need - user_experience
                return max(0.0, 1.0 - (shortfall * 0.4))
        
        # ---- SPECIAL CASE: EMERGENCY CARE AND LIFETIME COSTS ----
        if question_key in ['emergency_care_risk', 'lifetime_cost_level', 'care_cost']:
            """
            User's financial preparedness for various cost scenarios.
            If user is fully prepared/has budget, perfect match with any breed cost profile.
            """
            # Map responses to preparation level (1-3)
            if question_key == 'emergency_care_risk':
                prep_levels = {'No': 1, 'Somewhat': 2, 'Yes, fully prepared': 3}
            else:
                prep_levels = {'Limited budget': 1, 'Moderate budget': 2, 'No budget constraints': 3}
            
            user_prep = prep_levels.get(user_answer, 2)
            
            # If user is fully prepared (3), perfect match with any cost scenario
            if user_prep == 3:
                return 1.0
            
            # For lower prep levels, give moderate to good score
            # (Financial mismatches are serious but often manageable)
            breed_cost_level = {'Low': 1, 'Medium': 2, 'High': 3}.get(breed_value, 2)
            
            if user_prep >= breed_cost_level:
                return 1.0  # User can afford this level
            elif user_prep == breed_cost_level - 1:
                return 0.7  # Slightly below, but manageable
            else:
                return 0.4  # Significant budget mismatch
        
        # ---- DEFAULT: DIRECT STRING COMPARISON ----
        if breed_value is None:
            return 0.5  # Unknown attribute
        
        if str(user_answer).strip() == str(breed_value).strip():
            return 1.0
        else:
            return 0.0
    
    @staticmethod
    def _generate_mismatch_description(question_key, user_answer, breed_value, breed):
        """
        Generate human-readable description of compatibility mismatches.
        
        Creates clear, concise explanations of why a user-breed pair may have
        compatibility issues, formatted for user-facing feedback.
        
        Args:
            question_key (str): Question identifier
            user_answer (str): User's response
            breed_value (any): Breed's attribute value
            breed (Breed): Breed model instance
            
        Returns:
            str: Formatted mismatch description or None if not found
        """
        
        descriptions = {
            'energy_level': f"Energy mismatch: You prefer \"{user_answer}\" activity, but \"{breed.name}\" has \"{breed_value}\" energy",
            'exercise_needs': f"Exercise mismatch: You can provide \"{user_answer}\" exercise, but \"{breed.name}\" needs \"{breed_value}\" exercise",
            'noise_level': f"Noise tolerance mismatch: You prefer \"{user_answer}\", but \"{breed.name}\" produces \"{breed_value}\" noise",
            'grooming_needs': f"Grooming mismatch: You groom \"{user_answer}\", but \"{breed.name}\" needs \"{breed_value}\" grooming",
            'space_needs': f"Space mismatch: Your space is \"{user_answer}\", but \"{breed.name}\" needs \"{breed_value}\" space",
            'experience_required': f"Experience mismatch: You're \"{user_answer}\", but \"{breed.name}\" is best for \"{breed_value}\" owners",
            'monthly_cost_level': f"Budget mismatch: Your budget is \"{user_answer}\", but \"{breed.name}\" costs \"{breed_value}\"",
            'daily_care_time': f"Time commitment mismatch: You have \"{user_answer}\" available, but \"{breed.name}\" may need more care",
            'child_friendly': f"Child safety: \"{breed.name}\" is {'not suitable' if breed_value is False else 'suitable'} for children",
            'dog_friendly': f"Dog compatibility: \"{breed.name}\" is {'not dog-friendly' if breed_value is False else 'dog-friendly'}",
            'cat_friendly': f"Cat compatibility: \"{breed.name}\" is {'not cat-friendly' if breed_value is False else 'cat-friendly'}",
            'small_pet_friendly': f"Small pet safety: \"{breed.name}\" is {'not safe' if breed_value is False else 'safe'} with small pets",
            'okay_fragile': f"This \"{breed.species.name}\" breed is delicate, but you prefer hardy pets",
            'okay_permit': f"This breed \"{breed.name}\" requires special permits, but you prefer not to deal with legal requirements",
            'okay_special_vet': f"This breed \"{breed.name}\" may need exotic veterinary care, which isn't available to you",
            'prey_drive': f"Prey drive mismatch: \"{breed.name}\" has \"{breed_value}\" prey drive",
        }
        
        return descriptions.get(question_key)
    
    @staticmethod
    def _get_compatibility_level(score):
        """
        Convert numeric compatibility score to human-readable level.
        
        Args:
            score (float): Compatibility score (0-100)
            
        Returns:
            str: Level classification
                - Excellent: 85-100 (highly recommended)
                - Good: 70-84 (viable option)
                - Moderate: 55-69 (consider carefully)
                - Low: 40-54 (likely challenges)
                - Poor: 0-39 (not recommended)
        """
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
    def get_random_suggestions(cls, answers, breed_id=None, limit=5):
        """
        Get random breed suggestions to show diversity.
        
        If breed_id provided, rank suggestions by compatibility to that breed.
        Otherwise return random active breeds for discovery.
        
        Args:
            answers (dict): User quiz responses
            breed_id (int): Optional breed to use as ranking basis
            limit (int): Number of suggestions to return
            
        Returns:
            list: Random breed suggestions with format:
                {
                    'breed': Breed object,
                    'score': float or None,
                    'name': str,
                    'species': str,
                }
        """
        from app.models.breed import Breed
        import random
        
        all_breeds = Breed.query.filter(
            Breed.is_active == True,
            Breed.deleted_at.is_(None)
        ).all()
        
        if not all_breeds:
            return []
        
        # If breed_id provided, score and rank suggestions
        if breed_id:
            target_breed = Breed.query.get(breed_id)
            if not target_breed:
                suggestions = random.sample(all_breeds, min(limit, len(all_breeds)))
                return [
                    {
                        'breed': b,
                        'score': None,
                        'name': b.name,
                        'species': b.species.name if b.species else 'Unknown',
                    }
                    for b in suggestions
                ]
            
            # Calculate scores relative to target breed
            matches = []
            for breed in all_breeds:
                result = cls.calculate_match_score(answers, breed)
                matches.append({
                    'breed': breed,
                    'score': result['score'],
                    'name': breed.name,
                    'species': breed.species.name if breed.species else 'Unknown',
                })
            
            # Sort by score, then randomly select
            matches.sort(key=lambda x: x['score'], reverse=True)
            return matches[:limit]
        
        # Random selection for discovery
        suggestions = random.sample(all_breeds, min(limit, len(all_breeds)))
        return [
            {
                'breed': b,
                'score': None,
                'name': b.name,
                'species': b.species.name if b.species else 'Unknown',
            }
            for b in suggestions
        ]
    
    @classmethod
    def get_breed_compatibility_percentage(cls, answers, breed):
        """
        Calculate compatibility percentage (0-100) for specific breed.
        
        Returns detailed percentage breakdown with category breakdown and
        explanations suitable for display on breed detail page.
        
        Args:
            answers (dict): User quiz responses
            breed (Breed): Target breed to evaluate
            
        Returns:
            dict: Detailed compatibility with:
                {
                    'overall_score': float (0-100),
                    'compatibility_level': str,
                    'percentage': float (0-100),
                    'category_scores': dict,
                    'is_good_match': bool,
                    'key_strengths': list,
                    'key_challenges': list,
                    'improvement_suggestions': list,
                }
        """
        result = cls.calculate_match_score(answers, breed)
        
        # Extract key information
        category_results = result.get('category_scores', {})
        
        # Find strengths (scores >= 0.7)
        strengths = []
        challenges = []
        suggestions = []
        
        for item in result.get('individual_scores', []):
            score = item.get('score', 0)
            question_key = item.get('question', '')
            
            if score >= 0.7:
                # Strength
                strength_text = cls._generate_strength_description(
                    question_key,
                    item.get('user_answer'),
                    breed
                )
                if strength_text:
                    strengths.append(strength_text)
            elif score < 0.5:
                # Challenge - need improvement
                improvement = cls._generate_improvement_suggestion(
                    question_key,
                    item.get('user_answer'),
                    item.get('breed_value'),
                    breed,
                    score
                )
                if improvement:
                    challenges.append(improvement['title'])
                    suggestions.append(improvement['action'])
        
        return {
            'overall_score': result['score'],
            'compatibility_level': result['compatibility_level'],
            'percentage': round(result['score'], 1),
            'category_scores': {
                k: round(v.get('raw_score', 0) * 100, 1)
                for k, v in category_results.items()
            },
            'is_good_match': result['score'] >= 70,
            'key_strengths': strengths[:3],  # Top 3 strengths
            'key_challenges': challenges[:3],  # Top 3 challenges
            'improvement_suggestions': suggestions[:3],  # Top 3 actions
            'total_score_breakdown': result['score'],
            'mismatches': result.get('mismatches', [])[:3],
        }
    
    @classmethod
    def find_top_matches(cls, answers, limit=5):
        """
        Find top N most compatible pets based on quiz answers.
        
        Queries all active, non-deleted breeds and calculates compatibility scores,
        returning the highest-scoring matches ranked by compatibility.
        
        Args:
            answers (dict): User quiz responses with question keys as dict keys
            limit (int): Maximum number of matches to return (default: 5)
            
        Returns:
            list: Sorted list of dicts with structure:
                {
                    'breed': Breed model instance,
                    'score': float (0-100),
                    'level': str (Excellent/Good/Moderate/Low/Poor),
                    'mismatches': list of mismatch descriptions,
                    'details': dict with complete scoring breakdown
                }
                
        Note:
            Results are sorted by score in descending order (best matches first).
            Only includes active breeds (is_active=True, deleted_at=None).
        """
        matches = []
        
        # Query all active breeds
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
                'details': result,
            })
        
        # Sort by score descending
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        return matches[:limit]
    
    @classmethod
    def get_improvement_suggestions(cls, answers, breed):
        """
        Generate specific, actionable suggestions to improve compatibility with a breed.
        
        Performs detailed analysis of each quiz question to identify:
        - Strength areas: Questions where user is well-matched (score >= 0.95)
        - Improvement areas: Questions where user could adjust (score < 0.95)
        - Priority levels: High (score < 0.5) or Medium (score 0.5-0.95)
        
        Args:
            answers (dict): User quiz responses
            breed (Breed): Breed model instance
            
        Returns:
            dict: Comprehensive suggestions with structure:
                {
                    'breed_name': str,
                    'species_name': str,
                    'current_score': float,
                    'compatibility_level': str,
                    'strength_areas': list of positive descriptions,
                    'improvement_areas': list of dicts with title, current, ideal, action, priority,
                    'total_improvement_areas': int,
                    'suggestions': list of action strings (backward compatibility),
                    'mismatches': list of detailed mismatch descriptions
                }
        """
        result = cls.calculate_match_score(answers, breed)
        suggestions = []
        strength_areas = []
        improvement_areas = []
        
        # Analyze individual scores for all questions
        for item in result['individual_scores']:
            question_key = item['question']
            user_answer = item['user_answer']
            breed_value = item['breed_value']
            match_score = item['score']
            
            # If perfect match, add to strength areas
            if match_score >= 0.95:
                strength = cls._generate_strength_description(question_key, user_answer, breed)
                if strength:
                    strength_areas.append(strength)
            
            # If not perfect match, generate improvement suggestion
            elif match_score < 0.95:
                suggestion = cls._generate_improvement_suggestion(
                    question_key,
                    user_answer,
                    breed_value,
                    breed,
                    match_score
                )
                if suggestion:
                    improvement_areas.append({
                        'title': suggestion['title'],
                        'current': suggestion['current'],
                        'ideal': suggestion['ideal'],
                        'action': suggestion['action'],
                        'priority': 'High' if match_score < 0.5 else 'Medium'
                    })
        
        return {
            'breed_name': breed.name,
            'species_name': breed.species.name,
            'current_score': result['score'],
            'compatibility_level': result['compatibility_level'],
            'suggestions': [s['action'] for s in improvement_areas],  # For backward compatibility
            'improvement_areas': improvement_areas,  # Detailed improvement info
            'strength_areas': strength_areas,
            'mismatches': result['mismatches'],
            'total_improvement_areas': len(improvement_areas),
        }
    
    @staticmethod
    def _generate_strength_description(question_key, user_answer, breed):
        """
        Generate human-readable description of user strengths for this breed.
        
        Creates positive affirmations highlighting areas where the user's
        characteristics align well with breed requirements.
        
        Args:
            question_key (str): Quiz question identifier
            user_answer (str): User's response value
            breed (Breed): Breed model instance
            
        Returns:
            str: Formatted strength description or None if not applicable
        """
        
        strengths_map = {
            'energy_level': (
                f"✅ Perfect energy match: Your {user_answer} activity level matches {breed.name}'s needs"
            ),
            'exercise_needs': (
                f"✅ Exercise alignment: You can provide the {user_answer} exercise {breed.name} needs"
            ),
            'daily_care_time': (
                f"✅ Time commitment: You have {user_answer} available, matching {breed.name}'s care needs"
            ),
            'grooming_needs': (
                f"✅ Grooming ready: You're willing to groom {user_answer}, perfect for {breed.name}"
            ),
            'space_needs': (
                f"✅ Space ready: Your {user_answer} space is ideal for {breed.name}"
            ),
            'experience_required': (
                f"✅ Experience match: Your {user_answer} experience is perfect for {breed.name}"
            ),
            'monthly_cost_level': (
                f"✅ Budget ready: Your {user_answer} budget aligns with {breed.name}'s costs"
            ),
            'noise_level': (
                f"✅ Noise compatibility: Your {user_answer} home suits {breed.name}'s noise level"
            ),
            'social_needs': (
                f"✅ Social alignment: Your {user_answer} attention matches {breed.name}'s needs"
            ),
            'child_friendly': (
                f"✅ Family ready: {breed.name} is great with children, matching your household"
            ),
            'dog_friendly': (
                f"✅ Dog compatible: {breed.name} is dog-friendly, perfect for your home"
            ),
            'cat_friendly': (
                f"✅ Cat compatible: {breed.name} is cat-friendly, perfect for your home"
            ),
            'small_pet_friendly': (
                f"✅ Small pet safe: {breed.name} is safe with small pets in your household"
            ),
            'preventive_care_level': (
                f"✅ Health-conscious: Your commitment to preventive care matches {breed.name}'s needs"
            ),
            'stress_sensitivity': (
                f"✅ Stable environment: Your home's stability is perfect for {breed.name}"
            ),
            'lifespan': (
                f"✅ Long-term commitment: You can provide {breed.name} with a stable, long-term home"
            ),
            'care_cost': (
                f"✅ Financial alignment: Your budget matches {breed.name}'s estimated care costs"
            ),
        }
        
        return strengths_map.get(question_key)
    
    @staticmethod
    def _generate_improvement_suggestion(question_key, user_answer, breed_value, breed, score):
        """
        Generate detailed improvement suggestions with actionable steps.
        
        Creates practical recommendations showing the gap between user's current
        situation and breed requirements, with specific actions to improve alignment.
        
        Args:
            question_key (str): Quiz question identifier
            user_answer (str): User's current response
            breed_value (any): Breed's requirement value
            breed (Breed): Breed model instance
            score (float): Current match score (0-1) for this question
            
        Returns:
            dict: Improvement details or None if not applicable
                {
                    'title': str,  # Short category title
                    'current': str,  # User's current situation
                    'ideal': str,  # Breed's requirement
                    'action': str,  # Specific actionable suggestion
                }
        """
        
        actions_map = {
            'energy_level': "💡 Adjust your lifestyle to increase activity levels and outdoor time with {breed_name}",
            'exercise_needs': "💡 Schedule daily exercise routines like walks, runs, or playtime to meet {breed_name}'s needs",
            'noise_level': "💡 Plan your home environment to minimize loud noises or create quiet spaces for {breed_name}",
            'social_needs': "💡 Dedicate more time for bonding, playtime, and interaction with {breed_name}",
            'handling_tolerance': "💡 Create a calm, structured home environment with predictable routines for {breed_name}",
            'daily_care_time': "💡 Rearrange your schedule or hire help to meet {breed_name}'s daily care requirements",
            'grooming_needs': "💡 Schedule regular grooming sessions or hire a professional groomer for {breed_name}",
            'experience_required': "💡 Take training courses, join breed communities, or consult with experienced owners before getting {breed_name}",
            'space_needs': "💡 Optimize your space with enrichment items, climbing areas, or outdoor access for {breed_name}",
            'environment_complexity': "💡 Be prepared to invest in proper setups like enclosures, tanks, or special housing for {breed_name}",
            'monthly_cost_level': "💡 Budget for higher monthly expenses including food, toys, and veterinary care for {breed_name}",
            'emergency_care_risk': "💡 Set aside an emergency fund and identify vets near you for {breed_name}'s unexpected health needs",
            'lifetime_cost_level': "💡 Research and plan for the total lifetime costs of owning {breed_name}",
            'care_cost': "💡 Review the estimated care costs for {breed_name} and ensure it fits your budget",
            'preventive_care_level': "💡 Schedule regular veterinary checkups and preventive care for {breed_name}'s health",
            'stress_sensitivity': "💡 Create a stable, calm home environment to help {breed_name} thrive and reduce stress",
            'common_health_issues': "💡 Learn about {breed_name}'s common health challenges and prepare for potential medical needs",
            'lifespan': "💡 Ensure you can commit to {breed_name} for its expected lifetime of {years} years",
            'child_friendly': "💡 Consider if {breed_name} is suitable for children or find a more family-friendly breed alternative",
            'dog_friendly': "💡 Introduce {breed_name} gradually to dogs and consider training for peaceful coexistence",
            'cat_friendly': "💡 Plan careful introductions between {breed_name} and your cats with proper supervision",
            'small_pet_friendly': "💡 Keep small pets separate or train {breed_name} with proper supervision and boundaries",
            'prey_drive': "💡 Be aware of {breed_name}'s hunting instincts and manage interactions with smaller animals carefully",
            'okay_fragile': "💡 Learn proper handling techniques and be extra careful with {breed_name}'s delicate nature",
            'okay_permit': "💡 Research local regulations and prepare necessary permits and documentation for owning {breed_name}",
            'okay_special_vet': "💡 Locate exotic or specialist veterinarians in your area before getting {breed_name}",
        }
        
        action_template = actions_map.get(question_key, "💡 Improve your match with this breed by adjusting your circumstances")
        action = action_template.format(breed_name=breed.name)
        
        improvement_suggestions = {
            'energy_level': {
                'title': 'Activity Level',
                'current': f"You prefer: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value}",
                'action': action
            },
            'exercise_needs': {
                'title': 'Daily Exercise',
                'current': f"You can provide: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value}",
                'action': action
            },
            'noise_level': {
                'title': 'Noise Tolerance',
                'current': f"Your tolerance: {user_answer}",
                'ideal': f"{breed.name} produces: {breed_value} noise",
                'action': action
            },
            'social_needs': {
                'title': 'Social Attention',
                'current': f"You prefer: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value}",
                'action': action
            },
            'handling_tolerance': {
                'title': 'Home Calmness',
                'current': f"Your home is: {user_answer}",
                'ideal': f"{breed.name} prefers: {breed_value}",
                'action': action
            },
            'daily_care_time': {
                'title': 'Daily Care Time',
                'current': f"You have available: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value}",
                'action': action
            },
            'grooming_needs': {
                'title': 'Grooming Commitment',
                'current': f"You can groom: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value}",
                'action': action
            },
            'experience_required': {
                'title': 'Experience Level',
                'current': f"Your experience: {user_answer}",
                'ideal': f"{breed.name} best for: {breed_value}",
                'action': action
            },
            'space_needs': {
                'title': 'Living Space',
                'current': f"Your space: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value}",
                'action': action
            },
            'environment_complexity': {
                'title': 'Environment Setup',
                'current': f"Your capability: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value}",
                'action': action
            },
            'monthly_cost_level': {
                'title': 'Monthly Budget',
                'current': f"Your budget: {user_answer}",
                'ideal': f"{breed.name} costs: {breed_value}",
                'action': action
            },
            'emergency_care_risk': {
                'title': 'Emergency Care',
                'current': f"Your capability: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value}",
                'action': action
            },
            'lifetime_cost_level': {
                'title': 'Lifetime Costs',
                'current': f"Your readiness: {user_answer}",
                'ideal': f"{breed.name} costs: {breed_value}",
                'action': action
            },
            'care_cost': {
                'title': 'Estimated Care Costs',
                'current': f"Your budget: {user_answer}",
                'ideal': f"{breed.name} estimated: {breed_value}",
                'action': action
            },
            'preventive_care_level': {
                'title': 'Preventive Care Requirements',
                'current': f"Your willingness: {user_answer}",
                'ideal': f"{breed.name} needs: {breed_value}",
                'action': action
            },
            'stress_sensitivity': {
                'title': 'Stress Sensitivity',
                'current': f"Your lifestyle stability: {user_answer}",
                'ideal': f"{breed.name} sensitivity: {breed_value}",
                'action': action
            },
            'common_health_issues': {
                'title': 'Health Challenges',
                'current': f"Your preparedness: {user_answer}",
                'ideal': f"{breed.name} may face: {breed_value if breed_value else 'No common issues'}",
                'action': action
            },
            'lifespan': {
                'title': 'Lifespan Commitment',
                'current': f"Your commitment: {user_answer}",
                'ideal': f"{breed.name} lifespan: {breed_value}",
                'action': action
            },
            'child_friendly': {
                'title': 'Child Compatibility',
                'current': f"You have: {user_answer}",
                'ideal': f"{breed.name} is: {'Child-friendly' if breed_value else 'Not recommended for children'}",
                'action': action
            },
            'dog_friendly': {
                'title': 'Dog Compatibility',
                'current': f"You have: {'Dogs' if user_answer == 'Yes' else 'No dogs'}",
                'ideal': f"{breed.name} is: {'Dog-friendly' if breed_value else 'Not dog-friendly'}",
                'action': action
            },
            'cat_friendly': {
                'title': 'Cat Compatibility',
                'current': f"You have: {'Cats' if user_answer == 'Yes' else 'No cats'}",
                'ideal': f"{breed.name} is: {'Cat-friendly' if breed_value else 'Not cat-friendly'}",
                'action': action
            },
            'small_pet_friendly': {
                'title': 'Small Pet Safety',
                'current': f"You have: {'Small pets' if user_answer == 'Yes' else 'No small pets'}",
                'ideal': f"{breed.name} is: {'Safe with small pets' if breed_value else 'Not safe with small pets'}",
                'action': action
            },
            'prey_drive': {
                'title': 'Prey Drive',
                'current': f"Your comfort: {user_answer}",
                'ideal': f"{breed.name} has: {breed_value} prey drive",
                'action': action
            },
            'okay_fragile': {
                'title': 'Fragility Tolerance',
                'current': f"You prefer: {'Fragile animals' if user_answer == 'Yes' else 'Hardy animals'}",
                'ideal': f"{breed.name} is: {'Fragile and delicate' if breed_value else 'Hardy'}",
                'action': action
            },
            'okay_permit': {
                'title': 'Legal Requirements',
                'current': f"You're: {'Willing to deal with permits' if user_answer == 'Yes' else 'Prefer no permits'}",
                'ideal': f"{breed.name}: {'Requires permits' if breed_value else 'No permits needed'}",
                'action': action
            },
            'okay_special_vet': {
                'title': 'Specialist Vet Access',
                'current': f"You can: {'Access special vets' if user_answer == 'Yes' else 'Only use regular vets'}",
                'ideal': f"{breed.name}: {'Needs exotic vet care' if breed_value else 'Regular vet care is fine'}",
                'action': action
            },
        }
        
        return improvement_suggestions.get(question_key)
