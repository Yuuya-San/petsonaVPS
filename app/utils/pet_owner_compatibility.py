"""
Pet Owner Compatibility Assessment Engine

Calculates compatibility between a pet owner's lifestyle/personality
and their own pet's characteristics and needs.

Architecture:
1. User Lifestyle Mapping - Convert user answers to compatibility metrics
2. Pet Trait Mapping - Extract pet's behavioral traits and Big Five from database
3. Lifestyle Compatibility - Compare user's capacity with pet's needs
4. Personality Compatibility - Compare user's Big Five with pet's Big Five
5. Overall Scoring - Weighted combination of lifestyle + personality factors
6. Results Generation - Compatibility score, breakdown, and insights

Key Differences from Breed Matching:
- Matches USER to their SPECIFIC PET (not general breed compatibility)
- Uses pet's actual stored traits and Big Five scores from database
- Focuses on relationship quality and lifestyle fit
- Generates insights specific to pet's individual characteristics
"""

from typing import Dict, Any, List, Optional, Tuple
from app.utils.big_five_personality import (
    calculate_user_big_five_scores,
    calculate_big_five_compatibility,
    get_big_five_recommendations,
    integrate_big_five_into_compatibility,
)
import math


# ============================================================================
# USER LIFESTYLE ANSWER MAPPING - Convert answers to numeric scores
# ============================================================================

USER_LIFESTYLE_MAPPING = {
    # Activity Level
    'user_activity_level': {
        'Very calm, I mostly relax at home': 1,
        'Moderately active': 3,
        'Very energetic, always busy': 4,
    },
    
    # Daily Time Available
    'user_daily_time': {
        'Less than 1 hour': 1,
        '1-2 hours': 2,
        '2-4 hours': 3,
        'More than 4 hours': 4,
    },
    
    # Experience Level
    'user_experience': {
        'This is my first pet': 1,
        'I\'ve had a few pets': 3,
        'I have extensive pet experience': 4,
    },
    
    # Patience
    'user_patience': {
        'Not very patient': 1,
        'Somewhat patient': 3,
        'Very patient': 4,
    },
    
    # Space
    'user_space': {
        'Small apartment or room': 1,
        'Medium-sized home': 3,
        'Large home with outdoor space': 4,
    },
    
    # Household (Children)
    'user_household': {
        'Yes, young children': 1,
        'Yes, older children': 2,
        'No children': 4,
    },
    
    # Other Pets
    'user_other_pets': {
        'No other pets': 4,
        'Dogs': 2,
        'Cats': 2,
        'Other animals': 2,
        'Multiple different types': 1,
    },
    
    # Routine Structure
    'user_routine': {
        'Very structured, predictable': 4,
        'Somewhat flexible': 3,
        'Quite chaotic and unpredictable': 1,
    },
    
    # Budget
    'user_budget': {
        'Low budget (₱1,000-₱3,000)': 1,
        'Medium budget (₱3,001-₱8,000)': 2,
        'High budget (₱8,001+)': 4,
    },
    
    # Emergency Vet Costs
    'user_emergency': {
        'No, I cannot': 0,
        'Maybe, it would be difficult': 2,
        'Yes, I can manage': 4,
    },
    
    # Social Nature
    'user_social_nature': {
        'I prefer quiet time alone': 1,
        'Balanced mix of social and alone time': 3,
        'I love social interaction and people': 4,
    },
    
    # Adaptability
    'user_adaptability': {
        'I get stressed by changes': 1,
        'I adapt gradually': 3,
        'I adapt quickly to change': 4,
    },
    
    # Responsibility
    'user_responsibility': {
        'Sometimes forgetful': 1,
        'Generally reliable': 3,
        'Very dependable and organized': 4,
    },
    
    # Affection Needs
    'user_affection_needs': {
        'Not very important': 1,
        'Moderately important': 3,
        'Very important, I value bonding': 4,
    },
    
    # Commitment
    'user_commitment': {
        'Not sure yet': 1,
        'Somewhat committed': 2,
        'Fully committed for their lifetime': 4,
    },
}


