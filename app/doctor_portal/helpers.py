"""
Doctor Portal Helpers
=====================
Utility functions for the Doctor Portal blueprint.
"""
from functools import wraps
from flask import abort, redirect, url_for, flash
from flask_login import current_user
from app.doctors.models import Doctor


def get_doctor_record(user=None):
    """
    Resolve the Doctor model record for a given User (or current_user).
    Returns None if no Doctor record is found.
    """
    target_user = user or current_user
    if not target_user or not target_user.is_authenticated:
        return None
    # Try direct user_id link
    doc = Doctor.query.filter_by(user_id=target_user.id).first()
    return doc


def require_doctor_record(f):
    """
    Decorator that ensures the logged-in Doctor has a Doctor model record.
    Injects `doctor` into the view's kwargs.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        doc = get_doctor_record()
        if not doc:
            flash('Your doctor profile has not been configured yet. Please contact the administrator.', 'warning')
            return redirect(url_for('auth.logout'))
        kwargs['doctor'] = doc
        return f(*args, **kwargs)
    return decorated
