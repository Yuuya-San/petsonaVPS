"""
Integration Examples for Merchant Pricing System

This file demonstrates how to integrate the merchant pricing system
with the booking system and other PetSona components.
"""
from datetime import datetime
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)

def calculate_booking_price(merchant_id, pet_size, service_name, duration_unit=None):
    """
    Calculate estimated price for a booking based on service configuration.
    
    Args:
        merchant_id: The merchant ID
        pet_size: Size of pet (small, medium, large, xlarge)
        service_name: Name of service (e.g., 'Pet Grooming')
        duration_unit: Duration unit for duration-dependent services (e.g., 'day')
    
    Returns:
        dict with 'min', 'max' pricing or None if not available
    """
    from app.models.merchant import Merchant
    
    merchant = Merchant.query.get(merchant_id)
    if not merchant:
        return None
    
    # Get price based on service configuration
    price_info = merchant.get_price_for_service(
        service_name=service_name,
        size=pet_size,
        duration=duration_unit
    )
    
    if price_info:
        return {
            'min': price_info.get('min'),
            'max': price_info.get('max'),
            'currency': '₱',
            'service': service_name,
            'pet_size': pet_size,
            'duration': duration_unit
        }
    
    return None


# ========== EXAMPLE 2: BOOKING API RESPONSE ==========

def format_booking_options(merchant_id, pet_size):
    """
    Format available booking options and pricing for a pet.
    
    Args:
        merchant_id: The merchant ID
        pet_size: Size of pet
    
    Returns:
        List of available services with pricing
    """
    from app.models.merchant import Merchant
    
    merchant = Merchant.query.get(merchant_id)
    if not merchant:
        return []
    
    options = []
    pricing = merchant.get_service_pricing()
    
    for service_name, config in pricing.items():
        option = {
            'service': service_name,
            'type': config.get('type'),
            'available': False,
            'pricing': []
        }
        
        if config.get('type') == 'flat':
            # Flat rate - always available
            option['available'] = True
            option['pricing'] = [{
                'description': 'Standard',
                'min': config.get('min_price'),
                'max': config.get('max_price')
            }]
        
        elif config.get('type') == 'size':
            # Size-dependent - check if this size is available
            if pet_size in config.get('by_size', {}):
                option['available'] = True
                size_data = config['by_size'][pet_size]
                option['pricing'] = [{
                    'size': pet_size,
                    'min': size_data.get('min_price'),
                    'max': size_data.get('max_price')
                }]
        
        elif config.get('type') == 'duration':
            # Duration-dependent - show all durations
            option['available'] = True
            for duration_id, duration_data in config.get('by_duration', {}).items():
                option['pricing'].append({
                    'duration': duration_id,
                    'label': duration_data.get('label'),
                    'min': duration_data.get('min_price'),
                    'max': duration_data.get('max_price')
                })
        
        elif config.get('type') == 'duration+size':
            # Matrix pricing - check if this size is available for any duration
            duration_data = config.get('by_duration_and_size', {})
            for duration_id, dur_info in duration_data.items():
                if pet_size in dur_info.get('by_size', {}):
                    option['available'] = True
                    size_pricing = dur_info['by_size'][pet_size]
                    option['pricing'].append({
                        'duration': duration_id,
                        'duration_label': dur_info.get('label'),
                        'size': pet_size,
                        'min': size_pricing.get('min_price'),
                        'max': size_pricing.get('max_price')
                    })
        
        if option['available']:
            options.append(option)
    
    return options


# ========== EXAMPLE 3: BOOKING MODEL INTEGRATION ==========

class BookingWithPricing:
    """
    Example integration with Booking model to automatically
    calculate and store pricing information.
    """
    
    @staticmethod
    def create_booking_with_pricing(merchant_id, customer_id, pet_id, 
                                    service_name, pet_size, duration_unit=None):
        """
        Create a booking and automatically calculate pricing.
        """
        from app.models.merchant import Merchant
        from app.models.booking import Booking
        from datetime import datetime
        from app.extensions import db
        
        # Get merchant and calculate price
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            raise ValueError(f"Merchant {merchant_id} not found")
        
        price_info = merchant.get_price_for_service(
            service_name=service_name,
            size=pet_size,
            duration=duration_unit
        )
        
        if not price_info:
            raise ValueError(f"No pricing available for {service_name}")
        
        # Create booking with estimated pricing
        booking = Booking(
            merchant_id=merchant_id,
            customer_id=customer_id,
            pet_id=pet_id,
            service_name=service_name,
            estimated_min_price=price_info.get('min'),
            estimated_max_price=price_info.get('max'),
            pet_size=pet_size,
            duration_unit=duration_unit,
            status='pending',
            created_at=get_ph_datetime()
        )
        
        db.session.add(booking)
        db.session.commit()
        
        return booking


