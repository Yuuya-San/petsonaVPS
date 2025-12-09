from flask import Blueprint

bp = Blueprint('auth', __name__, template_folder='templates')

from . import routes  # noqa: F401
from . import admin_dashboard  # noqa: F401
from . import merchant_dashboard  # noqa: F401
from . import user_dashboard  # noqa: F401
