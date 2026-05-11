"""Messages blueprint."""
from flask import Blueprint

bp = Blueprint('messages', __name__, url_prefix='/messages')

from . import routes
