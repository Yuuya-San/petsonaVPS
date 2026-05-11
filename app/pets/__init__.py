from flask import Blueprint

bp = Blueprint(
    'pets',
    __name__,
    url_prefix='/pets'
)

from app.pets import routes