# PET TRAIT MAPPING - How pet traits map to user answer questions
PET_TRAIT_MAPPINGS = {
    'activity_level': {
        'user_activity_level': {
            'Very calm': 1,
            'Moderately active': 2.5,
            'Very energetic': 4,
        },
        'user_daily_time': {
            'Very calm': 2,
            'Moderately active': 3,
            'Very energetic': 4,
        },
    },
    'animal_social_behavior': {
        'user_household': {
            'Aggressive or territorial': 4,
            'Nervous or avoidant': 2,
            'Neutral': 3,
            'Friendly and playful': 1,
        },
        'user_other_pets': {
            'Aggressive or territorial': 0,
            'Nervous or avoidant': 2,
            'Neutral': 3,
            'Friendly and playful': 4,
        },
    },
    'people_sociality': {
        'user_social_nature': {
            'Very shy': 1,
            'Selectively friendly': 2,
            'Friendly with most people': 3,
            'Extremely social': 4,
        },
    },
    'independence_level': {
        'user_daily_time': {
            'Very dependent/clingy': 4,
            'Balanced': 3,
            'Very independent': 1,
        },
    },
    'adaptability': {
        'user_adaptability': {
            'Gets stressed easily': 4,
            'Needs time to adjust': 2,
            'Adapts quickly': 1,
        },
        'user_routine': {
            'Gets stressed easily': 1,
            'Needs time to adjust': 2,
            'Adapts quickly': 3,
        },
    },
    'affection_level': {
        'user_affection_needs': {
            'Rarely affectionate': 1,
            'Occasionally affectionate': 2,
            'Very affectionate': 4,
        },
    },
    'alone_behavior': {
        'user_daily_time': {
            'Gets anxious or destructive': 4,
            'Usually stays calm': 2,
            'Prefers being alone': 1,
        },
    },
    'trainability': {
        'user_patience': {
            'Difficult to train': 4,
            'Learns gradually': 2,
            'Learns quickly': 1,
        },
        'user_responsibility': {
            'Difficult to train': 1,
            'Learns gradually': 2,
            'Learns quickly': 4,
        },
    },
}


def calculate_pet_owner_compatibility(pet, user_answers: Dict[str, str]) -> Dict[str, Any]:
    """
    Calculate overall pet-owner compatibility score.
    
    Process:
    1. Parse user lifestyle answers into normalized scores
    2. Extract pet's behavioral traits and Big Five from database
    3. Calculate lifestyle compatibility (15-question answers vs pet needs)
    4. Calculate personality compatibility (user Big Five vs pet Big Five)
    5. Weighted combination of both factors
    6. Generate detailed insights and recommendations
    
    Args:
        pet: MyPet model instance with all attributes and traits
        user_answers: Dict of user answers {question_key: answer_text}
    
    Returns:
        Dictionary containing:
        - overall_score: 0-100 compatibility percentage
        - compatibility_level: 'Excellent'|'Good'|'Moderate'|'Fair'|'Poor'
        - lifestyle_score: Compatibility with pet's behavioral needs (0-100)
        - personality_score: Big Five personality match (0-100)
        - category_breakdown: {category_name: {score, weight, status}}
        - strengths: List of compatibility strengths
        - considerations: List of potential challenges
        - recommendations: Actionable suggestions
        - insights: Detailed explanations
    """
    
    # ========================================================================
    # STEP 1: CALCULATE LIFESTYLE COMPATIBILITY
    # ========================================================================
    lifestyle_result = _calculate_lifestyle_compatibility(pet, user_answers)
    lifestyle_score = lifestyle_result['score']
    lifestyle_breakdown = lifestyle_result['breakdown']
    lifestyle_insights = lifestyle_result['insights']
    
    # ========================================================================
    # STEP 2: CALCULATE PERSONALITY COMPATIBILITY (BIG FIVE)
    # ========================================================================
    personality_result = _calculate_personality_compatibility(pet, user_answers)
    personality_score = personality_result['score']
    personality_breakdown = personality_result['breakdown']
    personality_insights = personality_result['insights']
    
    # ========================================================================
    # STEP 3: WEIGHTED COMBINATION
    # ========================================================================
    # Lifestyle is weighted slightly higher (60%) as it's more practical
    # Personality is supporting factor (40%) for relationship quality
    overall_score = (lifestyle_score * 0.60) + (personality_score * 0.40)
    overall_score = max(0, min(100, overall_score))  # Clamp to 0-100
    
    # ========================================================================
    # STEP 4: DETERMINE COMPATIBILITY LEVEL
    # ========================================================================
    if overall_score >= 85:
        level = 'Excellent'
        emoji = '🟢'
    elif overall_score >= 70:
        level = 'Good'
        emoji = '🟡'
    elif overall_score >= 55:
        level = 'Moderate'
        emoji = '🟠'
    elif overall_score >= 40:
        level = 'Fair'
        emoji = '🔴'
    else:
        level = 'Poor'
        emoji = '⛔'
    
    # ========================================================================
    # STEP 5: GENERATE CATEGORY BREAKDOWN
    # ========================================================================
    category_breakdown = _generate_category_breakdown(
        pet, user_answers, lifestyle_breakdown, personality_breakdown
    )
    
    # ========================================================================
    # STEP 6: GENERATE INSIGHTS & RECOMMENDATIONS
    # ========================================================================
    strengths = _extract_strengths(lifestyle_insights, personality_insights)
    considerations = _extract_considerations(lifestyle_insights, personality_insights)
    recommendations = _generate_recommendations(
        pet, user_answers, lifestyle_insights, personality_insights
    )
    
    return {
        'overall_score': round(overall_score, 1),
        'compatibility_level': level,
        'compatibility_emoji': emoji,
        'lifestyle_score': round(lifestyle_score, 1),
        'personality_score': round(personality_score, 1),
        'category_breakdown': category_breakdown,
        'strengths': strengths,
        'considerations': considerations,
        'recommendations': recommendations,
        'detailed_insights': {
            'lifestyle': lifestyle_insights,
            'personality': personality_insights,
        },
    }


