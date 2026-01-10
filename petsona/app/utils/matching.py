def calculate_compatibility(answers, breed):
    """
    Advanced Pet Compatibility Calculation (0-100)
    
    Comprehensive scoring across 7 dimensions:
    1. Lifestyle & Activity (energy, exercise, time)
    2. Experience & Training (experience_required, trainability, temperament_tolerance)
    3. Space & Environment (space_needs, environment_complexity, min_enclosure_size)
    4. Grooming & Care (grooming_needs, care intensity)
    5. Household Compatibility (children, other pets)
    6. Financial Reality (monthly_cost_level, emergency_care_risk, lifetime_cost_level)
    7. Species-Specific Safety (prey_drive, fragility, permits, special vets)
    """
    
    # Category weights - prioritize safety and experience
    category_weights = {
        'lifestyle': 1.15,
        'experience': 1.35,  # Most critical - prevents abandonment
        'space': 1.10,
        'care': 1.05,
        'household': 1.20,
        'financial': 1.0,
        'safety': 1.25,  # Important for responsible ownership
    }
    
    # Individual question weights within categories
    question_weights = {
        # Lifestyle (1.15 base)
        'energy_level': 0.95,
        'exercise_needs': 0.95,
        'noise_level': 0.80,
        'social_needs': 0.85,
        'handling_tolerance': 0.85,
        'daily_care_time': 0.90,
        
        # Experience (1.35 base)
        'experience_required': 1.00,
        'trainability': 0.95,
        'temperament_tolerance': 0.95,
        
        # Space (1.10 base)
        'space_needs': 0.90,
        'environment_complexity': 0.85,
        'min_enclosure_size': 0.85,
        
        # Care (1.05 base)
        'grooming_needs': 0.90,
        
        # Household (1.20 base)
        'child_friendly': 0.95,
        'dog_friendly': 0.90,
        'cat_friendly': 0.90,
        'small_pet_friendly': 0.90,
        
        # Financial (1.0 base)
        'monthly_cost_level': 0.85,
        'emergency_care_risk': 0.90,
        'lifetime_cost_level': 0.85,
        
        # Safety (1.25 base)
        'prey_drive': 0.95,
        'okay_fragile': 0.95,
        'okay_permit': 0.90,
        'okay_special_vet': 0.85,
    }
    
    # Mapping of user answers to breed attributes
    category_mapping = {
        'lifestyle': {
            'energy_level': 'energy_level',
            'exercise_needs': 'exercise_needs',
            'noise_level': 'noise_level',
            'social_needs': 'social_needs',
            'handling_tolerance': 'handling_tolerance',
            'daily_care_time': 'time_commitment',
        },
        'experience': {
            'experience_required': 'experience_required',
            'trainability': 'trainability',
            'temperament_tolerance': 'trainability',  # Proxy
        },
        'space': {
            'space_needs': 'space_needs',
            'environment_complexity': 'environment_complexity',
            'min_enclosure_size': 'min_enclosure_size',
        },
        'care': {
            'grooming_needs': 'grooming_needs',
        },
        'household': {
            'child_friendly': 'child_friendly',
            'dog_friendly': 'dog_friendly',
            'cat_friendly': 'cat_friendly',
            'small_pet_friendly': 'small_pet_friendly',
        },
        'financial': {
            'monthly_cost_level': 'monthly_cost_level',
            'emergency_care_risk': 'emergency_care_risk',
            'lifetime_cost_level': 'lifetime_cost_level',
        },
        'safety': {
            'prey_drive': 'prey_drive',
            'okay_fragile': 'fragile_species',
            'okay_permit': 'requires_permit',
            'okay_special_vet': 'special_vet_required',
        },
    }
    
    category_scores = {}
    mismatches = []
    total_weighted_score = 0
    total_weight = 0
    
    # Score each category
    for category, questions_map in category_mapping.items():
        category_score = 0
        category_weight = 0
        
        for user_key, breed_attr in questions_map.items():
            user_answer = answers.get(user_key)
            if user_answer is None:
                continue
            
            # Special handling for species-level attributes
            if category == 'safety' and breed_attr not in ['prey_drive']:
                # These come from species, not breed
                breed_value = getattr(breed.species, breed_attr, None)
            else:
                breed_value = getattr(breed, breed_attr, None)
            
            q_weight = question_weights.get(user_key, 0.8)
            
            # Calculate match score for this question
            match_score = _calculate_question_score(
                user_key, user_answer, breed_value, breed
            )
            
            category_score += match_score * q_weight
            category_weight += q_weight
        
        if category_weight > 0:
            # Normalize to 0-1 and apply category weight
            normalized = category_score / category_weight
            weighted = normalized * category_weights.get(category, 1.0)
            category_scores[category] = {
                'raw_score': round(normalized, 2),
                'weighted_score': round(weighted, 2),
                'weight': category_weights.get(category, 1.0)
            }
            total_weighted_score += weighted
            total_weight += category_weights.get(category, 1.0)
    
    # Convert to 0-100 scale
    final_score = (total_weighted_score / total_weight * 100) if total_weight > 0 else 0
    final_score = max(0, min(100, final_score))  # Clamp to 0-100
    
    return {
        'score': round(final_score, 1),
        'category_scores': category_scores,
        'mismatches': mismatches,
    }


