def calculate_compatibility(answers, breed):
    """Return a numeric score (0-100) for compatibility"""
    score = 0
    total = 0

    mapping = {
        "energy_level": ["Low", "Medium", "High"],
        "exercise_needs": ["Low", "Medium", "High"],
        "grooming_needs": ["Low", "Medium", "High"],
        "noise_level": ["Silent", "Low", "Moderate", "Loud"],
        "social_needs": ["Low", "Medium", "High"],
        "handling_tolerance": ["Low", "Medium", "High"],
        "time_commitment": ["Low", "Medium", "High"],
    }

    for key, options in mapping.items():
        user_val = answers.get(key)
        breed_val = getattr(breed, key, None)
        if user_val and breed_val:
            total += 1
            if user_val == breed_val:
                score += 1

    return (score / total * 100) if total else 0