def _calculate_lifestyle_compatibility(pet, user_answers: Dict[str, str]) -> Dict[str, Any]:
    """
    Calculate user's lifestyle compatibility with pet's needs.
    
    Maps user answers to pet's behavioral traits using PET_TRAIT_MAPPINGS.
    Calculates gap between user's capacity and pet's actual needs.
    """
    scores = []
    breakdown = {}
    insights = []
    
    # Normalize user answers
    normalized_answers = {}
    for key, answer in user_answers.items():
        if key.startswith('user_'):
            if key in USER_LIFESTYLE_MAPPING and answer in USER_LIFESTYLE_MAPPING[key]:
                normalized_answers[key] = USER_LIFESTYLE_MAPPING[key][answer]
    
    # Score each pet trait mapping
    for pet_trait, question_mappings in PET_TRAIT_MAPPINGS.items():
        if not hasattr(pet, pet_trait):
            continue
        
        pet_value = getattr(pet, pet_trait)
        pet_score = _trait_value_to_score(pet_value)
        
        trait_scores = []
        
        for question_key, trait_mapping in question_mappings.items():
            if question_key not in normalized_answers:
                continue
            
            user_score = normalized_answers[question_key]
            
            if pet_value in trait_mapping:
                expected_user_score = trait_mapping[pet_value]
                
                # Calculate compatibility: how close user is to what pet needs
                gap = abs(user_score - expected_user_score)
                max_gap = 4
                trait_compatibility = max(0, 1 - (gap / max_gap))
                trait_scores.append(trait_compatibility)
        
        if trait_scores:
            avg_trait_score = sum(trait_scores) / len(trait_scores)
            scores.append(avg_trait_score)
            breakdown[pet_trait] = {
                'score': round(avg_trait_score * 100, 1),
                'pet_trait': pet_value,
                'num_questions': len(trait_scores),
            }
            
            # Generate insight
            insight = _generate_lifestyle_insight(pet_trait, pet_value, avg_trait_score)
            if insight:
                insights.append(insight)
    
    # Calculate average
    avg_score = sum(scores) / len(scores) * 100 if scores else 50
    
    return {
        'score': round(avg_score, 1),
        'breakdown': breakdown,
        'insights': insights,
    }


