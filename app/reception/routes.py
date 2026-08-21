from datetime import datetime, date, time
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.auth.models import User, Role
from app.patients.models import Patient
from app.appointments.models import Appointment, DoctorAvailability
from app.reception.models import CheckIn
from app.reception.forms import CheckInForm

reception_bp = Blueprint('reception', __name__, template_folder='templates', url_prefix='/reception')

@reception_bp.route('/')
@reception_bp.route('/dashboard')
@login_required
@role_required('Admin', 'Receptionist')
def dashboard():
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    # 1. Query today's scheduled appointments
    today_apts = Appointment.query.filter(
        Appointment.appointment_date == today
    ).order_by(Appointment.slot_time.asc()).all()

    # 2. Query today's check-ins & queue
    today_check_ins = CheckIn.query.filter(
        CheckIn.check_in_time >= today_start
    ).order_by(CheckIn.id.desc()).all()
    
    # 3. Operational Counters
    count_today_apts = len(today_apts)
    count_checked_in = len(today_check_ins)
    count_waiting = sum(1 for c in today_check_ins if c.status == 'WAITING')
    count_consulting = sum(1 for c in today_check_ins if c.status == 'IN_CONSULTATION')
    count_completed = sum(1 for c in today_check_ins if c.status == 'COMPLETED')
    count_new_patients_today = Patient.query.filter(Patient.created_at >= today_start).count()
    count_emergency_today = (
        sum(1 for a in today_apts if a.priority == 'Emergency' or a.booking_type == 'Emergency') +
        sum(1 for c in today_check_ins if c.priority == 'Emergency')
    )

    # 4. Patient Search Query for fast lookup & check-in
    search_q = request.args.get('q', '').strip()
    searched_patients = []
    if search_q:
        filter_str = f"%{search_q}%"
        searched_patients = Patient.query.filter(
            (Patient.patient_code.ilike(filter_str)) |
            (Patient.full_name.ilike(filter_str)) |
            (Patient.mobile.ilike(filter_str)) |
            (Patient.aadhaar_masked.ilike(filter_str))
        ).limit(10).all()

    # 5. OPD Doctors on Duty Today
    doctor_role = Role.query.filter_by(name='Doctor').first()
    all_doctors = User.query.filter_by(role_id=doctor_role.id, is_active=True).all() if doctor_role else []
    
    today_weekday = today.weekday()
    availabilities = DoctorAvailability.query.filter_by(day_of_week=today_weekday, is_active=True).all()
    avail_doc_ids = {a.doctor_id for a in availabilities}
    
    doctors_today = []
    for doc in all_doctors:
        is_on_duty = (doc.id in avail_doc_ids) or (len(availabilities) == 0)
        q_count = sum(1 for c in today_check_ins if c.doctor_id == doc.id and c.status == 'WAITING')
        doctors_today.append({
            'doctor': doc,
            'is_on_duty': is_on_duty,
            'specialization': doc.specialization or 'Specialist',
            'department': doc.department or 'OPD',
            'queue_count': q_count
        })

    # 6. Check-in Form instance for quick modal check-in
    form = CheckInForm()
    form.doctor_id.choices = [(d.id, f"{d.name} ({d.user_code})") for d in all_doctors]

    return render_template('reception/dashboard.html',
                           today_apts=today_apts,
                           today_check_ins=today_check_ins,
                           count_today_apts=count_today_apts,
                           count_checked_in=count_checked_in,
                           count_waiting=count_waiting,
                           count_consulting=count_consulting,
                           count_completed=count_completed,
                           count_new_patients_today=count_new_patients_today,
                           count_emergency_today=count_emergency_today,
                           doctors_today=doctors_today,
                           search_q=search_q,
                           searched_patients=searched_patients,
                           form=form,
                           now=datetime.now())


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
    doctor_role = Role.query.filter_by(name='Doctor').first()
    doctors = User.query.filter_by(role_id=doctor_role.id, is_active=True).all() if doctor_role else []
    form.doctor_id.choices = [(d.id, f"{d.name} ({d.user_code})") for d in doctors]

    if request.method == 'GET' and patient:
        form.patient_id.data = patient.id

    if form.validate_on_submit():
        target_patient_id = int(form.patient_id.data)
        patient_obj = Patient.query.get_or_404(target_patient_id)
        
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

        # Sync matching appointment status for today if present
        today = date.today()
        matching_apt = Appointment.query.filter(
            Appointment.patient_id == patient_obj.id,
            Appointment.doctor_id == form.doctor_id.data,
            Appointment.appointment_date == today,
            Appointment.status == 'BOOKED'
        ).first()
        if matching_apt:
            matching_apt.status = 'CHECKED_IN'

        db.session.commit()

        flash(f'Patient {patient_obj.full_name} checked-in successfully! Token Issued: {token_no}', 'success')
        return redirect(url_for('reception.print_token', check_in_id=check_in_obj.id))

    return render_template('reception/check_in.html', form=form, patient=patient, doctors=doctors)


@reception_bp.route('/quick-checkin-apt/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def quick_checkin_apt(appointment_id):
    apt = Appointment.query.get_or_404(appointment_id)
    
    # Check if a check-in already exists for this appointment today
    today_start = datetime.combine(date.today(), datetime.min.time())
    existing_checkin = CheckIn.query.filter(
        CheckIn.patient_id == apt.patient_id,
        CheckIn.doctor_id == apt.doctor_id,
        CheckIn.check_in_time >= today_start
    ).first()

    if existing_checkin:
        flash(f'Patient {apt.patient.full_name} is already checked in with Token {existing_checkin.token_no}.', 'info')
        return redirect(url_for('reception.print_token', check_in_id=existing_checkin.id))

    token_no = CheckIn.generate_token_number()
    check_in_obj = CheckIn(
        patient_id=apt.patient_id,
        doctor_id=apt.doctor_id,
        token_no=token_no,
        department=apt.doctor.department or 'General OPD',
        priority=apt.priority or 'Regular',
        status='WAITING',
        checked_in_by_id=current_user.id
    )
    db.session.add(check_in_obj)
    apt.status = 'CHECKED_IN'
    db.session.commit()

    flash(f'Appointment checked in! Token {token_no} generated for {apt.patient.full_name}.', 'success')
    return redirect(url_for('reception.print_token', check_in_id=check_in_obj.id))


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


@reception_bp.route('/schedules')
@login_required
@role_required('Admin', 'Receptionist')
def schedules():
    doctor_role = Role.query.filter_by(name='Doctor').first()
    doctors = User.query.filter_by(role_id=doctor_role.id, is_active=True).all() if doctor_role else []
    availabilities = DoctorAvailability.query.filter_by(is_active=True).all()
    
    # Map by day of week
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    return render_template('reception/schedules.html',
                           doctors=doctors,
                           availabilities=availabilities,
                           days=days,
                           today_weekday=date.today().weekday())


@reception_bp.route('/emergency-desk', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Receptionist')
def emergency_desk():
    today_start = datetime.combine(date.today(), datetime.min.time())
    
    emergency_checkins = CheckIn.query.filter(
        CheckIn.check_in_time >= today_start,
        CheckIn.priority == 'Emergency'
    ).order_by(CheckIn.id.desc()).all()

    doctor_role = Role.query.filter_by(name='Doctor').first()
    doctors = User.query.filter_by(role_id=doctor_role.id, is_active=True).all() if doctor_role else []

    return render_template('reception/emergency.html',
                           emergency_checkins=emergency_checkins,
                           doctors=doctors)

