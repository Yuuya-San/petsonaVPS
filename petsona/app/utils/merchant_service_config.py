"""
Merchant Service Configuration and Pricing Logic
Handles service-to-category mapping and pricing structure generation
"""

# ========== BUSINESS CATEGORY TO SERVICES MAPPING ==========
CATEGORY_TO_SERVICES = {
    'Health & Wellness': [
        'Veterinary Clinic',
        'Vaccination Services',
        'Pet Rehabilitation',
    ],
    'Care & Handling': [
        'Pet Boarding',
        'Pet Daycare',
        'Pet Sitting',
        'Pet Training',
        'Pet Transport',
    ],
    'Personal Care & Aesthetics': [
        'Pet Grooming',
        'Pet Photography',
    ],
    'Support & Specialty': [
        'Pet Events',
        'Pet Cremation & Memorial',
    ],
    'Retail & Lifestyle': [
        'Pet Supplies Store',
        'Pet Food & Treats',
        'Pet Bakery',
        'Pet Café',
    ],
}

# ========== SERVICE PRICING TYPES ==========
SERVICE_PRICING_TYPES = {
    # Flat-rate services (no size/duration dependency)
    'Veterinary Clinic': 'flat',
    'Vaccination Services': 'flat',
    'Pet Rehabilitation': 'flat',
    'Pet Training': 'flat',
    'Pet Events': 'flat',
    'Pet Cremation & Memorial': 'flat',
    'Pet Photography': 'flat',
    'Pet Supplies Store': 'flat',
    'Pet Food & Treats': 'flat',
    'Pet Bakery': 'flat',
    'Pet Café': 'flat',
    
    # Size-dependent services
    'Pet Grooming': 'size',
    'Pet Transport': 'size',
    
    # Duration-dependent services (with optional size)
    'Pet Boarding': 'duration+size',
    'Pet Daycare': 'duration+size',
    'Pet Sitting': 'duration',
}

# ========== PET SIZE TIERS ==========
PET_SIZE_TIERS = [
    {'id': 'small', 'label': 'Small (up to 10kg)', 'description': 'Rabbits, Cats, Small Dogs'},
    {'id': 'medium', 'label': 'Medium (10-30kg)', 'description': 'Medium Dogs'},
    {'id': 'large', 'label': 'Large (30-60kg)', 'description': 'Large Dogs'},
    {'id': 'xlarge', 'label': 'XL (60kg+)', 'description': 'Giant Breeds'},
]

# ========== PET SIZE TIER MAPPING ==========
PET_SIZE_MAPPING = {
    'Dogs': ['small', 'medium', 'large', 'xlarge'],
    'Cats': ['small'],
    'Small Mammals': ['small'],
    'Birds': ['small'],
    'Reptiles & Amphibians': ['small'],
    'Aquatic Pets': ['small'],
    'Exotic': ['small'],
}

# ========== DURATION UNITS ==========
DURATION_UNITS = [
    {'id': 'hour', 'label': 'Per Hour'},
    {'id': 'halfday', 'label': 'Half Day (4 hours)'},
    {'id': 'day', 'label': 'Per Day'},
    {'id': 'night', 'label': 'Per Night'},
    {'id': 'overnight', 'label': 'Overnight (24 hours)'},
]

# ========== FLAT-RATE UNITS ==========
FLAT_RATE_UNITS = [
    {'id': 'services', 'label': 'Per Service'},
    {'id': 'session', 'label': 'Per Session'},
    {'id': 'visit', 'label': 'Per Visit'},
    {'id': 'item', 'label': 'Per Item'},
    {'id': 'pet', 'label': 'Per Pet'},
]

def get_allowed_services_for_category(category):
    """Get list of services for a given category"""
    return CATEGORY_TO_SERVICES.get(category, [])

def get_pricing_type_for_service(service):
    """Get the pricing type for a service"""
    return SERVICE_PRICING_TYPES.get(service, 'flat')

def get_size_tiers_for_pets(pets):
    """
    Get unique size tiers across all selected pets
    
    Args:
        pets: list of pet names
        
    Returns:
        list of dictionaries with size tier info
    """
    tier_ids = set()
    for pet in pets:
        if pet in PET_SIZE_MAPPING:
            tier_ids.update(PET_SIZE_MAPPING[pet])
    
    # Return size tiers in order
    return [tier for tier in PET_SIZE_TIERS if tier['id'] in tier_ids]