def _calculate_personality_compatibility(pet, user_answers: Dict[str, str]) -> Dict[str, Any]:
    """
    Calculate user's personality compatibility with pet using Big Five model.
    
    1. Calculate user's Big Five scores from questionnaire
    2. Extract pet's Big Five scores from database
    3. Use Big Five compatibility algorithm (gap-based scoring)
    4. Convert to 0-100 scale
    5. Generate detailed insights for each trait
    """
    
    # Get user's Big Five scores
    user_big_five = calculate_user_big_five_scores(user_answers)
    
    # Get pet's Big Five scores (1-5 scale from database)
    pet_big_five = {
        'Openness': pet.big_five_openness or 3,
        'Conscientiousness': pet.big_five_conscientiousness or 3,
        'Extraversion': pet.big_five_extraversion or 3,
        'Agreeableness': pet.big_five_agreeableness or 3,
        'Neuroticism': pet.big_five_neuroticism or 2,
    }
    
    # Calculate compatibility using improved algorithm
    compatibility = calculate_big_five_compatibility(
        user_big_five,
        pet_big_five,
        breed_flexibility=0.5  # Pets have moderate flexibility
    )
    
    # Get the overall percentage score
    score = compatibility['compatibility_percentage']
    
    # Generate detailed insights for each trait
    insights = []
    for trait, gap_data in compatibility['trait_gaps'].items():
        user_score = gap_data['user']
        pet_score = gap_data['breed']
        gap = gap_data['gap']
        trait_compat = gap_data['compatibility']
        
        # Create insight based on compatibility level
        if trait_compat >= 85:
            insights.append(
                f"✅ {trait}: Perfect alignment! You both score {user_score}/5 "
                f"vs {pet_score}/5 (gap: {gap})"
            )
        elif trait_compat >= 70:
            insights.append(
                f"✅ {trait}: Good match - You ({user_score}/5) are compatible with "
                f"pet's needs ({pet_score}/5)"
            )
        elif trait_compat >= 55:
            insights.append(
                f"⚠️ {trait}: Moderate - Some adjustment needed. You ({user_score}/5) "
                f"vs pet ({pet_score}/5) - gap of {gap}"
            )
        elif trait_compat >= 40:
            insights.append(
                f"⚠️ {trait}: Lower compatibility. Significant difference between you "
                f"({user_score}/5) and pet's needs ({pet_score}/5)"
            )
        else:
            insights.append(
                f"<br style='color: red;'> {trait}: Major mismatch! You ({user_score}/5) "
                f"are very different from pet ({pet_score}/5) - this trait needs attention"
            )
    
    return {
        'score': score,
        'breakdown': compatibility,
        'insights': insights,
        'user_scores': user_big_five,
        'pet_scores': pet_big_five,
    }


def _trait_value_to_score(trait_value: str) -> float:
    """
    Convert pet trait enum value to numeric score (1-4).
    
    Used for comparing with user answer scores.
    """
    if isinstance(trait_value, (int, float)):
        return trait_value
    
    # Map common trait descriptions to scores
    value_lower = str(trait_value).lower()
    
    if any(x in value_lower for x in ['very calm', 'rarely', 'very shy', 'never', 'difficult']):
        return 1.0
    elif any(x in value_lower for x in ['calm', 'shy', 'gradual', 'selective', 'nervous']):
        return 2.0
    elif any(x in value_lower for x in ['moderate', 'balanced', 'neutral', 'adjust']):
        return 3.0
    elif any(x in value_lower for x in ['energetic', 'active', 'social', 'friendly', 'quickly', 'playful']):
        return 4.0
    
    return 3.0  # Default to moderate


def _generate_lifestyle_insight(pet_trait: str, pet_value: str, compatibility: float) -> Optional[str]:
    """
    Generate human-readable insight about lifestyle compatibility for a trait.
    """
    if compatibility >= 0.85:
        status = 'excellent alignment'
    elif compatibility >= 0.70:
        status = 'good match'
    elif compatibility >= 0.55:
        status = 'moderate match'
    else:
        status = 'potential mismatch'
    
    return f"{pet_trait.replace('_', ' ').title()}: {status} with your lifestyle ({pet_value})"


def _extract_strengths(lifestyle_insights: List[str], personality_insights: List[str]) -> List[str]:
    """
    Extract positive compatibility factors from insights.
    
    Only include insights that show alignment and good compatibility.
    """
    strengths = []
    
    # Find lifestyle strengths
    for insight in lifestyle_insights:
        insight_lower = insight.lower()
        if 'excellent' in insight_lower or ('good' in insight_lower and 'match' in insight_lower):
            # Clean up the insight for display
            cleaned = insight.replace('Excellent alignment', 'Excellent alignment').strip()
            if cleaned:
                strengths.append(cleaned)
    
    # Find personality strengths
    for insight in personality_insights:
        insight_lower = insight.lower()
        if '✅' in insight:  # Checkmark emoji indicates positive
            # Clean up the insight for display
            cleaned = insight.replace('✅', '').strip()
            if cleaned:
                strengths.append(cleaned)
    
    # Return unique strengths, limit to 8
    return list(set(strengths))[:8]


