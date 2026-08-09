from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.patients.models import Patient
from app.reception.models import CheckIn
from app.appointments.models import Appointment
from app.consultations.models import Consultation, Vital
from app.consultations.forms import ConsultationForm
from app.ehr.timeline_builder import build_patient_ehr_timeline

consultations_bp = Blueprint('consultations', __name__, template_folder='templates', url_prefix='/consultations')

@consultations_bp.route('/')
@login_required
def list_consultations():
    role_name = current_user.role.name
    query = request.args.get('q', '').strip()
    
    cns_query = Consultation.query

    if role_name == 'Doctor':
        cns_query = cns_query.filter_by(doctor_id=current_user.id)
    elif role_name == 'Patient':
        pat_obj = Patient.query.filter_by(email=current_user.email).first()
        if pat_obj:
            cns_query = cns_query.filter_by(patient_id=pat_obj.id)
        else:
            cns_query = cns_query.filter_by(patient_id=-1)

    consultations = cns_query.order_by(Consultation.id.desc()).all()

    return render_template('consultations/list.html', consultations=consultations)


@consultations_bp.route('/start', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Doctor')
def start_consultation():
    patient_id = request.args.get('patient_id', type=int)
    check_in_id = request.args.get('check_in_id', type=int)
    appointment_id = request.args.get('appointment_id', type=int)

    if not patient_id and request.method == 'GET':
        flash('Please select a patient to start consultation.', 'warning')
        return redirect(url_for('queue.doctor_queue_desk'))

    patient = Patient.query.get_or_404(patient_id) if patient_id else None
    check_in = db.session.get(CheckIn, check_in_id) if check_in_id else None
    appointment = db.session.get(Appointment, appointment_id) if appointment_id else None

    form = ConsultationForm()

    if request.method == 'GET' and patient:
        form.patient_id.data = patient.id
        if check_in_id: form.check_in_id.data = check_in_id
        if appointment_id: form.appointment_id.data = appointment_id

    # Build patient EHR timeline for side-by-side clinical reference
    ehr_events = build_patient_ehr_timeline(patient_id) if patient_id else []

    if form.validate_on_submit():
        target_patient_id = int(form.patient_id.data)

        cns = Consultation(
            consultation_code=Consultation.generate_consultation_code(),
            patient_id=target_patient_id,
            doctor_id=current_user.id,
            check_in_id=int(form.check_in_id.data) if form.check_in_id.data else None,
            appointment_id=int(form.appointment_id.data) if form.appointment_id.data else None,
            symptoms=form.symptoms.data.strip(),
            diagnosis=form.diagnosis.data.strip(),
            treatment_plan=form.treatment_plan.data.strip() if form.treatment_plan.data else None,
            notes=form.notes.data.strip() if form.notes.data else None
        )
        db.session.add(cns)
        db.session.flush() # Populate cns.id

        # Save Vitals record if any vitals entered
        if any([form.bp_systolic.data, form.bp_diastolic.data, form.temperature_f.data, form.pulse_bpm.data, form.spo2_percent.data]):
            vitals = Vital(
                consultation_id=cns.id,
                bp_systolic=form.bp_systolic.data,
                bp_diastolic=form.bp_diastolic.data,
                temperature_f=form.temperature_f.data,
                pulse_bpm=form.pulse_bpm.data,
                spo2_percent=form.spo2_percent.data
            )
            db.session.add(vitals)

        # Update CheckIn status to COMPLETED if linked
        if cns.check_in_id:
            chk = db.session.get(CheckIn, cns.check_in_id)
            if chk:
                chk.status = 'COMPLETED'
                chk.completed_time = datetime.utcnow()

        db.session.commit()

        flash(f'Consultation {cns.consultation_code} completed successfully!', 'success')
        return redirect(url_for('consultations.view_consultation', consultation_id=cns.id))

    return render_template('consultations/consult.html',
                           form=form,
                           patient=patient,
                           check_in=check_in,
                           appointment=appointment,
                           ehr_events=ehr_events)


@consultations_bp.route('/<int:consultation_id>')
@login_required
def view_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Patient role restriction check
    if current_user.role.name == 'Patient' and consultation.patient.email != current_user.email:
        flash('Access denied. You can only view your own health records.', 'danger')
        return redirect(url_for('auth.dashboard'))

    return render_template('consultations/view.html', consultation=consultation)