def initialize_service_pricing_structure(category, pets):
    """
    Initialize the pricing structure for a merchant based on category and pets
    
    Returns:
        dict with service pricing configuration
    """
    services = get_allowed_services_for_category(category)
    size_tiers = get_size_tiers_for_pets(pets)
    
    pricing_structure = {}
    
    for service in services:
        pricing_type = get_pricing_type_for_service(service)
        
        if pricing_type == 'flat':
            pricing_structure[service] = {
                'type': 'flat',
                'unit': 'services',
                'min_price': None,
                'max_price': None,
            }
        elif pricing_type == 'size':
            pricing_structure[service] = {
                'type': 'size',
                'unit': 'services',
                'by_size': {
                    tier['id']: {
                        'label': tier['label'],
                        'min_price': None,
                        'max_price': None,
                    }
                    for tier in size_tiers
                }
            }
        elif pricing_type == 'duration':
            pricing_structure[service] = {
                'type': 'duration',
                'unit': 'day',
                'by_duration': {
                    unit['id']: {
                        'label': unit['label'],
                        'min_price': None,
                        'max_price': None,
                    }
                    for unit in DURATION_UNITS
                }
            }
        elif pricing_type == 'duration+size':
            pricing_structure[service] = {
                'type': 'duration+size',
                'unit': 'day',
                'by_duration_and_size': {
                    duration['id']: {
                        'label': duration['label'],
                        'by_size': {
                            tier['id']: {
                                'label': tier['label'],
                                'min_price': None,
                                'max_price': None,
                            }
                            for tier in size_tiers
                        }
                    }
                    for duration in DURATION_UNITS
                }
            }
    
    return pricing_structure

def validate_pricing_structure(pricing_structure):
    """Validate that all required prices are filled"""
    errors = []
    
    for service, config in pricing_structure.items():
        if config['type'] == 'flat':
            if config['min_price'] is None or config['max_price'] is None:
                errors.append(f"{service}: Both min and max price are required")
        elif config['type'] == 'size':
            for size_id, size_data in config.get('by_size', {}).items():
                if size_data.get('min_price') is None or size_data.get('max_price') is None:
                    errors.append(f"{service} ({size_data.get('label')}): Both min and max price required")
        elif config['type'] == 'duration':
            for duration_id, duration_data in config.get('by_duration', {}).items():
                if duration_data.get('min_price') is None or duration_data.get('max_price') is None:
                    errors.append(f"{service} ({duration_data.get('label')}): Both min and max price required")
        elif config['type'] == 'duration+size':
            for duration_id, duration_data in config.get('by_duration_and_size', {}).items():
                for size_id, size_data in duration_data.get('by_size', {}).items():
                    if size_data.get('min_price') is None or size_data.get('max_price') is None:
                        errors.append(
                            f"{service} ({duration_data.get('label')} - {size_data.get('label')}): "
                            f"Both min and max price required"
                        )
    
    return errors

def get_price_range(service, pricing_structure, size=None, duration=None):
    """
    Get the price range for a service based on parameters
    
    Returns:
        dict with 'min' and 'max' keys, or None if not available
    """
    if service not in pricing_structure:
        return None
    
    config = pricing_structure[service]
    
    if config['type'] == 'flat':
        return {
            'min': config.get('min_price'),
            'max': config.get('max_price'),
            'unit': config.get('unit', 'services')
        }
    
    elif config['type'] == 'size':
        if size and size in config.get('by_size', {}):
            size_data = config['by_size'][size]
            return {
                'min': size_data.get('min_price'),
                'max': size_data.get('max_price'),
                'unit': config.get('unit', 'services'),
                'size': size
            }
        return None
    
    elif config['type'] == 'duration':
        if duration and duration in config.get('by_duration', {}):
            duration_data = config['by_duration'][duration]
            return {
                'min': duration_data.get('min_price'),
                'max': duration_data.get('max_price'),
                'unit': duration,
            }
        return None
    
    elif config['type'] == 'duration+size':
        if duration and size:
            duration_data = config.get('by_duration_and_size', {}).get(duration, {})
            size_data = duration_data.get('by_size', {}).get(size, {})
            if size_data:
                return {
                    'min': size_data.get('min_price'),
                    'max': size_data.get('max_price'),
                    'duration': duration,
                    'size': size,
                }
        return None
    
    return None