def _extract_considerations(lifestyle_insights: List[str], personality_insights: List[str]) -> List[str]:
    """
    Extract areas of concern or adjustment needed.
    
    Include insights that show potential challenges or areas requiring work.
    """
    considerations = []
    
    # Find lifestyle considerations
    for insight in lifestyle_insights:
        insight_lower = insight.lower()
        if 'moderate' in insight_lower or 'mismatch' in insight_lower:
            cleaned = insight.strip()
            if cleaned:
                considerations.append(cleaned)
    
    # Find personality considerations and warnings
    for insight in personality_insights:
        if '⚠️' in insight or '❌' in insight:  # Warning or X emoji
            # Clean up the insight for display
            cleaned = insight.replace('⚠️', '').replace('❌', '').strip()
            if cleaned:
                considerations.append(cleaned)
    
    # Return unique considerations, limit to 8
    return list(set(considerations))[:8]


def _generate_category_breakdown(pet, user_answers: Dict[str, str], 
                                  lifestyle_breakdown: Dict, 
                                  personality_breakdown: Dict) -> Dict[str, Dict]:
    """Generate category-level breakdown for display."""
    categories = {
        'Activity & Energy': {},
        'Sociability': {},
        'Adaptability': {},
        'Training & Behavior': {},
        'Personality Match': {},
    }
    
    # Map traits to categories
    trait_category_map = {
        'activity_level': 'Activity & Energy',
        'adaptability': 'Adaptability',
        'independence_level': 'Adaptability',
        'trainability': 'Training & Behavior',
        'animal_social_behavior': 'Sociability',
        'people_sociality': 'Sociability',
        'affection_level': 'Sociability',
    }
    
    # Populate lifestyle categories
    for trait, data in lifestyle_breakdown.items():
        category = trait_category_map.get(trait, 'Other')
        if category in categories:
            if 'scores' not in categories[category]:
                categories[category]['scores'] = []
            categories[category]['scores'].append(data['score'])
    
    # Calculate category averages
    for category_name, category_data in categories.items():
        if 'scores' in category_data and category_data['scores']:
            avg_score = sum(category_data['scores']) / len(category_data['scores'])
            categories[category_name] = {
                'score': round(avg_score, 1),
                'status': _get_score_status(avg_score),
                'weight': 0.20 if category_name != 'Personality Match' else 0.40,
            }
        else:
            categories[category_name] = {
                'score': 50,
                'status': 'Unknown',
                'weight': 0.20,
            }
    
    # Add personality category
    if 'compatibility_percentage' in personality_breakdown:
        categories['Personality Match']['score'] = personality_breakdown['compatibility_percentage']
        categories['Personality Match']['status'] = _get_score_status(
            personality_breakdown['compatibility_percentage']
        )
    
    return categories


def _get_score_status(score: float) -> str:
    """Convert score to status label."""
    if score >= 85:
        return 'Excellent'
    elif score >= 70:
        return 'Good'
    elif score >= 55:
        return 'Moderate'
    elif score >= 40:
        return 'Fair'
    else:
        return 'Needs Work'


def _generate_recommendations(pet, user_answers: Dict[str, str],
                              lifestyle_insights: List[str],
                              personality_insights: List[str]) -> List[str]:
    """Generate actionable recommendations for improving compatibility."""
    recommendations = []
    
    # Add lifestyle recommendations
    for insight in lifestyle_insights:
        if 'mismatch' in insight.lower():
            trait = insight.split(':')[0].lower()
            if 'energy' in trait:
                recommendations.append('Increase daily activity and playtime with your pet')
            elif 'social' in trait:
                recommendations.append('Schedule regular socialization sessions')
            elif 'training' in trait:
                recommendations.append('Invest in professional training if needed')
            elif 'adapt' in trait:
                recommendations.append('Establish consistent routines to help your pet feel secure')
    
    # Add personality recommendations from Big Five
    big_five_recs = get_big_five_recommendations(
        {k: v for k, v in user_answers.items() if k.startswith('big_five')},
        {
            'Openness': pet.big_five_openness or 3,
            'Conscientiousness': pet.big_five_conscientiousness or 3,
            'Extraversion': pet.big_five_extraversion or 3,
            'Agreeableness': pet.big_five_agreeableness or 3,
            'Neuroticism': pet.big_five_neuroticism or 2,
        }
    )
    recommendations.extend(big_five_recs)
    
    return list(set(recommendations))[:10]  # Remove duplicates, limit to 10