# ========== EXAMPLE 4: DYNAMIC PRICING DISPLAY ==========

def render_service_pricing_table(merchant_id):
    """
    Generate HTML table for displaying all merchant services and pricing.
    """
    from app.models.merchant import Merchant
    
    merchant = Merchant.query.get(merchant_id)
    if not merchant:
        return None
    
    pricing = merchant.get_service_pricing()
    
    html = '<table class="pricing-table">'
    html += '<thead><tr><th>Service</th><th>Pet Size/Duration</th><th>Min Price</th><th>Max Price</th></tr></thead>'
    html += '<tbody>'
    
    for service_name, config in pricing.items():
        if config.get('type') == 'flat':
            html += f'<tr>'
            html += f'<td>{service_name}</td>'
            html += f'<td>-</td>'
            html += f'<td>₱{config.get("min_price")}</td>'
            html += f'<td>₱{config.get("max_price")}</td>'
            html += f'</tr>'
        
        elif config.get('type') == 'size':
            for size_id, size_data in config.get('by_size', {}).items():
                html += f'<tr>'
                html += f'<td>{service_name}</td>'
                html += f'<td>{size_data.get("label")}</td>'
                html += f'<td>₱{size_data.get("min_price")}</td>'
                html += f'<td>₱{size_data.get("max_price")}</td>'
                html += f'</tr>'
        
        elif config.get('type') == 'duration':
            for duration_id, duration_data in config.get('by_duration', {}).items():
                html += f'<tr>'
                html += f'<td>{service_name}</td>'
                html += f'<td>{duration_data.get("label")}</td>'
                html += f'<td>₱{duration_data.get("min_price")}</td>'
                html += f'<td>₱{duration_data.get("max_price")}</td>'
                html += f'</tr>'
        
        elif config.get('type') == 'duration+size':
            for duration_id, dur_data in config.get('by_duration_and_size', {}).items():
                for size_id, size_data in dur_data.get('by_size', {}).items():
                    html += f'<tr>'
                    html += f'<td>{service_name}</td>'
                    html += f'<td>{dur_data.get("label")} - {size_data.get("label")}</td>'
                    html += f'<td>₱{size_data.get("min_price")}</td>'
                    html += f'<td>₱{size_data.get("max_price")}</td>'
                    html += f'</tr>'
    
    html += '</tbody></table>'
    return html


# ========== EXAMPLE 5: SEARCH & FILTER ==========

def find_merchants_with_service_budget(service_name, max_budget, pet_size='small'):
    """
    Find merchants offering a service within budget.
    """
    from app.models.merchant import Merchant
    from app.utils.merchant_service_config import get_pricing_type_for_service
    
    merchants = Merchant.query.filter(
        Merchant.services_offered.contains(service_name),
        Merchant.application_status == 'approved'
    ).all()
    
    available_merchants = []
    pricing_type = get_pricing_type_for_service(service_name)
    
    for merchant in merchants:
        price_info = merchant.get_price_for_service(
            service_name=service_name,
            size=pet_size if pricing_type in ['size', 'duration+size'] else None
        )
        
        if price_info and price_info.get('min', 0) <= max_budget:
            available_merchants.append({
                'merchant_id': merchant.id,
                'name': merchant.business_name,
                'location': f"{merchant.city}, {merchant.province}",
                'price_min': price_info.get('min'),
                'price_max': price_info.get('max'),
                'contact': merchant.contact_phone
            })
    
    return available_merchants


# ========== EXAMPLE 6: PRICE VALIDATION ==========

def validate_booking_price(booking):
    """
    Validate that a booking's quoted price matches the merchant's current pricing.
    """
    from app.models.merchant import Merchant
    
    merchant = Merchant.query.get(booking.merchant_id)
    if not merchant:
        return False, "Merchant not found"
    
    current_price = merchant.get_price_for_service(
        service_name=booking.service_name,
        size=booking.pet_size,
        duration=booking.duration_unit
    )
    
    if not current_price:
        return False, "Service pricing no longer available"
    
    if booking.final_amount is None:
        return True, "Booking not finalized yet"
    
    # Check if quoted price is still within merchant's range
    if current_price['min'] <= booking.final_amount <= current_price['max']:
        return True, "Price is valid"
    else:
        return False, f"Price mismatch. Current range: ₱{current_price['min']}-{current_price['max']}"


# ========== EXAMPLE 7: BULK PRICE UPDATE ==========

