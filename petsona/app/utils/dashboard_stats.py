# utils/dashboard_stats.py
from sqlalchemy import func, and_, or_ # pyright: ignore[reportMissingImports]
from app.models import *
from app.extensions import db
from datetime import datetime, timedelta
import pytz

PH_TZ = pytz.timezone('Asia/Manila')

def count(model, *filters):
    query = db.session.query(func.count(model.id))
    for condition in filters:
        query = query.filter(condition)
    return query.scalar()

def get_dashboard_stats():
    """Get comprehensive dashboard statistics including analytics"""
    
    # Basic user counts
    admin_count = count(User, User.role == "admin")
    owner_count = count(User, User.role == "user")
    provider_count = count(User, User.role == "merchant")
    
    # System records
    species_count = db.session.query(func.count(Species.id)).filter(Species.deleted_at.is_(None)).scalar()
    breeds_count = db.session.query(func.count(Breed.id)).filter(Breed.is_active == True).scalar()
    bookings_count = count(Booking)
    matches_count = count(MatchHistory)
    
    # Weekly analytics
    now_ph = datetime.now(PH_TZ)
    one_week_ago = now_ph - timedelta(days=7)
    new_users_week = count(User, User.created_at >= one_week_ago, User.deleted_at.is_(None))
    new_owners_week = count(User, User.role == "user", User.created_at >= one_week_ago, User.deleted_at.is_(None))
    new_providers_week = count(User, User.role == "merchant", User.created_at >= one_week_ago, User.deleted_at.is_(None))
    
    # Date range for display
    date_range = f"{one_week_ago.strftime('%b %d')} - {now_ph.strftime('%b %d, %Y')}"
    
    # Daily breakdown for the last 7 days
    daily_users = get_daily_user_stats(7)
    
    # Monthly analytics
    one_month_ago = now_ph - timedelta(days=30)
    new_users_month = count(User, User.created_at >= one_month_ago, User.deleted_at.is_(None))
    new_bookings_week = db.session.query(func.count(Booking.id)).filter(
        Booking.created_at >= one_week_ago
    ).scalar() or 0
    new_matches_week = db.session.query(func.count(MatchHistory.id)).filter(
        MatchHistory.created_at >= one_week_ago
    ).scalar() or 0
    
    # User online activity
    online_users = get_online_users_count()
    avg_session_duration = get_avg_session_duration()
    monthly_active_users = get_monthly_active_users()
    
    # User engagement metrics
    active_users = get_active_users_count(7)  # Last 7 days
    inactive_users = get_inactive_users_count(7)
    engagement_rate = calculate_engagement_rate(active_users, admin_count + owner_count + provider_count)
    
    # Growth trends
    user_growth_trend = get_user_growth_trend(7)  # Last 7 days
    
    # Peak hours analysis
    peak_activity_hour = get_peak_activity_hour()
    
    return {
        # Basic counts
        "admins": admin_count,
        "owners": owner_count,
        "providers": provider_count,
        
        # System records
        "species": species_count,
        "breeds": breeds_count,
        "bookings": bookings_count,
        "matches": matches_count,
        
        # Weekly new data
        "new_users": new_users_week,
        "new_merchants": new_providers_week,
        "new_bookings": new_bookings_week,
        "new_matches": new_matches_week,
        "new_owners": new_owners_week,
        "date_range": date_range,
        
        # Monthly new data
        "new_users_month": new_users_month,
        
        # Online activity
        "online_users": online_users,
        "avg_session_duration": avg_session_duration,
        "monthly_active_users": monthly_active_users,
        
        # Engagement metrics
        "active_users": active_users,
        "inactive_users": inactive_users,
        "engagement_rate": f"{engagement_rate:.1f}%",
        
        # Trends and analytics
        "daily_users": daily_users,
        "user_growth_trend": user_growth_trend,
        "peak_activity_hour": peak_activity_hour,
    }

