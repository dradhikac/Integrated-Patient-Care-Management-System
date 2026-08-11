from datetime import datetime, date, time, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.auth.models import User, Role
from app.patients.models import Patient
from app.appointments.models import DoctorAvailability, Holiday, Appointment, Waitlist
from app.appointments.forms import BookAppointmentForm, DoctorAvailabilityForm, HolidayForm
from app.appointments.slot_generator import generate_doctor_slots

appointments_bp = Blueprint('appointments', __name__, template_folder='templates', url_prefix='/appointments')

@appointments_bp.route('/')
@login_required
def list_appointments():
    role_name = current_user.role.name
    query_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    
    try:
        selected_date = datetime.strptime(query_date, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()

    apt_query = Appointment.query.filter_by(appointment_date=selected_date)

    if role_name == 'Doctor':
        apt_query = apt_query.filter_by(doctor_id=current_user.id)
    elif role_name == 'Patient':
        patient_obj = Patient.query.filter_by(email=current_user.email).first()
        if patient_obj:
            apt_query = apt_query.filter_by(patient_id=patient_obj.id)
        else:
            apt_query = apt_query.filter_by(patient_id=-1)

    appointments = apt_query.order_by(Appointment.slot_time.asc()).all()

    # Fetch active waitlists for this date/doctor
    waitlist_query = Waitlist.query.filter(
        Waitlist.preferred_date == selected_date,
        Waitlist.status.in_(['WAITING', 'OFFERED'])
    )
    if role_name == 'Doctor':
        waitlist_query = waitlist_query.filter_by(doctor_id=current_user.id)
    elif role_name == 'Patient':
        if patient_obj:
            waitlist_query = waitlist_query.filter_by(patient_id=patient_obj.id)

    active_waitlist = waitlist_query.order_by(Waitlist.created_at.asc()).all()

    return render_template('appointments/list.html',
                           appointments=appointments,
                           active_waitlist=active_waitlist,
                           selected_date=selected_date,
                           today_date=date.today())


@appointments_bp.route('/book', methods=['GET', 'POST'])
@login_required
def book_appointment():
    form = BookAppointmentForm()
    
    doc_role = Role.query.filter_by(name='Doctor').first()
    doctors = User.query.filter_by(role_id=doc_role.id, is_active=True).all() if doc_role else []
    form.doctor_id.choices = [(d.id, f"{d.name} ({d.user_code})") for d in doctors]

    patients = Patient.query.order_by(Patient.full_name.asc()).all()
    form.patient_id.choices = [(p.id, f"{p.full_name} ({p.patient_code})") for p in patients]

    if current_user.role.name == 'Patient':
        pat_profile = Patient.query.filter_by(email=current_user.email).first()
        if pat_profile:
            form.patient_id.data = pat_profile.id

    selected_doc_id = request.args.get('doctor_id', type=int) or (doctors[0].id if doctors else None)
    selected_date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()

    slot_info = generate_doctor_slots(selected_doc_id, selected_date) if selected_doc_id else {'slots': []}

    if form.validate_on_submit():
        slot_time_str = form.slot_time.data.strip()
        try:
            slot_t = datetime.strptime(slot_time_str, '%H:%M:%S').time()
        except ValueError:
            try:
                slot_t = datetime.strptime(slot_time_str, '%H:%M').time()
            except ValueError:
                flash('Invalid time slot format selected.', 'danger')
                return render_template('appointments/book.html', form=form, doctors=doctors, selected_doc_id=selected_doc_id, selected_date=selected_date, slot_info=slot_info)

        target_doc_id = form.doctor_id.data
        target_date = form.appointment_date.data

        # Double Booking Prevention Check
        existing_booking = Appointment.query.filter(
            Appointment.doctor_id == target_doc_id,
            Appointment.appointment_date == target_date,
            Appointment.slot_time == slot_t,
            Appointment.status != 'CANCELLED'
        ).first()

        if existing_booking:
            flash(f'Slot {slot_time_str} is already booked for this doctor. Please choose another available slot.', 'danger')
            return redirect(url_for('appointments.book_appointment', doctor_id=target_doc_id, date=target_date.strftime('%Y-%m-%d')))

        apt = Appointment(
            appointment_code=Appointment.generate_appointment_code(),
            patient_id=form.patient_id.data,
            doctor_id=target_doc_id,
            appointment_date=target_date,
            slot_time=slot_t,
            booking_type=form.booking_type.data,
            status='BOOKED',
            notes=form.notes.data.strip() if form.notes.data else None
        )
        db.session.add(apt)
        db.session.commit()

        flash(f'Appointment {apt.appointment_code} booked successfully for {apt.appointment_date} at {apt.slot_time.strftime("%I:%M %p")}!', 'success')
        return redirect(url_for('appointments.list_appointments', date=target_date.strftime('%Y-%m-%d')))

    return render_template('appointments/book.html',
                           form=form,
                           doctors=doctors,
                           selected_doc_id=selected_doc_id,
                           selected_date=selected_date,
                           slot_info=slot_info)


@appointments_bp.route('/cancel/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    apt = Appointment.query.get_or_404(appointment_id)
    apt.status = 'CANCELLED'
    db.session.commit()

    flash(f'Appointment {apt.appointment_code} has been cancelled.', 'info')

    # AUTO-WAITLIST PROMOTION OFFER
    # Find top waiting patient in waitlist for same doctor and date
    top_waitlist = Waitlist.query.filter_by(
        doctor_id=apt.doctor_id,
        preferred_date=apt.appointment_date,
        status='WAITING'
    ).order_by(Waitlist.created_at.asc()).first()

    if top_waitlist:
        top_waitlist.offered_slot_time = apt.slot_time
        top_waitlist.status = 'OFFERED'
        db.session.commit()

        flash(f'🔔 Waitlist Promotion Offered: Freed slot {apt.slot_time.strftime("%I:%M %p")} offered to waitlisted patient {top_waitlist.patient.full_name}. Awaiting agreement to confirm promotion.', 'warning')

    return redirect(url_for('appointments.list_appointments', date=apt.appointment_date.strftime('%Y-%m-%d')))


@appointments_bp.route('/waitlist/<int:waitlist_id>/accept', methods=['POST'])
@login_required
def accept_waitlist_promotion(waitlist_id):
    w_entry = Waitlist.query.get_or_404(waitlist_id)

    # Permission check: Patient can accept their own; Receptionist/Admin/Doctor can accept on patient's behalf
    if current_user.role.name == 'Patient' and w_entry.patient.email != current_user.email:
        flash('Access denied. You can only confirm promotion for your own waitlist entry.', 'danger')
        return redirect(url_for('appointments.list_appointments'))

    if w_entry.status != 'OFFERED' or not w_entry.offered_slot_time:
        flash('This waitlist promotion offer is no longer pending or valid.', 'warning')
        return redirect(url_for('appointments.list_appointments'))

    w_entry.status = 'ACCEPTED'

    # Book the promoted appointment
    promoted_apt = Appointment(
        appointment_code=Appointment.generate_appointment_code(),
        patient_id=w_entry.patient_id,
        doctor_id=w_entry.doctor_id,
        appointment_date=w_entry.preferred_date,
        slot_time=w_entry.offered_slot_time,
        booking_type='Waitlist Promoted',
        status='BOOKED',
        notes='Promotion agreed & confirmed by Patient/Receptionist'
    )
    db.session.add(promoted_apt)
    db.session.commit()

    flash(f'🎉 Waitlist Promotion Confirmed! Appointment {promoted_apt.appointment_code} booked for {w_entry.patient.full_name} at {w_entry.offered_slot_time.strftime("%I:%M %p")}!', 'success')
    return redirect(url_for('appointments.list_appointments', date=w_entry.preferred_date.strftime('%Y-%m-%d')))


@appointments_bp.route('/waitlist/<int:waitlist_id>/decline', methods=['POST'])
@login_required
def decline_waitlist_promotion(waitlist_id):
    w_entry = Waitlist.query.get_or_404(waitlist_id)

    if current_user.role.name == 'Patient' and w_entry.patient.email != current_user.email:
        flash('Access denied.', 'danger')
        return redirect(url_for('appointments.list_appointments'))

    freed_slot_time = w_entry.offered_slot_time
    doc_id = w_entry.doctor_id
    pref_date = w_entry.preferred_date

    w_entry.status = 'DECLINED'
    w_entry.offered_slot_time = None
    db.session.commit()

    flash(f'Waitlist promotion declined for {w_entry.patient.full_name}.', 'info')

    # Offer to the NEXT candidate on the waitlist!
    next_candidate = Waitlist.query.filter_by(
        doctor_id=doc_id,
        preferred_date=pref_date,
        status='WAITING'
    ).order_by(Waitlist.created_at.asc()).first()

    if next_candidate and freed_slot_time:
        next_candidate.offered_slot_time = freed_slot_time
        next_candidate.status = 'OFFERED'
        db.session.commit()
        flash(f'🔔 Freed slot {freed_slot_time.strftime("%I:%M %p")} offered to next waitlisted candidate {next_candidate.patient.full_name}!', 'warning')

    return redirect(url_for('appointments.list_appointments', date=pref_date.strftime('%Y-%m-%d')))


@appointments_bp.route('/waitlist/add', methods=['POST'])
@login_required
def add_to_waitlist():
    patient_id = request.form.get('patient_id', type=int)
    doctor_id = request.form.get('doctor_id', type=int)
    pref_date_str = request.form.get('preferred_date')

    if patient_id and doctor_id and pref_date_str:
        pref_date = datetime.strptime(pref_date_str, '%Y-%m-%d').date()
        entry = Waitlist(
            patient_id=patient_id,
            doctor_id=doctor_id,
            preferred_date=pref_date,
            status='WAITING'
        )
        db.session.add(entry)
        db.session.commit()
        flash('Added to Doctor Waitlist. If a cancellation occurs, a promotion offer will be extended to you!', 'info')
        
    return redirect(url_for('appointments.list_appointments', date=pref_date_str))


@appointments_bp.route('/schedule', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Doctor')
def schedule():
    avail_form = DoctorAvailabilityForm()
    holiday_form = HolidayForm()

    doc_role = Role.query.filter_by(name='Doctor').first()
    doctors = User.query.filter_by(role_id=doc_role.id, is_active=True).all() if doc_role else []

    if request.method == 'POST' and 'submit_availability' in request.form:
        doc_id = request.form.get('doctor_id', type=int)
        day_of_week = int(request.form.get('day_of_week'))
        s_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
        e_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
        duration = int(request.form.get('slot_duration_minutes', 15))

        existing = DoctorAvailability.query.filter_by(doctor_id=doc_id, day_of_week=day_of_week).first()
        if existing:
            existing.start_time = s_time
            existing.end_time = e_time
            existing.slot_duration_minutes = duration
            existing.is_active = True
        else:
            avail = DoctorAvailability(
                doctor_id=doc_id,
                day_of_week=day_of_week,
                start_time=s_time,
                end_time=e_time,
                slot_duration_minutes=duration
            )
            db.session.add(avail)
            
        db.session.commit()
        flash('Doctor shift schedule saved successfully!', 'success')
        return redirect(url_for('appointments.schedule'))

    if request.method == 'POST' and 'submit_holiday' in request.form:
        h_date = datetime.strptime(request.form.get('holiday_date'), '%Y-%m-%d').date()
        desc = request.form.get('description').strip()

        holiday = Holiday(holiday_date=h_date, description=desc)
        db.session.add(holiday)
        db.session.commit()
        flash(f'Hospital holiday added for {h_date}!', 'warning')
        return redirect(url_for('appointments.schedule'))

    availabilities = DoctorAvailability.query.order_by(DoctorAvailability.doctor_id, DoctorAvailability.day_of_week).all()
    holidays = Holiday.query.order_by(Holiday.holiday_date.asc()).all()

    return render_template('appointments/schedule.html',
                           avail_form=avail_form,
                           holiday_form=holiday_form,
                           doctors=doctors,
                           availabilities=availabilities,
                           holidays=holidays)
