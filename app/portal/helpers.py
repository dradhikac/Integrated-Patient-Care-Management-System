"""
Patient Portal helpers — resolves the Patient record for the logged-in User.
"""
from app.patients.models import Patient


def get_patient_for_user(user):
    """
    Resolve the Patient record linked to a User via portal_user_id.
    Returns the Patient object or None if no link exists.
    """
    if not user or not user.is_authenticated:
        return None
    return Patient.query.filter_by(portal_user_id=user.id).first()


def get_patient_or_fallback(user):
    """
    Try portal_user_id first, then fall back to email match.
    This handles legacy patients who were created before the portal system.
    """
    patient = get_patient_for_user(user)
    if patient:
        return patient
    # Fallback: match by email (for patients registered before portal linking)
    if user.email:
        patient = Patient.query.filter_by(email=user.email).first()
        if patient:
            # Auto-link for future lookups
            patient.portal_user_id = user.id
            if patient.portal_status == 'NOT_ACTIVATED':
                patient.portal_status = 'ACTIVE'
            from app.extensions import db
            db.session.commit()
            return patient
    return None