def update_merchant_pricing_bulk(merchant_id, price_updates):
    """
    Update multiple service prices at once.
    
    Args:
        merchant_id: Merchant ID
        price_updates: Dict of service updates
        
    Example:
        price_updates = {
            'Pet Grooming': {
                'small': {'min': 600, 'max': 900},
                'medium': {'min': 900, 'max': 1300}
            }
        }
    """
    from app.models.merchant import Merchant
    from app.extensions import db
    from datetime import datetime
    
    merchant = Merchant.query.get(merchant_id)
    if not merchant:
        return False, "Merchant not found"
    
    try:
        pricing = merchant.get_service_pricing()
        
        for service_name, updates in price_updates.items():
            if service_name not in pricing:
                continue
            
            config = pricing[service_name]
            
            if config['type'] == 'size':
                for size_id, prices in updates.items():
                    if size_id in config.get('by_size', {}):
                        config['by_size'][size_id].update(prices)
            
            # Similar logic for other types...
        
        merchant.service_pricing = pricing
        merchant.updated_at = get_ph_datetime()
        db.session.commit()
        
        return True, "Pricing updated successfully"
    
    except Exception as e:
        db.session.rollback()
        return False, str(e)


# ========== EXAMPLE 8: ADMIN PRICING AUDIT ==========

def get_pricing_audit_report(merchant_id):
    """
    Generate audit report of merchant pricing configuration.
    """
    from app.models.merchant import Merchant
    
    merchant = Merchant.query.get(merchant_id)
    if not merchant:
        return None
    
    report = {
        'merchant': {
            'id': merchant.id,
            'name': merchant.business_name,
            'category': merchant.business_category,
            'status': merchant.application_status
        },
        'services': {},
        'summary': {
            'total_services': 0,
            'pricing_types': {},
            'min_price': None,
            'max_price': None
        }
    }
    
    pricing = merchant.get_service_pricing()
    
    for service_name, config in pricing.items():
        pricing_type = config.get('type')
        report['services'][service_name] = {
            'type': pricing_type,
            'configured': True,
            'data': config
        }
        
        # Track summary stats
        report['summary']['total_services'] += 1
        report['summary']['pricing_types'][pricing_type] = \
            report['summary']['pricing_types'].get(pricing_type, 0) + 1
    
    return report


# ========== EXAMPLE 9: FRONTEND STATE MANAGEMENT ==========

def get_merchant_pricing_state_json(merchant_id):
    """
    Get merchant pricing configuration in format suitable for frontend state management.
    Used for pre-filling edit forms or dynamic UI updates.
    """
    from app.models.merchant import Merchant
    import json
    
    merchant = Merchant.query.get(merchant_id)
    if not merchant:
        return None
    
    return {
        'merchantId': merchant.id,
        'businessCategory': merchant.business_category,
        'servicesOffered': merchant.get_services_list(),
        'petsAccepted': merchant.get_pets_list(),
        'servicePricing': merchant.get_service_pricing(),
        'lastUpdated': merchant.updated_at.isoformat() if merchant.updated_at else None
    }


# ========== EXAMPLE 10: NOTIFICATION WHEN PRICE CHANGES ==========

def notify_customers_of_price_change(merchant_id, old_pricing, new_pricing):
    """
    Send notifications to customers with pending bookings if prices change.
    """
    from app.models.booking import Booking
    from app.models.user import User
    
    affected_bookings = Booking.query.filter(
        Booking.merchant_id == merchant_id,
        Booking.status.in_(['pending', 'confirmed']),
        Booking.estimated_min_price.isnot(None)
    ).all()
    
    notifications = []
    
    for booking in affected_bookings:
        service = booking.service_name
        
        if service in new_pricing:
            new_price = new_pricing[service]
            old_price = old_pricing.get(service, {})
            
            # Determine if price increased or decreased
            old_min = old_price.get('min_price', 0) if isinstance(old_price, dict) else 0
            new_min = new_price.get('min_price', 0) if isinstance(new_price, dict) else 0
            
            if new_min > old_min:
                notifications.append({
                    'booking_id': booking.id,
                    'customer_id': booking.customer_id,
                    'type': 'price_increase',
                    'service': service,
                    'old_price': old_min,
                    'new_price': new_min,
                    'message': f"Price for {service} has increased from ₱{old_min} to ₱{new_min}"
                })
            elif new_min < old_min:
                notifications.append({
                    'booking_id': booking.id,
                    'customer_id': booking.customer_id,
                    'type': 'price_decrease',
                    'service': service,
                    'old_price': old_min,
                    'new_price': new_min,
                    'message': f"Good news! Price for {service} has decreased from ₱{old_min} to ₱{new_min}"
                })
    
    return notifications


if __name__ == "__main__":
    print("Integration examples loaded successfully!")
    print("\nUsage: Import these functions in your routes/models/services:")
    print("  from app.utils.merchant_pricing_integration import calculate_booking_price")
