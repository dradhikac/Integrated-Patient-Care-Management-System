"""
Doctor Portal Routes
====================
All routes are protected by @role_required('Doctor').
Patient data access is scoped by doctor_id = current_user.id at query level.
"""
from datetime import datetime, date, timedelta
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import current_user, login_required
from app.extensions import db
from app.auth.utils import role_required
from app.doctor_portal import doctor_portal_bp
from app.doctor_portal.helpers import get_doctor_record
from app.doctors.models import Doctor
from app.patients.models import Patient
from app.appointments.models import Appointment, DoctorAvailability
from app.reception.models import CheckIn
from app.consultations.models import Consultation, Vital
from app.prescriptions.models import Prescription, PrescriptionItem, Medicine
from app.lab.models import LabRequest
from app.appointments.slot_generator import generate_doctor_slots


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/')
@role_required('Doctor')
def dashboard():
    doctor = get_doctor_record()
    today = date.today()
    now = datetime.now()

    # Today's appointments
    today_apts = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.appointment_date == today
    ).order_by(Appointment.slot_time).all()

    # Stats
    total_today = len(today_apts)
    checked_in = sum(1 for a in today_apts if a.status == 'CHECKED_IN')
    waiting = CheckIn.query.filter(
        CheckIn.doctor_id == current_user.id,
        CheckIn.status == 'WAITING'
    ).count()
    completed_today = sum(1 for a in today_apts if a.status == 'COMPLETED')

    # Upcoming appointments (next 7 days, not today)
    upcoming = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.appointment_date > today,
        Appointment.appointment_date <= today + timedelta(days=7),
        Appointment.status == 'BOOKED'
    ).order_by(Appointment.appointment_date, Appointment.slot_time).limit(5).all()

    # Pending lab reports
    pending_labs = LabRequest.query.filter(
        LabRequest.doctor_id == current_user.id,
        LabRequest.status.in_(['REQUESTED', 'SAMPLE_COLLECTED', 'IN_TESTING'])
    ).count()

    # Pending consultations (checked-in patients without a consultation record)
    active_checkins = CheckIn.query.filter(
        CheckIn.doctor_id == current_user.id,
        CheckIn.status.in_(['WAITING', 'IN_CONSULTATION'])
    ).order_by(CheckIn.check_in_time).limit(10).all()

    return render_template(
        'doctor/dashboard.html',
        doctor=doctor,
        today=today,
        today_apts=today_apts,
        total_today=total_today,
        checked_in=checked_in,
        waiting=waiting,
        completed_today=completed_today,
        upcoming=upcoming,
        pending_labs=pending_labs,
        active_checkins=active_checkins
    )


# ─────────────────────────────────────────────────────────────────────────────
# TODAY'S APPOINTMENTS
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/appointments/today')
@role_required('Doctor')
def today_appointments():
    doctor = get_doctor_record()
    today = date.today()
    apts = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.appointment_date == today
    ).order_by(Appointment.slot_time).all()

    # Enrich with check-in info
    for apt in apts:
        apt._checkin = CheckIn.query.filter(
            CheckIn.patient_id == apt.patient_id,
            CheckIn.doctor_id == current_user.id,
            db.cast(CheckIn.check_in_time, db.Date) == today
        ).order_by(CheckIn.id.desc()).first()

    return render_template('doctor/today_appointments.html', doctor=doctor, apts=apts, today=today)


