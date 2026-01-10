"""
Advanced Pet Compatibility Matching Engine

This module implements a sophisticated weighted matching algorithm that calculates
compatibility scores between user preferences and pet breeds/species across 7 key dimensions:

1. Lifestyle & Activity (energy, exercise, time, noise tolerance)
2. Experience & Training (experience required, trainability, temperament tolerance)
3. Space & Environment (living space, enclosures, environmental complexity)
4. Grooming & Care (grooming needs, care intensity)
5. Household Compatibility (children, other pets - dogs, cats, small animals)
6. Financial Reality (monthly costs, emergency care, lifetime costs)
7. Species-Specific Safety (prey drive, fragility, permits, special vets)

Two matching modes:
1. Random Matching: Finds top 5 most compatible pets
2. Specific Breed: Analyzes compatibility with a chosen breed and suggests improvements
"""

from app.models.breed import Breed
from app.models.species import Species


class CompatibilityEngine:
    """Main compatibility matching engine"""
    
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
        
        # ---- FINANCIAL REALITY (3 questions) ----
        'monthly_cost_level': ('monthly_cost_level', 'breed'),
        'emergency_care_risk': ('emergency_care_risk', 'breed'),
        'lifetime_cost_level': ('lifetime_cost_level', 'breed'),
        
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
        'financial': 1.00,       # Standard - affects commitment
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
    def map_exercise_response(user_value):
        """Map exercise frequency response to needs level"""
        mapping = {
            'No': 'Low',
            'Sometimes': 'Medium',
            'Yes, every day': 'High',
        }
        return mapping.get(user_value, 'Medium')
    
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
        Calculate comprehensive compatibility score (0-100) across 7 dimensions.
        
        Scoring Categories:
        1. Lifestyle & Activity: Daily energy, exercise, time commitments
        2. Experience & Training: Experience required, trainability, temperament handling
        3. Space & Environment: Living space, enclosures, environmental complexity
        4. Grooming & Care: Grooming frequency and care intensity
        5. Household Compatibility: Safety with children and other pets
        6. Financial Reality: Monthly costs, emergency care, lifetime expenses
        7. Species-Specific Safety: Prey drive, fragility, permits, special veterinary needs
        
        Args:
            answers: dict of user quiz answers
            breed: Breed model instance
            
        Returns:
            dict with comprehensive score breakdown
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
        """Determine which category a question belongs to"""
        categories_map = {
            'lifestyle': ['energy_level', 'exercise_needs', 'noise_level', 'social_needs', 'handling_tolerance'],
            'experience': ['experience_required', 'trainability', 'temperament_tolerance'],
            'space': ['space_needs', 'environment_complexity', 'min_enclosure_size'],
            'care': ['daily_care_time', 'grooming_needs'],
            'household': ['child_friendly', 'dog_friendly', 'cat_friendly', 'small_pet_friendly'],
            'financial': ['monthly_cost_level', 'emergency_care_risk', 'lifetime_cost_level'],
            'safety': ['prey_drive', 'okay_fragile', 'okay_permit', 'okay_special_vet'],
        }
        
        for category, questions in categories_map.items():
            if question_key in questions:
                return category
        
        return 'lifestyle'  # Default
    
    @classmethod
    def _calculate_question_match_score(cls, question_key, user_answer, attr_name, breed_value, breed):
        """
        Calculate match score (0-1.0) for a specific question.
        Handles special logic where direct matching isn't appropriate.
        """
        
        # ---- SPECIAL CASE: FRAGILE ANIMALS ----
        if question_key == 'okay_fragile':
            user_okay = user_answer == 'Yes'
            if not user_okay and breed.species.fragile_species:
                return 0.0  # Critical mismatch
            return 1.0
        
        # ---- SPECIAL CASE: PERMITS/LEGAL REQUIREMENTS ----
        if question_key == 'okay_permit':
            user_okay = user_answer == 'Yes'
            if not user_okay and breed.species.requires_permit:
                return 0.0  # Critical mismatch
            return 1.0
        
        # ---- SPECIAL CASE: SPECIAL VETERINARY CARE ----
        if question_key == 'okay_special_vet':
            user_okay = user_answer == 'Yes'
            if not user_okay and breed.species.special_vet_required:
                return 0.5  # Soft penalty - not ideal but manageable
            return 1.0
        
        # ---- SPECIAL CASE: DAILY CARE TIME ----
        if question_key == 'daily_care_time':
            mapped_answer = cls.map_care_time(user_answer)
            breed_requirement = breed.time_commitment
            if mapped_answer == breed_requirement:
                return 1.0
            elif mapped_answer == 'High' or breed_requirement == 'Low':
                return 0.9  # User has more than enough
            elif mapped_answer == 'Medium' and breed_requirement == 'High':
                return 0.6  # User might be short
            else:
                return 0.3  # Poor match
        
        # ---- SPECIAL CASE: GROOMING NEEDS ----
        if question_key == 'grooming_needs':
            mapped_answer = cls.map_grooming_response(user_answer)
            breed_requirement = breed.grooming_needs
            if mapped_answer == breed_requirement:
                return 1.0
            elif mapped_answer == 'Very often' or breed_requirement == 'Low':
                return 0.85  # User can do more than needed
            else:
                return 0.4
        
        # ---- SPECIAL CASE: EXERCISE CAPABILITY ----
        if question_key == 'exercise_needs':
            mapped_answer = cls.map_exercise_response(user_answer)
            breed_requirement = breed.exercise_needs
            if mapped_answer == breed_requirement:
                return 1.0
            elif mapped_answer == 'High' or breed_requirement == 'Low':
                return 0.85  # User can do more than needed
            else:
                return 0.4
        
        # ---- SPECIAL CASE: TEMPERAMENT TOLERANCE ----
        if question_key == 'temperament_tolerance':
            user_patience = cls.map_temperament_tolerance(user_answer)
            breed_trainability = breed.trainability
            
            if user_patience == 'Easy':
                # Very patient user - matches all trainability levels
                return 1.0 if breed_trainability in ['Easy', 'Moderate'] else 0.75
            elif user_patience == 'Moderate':
                # Moderate patience - prefer moderate or easy
                return 1.0 if breed_trainability in ['Easy', 'Moderate'] else 0.5
            else:
                # Low patience - only works with easy breeds
                return 1.0 if breed_trainability == 'Easy' else 0.2
        
        # ---- SPECIAL CASE: MIN ENCLOSURE SIZE ----
        if question_key == 'min_enclosure_size':
            try:
                user_capacity = int(user_answer) if isinstance(user_answer, str) else user_answer
                breed_requirement = breed.min_enclosure_size or 0
                
                if breed_requirement == 0:
                    return 1.0  # No enclosure needed
                if user_capacity >= breed_requirement:
                    return 1.0  # User can provide what's needed
                else:
                    # User's capacity is insufficient - penalize
                    shortfall = breed_requirement - user_capacity
                    return max(0, 1.0 - shortfall * 0.4)
            except:
                return 0.5
        
        # ---- SPECIAL CASE: BOOLEAN COMPARISONS (Household) ----
        if isinstance(breed_value, bool):
            user_bool = user_answer == 'Yes'
            if user_bool == breed_value:
                return 1.0
            else:
                # If user wants something breed doesn't support, it's bad
                # If user doesn't care but breed does, it's okay
                return 0.0 if user_bool else 0.4
        
        # ---- DEFAULT: DIRECT STRING COMPARISON ----
        if breed_value is None:
            return 0.5  # Unknown attribute
        
        if str(user_answer).strip() == str(breed_value).strip():
            return 1.0
        else:
            return 0.0
    
    @staticmethod
    def _generate_mismatch_description(question_key, user_answer, breed_value, breed):
        """Generate human-readable description of compatibility mismatches"""
        
        descriptions = {
            'energy_level': f"Energy mismatch: You prefer {user_answer} activity, but {breed.name} has {breed_value} energy",
            'exercise_needs': f"Exercise mismatch: You can provide {user_answer} exercise, but {breed.name} needs {breed_value} exercise",
            'noise_level': f"Noise tolerance mismatch: You prefer {user_answer}, but {breed.name} produces {breed_value} noise",
            'grooming_needs': f"Grooming mismatch: You groom {user_answer}, but {breed.name} needs {breed_value} grooming",
            'space_needs': f"Space mismatch: Your space is {user_answer}, but {breed.name} needs {breed_value} space",
            'experience_required': f"Experience mismatch: You're {user_answer}, but {breed.name} is best for {breed_value} owners",
            'monthly_cost_level': f"Budget mismatch: Your budget is {user_answer}, but {breed.name} costs {breed_value}",
            'daily_care_time': f"Time commitment mismatch: You have {user_answer} available, but {breed.name} may need more care",
            'child_friendly': f"Child safety: {breed.name} is {'not suitable' if breed_value is False else 'suitable'} for children",
            'dog_friendly': f"Dog compatibility: {breed.name} is {'not dog-friendly' if breed_value is False else 'dog-friendly'}",
            'cat_friendly': f"Cat compatibility: {breed.name} is {'not cat-friendly' if breed_value is False else 'cat-friendly'}",
            'small_pet_friendly': f"Small pet safety: {breed.name} is {'not safe' if breed_value is False else 'safe'} with small pets",
            'okay_fragile': f"This {breed.species.name} breed is delicate, but you prefer hardy pets",
            'okay_permit': f"This breed requires special permits, but you prefer not to deal with legal requirements",
            'okay_special_vet': f"This breed may need exotic veterinary care, which isn't available to you",
            'prey_drive': f"Prey drive mismatch: {breed.name} has {breed_value} prey drive",
        }
        
        return descriptions.get(question_key)
    
    @staticmethod
    def _get_compatibility_level(score):
        """Convert score to human-readable compatibility level"""
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
    def find_top_matches(cls, answers, limit=5):
        """
        Find top N most compatible pets based on quiz answers
        
        Args:
            answers: dict of user quiz answers
            limit: number of top matches to return
            
        Returns:
            list of dicts containing breed info and compatibility
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
        Analyzes every quiz question and provides improvement tips for non-optimal matches.
        
        Args:
            answers: dict of user quiz answers
            breed: Breed model instance
            
        Returns:
            dict with detailed suggestions, strength areas, and action items
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
        """Generate description of what the user does well for this breed"""
        
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
        }
        
        return strengths_map.get(question_key)
    
    @staticmethod
    def _generate_improvement_suggestion(question_key, user_answer, breed_value, breed, score):
        """Generate detailed improvement suggestion with actionable steps"""
        
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
