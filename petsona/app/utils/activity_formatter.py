from pytz import timezone, UTC # pyright: ignore[reportMissingModuleSource]
from datetime import datetime

PH_TZ = timezone("Asia/Manila")  # Philippine timezone

def format_activity(log):
    """
    Formats an AuditLog entry for display in the dashboard.
    Converts timestamps to Philippine time and adds Font Awesome icons with colored CRUD actions.
    """
    data = log.details if isinstance(log.details, dict) else {}

    # Map event types to Font Awesome icons
    icons = {
        "species.created": "fas fa-paw",          
        "species.updated": "fas fa-pencil-alt",   
        "species.deleted": "fas fa-trash-alt",   
        "species.restored": "fas fa-undo",        
        "breed.created": "fas fa-dog",           
        "breed.updated": "fas fa-pencil-alt",
        "breed.deleted": "fas fa-trash-alt",
        "breed.restored": "fas fa-undo",
        "user.registered": "fas fa-user-plus",    
        "user.updated": "fas fa-user-edit",        
        "user.deleted": "fas fa-trash-alt",   
        "user.restored": "fas fa-undo",       
    }

    # Map event types to friendly messages
    messages = {
        "species.created": "New species added",
        "species.updated": "Species record updated",
        "species.deleted": "Species deleted",
        "species.restored": "Species restored",
        "breed.created": "New breed added",
        "breed.updated": "Breed record updated",
        "breed.deleted": "Breed deleted",
        "breed.restored": "Breed restored",
        "user.registered": "New user registered",
        "user.updated": "User information updated",
        "user.deleted": "User deleted",
        "user.restored": "User restored",
    }

    # Determine color based on CRUD type
    if "created" in log.event or "registered" in log.event:
        color = "#28a745"  # green
    elif "updated" in log.event:
        color = "#ffc107"  # yellow
    elif "deleted" in log.event:
        color = "#dc3545"  # red
    elif "restored" in log.event:
        color = "#17a2b8"  # blue
    else:
        color = "#6c757d"  # gray for unknown

    # Handle timestamp: convert to PH time
    ts = log.timestamp or datetime.utcnow()
    if ts.tzinfo is None:
        ts = UTC.localize(ts)
    ts_ph = ts.astimezone(PH_TZ)

    return {
        "icon": f'<i class="{icons.get(log.event, "fas fa-info-circle")}" style="color: {color};"></i>',
        "message": messages.get(log.event, log.event.replace("_", " ").title()),
        "actor": log.actor_email or "System",
        "time": ts_ph,
        "entity_id": data.get("species_id") or data.get("breed_id") or data.get("id"),
        "color": color,  # optional, in case you want to color text too
    }
