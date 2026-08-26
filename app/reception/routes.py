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
                subject='MediCore+ Portal Activation',
                sender=flask.current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[patient.email],
                body=(
                    f"Dear {patient.full_name},\n\n"
                    f"Your MediCore+ Patient Portal account has been created.\n"
                    f"Click the link below to set your password and activate your account:\n\n"
                    f"{activation_url}\n\n"
                    f"Or use OTP code: {otp}  (valid 24 hours)\n\n"
                    f"If you did not request this, please ignore this email.\n\n"
                    f"— MediCore+ Team"
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
                    email=patient.email or f"patient_{patient.id}@medicore.local",
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

            flash(f'Welcome, {patient.full_name}! Your MediCore+ Patient Portal is now active.', 'success')
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
