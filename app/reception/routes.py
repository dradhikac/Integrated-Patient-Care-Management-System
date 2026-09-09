import io
import csv
from datetime import datetime, date, time, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.auth.models import User, Role
from app.patients.models import Patient
from app.appointments.models import Appointment, DoctorAvailability
from app.reception.models import CheckIn, EmergencyEncounter
from app.reception.forms import CheckInForm
from app.billing.models import Bill, Payment
from app.consultations.models import Consultation

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
            check_in_obj.called_time = datetime.now()
        elif new_status == 'COMPLETED':
            check_in_obj.completed_time = datetime.now()

        today = date.today()
        apt = Appointment.query.filter(
            Appointment.patient_id == check_in_obj.patient_id,
            Appointment.doctor_id == check_in_obj.doctor_id,
            Appointment.appointment_date == today
        ).first()
        if apt and new_status in ['IN_CONSULTATION', 'COMPLETED', 'NO_SHOW', 'CANCELLED']:
            apt.status = new_status
            
        db.session.commit()
        flash(f'Token {check_in_obj.token_no} status updated to {new_status}.', 'info')
        
    return redirect(url_for('reception.dashboard'))


@reception_bp.route('/mark-noshow-apt/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def mark_noshow_apt(appointment_id):
    apt = Appointment.query.get_or_404(appointment_id)
    apt.status = 'NO_SHOW'
    db.session.commit()
    flash(f'Appointment {apt.appointment_code} for {apt.patient.full_name} marked as No Show.', 'warning')
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


@reception_bp.route('/emergency-desk', methods=['GET'])
@login_required
@role_required('Admin', 'Receptionist')
def emergency_desk():
    today_start = datetime.combine(date.today(), datetime.min.time())
    
    # 1. Today's Emergency Encounters
    encounters = EmergencyEncounter.query.filter(
        EmergencyEncounter.arrival_time >= today_start
    ).order_by(EmergencyEncounter.id.desc()).all()

    # 2. Backwards compatibility for raw CheckIns with priority == 'Emergency' not yet linked
    linked_checkin_ids = {e.check_in_id for e in encounters if e.check_in_id}
    legacy_checkins = CheckIn.query.filter(
        CheckIn.check_in_time >= today_start,
        CheckIn.priority == 'Emergency',
        ~CheckIn.id.in_(linked_checkin_ids) if linked_checkin_ids else True
    ).order_by(CheckIn.id.desc()).all()

    doctor_role = Role.query.filter_by(name='Doctor').first()
    doctors = User.query.filter_by(role_id=doctor_role.id, is_active=True).all() if doctor_role else []

    next_temp_id = EmergencyEncounter.generate_temp_id()
    next_token_no = EmergencyEncounter.generate_token_no()

    return render_template('reception/emergency.html',
                           encounters=encounters,
                           legacy_checkins=legacy_checkins,
                           emergency_checkins=encounters,
                           doctors=doctors,
                           next_temp_id=next_temp_id,
                           next_token_no=next_token_no,
                           now=datetime.now())


@reception_bp.route('/emergency/register-unknown', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def emergency_register_unknown():
    """Option A: Register an unidentified / unknown emergency patient with minimum information."""
    emergency_type = request.form.get('emergency_type', 'Medical Emergency').strip()
    priority = request.form.get('priority', 'Emergency / Critical').strip()
    arrival_source = request.form.get('arrival_source', 'Walk-In').strip()
    doctor_id = request.form.get('doctor_id', type=int)
    notes = request.form.get('notes', '').strip() or None

    temp_id = EmergencyEncounter.generate_temp_id()
    token_no = EmergencyEncounter.generate_token_no()

    encounter = EmergencyEncounter(
        temp_id=temp_id,
        token_no=token_no,
        patient_id=None,
        is_identified=False,
        emergency_type=emergency_type,
        priority=priority,
        status='Registered',
        arrival_source=arrival_source,
        assigned_doctor_id=doctor_id if doctor_id and doctor_id > 0 else None,
        notes=notes,
        registered_by_id=current_user.id,
        arrival_time=datetime.now()
    )
    db.session.add(encounter)
    db.session.commit()

    flash(f"Emergency Temporary Record created: {temp_id} with Token {token_no}. Patient routed to Emergency Care!", "success")
    return redirect(url_for('reception.emergency_desk'))


@reception_bp.route('/emergency/register-existing', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def emergency_register_existing():
    """Option B: Register an emergency encounter attached to an existing patient."""
    patient_id = request.form.get('patient_id', type=int)
    if not patient_id:
        flash("Please select an existing patient from the directory.", "warning")
        return redirect(url_for('reception.emergency_desk'))

    patient = Patient.query.get_or_404(patient_id)
    emergency_type = request.form.get('emergency_type', 'Medical Emergency').strip()
    priority = request.form.get('priority', 'Emergency / Critical').strip()
    arrival_source = request.form.get('arrival_source', 'Walk-In').strip()
    doctor_id = request.form.get('doctor_id', type=int)
    notes = request.form.get('notes', '').strip() or None

    temp_id = EmergencyEncounter.generate_temp_id()
    token_no = EmergencyEncounter.generate_token_no()

    encounter = EmergencyEncounter(
        temp_id=temp_id,
        token_no=token_no,
        patient_id=patient.id,
        is_identified=True,
        identified_at=datetime.now(),
        identified_by_id=current_user.id,
        emergency_type=emergency_type,
        priority=priority,
        status='Registered',
        arrival_source=arrival_source,
        assigned_doctor_id=doctor_id if doctor_id and doctor_id > 0 else None,
        notes=notes,
        registered_by_id=current_user.id,
        arrival_time=datetime.now()
    )
    db.session.add(encounter)

    # If doctor is assigned, also link to queue check-in
    if doctor_id and doctor_id > 0:
        chk = CheckIn(
            patient_id=patient.id,
            doctor_id=doctor_id,
            token_no=token_no,
            department='Emergency / Trauma',
            priority='Emergency',
            status='WAITING',
            checked_in_by_id=current_user.id
        )
        db.session.add(chk)
        db.session.flush()
        encounter.check_in_id = chk.id

    db.session.commit()

    flash(f"Emergency encounter registered for {patient.full_name} ({patient.patient_code}) with Token {token_no}!", "success")
    return redirect(url_for('reception.emergency_desk'))


@reception_bp.route('/emergency/<int:encounter_id>/update', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def emergency_update(encounter_id):
    """Update emergency encounter status, triage, assigned doctor, or operational notes."""
    encounter = EmergencyEncounter.query.get_or_404(encounter_id)
    
    new_status = request.form.get('status')
    new_doctor_id = request.form.get('doctor_id', type=int)
    new_priority = request.form.get('priority')
    new_notes = request.form.get('notes')

    if new_status:
        encounter.status = new_status
    if new_doctor_id is not None:
        encounter.assigned_doctor_id = new_doctor_id if new_doctor_id > 0 else None
    if new_priority:
        encounter.priority = new_priority
    if new_notes is not None:
        encounter.notes = new_notes.strip() or None

    # Sync check_in status if linked
    if encounter.check_in:
        if new_status in ('Under Treatment', 'In Cabin'):
            encounter.check_in.status = 'IN_CONSULTATION'
            if not encounter.check_in.called_time:
                encounter.check_in.called_time = datetime.now()
        elif new_status in ('Stabilized', 'Completed', 'Discharged'):
            encounter.check_in.status = 'COMPLETED'
            if not encounter.check_in.completed_time:
                encounter.check_in.completed_time = datetime.now()

    db.session.commit()
    flash(f"Emergency Case {encounter.token_no} updated successfully.", "info")
    return redirect(url_for('reception.emergency_desk'))


@reception_bp.route('/emergency/<int:encounter_id>/link-existing', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def emergency_link_existing(encounter_id):
    """Link an unidentified temporary emergency record to an existing patient found in the directory."""
    encounter = EmergencyEncounter.query.get_or_404(encounter_id)
    target_patient_id = request.form.get('patient_id', type=int)
    
    if not target_patient_id:
        flash("Please select a valid patient to link.", "warning")
        return redirect(url_for('reception.emergency_desk'))

    patient = Patient.query.get_or_404(target_patient_id)
    
    # Update encounter while preserving temp_id for audit history
    encounter.patient_id = patient.id
    encounter.is_identified = True
    encounter.identified_at = datetime.now()
    encounter.identified_by_id = current_user.id

    # If doctor is assigned and no check_in exists yet, create check_in
    if encounter.assigned_doctor_id and not encounter.check_in_id:
        chk = CheckIn(
            patient_id=patient.id,
            doctor_id=encounter.assigned_doctor_id,
            token_no=encounter.token_no,
            department='Emergency / Trauma',
            priority='Emergency',
            status='WAITING',
            checked_in_by_id=current_user.id
        )
        db.session.add(chk)
        db.session.flush()
        encounter.check_in_id = chk.id

    db.session.commit()
    flash(f"Temporary Record {encounter.temp_id} successfully linked to verified patient {patient.full_name} ({patient.patient_code})!", "success")
    return redirect(url_for('reception.emergency_desk'))


@reception_bp.route('/emergency/<int:encounter_id>/convert-new-patient', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def emergency_convert_new_patient(encounter_id):
    """Convert an unidentified emergency record to a newly registered permanent patient."""
    encounter = EmergencyEncounter.query.get_or_404(encounter_id)
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    dob_str = request.form.get('dob', '').strip()
    age_str = request.form.get('age', '').strip()
    gender = request.form.get('gender', 'Other').strip()
    mobile = request.form.get('mobile', '').strip() or None
    aadhaar_raw = request.form.get('aadhaar_number', '').strip() or None
    blood_group = request.form.get('blood_group', '').strip() or None
    emergency_contact_name = request.form.get('emergency_contact_name', '').strip() or None
    emergency_contact_mobile = request.form.get('emergency_contact_mobile', '').strip() or None
    address = request.form.get('address', '').strip() or None

    if not first_name or not last_name:
        flash("First Name and Last Name are required to create a patient profile.", "danger")
        return redirect(url_for('reception.emergency_desk'))

    # Parse or compute DOB
    dob = None
    if dob_str:
        try:
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if not dob and age_str and age_str.isdigit():
        dob = date(date.today().year - int(age_str), 1, 1)
    if not dob:
        dob = date(2000, 1, 1)

    patient = Patient(
        patient_code=Patient.generate_patient_code(),
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name} {last_name}",
        dob=dob,
        gender=gender,
        mobile=mobile or '—',
        blood_group=blood_group,
        emergency_contact_name=emergency_contact_name,
        emergency_contact_mobile=emergency_contact_mobile,
        address=address,
        registered_by_id=current_user.id,
        portal_status='NOT_ACTIVATED',
    )
    if aadhaar_raw:
        patient.set_aadhaar(aadhaar_raw)

    db.session.add(patient)
    db.session.flush()

    # Link encounter to this new permanent patient, keeping temp_id in history
    encounter.patient_id = patient.id
    encounter.is_identified = True
    encounter.identified_at = datetime.now()
    encounter.identified_by_id = current_user.id

    if encounter.assigned_doctor_id and not encounter.check_in_id:
        chk = CheckIn(
            patient_id=patient.id,
            doctor_id=encounter.assigned_doctor_id,
            token_no=encounter.token_no,
            department='Emergency / Trauma',
            priority='Emergency',
            status='WAITING',
            checked_in_by_id=current_user.id
        )
        db.session.add(chk)
        db.session.flush()
        encounter.check_in_id = chk.id

    db.session.commit()
    flash(f"New patient profile created ({patient.patient_code}: {patient.full_name}) and linked to emergency record {encounter.temp_id}!", "success")
    return redirect(url_for('reception.emergency_desk'))


@reception_bp.route('/emergency/print-token/<int:encounter_id>', methods=['GET'])
@login_required
@role_required('Admin', 'Receptionist')
def emergency_print_token(encounter_id):
    """Printable emergency routing and token slip."""
    encounter = EmergencyEncounter.query.get_or_404(encounter_id)
    return render_template('reception/print_emergency_token.html', encounter=encounter)


@reception_bp.route('/api/emergency/search-patients', methods=['GET'])
@login_required
@role_required('Admin', 'Receptionist')
def api_emergency_search_patients():
    """Fast AJAX patient search for emergency desk modals."""
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'success': True, 'patients': []})

    sf = f"%{q}%"
    patients = Patient.query.filter(
        (Patient.patient_code.ilike(sf)) |
        (Patient.full_name.ilike(sf)) |
        (Patient.mobile.ilike(sf)) |
        (Patient.aadhaar_masked.ilike(sf))
    ).limit(10).all()

    results = []
    for p in patients:
        results.append({
            'id': p.id,
            'patient_code': p.patient_code,
            'full_name': p.full_name,
            'mobile': p.mobile or '—',
            'gender': p.gender,
            'blood_group': p.blood_group or '—',
            'dob': p.dob.strftime('%d-%b-%Y') if p.dob else '—',
            'masked_aadhaar': p.aadhaar_masked or '—'
        })

    return jsonify({'success': True, 'patients': results})


# ───────────────────────────────────────────────────────────────────────────────
#  PATIENT MANAGEMENT — Receptionist Shell
# ───────────────────────────────────────────────────────────────────────────────

@reception_bp.route('/patients')
@login_required
@role_required('Admin', 'Receptionist')
def patients_directory():
    """Patient Directory wrapped in the Receptionist shell."""
    query = request.args.get('q', '').strip()
    portal_filter = request.args.get('portal', '').strip()
    page = request.args.get('page', 1, type=int)

    patient_query = Patient.query
    if query:
        sf = f"%{query}%"
        patient_query = patient_query.filter(
            (Patient.patient_code.ilike(sf)) |
            (Patient.full_name.ilike(sf)) |
            (Patient.mobile.ilike(sf)) |
            (Patient.aadhaar_masked.ilike(sf))
        )
    if portal_filter in ('NOT_ACTIVATED', 'PENDING', 'ACTIVE', 'LOCKED'):
        patient_query = patient_query.filter(Patient.portal_status == portal_filter)

    pagination = patient_query.order_by(Patient.id.desc()).paginate(page=page, per_page=20, error_out=False)
    patients = pagination.items

    # Portal status counts for filter pills
    from sqlalchemy import func
    portal_counts = {
        row[0]: row[1]
        for row in db.session.query(Patient.portal_status, func.count(Patient.id)).group_by(Patient.portal_status).all()
    }

    return render_template('reception/patients_directory.html',
                           patients=patients,
                           pagination=pagination,
                           query=query,
                           portal_filter=portal_filter,
                           portal_counts=portal_counts,
                           now=datetime.now())


@reception_bp.route('/patients/register', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Receptionist')
def register_patient_rec():
    """Register a new patient — rendered inside the Receptionist shell."""
    from app.patients.forms import PatientRegistrationForm
    from app.patients.models import Patient, PatientMedicalHistory, PatientAllergy
    from app.patients.duplicate_check import check_for_duplicates

    form = PatientRegistrationForm()
    force_create = request.args.get('force_create', '0') == '1'

    if form.validate_on_submit():
        first_name = form.first_name.data.strip()
        last_name = form.last_name.data.strip()
        dob = form.dob.data
        mobile = form.mobile.data.strip()
        aadhaar_raw = form.aadhaar_number.data.strip() if form.aadhaar_number.data else None

        # Duplicate detection (unless force_create)
        if not force_create:
            is_dup, dup_matches = check_for_duplicates(first_name, last_name, dob, mobile, aadhaar_raw)
            if is_dup:
                return render_template('reception/duplicate_alert_rec.html',
                                       form_data=request.form,
                                       form=form,
                                       dup_matches=dup_matches)

        # Create Patient Record
        patient = Patient(
            patient_code=Patient.generate_patient_code(),
            first_name=first_name,
            last_name=last_name,
            full_name=f"{first_name} {last_name}",
            dob=dob,
            gender=form.gender.data,
            mobile=mobile,
            email=form.email.data.strip() if form.email.data else None,
            address=form.address.data.strip() if form.address.data else None,
            blood_group=form.blood_group.data if form.blood_group.data else None,
            emergency_contact_name=form.emergency_contact_name.data.strip() if form.emergency_contact_name.data else None,
            emergency_contact_mobile=form.emergency_contact_mobile.data.strip() if form.emergency_contact_mobile.data else None,
            insurance_provider=form.insurance_provider.data.strip() if form.insurance_provider.data else None,
            insurance_policy_no=form.insurance_policy_no.data.strip() if form.insurance_policy_no.data else None,
            height_cm=form.height_cm.data,
            weight_kg=form.weight_kg.data,
            vaccination_records=form.vaccination_records.data.strip() if form.vaccination_records.data else None,
            preferred_language=form.preferred_language.data,
            registered_by_id=current_user.id,
            portal_status='NOT_ACTIVATED',
        )
        patient.set_aadhaar(aadhaar_raw)
        patient.calculate_bmi()
        db.session.add(patient)
        db.session.flush()

        # Allergies
        if form.allergies.data:
            for item in [a.strip() for a in form.allergies.data.split(',') if a.strip()]:
                db.session.add(PatientAllergy(patient_id=patient.id, allergen=item, severity='Moderate'))

        # Medical history
        if form.chronic_diseases.data:
            db.session.add(PatientMedicalHistory(
                patient_id=patient.id,
                condition_type='Chronic Disease',
                description=form.chronic_diseases.data.strip()
            ))

        db.session.commit()

        return redirect(url_for('reception.registration_success', patient_id=patient.id))

    return render_template('reception/register_patient.html', form=form)


@reception_bp.route('/patients/<int:patient_id>/success')
@login_required
@role_required('Admin', 'Receptionist')
def registration_success(patient_id):
    """Success screen shown after registering a patient."""
    patient = Patient.query.get_or_404(patient_id)
    return render_template('reception/registration_success.html', patient=patient)


@reception_bp.route('/patients/<int:patient_id>')
@login_required
@role_required('Admin', 'Receptionist', 'Doctor')
def patient_profile_rec(patient_id):
    """Patient profile view wrapped in the Receptionist shell."""
    patient = Patient.query.get_or_404(patient_id)
    return render_template('reception/patient_profile.html', patient=patient)


@reception_bp.route('/patients/<int:patient_id>/send-activation', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def send_activation(patient_id):
    """Generate a portal activation token and email/display it to the patient."""
    from app.auth.utils import generate_otp, generate_reset_token
    from app.auth.models import PasswordResetToken

    patient = Patient.query.get_or_404(patient_id)

    # Don't re-send if already active
    if patient.portal_status == 'ACTIVE':
        flash(f'Portal for {patient.full_name} is already active.', 'info')
        return redirect(url_for('reception.patient_profile_rec', patient_id=patient.id))

    if not patient.email and not patient.mobile:
        flash('Patient must have an email address or mobile number to receive an activation link.', 'danger')
        return redirect(url_for('reception.patient_profile_rec', patient_id=patient.id))

    # Invalidate any previous PORTAL_ACTIVATION tokens for this patient
    PasswordResetToken.query.filter_by(patient_id=patient.id, purpose='PORTAL_ACTIVATION', is_used=False).update({'is_used': True})
    db.session.flush()

    # Generate new token
    token_str = generate_reset_token()
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(hours=24)

    activation = PasswordResetToken(
        user_id=None,
        patient_id=patient.id,
        token=token_str,
        otp_code=otp,
        expires_at=expiry,
        purpose='PORTAL_ACTIVATION',
        is_used=False,
    )
    db.session.add(activation)
    patient.portal_status = 'PENDING'
    db.session.commit()

    # Build activation URL (patient clicks this to set their password)
    activation_url = url_for('reception.activate_portal', token=token_str, _external=True)

    # Email if configured
    sent_via = 'console'
    try:
        from app.extensions import mail
        from flask_mail import Message
        import flask
        if flask.current_app.config.get('MAIL_USERNAME'):
            msg = Message(
                subject='CareHub Portal Activation',
                sender=flask.current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[patient.email],
                body=(
                    f"Dear {patient.full_name},\n\n"
                    f"Your CareHub Patient Portal account has been created.\n"
                    f"Click the link below to set your password and activate your account:\n\n"
                    f"{activation_url}\n\n"
                    f"Or use OTP code: {otp}  (valid 24 hours)\n\n"
                    f"If you did not request this, please ignore this email.\n\n"
                    f"— CareHub Team"
                )
            )
            mail.send(msg)
            sent_via = f'email ({patient.email})'
    except Exception:
        pass  # Fall through to console/flash

    # Always show activation link in flash for dev/demo environments
    flash(
        f'Activation link generated for {patient.full_name}. '
        f'Status → PENDING. '
        f'Sent via: {sent_via}. '
        f'Dev link: {activation_url}',
        'success'
    )
    return redirect(url_for('reception.patient_profile_rec', patient_id=patient.id))


@reception_bp.route('/activate/<token>', methods=['GET', 'POST'])
def activate_portal(token):
    """
    Public route — patient clicks activation link, sets their own password.
    No login required (the token IS the authentication).
    """
    from app.auth.models import PasswordResetToken, Role
    from app.auth.utils import generate_reset_token

    record = PasswordResetToken.query.filter_by(
        token=token, purpose='PORTAL_ACTIVATION', is_used=False
    ).first_or_404()

    if datetime.utcnow() > record.expires_at:
        flash('This activation link has expired. Please ask the receptionist to resend it.', 'danger')
        return redirect(url_for('auth.login'))

    patient = Patient.query.get_or_404(record.patient_id)

    if patient.portal_status == 'ACTIVE':
        flash('This portal account is already active. Please log in.', 'info')
        return redirect(url_for('auth.login'))

    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if len(password) < 8:
            error = 'Password must be at least 8 characters long.'
        elif password != confirm:
            error = 'Passwords do not match.'
        else:
            # Check if a user account already exists for this email
            existing_user = User.query.filter_by(email=patient.email).first() if patient.email else None

            if existing_user:
                # Update existing user password and link
                existing_user.set_password(password)
                existing_user.is_active = True
                patient.portal_user_id = existing_user.id
            else:
                # Create new User account
                patient_role = Role.query.filter_by(name='Patient').first()
                if not patient_role:
                    patient_role = Role(name='Patient', description='Patient Portal User')
                    db.session.add(patient_role)
                    db.session.flush()

                user_code = f"PAT-{int(datetime.utcnow().timestamp()) % 1000000:06d}"
                new_user = User(
                    user_code=user_code,
                    name=patient.full_name,
                    email=patient.email or f"patient_{patient.id}@carehub.local",
                    mobile=patient.mobile,
                    role_id=patient_role.id,
                    is_active=True,
                )
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.flush()
                patient.portal_user_id = new_user.id

            patient.portal_status = 'ACTIVE'
            record.is_used = True
            db.session.commit()

            flash(f'Welcome, {patient.full_name}! Your CareHub Patient Portal is now active.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('reception/activate_portal.html', patient=patient, token=token, error=error)


@reception_bp.route('/appointments-view')
@login_required
@role_required('Admin', 'Receptionist')
def appointments_rec():
    """Today's appointments page wrapped in the Receptionist shell."""
    from app.appointments.models import Appointment
    today = date.today()
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    page = request.args.get('page', 1, type=int)

    apt_query = Appointment.query
    if q:
        sf = f"%{q}%"
        apt_query = apt_query.join(Appointment.patient).filter(
            (Patient.full_name.ilike(sf)) |
            (Patient.patient_code.ilike(sf)) |
            (Appointment.appointment_code.ilike(sf))
        )
    if status_filter:
        apt_query = apt_query.filter(Appointment.status == status_filter)

    pagination = apt_query.order_by(Appointment.appointment_date.desc(), Appointment.slot_time.asc()).paginate(page=page, per_page=25, error_out=False)

    return render_template('reception/appointments_rec.html',
                           appointments=pagination.items,
                           pagination=pagination,
                           q=q,
                           status_filter=status_filter,
                           today=today)


# ───────────────────────────────────────────────────────────────────────────────
#  PAYMENT & BILLING AFTER CONSULTATION — Receptionist Action
# ───────────────────────────────────────────────────────────────────────────────

@reception_bp.route('/payment-modal-data/<int:appointment_id>', methods=['GET'])
@login_required
@role_required('Admin', 'Receptionist')
def payment_modal_data(appointment_id):
    """Returns JSON data with billable items and payment status for an appointment."""
    from app.appointments.models import Appointment
    from app.consultations.models import Consultation
    from app.billing.models import Bill, Payment
    from app.billing.aggregator import generate_auto_bill_for_patient

    apt = Appointment.query.get_or_404(appointment_id)
    
    # 1. Find linked consultation
    cns = apt.consultation
    if not cns:
        cns = Consultation.query.filter_by(appointment_id=apt.id).first()
    if not cns:
        cns = Consultation.query.filter(
            Consultation.patient_id == apt.patient_id,
            Consultation.doctor_id == apt.doctor_id,
            Consultation.created_at >= datetime.combine(apt.appointment_date, datetime.min.time()),
            Consultation.created_at <= datetime.combine(apt.appointment_date, datetime.max.time())
        ).first()

    # 2. Find or generate bill
    bill = None
    if cns:
        bill = Bill.query.filter_by(consultation_id=cns.id).first()
        if not bill:
            bill = generate_auto_bill_for_patient(patient_id=apt.patient_id, consultation_id=cns.id)
    else:
        bill = Bill.query.filter(
            Bill.patient_id == apt.patient_id,
            Bill.created_at >= datetime.combine(apt.appointment_date, datetime.min.time()),
            Bill.created_at <= datetime.combine(apt.appointment_date, datetime.max.time())
        ).first()
        if not bill:
            bill = generate_auto_bill_for_patient(patient_id=apt.patient_id)

    # 3. Format items
    items_data = []
    for itm in bill.items:
        items_data.append({
            'type': itm.item_type,
            'description': itm.item_description,
            'unit_price': itm.unit_price,
            'quantity': itm.quantity,
            'total_price': itm.total_price
        })

    # Recent payments
    payments_data = []
    for p in bill.payments:
        payments_data.append({
            'code': p.payment_code,
            'amount': p.amount_paid,
            'method': p.payment_method,
            'ref': p.transaction_ref or '—',
            'date': p.paid_at.strftime('%d %b %Y, %I:%M %p')
        })

    doc_dept = apt.doctor.department or (apt.doctor.doctor_profile.department if (hasattr(apt.doctor, 'doctor_profile') and apt.doctor.doctor_profile) else 'General OPD')

    return jsonify({
        'success': True,
        'appointment_id': apt.id,
        'appointment_code': apt.appointment_code,
        'consultation_id': cns.id if cns else None,
        'consultation_code': cns.consultation_code if cns else 'CNS-OPD',
        'consultation_date': (cns.created_at if cns else apt.created_at).strftime('%d %B %Y, %I:%M %p'),
        'patient': {
            'id': apt.patient.id,
            'name': apt.patient.full_name,
            'code': apt.patient.patient_code,
            'mobile': apt.patient.mobile,
            'gender': apt.patient.gender
        },
        'doctor': {
            'id': apt.doctor.id,
            'name': apt.doctor.name,
            'department': doc_dept
        },
        'bill': {
            'id': bill.id,
            'invoice_code': bill.invoice_code,
            'subtotal': bill.subtotal,
            'discount': bill.discount,
            'tax_amount': bill.tax_amount,
            'grand_total': bill.grand_total,
            'paid_amount': bill.paid_amount,
            'balance_due': bill.balance_due,
            'status': bill.status,
            'items': items_data,
            'payments': payments_data
        }
    })


@reception_bp.route('/collect-payment', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def collect_payment():
    """Records patient consultation payment and updates bill status."""
    from app.appointments.models import Appointment
    from app.consultations.models import Consultation
    from app.billing.models import Bill, Payment
    from app.billing.aggregator import generate_auto_bill_for_patient

    bill_id = request.form.get('bill_id', type=int)
    appointment_id = request.form.get('appointment_id', type=int)
    consultation_id = request.form.get('consultation_id', type=int)
    amount_paid = request.form.get('amount_paid', type=float)
    payment_method = request.form.get('payment_method', 'Cash')
    transaction_ref = request.form.get('transaction_ref', '').strip() or None

    bill = None
    if bill_id:
        bill = Bill.query.get(bill_id)
    elif consultation_id:
        bill = Bill.query.filter_by(consultation_id=consultation_id).first()
        if not bill:
            cns = Consultation.query.get(consultation_id)
            if cns:
                bill = generate_auto_bill_for_patient(patient_id=cns.patient_id, consultation_id=cns.id)
    elif appointment_id:
        apt = Appointment.query.get(appointment_id)
        if apt:
            cns = apt.consultation or Consultation.query.filter_by(appointment_id=apt.id).first()
            if cns:
                bill = Bill.query.filter_by(consultation_id=cns.id).first() or generate_auto_bill_for_patient(patient_id=apt.patient_id, consultation_id=cns.id)
            else:
                bill = generate_auto_bill_for_patient(patient_id=apt.patient_id)

    if not bill:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.form.get('is_ajax') == '1':
            return jsonify({'success': False, 'message': 'Invoice / Bill record could not be located.'}), 404
        flash('Bill record could not be located.', 'danger')
        return redirect(url_for('reception.dashboard'))

    if not amount_paid or amount_paid <= 0:
        msg = 'Payment amount must be greater than zero.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.form.get('is_ajax') == '1':
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('reception.dashboard'))

    if amount_paid > bill.balance_due + 0.01:
        msg = f"Payment amount (₹{amount_paid:.2f}) cannot exceed balance due (₹{bill.balance_due:.2f})."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.form.get('is_ajax') == '1':
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'warning')
        return redirect(url_for('reception.dashboard'))

    payment_code = Payment.generate_payment_code()
    payment = Payment(
        bill_id=bill.id,
        payment_code=payment_code,
        payment_method=payment_method,
        amount_paid=amount_paid,
        transaction_ref=transaction_ref,
        recorded_by_id=current_user.id
    )
    db.session.add(payment)

    bill.paid_amount += amount_paid
    if bill.paid_amount >= bill.grand_total - 0.01:
        bill.status = 'PAID'
    else:
        bill.status = 'PARTIALLY_PAID'

    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.form.get('is_ajax') == '1':
        return jsonify({
            'success': True,
            'message': f"Payment of ₹{amount_paid:.2f} recorded successfully ({payment_method})!",
            'payment_code': payment_code,
            'bill_id': bill.id,
            'invoice_code': bill.invoice_code,
            'amount_paid': amount_paid,
            'payment_method': payment_method,
            'transaction_ref': transaction_ref or '—',
            'status': bill.status,
            'balance_due': bill.balance_due,
            'paid_at': payment.paid_at.strftime('%d %b %Y, %I:%M %p'),
            'patient_name': bill.patient.full_name,
            'receipt_url': url_for('billing.view_bill', bill_id=bill.id)
        })

    flash(f"Payment of ₹{amount_paid:.2f} recorded successfully! Receipt: {payment_code}", 'success')
    return redirect(url_for('billing.view_bill', bill_id=bill.id))


# ─────────────────────────────────────────────────────────────
# RECEPTIONIST OPERATIONAL NOTIFICATIONS (DROPDOWN & HISTORY)
# ─────────────────────────────────────────────────────────────
@reception_bp.route('/api/notifications/recent', methods=['GET'])
@login_required
@role_required('Admin', 'Receptionist')
def api_recent_notifications():
    """Returns real-time front desk notifications for the top bell popover."""
    from app.notifications.reception_notifications import (
        get_reception_notifications, get_reception_unread_count
    )
    unread_count = get_reception_unread_count()
    notifs = get_reception_notifications(limit=10)

    data = []
    for n in notifs:
        data.append({
            'id': n.id,
            'category': n.category,
            'title': n.title,
            'message': n.message,
            'icon': n.icon,
            'color': n.color,
            'link': n.link or url_for('reception.dashboard'),
            'is_read': n.is_read,
            'time_ago': n.time_ago,
            'created_at_str': n.created_at.strftime('%I:%M %p') if n.created_at else ''
        })

    return jsonify({
        'success': True,
        'unread_count': unread_count,
        'notifications': data
    })


@reception_bp.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def api_mark_notification_read(notif_id):
    """Marks a single receptionist notification as read."""
    from app.notifications.reception_notifications import (
        mark_reception_notification_read, get_reception_unread_count
    )
    success = mark_reception_notification_read(notif_id)
    unread_count = get_reception_unread_count()
    return jsonify({
        'success': success,
        'unread_count': unread_count
    })


@reception_bp.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def api_mark_all_notifications_read():
    """Marks all unread receptionist notifications as read."""
    from app.notifications.reception_notifications import (
        mark_all_reception_notifications_read
    )
    count = mark_all_reception_notifications_read()
    return jsonify({
        'success': True,
        'marked_count': count,
        'unread_count': 0
    })


@reception_bp.route('/notifications', methods=['GET'])
@login_required
@role_required('Admin', 'Receptionist')
def notification_history():
    """
    Dedicated Receptionist Notification History page.
    Renders in the modern MediCore+ Receptionist Dashboard UI.
    """
    from app.notifications.reception_notifications import (
        get_reception_notifications, get_reception_unread_count
    )
    from app.notifications.models import StaffNotification

    tab = request.args.get('tab', 'all').lower()
    search = request.args.get('q', '').strip()

    # Category mapping
    category_filter = None
    unread_only = False

    if tab == 'unread':
        unread_only = True
    elif tab == 'appointments':
        category_filter = 'APPOINTMENT'
    elif tab == 'patients':
        category_filter = 'PATIENT'
    elif tab == 'queue':
        category_filter = 'QUEUE'
    elif tab == 'payments':
        category_filter = 'PAYMENT'
    elif tab == 'checkin':
        category_filter = 'CHECK_IN'

    notifications = get_reception_notifications(
        limit=100,
        unread_only=unread_only,
        category=category_filter,
        search=search
    )

    unread_count = get_reception_unread_count()

    # Count stats for badge pills
    base_query = StaffNotification.query.filter_by(role_target='Receptionist')
    counts_by_tab = {
        'all': base_query.count(),
        'unread': base_query.filter_by(is_read=False).count(),
        'appointments': base_query.filter_by(category='APPOINTMENT').count(),
        'patients': base_query.filter_by(category='PATIENT').count(),
        'queue': base_query.filter_by(category='QUEUE').count(),
        'payments': base_query.filter_by(category='PAYMENT').count(),
    }

    return render_template('reception/notifications.html',
                           notifications=notifications,
                           current_tab=tab,
                           unread_count=unread_count,
                           counts_by_tab=counts_by_tab,
                           search=search)


@reception_bp.route('/reports', methods=['GET'])
@reception_bp.route('/daily-reports', methods=['GET'])
@login_required
@role_required('Admin', 'Receptionist')
def daily_reports():
    """
    Dedicated Receptionist Daily Reports Dashboard.
    Renders in the modern MediCore+ Receptionist UI with front-desk shift metrics,
    OPD token intake logs, doctor consultation breakdown, cash counter reconciliation,
    and printable shift handover report.
    """
    date_str = request.args.get('date', '').strip()
    shift = request.args.get('shift', 'all').lower()
    status_filter = request.args.get('status', 'ALL').upper()
    dept_filter = request.args.get('dept', 'ALL')
    search_q = request.args.get('q', '').strip()

    try:
        if date_str:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            selected_date = date.today()
    except (ValueError, TypeError):
        selected_date = date.today()

    # Time boundaries based on selected shift
    if shift == 'morning':
        start_dt = datetime.combine(selected_date, time(6, 0, 0))
        end_dt = datetime.combine(selected_date, time(13, 59, 59))
        shift_label = "Morning Shift (06:00 AM – 02:00 PM)"
    elif shift == 'evening':
        start_dt = datetime.combine(selected_date, time(14, 0, 0))
        end_dt = datetime.combine(selected_date, time(21, 59, 59))
        shift_label = "Evening Shift (02:00 PM – 10:00 PM)"
    elif shift == 'night':
        start_dt = datetime.combine(selected_date, time(22, 0, 0))
        end_dt = datetime.combine(selected_date + timedelta(days=1), time(5, 59, 59))
        shift_label = "Night Shift (10:00 PM – 06:00 AM)"
    else:
        shift = 'all'
        start_dt = datetime.combine(selected_date, time(0, 0, 0))
        end_dt = datetime.combine(selected_date, time(23, 59, 59))
        shift_label = "Full Day Shift (24 Hours)"

    # 1. Check-ins for the selected timeframe
    all_checkins = CheckIn.query.filter(
        CheckIn.check_in_time >= start_dt,
        CheckIn.check_in_time <= end_dt
    ).order_by(CheckIn.check_in_time.desc()).all()

    total_intakes = len(all_checkins)
    waiting_count = sum(1 for c in all_checkins if c.status == 'WAITING')
    in_consult_count = sum(1 for c in all_checkins if c.status == 'IN_CONSULTATION')
    completed_count = sum(1 for c in all_checkins if c.status == 'COMPLETED')
    cancelled_count = sum(1 for c in all_checkins if c.status in ('CANCELLED', 'NO_SHOW'))

    # Average wait time & consultation duration
    completed_wait_times = [c.waiting_duration_minutes for c in all_checkins if c.waiting_duration_minutes is not None]
    avg_wait_minutes = round(sum(completed_wait_times) / len(completed_wait_times), 1) if completed_wait_times else 0.0

    completed_durations = [c.actual_duration_minutes for c in all_checkins if c.actual_duration_minutes is not None]
    avg_consult_minutes = round(sum(completed_durations) / len(completed_durations), 1) if completed_durations else 0.0

    # 2. New patient registrations on this date
    new_patients_count = Patient.query.filter(
        Patient.created_at >= start_dt,
        Patient.created_at <= end_dt
    ).count()

    # 3. Scheduled appointments for this date
    day_apts = Appointment.query.filter(
        Appointment.appointment_date == selected_date
    ).all()
    total_apts = len(day_apts)
    apts_booked = sum(1 for a in day_apts if a.status == 'BOOKED')
    apts_checked_in = sum(1 for a in day_apts if a.status == 'CHECKED_IN')
    apts_completed = sum(1 for a in day_apts if a.status == 'COMPLETED')
    apts_cancelled = sum(1 for a in day_apts if a.status == 'CANCELLED')

    # 4. Emergency cases & walk-ins
    emergency_encounters = EmergencyEncounter.query.filter(
        EmergencyEncounter.arrival_time >= start_dt,
        EmergencyEncounter.arrival_time <= end_dt
    ).all()
    er_priority_checkins = sum(1 for c in all_checkins if c.priority == 'Emergency')
    emergency_cases_total = len(emergency_encounters) + er_priority_checkins

    # 5. Front-desk payments recorded during timeframe
    payments = Payment.query.filter(
        Payment.paid_at >= start_dt,
        Payment.paid_at <= end_dt
    ).order_by(Payment.paid_at.desc()).all()

    total_revenue = sum(p.amount_paid for p in payments)
    cash_revenue = sum(p.amount_paid for p in payments if (p.payment_method or '').strip() == 'Cash')
    upi_revenue = sum(p.amount_paid for p in payments if 'UPI' in (p.payment_method or ''))
    card_revenue = sum(p.amount_paid for p in payments if 'Card' in (p.payment_method or ''))
    other_revenue = total_revenue - (cash_revenue + upi_revenue + card_revenue)

    # 6. Priority & Department Breakdown
    priority_breakdown = {
        'Emergency': er_priority_checkins,
        'Senior Citizen': sum(1 for c in all_checkins if c.priority == 'Senior Citizen'),
        'Pregnant Woman': sum(1 for c in all_checkins if c.priority == 'Pregnant Woman'),
        'Child': sum(1 for c in all_checkins if c.priority == 'Child'),
        'Regular': sum(1 for c in all_checkins if c.priority in ('Regular', None, ''))
    }

    department_breakdown = {}
    for c in all_checkins:
        dept = c.department or 'General OPD'
        department_breakdown[dept] = department_breakdown.get(dept, 0) + 1

    # 7. Hourly Footfall Buckets
    hourly_distribution = {
        '08:00 - 10:00': 0,
        '10:00 - 12:00': 0,
        '12:00 - 14:00': 0,
        '14:00 - 16:00': 0,
        '16:00 - 18:00': 0,
        '18:00 - 20:00': 0,
        '20:00+': 0
    }
    for c in all_checkins:
        if c.check_in_time:
            hr = c.check_in_time.hour
            if 8 <= hr < 10:
                hourly_distribution['08:00 - 10:00'] += 1
            elif 10 <= hr < 12:
                hourly_distribution['10:00 - 12:00'] += 1
            elif 12 <= hr < 14:
                hourly_distribution['12:00 - 14:00'] += 1
            elif 14 <= hr < 16:
                hourly_distribution['14:00 - 16:00'] += 1
            elif 16 <= hr < 18:
                hourly_distribution['16:00 - 18:00'] += 1
            elif 18 <= hr < 20:
                hourly_distribution['18:00 - 20:00'] += 1
            else:
                hourly_distribution['20:00+'] += 1

    # 8. Doctor-wise OPD Performance
    doctor_role = Role.query.filter_by(name='Doctor').first()
    all_doctors = User.query.filter_by(role_id=doctor_role.id, is_active=True).all() if doctor_role else []

    today_weekday = selected_date.weekday()
    avail_doc_ids = {
        a.doctor_id for a in DoctorAvailability.query.filter_by(day_of_week=today_weekday, is_active=True).all()
    }

    doctor_summaries = []
    for doc in all_doctors:
        doc_tokens = [c for c in all_checkins if c.doctor_id == doc.id]
        doc_completed = sum(1 for c in doc_tokens if c.status == 'COMPLETED')
        doc_waiting = sum(1 for c in doc_tokens if c.status == 'WAITING')
        doc_in_consult = sum(1 for c in doc_tokens if c.status == 'IN_CONSULTATION')
        doc_cancelled = sum(1 for c in doc_tokens if c.status in ('CANCELLED', 'NO_SHOW'))

        doc_durations = [c.actual_duration_minutes for c in doc_tokens if c.actual_duration_minutes is not None]
        doc_avg_dur = round(sum(doc_durations) / len(doc_durations), 1) if doc_durations else 0.0

        is_on_duty = (doc.id in avail_doc_ids) or (len(avail_doc_ids) == 0)

        doctor_summaries.append({
            'doctor': doc,
            'is_on_duty': is_on_duty,
            'total_tokens': len(doc_tokens),
            'completed': doc_completed,
            'waiting': doc_waiting,
            'in_consultation': doc_in_consult,
            'cancelled': doc_cancelled,
            'avg_duration': doc_avg_dur
        })

    # Sort doctors: active ones with tokens first
    doctor_summaries.sort(key=lambda d: (d['total_tokens'], d['is_on_duty']), reverse=True)

    # 9. Filtered Check-in Table
    table_checkins = all_checkins
    if status_filter != 'ALL':
        table_checkins = [c for c in table_checkins if c.status == status_filter]
    if dept_filter != 'ALL':
        table_checkins = [c for c in table_checkins if (c.department or 'General OPD') == dept_filter]
    if search_q:
        q_lower = search_q.lower()
        table_checkins = [
            c for c in table_checkins
            if (c.token_no and q_lower in c.token_no.lower()) or
               (c.patient and (
                   (c.patient.full_name and q_lower in c.patient.full_name.lower()) or
                   (c.patient.patient_code and q_lower in c.patient.patient_code.lower()) or
                   (c.patient.mobile and q_lower in c.patient.mobile.lower())
               )) or
               (c.doctor and c.doctor.name and q_lower in c.doctor.name.lower())
        ]

    # Distinct departments for dropdown filter
    all_departments = sorted(list(set(list(department_breakdown.keys()) + ['General OPD', 'Pediatrics', 'Cardiology', 'Orthopedics', 'Gynecology', 'Emergency'])))

    kpis = {
        'total_intakes': total_intakes,
        'waiting_count': waiting_count,
        'in_consult_count': in_consult_count,
        'completed_count': completed_count,
        'cancelled_count': cancelled_count,
        'new_patients_count': new_patients_count,
        'total_apts': total_apts,
        'apts_booked': apts_booked,
        'apts_checked_in': apts_checked_in,
        'apts_completed': apts_completed,
        'apts_cancelled': apts_cancelled,
        'emergency_cases_total': emergency_cases_total,
        'avg_wait_minutes': avg_wait_minutes,
        'avg_consult_minutes': avg_consult_minutes,
        'total_revenue': total_revenue,
        'cash_revenue': cash_revenue,
        'upi_revenue': upi_revenue,
        'card_revenue': card_revenue,
        'other_revenue': other_revenue,
        'payment_count': len(payments)
    }

    return render_template(
        'reception/reports.html',
        selected_date=selected_date,
        selected_date_str=selected_date.strftime('%Y-%m-%d'),
        selected_shift=shift,
        shift_label=shift_label,
        status_filter=status_filter,
        dept_filter=dept_filter,
        search_q=search_q,
        kpis=kpis,
        doctor_summaries=doctor_summaries,
        payments=payments,
        checkins=table_checkins,
        all_departments=all_departments,
        priority_breakdown=priority_breakdown,
        department_breakdown=department_breakdown,
        hourly_distribution=hourly_distribution,
        is_today=(selected_date == date.today()),
        today_str=date.today().strftime('%Y-%m-%d'),
        yesterday_str=(date.today() - timedelta(days=1)).strftime('%Y-%m-%d'),
        timedelta=timedelta,
        now=datetime.now()
    )


@reception_bp.route('/reports/export-csv', methods=['GET'])
@login_required
@role_required('Admin', 'Receptionist')
def export_daily_reports_csv():
    """
    Exports front desk daily operational report datasets as CSV.
    Supported export types: 'intakes', 'payments', 'doctors'
    """
    export_type = request.args.get('type', 'intakes').lower()
    date_str = request.args.get('date', '').strip()
    shift = request.args.get('shift', 'all').lower()

    try:
        if date_str:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            selected_date = date.today()
    except (ValueError, TypeError):
        selected_date = date.today()

    if shift == 'morning':
        start_dt = datetime.combine(selected_date, time(6, 0, 0))
        end_dt = datetime.combine(selected_date, time(13, 59, 59))
    elif shift == 'evening':
        start_dt = datetime.combine(selected_date, time(14, 0, 0))
        end_dt = datetime.combine(selected_date, time(21, 59, 59))
    elif shift == 'night':
        start_dt = datetime.combine(selected_date, time(22, 0, 0))
        end_dt = datetime.combine(selected_date + timedelta(days=1), time(5, 59, 59))
    else:
        start_dt = datetime.combine(selected_date, time(0, 0, 0))
        end_dt = datetime.combine(selected_date, time(23, 59, 59))

    output = io.StringIO()
    writer = csv.writer(output)

    if export_type == 'payments':
        writer.writerow(['Payment Code', 'Invoice Code', 'Patient UHID', 'Patient Name', 'Payment Mode', 'Transaction Ref', 'Amount (₹)', 'Paid Timestamp', 'Recorded By'])
        payments = Payment.query.filter(
            Payment.paid_at >= start_dt,
            Payment.paid_at <= end_dt
        ).order_by(Payment.paid_at.desc()).all()

        for p in payments:
            patient_uhid = p.bill.patient.patient_code if (p.bill and p.bill.patient) else 'N/A'
            patient_name = p.bill.patient.full_name if (p.bill and p.bill.patient) else 'Unknown'
            inv_code = p.bill.invoice_code if p.bill else 'N/A'
            rec_by = p.recorded_by.name if p.recorded_by else 'Front Desk'
            paid_time = p.paid_at.strftime('%Y-%m-%d %H:%M:%S') if p.paid_at else ''

            writer.writerow([
                p.payment_code,
                inv_code,
                patient_uhid,
                patient_name,
                p.payment_method,
                p.transaction_ref or '',
                f"{p.amount_paid:.2f}",
                paid_time,
                rec_by
            ])
        filename = f"carehub_frontdesk_payments_{selected_date.strftime('%Y%m%d')}_{shift}.csv"

    elif export_type == 'doctors':
        writer.writerow(['Doctor Name', 'Doctor Code', 'Specialization', 'Department', 'Total Tokens', 'Completed', 'In Consultation', 'Waiting', 'Cancelled', 'Avg Duration (mins)'])
        doctor_role = Role.query.filter_by(name='Doctor').first()
        doctors = User.query.filter_by(role_id=doctor_role.id, is_active=True).all() if doctor_role else []
        all_checkins = CheckIn.query.filter(
            CheckIn.check_in_time >= start_dt,
            CheckIn.check_in_time <= end_dt
        ).all()

        for doc in doctors:
            doc_tokens = [c for c in all_checkins if c.doctor_id == doc.id]
            doc_completed = sum(1 for c in doc_tokens if c.status == 'COMPLETED')
            doc_waiting = sum(1 for c in doc_tokens if c.status == 'WAITING')
            doc_in_consult = sum(1 for c in doc_tokens if c.status == 'IN_CONSULTATION')
            doc_cancelled = sum(1 for c in doc_tokens if c.status in ('CANCELLED', 'NO_SHOW'))
            doc_durations = [c.actual_duration_minutes for c in doc_tokens if c.actual_duration_minutes is not None]
            doc_avg_dur = round(sum(doc_durations) / len(doc_durations), 1) if doc_durations else 0.0

            writer.writerow([
                doc.name,
                doc.user_code or '',
                doc.specialization or '',
                doc.department or 'General OPD',
                len(doc_tokens),
                doc_completed,
                doc_in_consult,
                doc_waiting,
                doc_cancelled,
                doc_avg_dur
            ])
        filename = f"carehub_doctor_opd_summary_{selected_date.strftime('%Y%m%d')}_{shift}.csv"

    else:
        # Default: Daily Intakes / Tokens
        writer.writerow(['Token No', 'Patient UHID', 'Patient Name', 'Mobile', 'Assigned Doctor', 'Department', 'Priority', 'Check-In Time', 'Called Time', 'Completed Time', 'Wait Mins', 'Duration Mins', 'Status'])
        checkins = CheckIn.query.filter(
            CheckIn.check_in_time >= start_dt,
            CheckIn.check_in_time <= end_dt
        ).order_by(CheckIn.check_in_time.asc()).all()

        for c in checkins:
            uhid = c.patient.patient_code if c.patient else 'N/A'
            p_name = c.patient.full_name if c.patient else 'Walk-In Patient'
            mobile = c.patient.mobile if c.patient else ''
            doc_name = c.doctor.name if c.doctor else 'Unassigned'
            dept = c.department or 'General OPD'
            cin_time = c.check_in_time.strftime('%H:%M:%S') if c.check_in_time else ''
            call_time = c.called_time.strftime('%H:%M:%S') if c.called_time else ''
            comp_time = c.completed_time.strftime('%H:%M:%S') if c.completed_time else ''
            wait_m = c.waiting_duration_minutes or ''
            dur_m = c.actual_duration_minutes or ''

            writer.writerow([
                c.token_no,
                uhid,
                p_name,
                mobile,
                doc_name,
                dept,
                c.priority or 'Regular',
                cin_time,
                call_time,
                comp_time,
                wait_m,
                dur_m,
                c.status
            ])
        filename = f"carehub_frontdesk_intakes_{selected_date.strftime('%Y%m%d')}_{shift}.csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