# ─────────────────────────────────────────────────────────────────────────────
# PATIENT QUEUE
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/queue')
@role_required('Doctor')
def patient_queue():
    doctor = get_doctor_record()
    today = date.today()
    queue = CheckIn.query.filter(
        CheckIn.doctor_id == current_user.id,
        CheckIn.status.in_(['WAITING', 'IN_CONSULTATION']),
        db.cast(CheckIn.check_in_time, db.Date) == today
    ).order_by(CheckIn.check_in_time).all()

    # Calculate wait times
    now = datetime.now()
    for item in queue:
        if item.check_in_time:
            delta = now - item.check_in_time
            item._wait_minutes = int(delta.total_seconds() // 60)
        else:
            item._wait_minutes = 0

    return render_template('doctor/patient_queue.html', doctor=doctor, queue=queue, today=today)


# ─────────────────────────────────────────────────────────────────────────────
# MY PATIENTS
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/patients')
@role_required('Doctor')
def patients():
    doctor = get_doctor_record()
    # Patients who have had at least one appointment with this doctor
    patient_ids = db.session.query(Appointment.patient_id).filter(
        Appointment.doctor_id == current_user.id
    ).distinct().all()
    patient_id_list = [pid[0] for pid in patient_ids]

    search = request.args.get('q', '').strip()
    query = Patient.query.filter(Patient.id.in_(patient_id_list))
    if search:
        query = query.filter(
            db.or_(
                Patient.full_name.ilike(f'%{search}%'),
                Patient.patient_code.ilike(f'%{search}%'),
                Patient.mobile.ilike(f'%{search}%')
            )
        )
    patient_list = query.order_by(Patient.full_name).all()

    return render_template('doctor/patients.html', doctor=doctor, patients=patient_list, search=search)


# ─────────────────────────────────────────────────────────────────────────────
# PATIENT DETAIL
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/patients/<int:patient_id>')
@role_required('Doctor')
def patient_detail(patient_id):
    doctor = get_doctor_record()

    # Authorization: only patients who had an appointment with this doctor
    has_access = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.patient_id == patient_id
    ).first()
    if not has_access:
        abort(403)

    patient = Patient.query.get_or_404(patient_id)
    consultations = Consultation.query.filter_by(
        patient_id=patient_id,
        doctor_id=current_user.id
    ).order_by(Consultation.created_at.desc()).all()
    prescriptions = Prescription.query.filter_by(
        patient_id=patient_id,
        doctor_id=current_user.id
    ).order_by(Prescription.created_at.desc()).all()
    lab_requests = LabRequest.query.filter_by(
        patient_id=patient_id,
        doctor_id=current_user.id
    ).order_by(LabRequest.created_at.desc()).all()
    appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.doctor_id == current_user.id
    ).order_by(Appointment.appointment_date.desc()).all()

    return render_template(
        'doctor/patient_detail.html',
        doctor=doctor,
        patient=patient,
        consultations=consultations,
        prescriptions=prescriptions,
        lab_requests=lab_requests,
        appointments=appointments
    )


