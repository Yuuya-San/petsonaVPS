# utils/dashboard_stats.py
from sqlalchemy import func # pyright: ignore[reportMissingImports]
from app.models import *
from app.extensions import db

def count(model, *filters):
    query = db.session.query(func.count(model.id))
    for condition in filters:
        query = query.filter(condition)
    return query.scalar()

def get_dashboard_stats():
    return {
        "admins": count(User, User.role == "admin"),
        "owners": count(User, User.role == "user"),
        "providers": count(User, User.role == "merchant"),

        "species": db.session.query(func.count(Species.id)).filter(Species.deleted_at.is_(None)).scalar(),
        "breeds": db.session.query(func.count(Breed.id)).filter(Breed.is_active == True ).scalar(),
        "bookings": count(User),
        "matches": count(User),
    }