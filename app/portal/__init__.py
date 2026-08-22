from flask import Blueprint

portal_bp = Blueprint('portal', __name__, template_folder='templates', url_prefix='/portal')

from app.portal import routes  # noqa: F401, E402