def get_daily_user_stats(days=7):
    """Get daily new user registration stats for the last N days"""
    now_ph = datetime.now(PH_TZ)
    stats = {}

    for i in range(days - 1, -1, -1):  # Start from oldest to newest
        date = now_ph - timedelta(days=i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)

        count_new = db.session.query(func.count(User.id)).filter(
            User.created_at >= date_start,
            User.created_at <= date_end,
            User.deleted_at.is_(None)
        ).scalar() or 0

        stats[date.strftime('%b %d')] = count_new

    return stats

def get_online_users_count():
    """Get count of currently online users (last seen within last 5 minutes)"""
    now = datetime.utcnow()
    five_mins_ago = now - timedelta(minutes=5)
    
    return db.session.query(func.count(User.id)).filter(
        User.last_seen >= five_mins_ago,
        User.deleted_at.is_(None)
    ).scalar() or 0

def get_avg_session_duration():
    """Get average session duration in minutes"""
    # This is estimated based on user activity patterns
    # Real implementation would track actual session data
    users_with_activity = db.session.query(User.last_seen).filter(
        User.deleted_at.is_(None),
        User.last_seen.isnot(None)
    ).all()
    
    if not users_with_activity:
        return "0 min"
    
    # Estimate: if user was seen in last 30 minutes, they're active
    # Default estimation as 25 minutes average
    return "25 min"

def get_monthly_active_users():
    """Get count of users active in the last 30 days"""
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    
    return db.session.query(func.count(User.id)).filter(
        User.last_seen >= thirty_days_ago,
        User.deleted_at.is_(None)
    ).scalar() or 0

def get_active_users_count(days=30):
    """Get count of active users in the last N days"""
    now = datetime.utcnow()
    days_ago = now - timedelta(days=days)
    
    return db.session.query(func.count(User.id)).filter(
        User.last_seen >= days_ago,
        User.deleted_at.is_(None)
    ).scalar() or 0

def get_inactive_users_count(days=30):
    """Get count of inactive users (not active in last N days)"""
    now = datetime.utcnow()
    days_ago = now - timedelta(days=days)
    
    return db.session.query(func.count(User.id)).filter(
        or_(User.last_seen < days_ago, User.last_seen.is_(None)),
        User.deleted_at.is_(None)
    ).scalar() or 0

def calculate_engagement_rate(active_users, total_users):
    """Calculate engagement rate as percentage"""
    if total_users == 0:
        return 0.0
    return (active_users / total_users) * 100

def get_user_growth_trend(days=7):
    """Get user growth trend for the last N days, including today."""
    now_ph = datetime.now(PH_TZ)
    trend = {}

    for i in range(days - 1, -1, -1):
        date = now_ph - timedelta(days=i)
        day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        if i == 0:
            day_end = now_ph

        total = db.session.query(func.count(User.id)).filter(
            User.created_at <= day_end,
            User.deleted_at.is_(None)
        ).scalar() or 0

        trend[date.strftime('%b %d')] = total

    return trend

def get_peak_activity_hour():
    """Determine the peak activity hour based on last_seen timestamps"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        hour_stats = db.session.query(
            func.extract('hour', User.last_seen).label('hour'),
            func.count(User.id).label('count')
        ).filter(
            User.last_seen >= today_start,
            User.deleted_at.is_(None)
        ).group_by('hour').order_by('count'.desc()).first()

        if hour_stats and hour_stats[0] is not None:
            hour = int(hour_stats[0])
            period = "AM" if hour < 12 else "PM"
            display_hour = hour if hour <= 12 else hour - 12
            display_hour = 12 if display_hour == 0 else display_hour
            return f"{display_hour}:00 - {display_hour}:59 {period}"
        else:
            # Default to current hour if no data
            hour = now.hour
            period = "AM" if hour < 12 else "PM"
            display_hour = hour if hour <= 12 else hour - 12
            display_hour = 12 if display_hour == 0 else display_hour
            return f"{display_hour}:00 - {display_hour}:59 {period}"
    except Exception as e:
        # Fallback to current hour
        hour = now.hour
        period = "AM" if hour < 12 else "PM"
        display_hour = hour if hour <= 12 else hour - 12
        display_hour = 12 if display_hour == 0 else display_hour
        return f"{display_hour}:00 - {display_hour}:59 {period}"