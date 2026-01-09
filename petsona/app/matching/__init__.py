from flask import Blueprint

bp = Blueprint(
    'matching',
    __name__,
    url_prefix='/matching'
)

from app.matching import routes