def _calculate_question_score(question_key, user_answer, breed_value, breed):
    """
    Calculate match score (0-1) for a specific question
    Handles special cases where direct matching isn't appropriate
    """
    
    # Convert 'Yes'/'No' to boolean for boolean comparisons
    if user_answer in ['Yes', 'No']:
        user_bool = user_answer == 'Yes'
    else:
        user_bool = None
    
    # Special handling for specific questions
    if question_key == 'okay_fragile':
        # User says 'No' (doesn't want fragile) but species is fragile = bad
        if not user_bool and breed.species.fragile_species:
            return 0.0
        return 1.0
    
    elif question_key == 'okay_permit':
        # User says 'No' (doesn't want permits) but species requires = bad
        if not user_bool and breed.species.requires_permit:
            return 0.0
        return 1.0
    
    elif question_key == 'okay_special_vet':
        # User says 'No' but species needs special vet = reduced score
        if not user_bool and breed.species.special_vet_required:
            return 0.5  # Softer penalty
        return 1.0
    
    elif question_key == 'daily_care_time':
        # Map user's available time to breed's time_commitment
        time_mapping = {
            'Less than 1 hour': 'Low',
            '1-2 hours': 'Medium',
            '2-4 hours': 'High',
            'More than 4 hours': 'High',
        }
        mapped_answer = time_mapping.get(user_answer)
        breed_value = breed.time_commitment
        return 1.0 if mapped_answer == breed_value else 0.5
    
    elif question_key == 'min_enclosure_size':
        # User's enclosure capacity vs breed's requirement
        # 0 = No, 1 = Small, 2 = Large
        try:
            user_num = int(user_answer) if isinstance(user_answer, str) else user_answer
            breed_num = breed.min_enclosure_size or 0
            if breed_num == 0:
                return 1.0  # No enclosure needed
            if user_num < breed_num:
                # User can't provide needed size
                return max(0, 1.0 - (breed_num - user_num) * 0.3)
            return 1.0
        except:
            return 0.5
    
    elif question_key == 'temperament_tolerance':
        # User's patience with difficult pets vs trainability
        patience_mapping = {
            'Not well': 'Difficult',
            'I can try': 'Moderate',
            'I handle them well': 'Easy',
        }
        mapped_answer = patience_mapping.get(user_answer)
        breed_value = breed.trainability
        # Better score if user's patience >= breed's difficulty
        if mapped_answer == 'Easy':
            return 1.0 if breed_value in ['Easy', 'Moderate', 'Difficult'] else 0.8
        elif mapped_answer == 'Moderate':
            return 1.0 if breed_value in ['Easy', 'Moderate'] else 0.6
        else:
            return 1.0 if breed_value == 'Easy' else 0.3
    
    elif question_key == 'trainability':
        # User's patience mapping to breed trainability
        patience_mapping = {
            'Difficult': 'Not very patient',
            'Moderate': 'Somewhat patient',
            'Easy': 'Very patient',
        }
        # Find user's patience level
        user_patience = None
        for key, val in patience_mapping.items():
            if user_answer == val:
                user_patience = key
                break
        
        if user_patience is None:
            return 0.5
        
        breed_trainability = breed.trainability
        if user_patience == 'Easy':
            return 1.0 if breed_trainability in ['Easy', 'Moderate'] else 0.7
        elif user_patience == 'Moderate':
            return 1.0 if breed_trainability in ['Easy', 'Moderate'] else 0.5
        else:
            return 1.0 if breed_trainability == 'Easy' else 0.3
    
    # Standard direct comparison
    if breed_value is None:
        return 0.5  # Unknown attribute
    
    # String comparison
    if isinstance(user_answer, bool) and isinstance(breed_value, bool):
        return 1.0 if user_answer == breed_value else 0.0
    else:
        return 1.0 if str(user_answer) == str(breed_value) else 0.0
