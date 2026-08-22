from flask import Blueprint

doctor_portal_bp = Blueprint('doctor_portal', __name__, url_prefix='/doctor')

from app.doctor_portal import routes  # noqa: E402, F401
