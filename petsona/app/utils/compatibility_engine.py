"""
Advanced Pet Compatibility Matching Engine

This module implements a sophisticated matching algorithm that calculates
compatibility scores between user preferences and pet breeds/species.

Two matching modes:
1. Random Matching: Finds top 5 most compatible pets
2. Specific Breed: Analyzes compatibility with a chosen breed and suggests improvements
"""

from app.models.breed import Breed
from app.models.species import Species


class CompatibilityEngine:
    """Main compatibility matching engine"""
    
    # Mapping of quiz questions to breed attributes
    # Value can be a single attribute or tuple (attribute, transform_function)
    ATTRIBUTE_MAPPING = {
        # Lifestyle & Activity
        'energy_level': 'energy_level',
        'exercise_needs': 'exercise_needs',
        
        # Noise & Environment
        'noise_level': 'noise_level',
        'handling_tolerance': 'handling_tolerance',
        'environment_complexity': 'environment_complexity',
        
        # Social Interaction
        'social_needs': 'social_needs',
        
        # Care & Time
        'daily_care_time': ('time_commitment', 'map_care_time'),
        'grooming_needs': 'grooming_needs',
        'trainability': ('trainability', None),
        
        # Experience
        'experience_required': 'experience_required',
        'temperament_tolerance': ('trainability', None),  # Proxy for handling difficulty
        
        # Space
        'space_needs': 'space_needs',
        'min_enclosure_size': ('min_enclosure_size', 'map_enclosure_size'),
        
        # Budget & Costs
        'monthly_cost_level': 'monthly_cost_level',
        'emergency_care_risk': 'emergency_care_risk',
        'lifetime_cost_level': 'lifetime_cost_level',
        
        # Household Compatibility
        'child_friendly': 'child_friendly',
        'dog_friendly': 'dog_friendly',
        'cat_friendly': 'cat_friendly',
        'small_pet_friendly': 'small_pet_friendly',
        
        # Species Traits
        'prey_drive': 'prey_drive',
        'okay_fragile': ('fragile_species', 'map_fragile'),
        'okay_permit': ('requires_permit', 'map_permit'),
        'okay_special_vet': ('special_vet_required', 'map_vet'),
    }
    
    # Weights for different matching categories (influences priority)
    CATEGORY_WEIGHTS = {
        'lifestyle': 1.2,      # Energy, exercise, time
        'space': 1.1,          # Living situation match
        'experience': 1.3,     # Very important - prevents abandonment
        'costs': 1.0,          # Budget compatibility
        'household': 1.15,     # Pet compatibility with family
        'personality': 1.2,    # Temperament & social needs
        'safety': 0.9,         # Risk factors
    }
    
    # Individual question weights (0.0-1.0)
    QUESTION_WEIGHTS = {
        'energy_level': 0.9,
        'exercise_needs': 0.9,
        'experience_required': 1.0,  # Critical!
        'temperament_tolerance': 0.95,
        'daily_care_time': 0.85,
        'space_needs': 0.8,
        'monthly_cost_level': 0.75,
        'child_friendly': 0.9,
        'dog_friendly': 0.85,
        'cat_friendly': 0.85,
        'small_pet_friendly': 0.85,
        'prey_drive': 0.8,
    }
    
    @staticmethod
    def map_care_time(user_value):
        """Map user's daily care time to breed's time_commitment"""
        mapping = {
            'Less than 1 hour': 'Low',
            '1-2 hours': 'Medium',
            '2-4 hours': 'High',
            'More than 4 hours': 'High',
        }
        return mapping.get(user_value, 'Medium')
    
    @staticmethod
    def map_enclosure_size(user_value):
        """Map user's enclosure willingness to breed requirement"""
        mapping = {
            '0': 0,      # No
            '1': 1,      # Small ones
            '2': 2,      # Large ones
        }
        return int(mapping.get(str(user_value), 0))
    
    @staticmethod
    def map_fragile(user_value):
        """Map user's fragile pet tolerance to species fragility"""
        # If user says 'No' and species is fragile = bad match
        return user_value == 'Yes'
    
    @staticmethod
    def map_permit(user_value):
        """Map user's permit tolerance"""
        return user_value == 'Yes'
    
    @staticmethod
    def map_vet(user_value):
        """Map user's special vet access"""
        return user_value == 'Yes'
    
    @classmethod
    def calculate_match_score(cls, answers, breed):
        """
        Calculate comprehensive compatibility score (0-100)
        
        Args:
            answers: dict of user quiz answers
            breed: Breed model instance
            
        Returns:
            dict with score and detailed breakdown
        """
        total_score = 0
        total_weight = 0
        category_scores = {}
        individual_scores = []
        mismatches = []  # Track specific incompatibilities
        
        for question_key, attribute in cls.ATTRIBUTE_MAPPING.items():
            user_answer = answers.get(question_key)
            
            if user_answer is None:
                continue
            
            # Get question weight
            weight = cls.QUESTION_WEIGHTS.get(question_key, 0.8)
            
            # Handle attribute transformation
            if isinstance(attribute, tuple):
                attr_name, transform_func = attribute
                if transform_func:
                    user_answer = getattr(cls, transform_func)(user_answer)
            else:
                attr_name = attribute
            
            # Get breed attribute value
            breed_value = getattr(breed, attr_name, None)
            
            # Handle special cases
            if attr_name == 'fragile_species':
                # If user doesn't want fragile pets but breed's species is fragile
                if user_answer is False and breed.species.fragile_species:
                    score = 0
                    mismatches.append(f"This breed's species is fragile, but you prefer hardy pets")
                else:
                    score = 1.0
            
            elif attr_name == 'requires_permit':
                if user_answer is False and breed.species.requires_permit:
                    score = 0
                    mismatches.append(f"This breed requires special permits, but you prefer not to deal with them")
                else:
                    score = 1.0
            
            elif attr_name == 'special_vet_required':
                if user_answer is False and breed.species.special_vet_required:
                    score = 0.4  # Softer penalty
                    mismatches.append(f"This breed may require exotic vets")
                else:
                    score = 1.0
            
            elif attr_name == 'min_enclosure_size':
                # User_answer and breed_value are numbers
                if breed_value and user_answer < breed_value:
                    score = max(0, 1.0 - (breed_value - user_answer) * 0.3)
                    if score < 0.5:
                        mismatches.append(f"Your living space may be too small for this breed's needs")
                else:
                    score = 1.0
            
            elif breed_value is None:
                score = 0.5  # Neutral if attribute not set
            
            else:
                # Direct comparison
                score = 1.0 if str(user_answer) == str(breed_value) else 0.0
            
            # Apply weight
            weighted_score = score * weight
            total_score += weighted_score
            total_weight += weight
            
            individual_scores.append({
                'question': question_key,
                'user_answer': user_answer,
                'breed_value': breed_value,
                'score': score,
                'weight': weight,
            })
        
        # Calculate final percentage
        final_score = (total_score / total_weight * 100) if total_weight > 0 else 0
        final_score = min(100, max(0, final_score))  # Clamp 0-100
        
        return {
            'score': round(final_score, 1),
            'total_weight': total_weight,
            'individual_scores': individual_scores,
            'mismatches': mismatches,
            'compatibility_level': cls._get_compatibility_level(final_score),
        }
    
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
        Generate specific suggestions to improve compatibility with a breed
        
        Args:
            answers: dict of user quiz answers
            breed: Breed model instance
            
        Returns:
            dict with suggestions and action items
        """
        result = cls.calculate_match_score(answers, breed)
        suggestions = []
        
        # Analyze individual scores
        for item in result['individual_scores']:
            if item['score'] < 0.5:  # Focus on low matches
                suggestion = cls._generate_suggestion(
                    item['question'],
                    item['user_answer'],
                    item['breed_value'],
                    breed
                )
                if suggestion:
                    suggestions.append(suggestion)
        
        return {
            'breed_name': breed.name,
            'species_name': breed.species.name,
            'current_score': result['score'],
            'compatibility_level': result['compatibility_level'],
            'suggestions': suggestions,
            'mismatches': result['mismatches'],
            'strength_areas': [
                item['question'] for item in result['individual_scores']
                if item['score'] >= 0.8
            ]
        }
    
    @staticmethod
    def _generate_suggestion(question_key, user_answer, breed_value, breed):
        """Generate a specific improvement suggestion"""
        
        suggestions_map = {
            'energy_level': (
                f"You prefer {{user}} activity, but {breed.name} has {{breed}} energy. "
                "Consider matching your activity level with the breed's needs."
            ),
            'exercise_needs': (
                f"You can provide {{user}} exercise, but {breed.name} needs {{breed}} exercise. "
                "This might be a compatibility concern."
            ),
            'daily_care_time': (
                f"You have {{user}} available daily, but {breed.name} may need {{breed}} care. "
                "Ensure you can commit the necessary time."
            ),
            'grooming_needs': (
                f"You're willing to groom {{user}}, but {breed.name} needs {{breed}} grooming. "
                "Schedule regular grooming sessions."
            ),
            'space_needs': (
                f"Your space is {{user}}, but {breed.name} prefers {{breed}} space. "
                "Consider ways to enrich your environment for this breed."
            ),
            'experience_required': (
                f"You're {{user}}, but {breed.name} is best for {{breed}} owners. "
                "Consider finding a more beginner-friendly breed or taking training courses."
            ),
            'monthly_cost_level': (
                f"Your budget is {{user}}, but {breed.name} costs {{breed}}. "
                "Ensure you can afford food, veterinary care, and supplies."
            ),
            'child_friendly': (
                f"{breed.name} is {'not ideal' if breed_value is False else 'good'} with children, "
                "which {'does not match' if user_answer != breed_value else 'matches'} your household."
            ),
            'prey_drive': (
                f"{breed.name} has a {{breed}} prey drive, but you prefer {{user}}. "
                "This may affect compatibility with smaller pets."
            ),
        }
        
        template = suggestions_map.get(question_key)
        if template:
            return template.format(user=user_answer, breed=breed_value)
        
        return None