# ─────────────────────────────────────────────────────────────────────────────
# CONSULTATIONS LIST
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/consultations')
@role_required('Doctor')
def consultations():
    doctor = get_doctor_record()
    page = request.args.get('page', 1, type=int)
    cons_list = Consultation.query.filter_by(
        doctor_id=current_user.id
    ).order_by(Consultation.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('doctor/consultations.html', doctor=doctor, consultations=cons_list)


# ─────────────────────────────────────────────────────────────────────────────
# CONSULTATION DETAIL
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/consultations/<int:consultation_id>')
@role_required('Doctor')
def consultation_detail(consultation_id):
    doctor = get_doctor_record()
    consultation = Consultation.query.get_or_404(consultation_id)
    if consultation.doctor_id != current_user.id:
        abort(403)
    prescription = Prescription.query.filter_by(consultation_id=consultation_id).first()
    lab_requests = LabRequest.query.filter_by(consultation_id=consultation_id).all()
    return render_template(
        'doctor/consultation_detail.html',
        doctor=doctor,
        consultation=consultation,
        prescription=prescription,
        lab_requests=lab_requests
    )


# ─────────────────────────────────────────────────────────────────────────────
# CREATE CONSULTATION
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/consultations/create', methods=['GET', 'POST'])
@role_required('Doctor')
def create_consultation():
    doctor = get_doctor_record()
    today = date.today()

    # Get appointment_id from query param or form
    appointment_id = request.args.get('appointment_id', type=int) or request.form.get('appointment_id', type=int)
    appointment = None
    patient = None

    if appointment_id:
        appointment = Appointment.query.get_or_404(appointment_id)
        if appointment.doctor_id != current_user.id:
            abort(403)
        patient = appointment.patient
    else:
        # Allow selecting from today's checked-in patients
        checkin_id = request.args.get('checkin_id', type=int) or request.form.get('checkin_id', type=int)
        if checkin_id:
            checkin = CheckIn.query.get_or_404(checkin_id)
            if checkin.doctor_id != current_user.id:
                abort(403)
            patient = checkin.patient
        else:
            # Get patient_id directly
            patient_id = request.args.get('patient_id', type=int) or request.form.get('patient_id', type=int)
            if patient_id:
                has_access = Appointment.query.filter_by(
                    doctor_id=current_user.id,
                    patient_id=patient_id
                ).first()
                if not has_access:
                    abort(403)
                patient = Patient.query.get_or_404(patient_id)

    if request.method == 'POST':
        patient_id = request.form.get('patient_id', type=int)
        if not patient_id:
            flash('Patient is required.', 'danger')
            return redirect(request.url)

        # Authorization check
        has_access = Appointment.query.filter_by(
            doctor_id=current_user.id,
            patient_id=patient_id
        ).first()
        if not has_access:
            abort(403)

        # Vitals (optional)
        bp_sys = request.form.get('bp_systolic', type=int)
        bp_dia = request.form.get('bp_diastolic', type=int)
        temp = request.form.get('temperature_f', type=float)
        pulse = request.form.get('pulse_bpm', type=int)
        spo2 = request.form.get('spo2_percent', type=int)

        consultation = Consultation(
            consultation_code=Consultation.generate_consultation_code(),
            patient_id=patient_id,
            doctor_id=current_user.id,
            appointment_id=appointment_id,
            symptoms=request.form.get('symptoms', '').strip(),
            diagnosis=request.form.get('diagnosis', '').strip(),
            treatment_plan=request.form.get('treatment_plan', '').strip(),
            notes=request.form.get('notes', '').strip()
        )
        db.session.add(consultation)
        db.session.flush()

        # Save vitals if any provided
        if any([bp_sys, bp_dia, temp, pulse, spo2]):
            vital = Vital(
                consultation_id=consultation.id,
                bp_systolic=bp_sys,
                bp_diastolic=bp_dia,
                temperature_f=temp,
                pulse_bpm=pulse,
                spo2_percent=spo2
            )
            db.session.add(vital)

        # Update appointment status
        if appointment_id and appointment:
            appointment.status = 'COMPLETED'

        db.session.commit()
        flash(f'Consultation {consultation.consultation_code} recorded successfully.', 'success')
        return redirect(url_for('doctor_portal.consultation_detail', consultation_id=consultation.id))

    # GET: get today's checked-in patients for selection
    todays_patients = CheckIn.query.filter(
        CheckIn.doctor_id == current_user.id,
        CheckIn.status.in_(['WAITING', 'IN_CONSULTATION']),
        db.cast(CheckIn.check_in_time, db.Date) == today
    ).order_by(CheckIn.check_in_time).all()

    return render_template(
        'doctor/create_consultation.html',
        doctor=doctor,
        appointment=appointment,
        patient=patient,
        appointment_id=appointment_id,
        todays_patients=todays_patients
    )


# ─────────────────────────────────────────────────────────────────────────────
# PRESCRIPTIONS LIST
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/prescriptions')
@role_required('Doctor')
def prescriptions():
    doctor = get_doctor_record()
    page = request.args.get('page', 1, type=int)
    rx_list = Prescription.query.filter_by(
        doctor_id=current_user.id
    ).order_by(Prescription.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('doctor/prescriptions.html', doctor=doctor, prescriptions=rx_list)


# ─────────────────────────────────────────────────────────────────────────────
# CREATE PRESCRIPTION
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/prescriptions/create', methods=['GET', 'POST'])
@role_required('Doctor')
def create_prescription():
    doctor = get_doctor_record()
    consultation_id = request.args.get('consultation_id', type=int) or request.form.get('consultation_id', type=int)
    consultation = None
    patient = None

    if consultation_id:
        consultation = Consultation.query.get_or_404(consultation_id)
        if consultation.doctor_id != current_user.id:
            abort(403)
        patient = consultation.patient

    medicines = Medicine.query.filter_by(is_active=True).order_by(Medicine.brand_name).all()

    if request.method == 'POST':
        patient_id = request.form.get('patient_id', type=int)
        if not patient_id:
            flash('Patient is required.', 'danger')
            return redirect(request.url)

        has_access = Appointment.query.filter_by(
            doctor_id=current_user.id,
            patient_id=patient_id
        ).first()
        if not has_access:
            abort(403)

        rx = Prescription(
            prescription_code=Prescription.generate_prescription_code(),
            consultation_id=consultation_id,
            patient_id=patient_id,
            doctor_id=current_user.id,
            general_advice=request.form.get('general_advice', '').strip()
        )
        db.session.add(rx)
        db.session.flush()

        # Process medicine items (submitted as arrays)
        med_names = request.form.getlist('medicine_name[]')
        frequencies = request.form.getlist('frequency[]')
        durations = request.form.getlist('duration[]')
        food_relations = request.form.getlist('food_relation[]')
        instructions_list = request.form.getlist('instructions[]')

        for i, med_name in enumerate(med_names):
            if not med_name.strip():
                continue
            item = PrescriptionItem(
                prescription_id=rx.id,
                medicine_name=med_name.strip(),
                frequency=frequencies[i] if i < len(frequencies) else '1-0-1',
                duration=durations[i] if i < len(durations) else '5 Days',
                food_relation=food_relations[i] if i < len(food_relations) else 'After Food',
                instructions=instructions_list[i] if i < len(instructions_list) else ''
            )
            db.session.add(item)

        db.session.commit()
        flash(f'Prescription {rx.prescription_code} created successfully.', 'success')
        return redirect(url_for('doctor_portal.prescription_detail', prescription_id=rx.id))

    return render_template(
        'doctor/create_prescription.html',
        doctor=doctor,
        consultation=consultation,
        patient=patient,
        consultation_id=consultation_id,
        medicines=medicines
    )


# ─────────────────────────────────────────────────────────────────────────────
# PRESCRIPTION DETAIL / PRINT
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/prescriptions/<int:prescription_id>')
@role_required('Doctor')
def prescription_detail(prescription_id):
    doctor = get_doctor_record()
    rx = Prescription.query.get_or_404(prescription_id)
    if rx.doctor_id != current_user.id:
        abort(403)
    return render_template('doctor/prescription_detail.html', doctor=doctor, rx=rx)


# ─────────────────────────────────────────────────────────────────────────────
# LAB REPORTS
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/lab-reports')
@role_required('Doctor')
def lab_reports():
    doctor = get_doctor_record()
    status_filter = request.args.get('status', '')
    query = LabRequest.query.filter_by(doctor_id=current_user.id)
    if status_filter:
        query = query.filter(LabRequest.status == status_filter)
    labs = query.order_by(LabRequest.created_at.desc()).all()
    return render_template('doctor/lab_reports.html', doctor=doctor, labs=labs, status_filter=status_filter)


# ─────────────────────────────────────────────────────────────────────────────
# FOLLOW-UPS
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/followups')
@role_required('Doctor')
def followups():
    doctor = get_doctor_record()
    today = date.today()
    # Follow-ups = future appointments for patients the doctor has previously consulted
    consulted_patient_ids = db.session.query(Consultation.patient_id).filter(
        Consultation.doctor_id == current_user.id
    ).distinct().all()
    patient_id_list = [p[0] for p in consulted_patient_ids]

    followup_apts = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.patient_id.in_(patient_id_list),
        Appointment.appointment_date >= today,
        Appointment.status.in_(['BOOKED', 'CHECKED_IN'])
    ).order_by(Appointment.appointment_date, Appointment.slot_time).all()

    # Attach latest consultation per patient
    for apt in followup_apts:
        apt._last_consultation = Consultation.query.filter_by(
            patient_id=apt.patient_id,
            doctor_id=current_user.id
        ).order_by(Consultation.created_at.desc()).first()

    return render_template('doctor/followups.html', doctor=doctor, followups=followup_apts, today=today)


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULE (WEEK VIEW)
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/schedule')
@role_required('Doctor')
def schedule():
    doctor = get_doctor_record()
    today = date.today()

    # Parse week_start from query param (default = this Monday)
    week_start_str = request.args.get('week', '')
    try:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
    except ValueError:
        week_start = today - timedelta(days=today.weekday())

    week_end = week_start + timedelta(days=6)

    apts = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.appointment_date >= week_start,
        Appointment.appointment_date <= week_end
    ).order_by(Appointment.appointment_date, Appointment.slot_time).all()

    # Group by date
    schedule_map = {}
    for i in range(7):
        d = week_start + timedelta(days=i)
        schedule_map[d] = []
    for apt in apts:
        if apt.appointment_date in schedule_map:
            schedule_map[apt.appointment_date].append(apt)

    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)

    return render_template(
        'doctor/schedule.html',
        doctor=doctor,
        schedule_map=schedule_map,
        week_start=week_start,
        week_end=week_end,
        prev_week=prev_week,
        next_week=next_week,
        today=today
    )


