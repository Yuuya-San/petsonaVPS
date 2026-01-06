
def format_activity(log):
    data = log.get_metadata()

    icons = {
        "pet_created": "🐾",
        "pet_updated": "✏️",
        "booking_created": "🏨",
        "booking_confirmed": "✅",
        "service_registered": "🛠️",
        "user_registered": "👤",
        "user_updated": "✏️",
    }

    messages = {
        "pet_created": "New pet added",
        "pet_updated": "Pet record updated",
        "booking_created": "New booking created",
        "booking_confirmed": "Booking confirmed",
        "service_registered": "New service provider registered",
        "user_registered": "New user registered",
        "user_updated": "User profile updated",
    }

    return {
        "icon": icons.get(log.event, "📝"),
        "message": messages.get(log.event, log.event.replace("_", " ").title()),
        "actor": log.actor_email or "System",
        "time": log.timestamp,
        "entity_id": data.get("id"),
    }
