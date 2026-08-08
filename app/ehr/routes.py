from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.patients.models import Patient
from app.ehr.timeline_builder import build_patient_ehr_timeline

ehr_bp = Blueprint('ehr', __name__, template_folder='templates', url_prefix='/ehr')

@ehr_bp.route('/patient/<int:patient_id>')
@login_required
def patient_timeline(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Patient role restriction check (Patients can only view their own EHR)
    if current_user.role.name == 'Patient' and patient.email != current_user.email:
        flash('Access denied. You can only view your own health records.', 'danger')
        return redirect(url_for('auth.dashboard'))

    search_q = request.args.get('q', '').strip()
    event_filter = request.args.get('type', 'ALL').strip()

    timeline_events = build_patient_ehr_timeline(patient_id, search_term=search_q, event_filter=event_filter)

    return render_template('ehr/timeline.html',
                           patient=patient,
                           events=timeline_events,
                           search_q=search_q,
                           event_filter=event_filter)
