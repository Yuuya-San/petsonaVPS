from flask import Blueprint

bp = Blueprint(
    'merchant',
    __name__,
    url_prefix='/merchant'
)

from app.merchant import routes