# ─────────────────────────────────────────────────────────────────────────────
# AVAILABILITY MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/availability', methods=['GET', 'POST'])
@role_required('Doctor')
def availability():
    doctor = get_doctor_record()
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    if request.method == 'POST':
        # Delete all existing availability for this doctor
        DoctorAvailability.query.filter_by(doctor_id=current_user.id).delete()
        db.session.flush()

        for day_idx in range(7):
            enabled = request.form.get(f'day_{day_idx}')
            if enabled:
                start_str = request.form.get(f'start_{day_idx}', '09:00')
                end_str = request.form.get(f'end_{day_idx}', '13:00')
                slot_dur = request.form.get(f'slot_{day_idx}', 15, type=int)
                try:
                    start_t = datetime.strptime(start_str, '%H:%M').time()
                    end_t = datetime.strptime(end_str, '%H:%M').time()
                except ValueError:
                    continue
                avail = DoctorAvailability(
                    doctor_id=current_user.id,
                    day_of_week=day_idx,
                    start_time=start_t,
                    end_time=end_t,
                    slot_duration_minutes=slot_dur,
                    is_active=True
                )
                db.session.add(avail)

        db.session.commit()
        flash('Your availability schedule has been updated.', 'success')
        return redirect(url_for('doctor_portal.availability'))

    availabilities = DoctorAvailability.query.filter_by(doctor_id=current_user.id).all()
    avail_map = {a.day_of_week: a for a in availabilities}

    return render_template(
        'doctor/availability.html',
        doctor=doctor,
        avail_map=avail_map,
        day_names=day_names
    )


