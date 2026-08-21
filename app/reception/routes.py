from datetime import datetime, date, time, timedelta
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

    # 1. Today's scheduled appointments (ordered by slot time)
    today_apts = Appointment.query.filter(
        Appointment.appointment_date == today
    ).order_by(Appointment.slot_time.asc()).all()

    # 2. Today's check-ins / queue
    today_check_ins = CheckIn.query.filter(
        CheckIn.check_in_time >= today_start
    ).order_by(CheckIn.check_in_time.desc()).all()

    # 3. KPI counters
    count_today_apts   = len(today_apts)
    count_checked_in   = len(today_check_ins)
    count_waiting      = sum(1 for c in today_check_ins if c.status == 'WAITING')
    count_consulting   = sum(1 for c in today_check_ins if c.status == 'IN_CONSULTATION')
    count_completed    = sum(1 for c in today_check_ins if c.status == 'COMPLETED')
    count_new_patients_today = Patient.query.filter(
        Patient.created_at >= today_start
    ).count()

    # 4. Patient search
    search_q = request.args.get('q', '').strip()
    searched_patients = []
    if search_q:
        f = f"%{search_q}%"
        searched_patients = Patient.query.filter(
            (Patient.patient_code.ilike(f)) |
            (Patient.full_name.ilike(f)) |
            (Patient.mobile.ilike(f)) |
            (Patient.aadhaar_masked.ilike(f))
        ).limit(10).all()

    # 5. Doctors on duty today (for sidebar + check-in form)
    doctor_role = Role.query.filter_by(name='Doctor').first()
    all_doctors = User.query.filter_by(role_id=doctor_role.id, is_active=True).all() if doctor_role else []

    today_weekday = today.weekday()
    avail_doc_ids = {
        a.doctor_id for a in DoctorAvailability.query.filter_by(day_of_week=today_weekday, is_active=True).all()
    }

    doctors_today = []
    for doc in all_doctors:
        q_count = sum(1 for c in today_check_ins if c.doctor_id == doc.id and c.status == 'WAITING')
        doctors_today.append({
            'doctor': doc,
            'is_on_duty': (doc.id in avail_doc_ids) or (len(avail_doc_ids) == 0),
            'queue_count': q_count,
        })

    # 6. Upcoming appointments — next 2 hours
    now = datetime.now()
    two_hours_later = now + timedelta(hours=2)
    upcoming_apts = [
        a for a in today_apts
        if a.status in ('BOOKED',) and
           datetime.combine(today, a.slot_time) >= now and
           datetime.combine(today, a.slot_time) <= two_hours_later
    ]

    # 7. Live waiting queue (sorted by priority then check-in time)
    priority_order = {'Emergency': 0, 'Senior Citizen': 1, 'Pregnant Woman': 2, 'Child': 3, 'Regular': 4}
    waiting_queue = [c for c in today_check_ins if c.status == 'WAITING']
    waiting_queue.sort(key=lambda c: (priority_order.get(c.priority, 5), c.id))

    # 8. Recent front-desk activity feed (last 15 events)
    recent_check_ins = CheckIn.query.filter(
        CheckIn.check_in_time >= today_start
    ).order_by(CheckIn.check_in_time.desc()).limit(10).all()

    recent_apts = Appointment.query.filter(
        Appointment.appointment_date == today,
        Appointment.created_at >= today_start
    ).order_by(Appointment.created_at.desc()).limit(5).all()

    # Build unified activity log
    activity_log = []
    for chk in recent_check_ins:
        icon = 'bi-person-check-fill'
        color = '#059669'
        if chk.status == 'COMPLETED':
            icon, color = 'bi-check2-all', '#2563EB'
        elif chk.status in ('NO_SHOW', 'CANCELLED'):
            icon, color = 'bi-x-circle-fill', '#DC2626'
        activity_log.append({
            'icon': icon,
            'color': color,
            'text': f'{"Checked in" if chk.status not in ("COMPLETED","NO_SHOW","CANCELLED") else chk.status.replace("_"," ").title()}: {chk.patient.full_name}',
            'sub': f'Token {chk.token_no} · Dr. {chk.doctor.name}',
            'time': chk.check_in_time,
        })
    for apt in recent_apts:
        activity_log.append({
            'icon': 'bi-calendar-plus-fill',
            'color': '#7C3AED',
            'text': f'Appointment booked: {apt.patient.full_name}',
            'sub': f'{apt.appointment_code} · Dr. {apt.doctor.name}',
            'time': apt.created_at,
        })
    activity_log.sort(key=lambda x: x['time'], reverse=True)
    activity_log = activity_log[:12]

    # 9. Check-in form for modal
    form = CheckInForm()
    form.doctor_id.choices = [(d.id, f"{d.name} — {d.department or 'OPD'}") for d in all_doctors]

    return render_template('reception/dashboard.html',
        today_apts=today_apts,
        today_check_ins=today_check_ins,
        waiting_queue=waiting_queue,
        upcoming_apts=upcoming_apts,
        activity_log=activity_log,
        doctors_today=doctors_today,
        count_today_apts=count_today_apts,
        count_checked_in=count_checked_in,
        count_waiting=count_waiting,
        count_consulting=count_consulting,
        count_completed=count_completed,
        count_new_patients_today=count_new_patients_today,
        search_q=search_q,
        searched_patients=searched_patients,
        form=form,
        now=now,
    )


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

