from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.auth.models import User, Role
from app.patients.models import Patient
from app.reception.models import CheckIn
from app.reception.forms import CheckInForm

reception_bp = Blueprint('reception', __name__, template_folder='templates', url_prefix='/reception')

@reception_bp.route('/')
@reception_bp.route('/dashboard')
@login_required
@role_required('Admin', 'Receptionist')
def dashboard():
    today_start = datetime.combine(date.today(), datetime.min.time())
    
    # Query today's check-ins
    today_check_ins = CheckIn.query.filter(CheckIn.check_in_time >= today_start).order_by(CheckIn.id.desc()).all()
    
    # Summary Counters
    count_total = len(today_check_ins)
    count_waiting = sum(1 for c in today_check_ins if c.status == 'WAITING')
    count_consulting = sum(1 for c in today_check_ins if c.status == 'IN_CONSULTATION')
    count_completed = sum(1 for c in today_check_ins if c.status == 'COMPLETED')
    count_no_show = sum(1 for c in today_check_ins if c.status in ['NO_SHOW', 'CANCELLED'])

    # Patient Search Query for check-in
    search_q = request.args.get('q', '').strip()
    searched_patients = []
    if search_q:
        filter_str = f"%{search_q}%"
        searched_patients = Patient.query.filter(
            (Patient.patient_code.ilike(filter_str)) |
            (Patient.full_name.ilike(filter_str)) |
            (Patient.mobile.ilike(filter_str))
        ).limit(10).all()

    return render_template('reception/dashboard.html',
                           today_check_ins=today_check_ins,
                           count_total=count_total,
                           count_waiting=count_waiting,
                           count_consulting=count_consulting,
                           count_completed=count_completed,
                           count_no_show=count_no_show,
                           search_q=search_q,
                           searched_patients=searched_patients)


@reception_bp.route('/check-in', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Receptionist')
def check_in():
    patient_id = request.args.get('patient_id', type=int)
    if not patient_id and request.method == 'GET':
        flash('Please select a patient to check-in.', 'warning')
        return redirect(url_for('reception.dashboard'))

    patient = Patient.query.get_or_404(patient_id) if patient_id else None
    
    form = CheckInForm()
    
    # Populate Doctors dropdown
    doctor_role = Role.query.filter_by(name='Doctor').first()
    doctors = User.query.filter_by(role_id=doctor_role.id, is_active=True).all() if doctor_role else []
    form.doctor_id.choices = [(d.id, f"{d.name} ({d.user_code})") for d in doctors]

    if request.method == 'GET' and patient:
        form.patient_id.data = patient.id

    if form.validate_on_submit():
        target_patient_id = int(form.patient_id.data)
        patient_obj = Patient.query.get_or_404(target_patient_id)
        
        # Create CheckIn record
        token_no = CheckIn.generate_token_number()
        check_in_obj = CheckIn(
            patient_id=patient_obj.id,
            doctor_id=form.doctor_id.data,
            token_no=token_no,
            department=form.department.data,
            priority=form.priority.data,
            status='WAITING',
            checked_in_by_id=current_user.id
        )
        db.session.add(check_in_obj)
        db.session.commit()

        flash(f'Patient {patient_obj.full_name} checked-in successfully! Token Issued: {token_no}', 'success')
        return redirect(url_for('reception.print_token', check_in_id=check_in_obj.id))

    return render_template('reception/check_in.html', form=form, patient=patient, doctors=doctors)


@reception_bp.route('/token/<int:check_in_id>')
@login_required
@role_required('Admin', 'Receptionist')
def print_token(check_in_id):
    check_in_obj = CheckIn.query.get_or_404(check_in_id)
    return render_template('reception/print_token.html', check_in=check_in_obj)


@reception_bp.route('/update-status/<int:check_in_id>', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist', 'Doctor')
def update_status(check_in_id):
    check_in_obj = CheckIn.query.get_or_404(check_in_id)
    new_status = request.form.get('status')
    
    if new_status in ['WAITING', 'IN_CONSULTATION', 'COMPLETED', 'NO_SHOW', 'CANCELLED']:
        check_in_obj.status = new_status
        if new_status == 'IN_CONSULTATION' and not check_in_obj.called_time:
            check_in_obj.called_time = datetime.utcnow()
        elif new_status == 'COMPLETED':
            check_in_obj.completed_time = datetime.utcnow()
            
        db.session.commit()
        flash(f'Token {check_in_obj.token_no} status updated to {new_status}.', 'info')
        
    return redirect(url_for('reception.dashboard'))
