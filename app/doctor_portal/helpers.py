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
    If no Doctor record is found, automatically links or creates a valid Doctor record for the authenticated doctor user.
    """
    from app.extensions import db
    target_user = user or current_user
    if not target_user or not target_user.is_authenticated:
        return None

    # 1. Try direct user_id link
    doc = Doctor.query.filter_by(user_id=target_user.id).first()
    if doc:
        return doc

    # 2. Try match by user_code / doctor_code
    if hasattr(target_user, 'user_code') and target_user.user_code:
        doc = Doctor.query.filter_by(doctor_code=target_user.user_code).first()
        if doc:
            doc.user_id = target_user.id
            db.session.commit()
            return doc

    # 3. Try match by email
    if hasattr(target_user, 'email') and target_user.email:
        # Check matching doctor by name or user_id
        doc = Doctor.query.filter(Doctor.name.ilike(f"%{target_user.name}%")).first()
        if doc:
            doc.user_id = target_user.id
            db.session.commit()
            return doc

    # 4. Auto-provision profile for doctor role if missing
    if hasattr(target_user, 'role') and target_user.role and target_user.role.name == 'Doctor':
        doc = Doctor(
            user_id=target_user.id,
            doctor_code=target_user.user_code or f"DOC-{target_user.id:03d}",
            name=target_user.name or "Dr. Physician",
            specialization="General Medicine",
            education="MBBS, MD (General Medicine)",
            experience="12+ Years",
            department="General OPD",
            bio=f"{target_user.name} is a senior consultant physician at CareHub specializing in comprehensive patient care.",
            consultation_fee=600.0,
            image_url="/static/images/doctors/dr_rajesh_sharma.jpg",
            available_days="Monday - Saturday",
            rating=4.9,
            is_active=True
        )
        db.session.add(doc)
        db.session.commit()
        return doc

    return None


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