# ─────────────────────────────────────────────────────────────────────────────
# MY PROFILE
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/profile', methods=['GET', 'POST'])
@role_required('Doctor')
def my_profile():
    doctor = get_doctor_record()
    if not doctor:
        flash('Doctor profile not found.', 'danger')
        return redirect(url_for('doctor_portal.dashboard'))

    if request.method == 'POST':
        doctor.bio = request.form.get('bio', '').strip()
        doctor.consultation_fee = float(request.form.get('consultation_fee', doctor.consultation_fee))
        doctor.available_days = request.form.get('available_days', '').strip()
        # Doctors can update bio, fee, available_days
        # Protected fields (specialization, department) are read-only in template
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('doctor_portal.my_profile'))

    return render_template('doctor/my_profile.html', doctor=doctor)


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────
@doctor_portal_bp.route('/notifications')
@role_required('Doctor')
def notifications():
    doctor = get_doctor_record()
    today = date.today()

    # Recent appointments (new bookings / changes in last 7 days)
    recent_apts = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.created_at >= datetime.now() - timedelta(days=7)
    ).order_by(Appointment.created_at.desc()).limit(20).all()

    # Completed lab reports for doctor's patients
    completed_labs = LabRequest.query.filter(
        LabRequest.doctor_id == current_user.id,
        LabRequest.status == 'COMPLETED'
    ).order_by(LabRequest.created_at.desc()).limit(10).all()

    return render_template(
        'doctor/notifications.html',
        doctor=doctor,
        recent_apts=recent_apts,
        completed_labs=completed_labs,
        today=today
    )
