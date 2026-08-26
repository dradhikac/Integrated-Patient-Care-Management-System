"""
MediCore+ Patient Portal — Routes
All routes are scoped to the authenticated Patient's own data.
"""
from datetime import datetime, date, timedelta
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.auth.models import User, Role
from app.portal import portal_bp
from app.portal.helpers import get_patient_or_fallback
from app.patients.models import Patient
from app.appointments.models import Appointment, DoctorAvailability, Holiday
from app.appointments.slot_generator import generate_doctor_slots
from app.consultations.models import Consultation
from app.prescriptions.models import Prescription
from app.prescriptions.qr_generator import generate_prescription_qr_base64
from app.lab.models import LabRequest, LabResult
from app.billing.models import Bill
from app.notifications.models import Notification


def _require_patient():
    """Resolve the Patient record for the current user or abort."""
    patient = get_patient_or_fallback(current_user)
    if not patient:
        flash('Your patient profile has not been linked yet. Please contact the reception desk.', 'warning')
        return None
    return patient


# ─────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/')
@login_required
@role_required('Patient')
def dashboard():
    patient = _require_patient()
    if not patient:
        return render_template('portal/not_linked.html')

    now = datetime.now()
    today = date.today()

    # Time-of-day greeting
    hour = now.hour
    if hour < 12:
        greeting = 'Good morning'
    elif hour < 17:
        greeting = 'Good afternoon'
    else:
        greeting = 'Good evening'

    # Summary counts
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.appointment_date >= today,
        Appointment.status.in_(['BOOKED', 'CHECKED_IN'])
    ).order_by(Appointment.appointment_date, Appointment.slot_time).all()

    next_appointment = upcoming_appointments[0] if upcoming_appointments else None

    total_prescriptions = Prescription.query.filter_by(patient_id=patient.id).count()

    lab_reports = LabRequest.query.filter_by(patient_id=patient.id).all()
    completed_labs = sum(1 for lr in lab_reports if lr.status == 'COMPLETED')
    pending_labs = sum(1 for lr in lab_reports if lr.status != 'COMPLETED')

    pending_bills = Bill.query.filter(
        Bill.patient_id == patient.id,
        Bill.status.in_(['UNPAID', 'PARTIALLY_PAID'])
    ).all()
    total_due = sum(b.balance_due for b in pending_bills)

    # Recent consultations (last 5)
    recent_consultations = Consultation.query.filter_by(
        patient_id=patient.id
    ).order_by(Consultation.created_at.desc()).limit(5).all()

    # Unread notifications count
    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()

    return render_template('portal/dashboard.html',
                           patient=patient,
                           greeting=greeting,
                           next_appointment=next_appointment,
                           upcoming_count=len(upcoming_appointments),
                           total_prescriptions=total_prescriptions,
                           completed_labs=completed_labs,
                           pending_labs=pending_labs,
                           pending_bills_count=len(pending_bills),
                           total_due=total_due,
                           recent_consultations=recent_consultations,
                           notif_count=notif_count,
                           today=today)


# ─────────────────────────────────────────────────────────────
# MY PROFILE
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@role_required('Patient')
def profile():
    patient = _require_patient()
    if not patient:
        return render_template('portal/not_linked.html')

    if request.method == 'POST':
        # Only allow editing safe fields
        patient.mobile = request.form.get('mobile', patient.mobile).strip()
        patient.email = request.form.get('email', patient.email).strip().lower()
        patient.address = request.form.get('address', patient.address).strip()
        patient.emergency_contact_name = request.form.get('emergency_contact_name', '').strip() or patient.emergency_contact_name
        patient.emergency_contact_mobile = request.form.get('emergency_contact_mobile', '').strip() or patient.emergency_contact_mobile
        patient.insurance_provider = request.form.get('insurance_provider', '').strip() or patient.insurance_provider
        patient.insurance_policy_no = request.form.get('insurance_policy_no', '').strip() or patient.insurance_policy_no
        patient.preferred_language = request.form.get('preferred_language', patient.preferred_language).strip()

        # Sync email to User record
        if patient.email and current_user.email != patient.email:
            current_user.email = patient.email

        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('portal.profile'))

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/profile.html', patient=patient, notif_count=notif_count)


# ─────────────────────────────────────────────────────────────
# MY APPOINTMENTS
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/appointments')
@login_required
@role_required('Patient')
def appointments():
    patient = _require_patient()
    if not patient:
        return render_template('portal/not_linked.html')

    today = date.today()
    tab = request.args.get('tab', 'upcoming')

    if tab == 'past':
        apts = Appointment.query.filter(
            Appointment.patient_id == patient.id,
            (Appointment.appointment_date < today) | (Appointment.status.in_(['COMPLETED', 'CANCELLED', 'NO_SHOW']))
        ).order_by(Appointment.appointment_date.desc(), Appointment.slot_time.desc()).all()
    else:
        apts = Appointment.query.filter(
            Appointment.patient_id == patient.id,
            Appointment.appointment_date >= today,
            Appointment.status.in_(['BOOKED', 'CHECKED_IN'])
        ).order_by(Appointment.appointment_date.asc(), Appointment.slot_time.asc()).all()

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/appointments.html',
                           patient=patient, appointments=apts,
                           tab=tab, today=today, notif_count=notif_count)


@portal_bp.route('/appointments/book', methods=['GET', 'POST'])
@login_required
@role_required('Patient')
def book_appointment():
    patient = _require_patient()
    if not patient:
        return render_template('portal/not_linked.html')

    doc_role = Role.query.filter_by(name='Doctor').first()
    doctors = User.query.filter_by(role_id=doc_role.id, is_active=True).all() if doc_role else []

    selected_doc_id = request.args.get('doctor_id', type=int)
    selected_date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()

    slot_info = generate_doctor_slots(selected_doc_id, selected_date) if selected_doc_id else {'slots': []}

    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id', type=int)
        apt_date_str = request.form.get('appointment_date')
        slot_time_str = request.form.get('slot_time', '').strip()
        notes = request.form.get('notes', '').strip()

        if not doctor_id or not apt_date_str or not slot_time_str:
            flash('Please select a doctor, date, and time slot.', 'danger')
            return redirect(url_for('portal.book_appointment'))

        try:
            apt_date = datetime.strptime(apt_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date.', 'danger')
            return redirect(url_for('portal.book_appointment'))

        slot_t = None
        for fmt in ('%H:%M:%S', '%H:%M', '%I:%M %p', '%I:%M%p'):
            try:
                slot_t = datetime.strptime(slot_time_str, fmt).time()
                break
            except ValueError:
                pass

        if not slot_t:
            flash('Invalid arrival time window.', 'danger')
            return redirect(url_for('portal.book_appointment', doctor_id=doctor_id, date=apt_date_str))

        # Double-booking prevention
        existing = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == apt_date,
            Appointment.slot_time == slot_t,
            Appointment.status != 'CANCELLED'
        ).first()
        if existing:
            flash('This slot is no longer available. Please choose another.', 'danger')
            return redirect(url_for('portal.book_appointment', doctor_id=doctor_id, date=apt_date_str))

        apt = Appointment(
            appointment_code=Appointment.generate_appointment_code(),
            patient_id=patient.id,
            doctor_id=doctor_id,
            appointment_date=apt_date,
            slot_time=slot_t,
            booking_type='Online',
            priority='Regular',
            status='BOOKED',
            notes=notes or None
        )
        db.session.add(apt)
        db.session.commit()

        flash(f'Appointment booked! {apt.appointment_code} — {apt.appointment_date.strftime("%d %b %Y")} at {apt.slot_time.strftime("%I:%M %p")}', 'success')
        return redirect(url_for('portal.appointments'))

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/book_appointment.html',
                           patient=patient, doctors=doctors,
                           selected_doc_id=selected_doc_id,
                           selected_date=selected_date,
                           slot_info=slot_info,
                           notif_count=notif_count)


@portal_bp.route('/appointments/<int:appointment_id>/cancel', methods=['POST'])
@login_required
@role_required('Patient')
def cancel_appointment(appointment_id):
    patient = _require_patient()
    if not patient:
        abort(403)

    apt = Appointment.query.get_or_404(appointment_id)
    if apt.patient_id != patient.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('portal.appointments'))

    if apt.status not in ('BOOKED',):
        flash('This appointment cannot be cancelled.', 'warning')
        return redirect(url_for('portal.appointments'))

    apt.status = 'CANCELLED'
    db.session.commit()
    flash(f'Appointment {apt.appointment_code} cancelled.', 'info')
    return redirect(url_for('portal.appointments'))


# ─────────────────────────────────────────────────────────────
# MY CONSULTATIONS / VISIT HISTORY
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/consultations')
@login_required
@role_required('Patient')
def consultations():
    patient = _require_patient()
    if not patient:
        return render_template('portal/not_linked.html')

    consults = Consultation.query.filter_by(
        patient_id=patient.id
    ).order_by(Consultation.created_at.desc()).all()

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/consultations.html',
                           patient=patient, consultations=consults, notif_count=notif_count)


@portal_bp.route('/consultations/<int:consultation_id>')
@login_required
@role_required('Patient')
def consultation_detail(consultation_id):
    patient = _require_patient()
    if not patient:
        abort(403)

    consultation = Consultation.query.get_or_404(consultation_id)
    if consultation.patient_id != patient.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('portal.consultations'))

    # Get linked prescription
    linked_rx = Prescription.query.filter_by(consultation_id=consultation.id).first()
    # Get linked lab requests
    linked_labs = LabRequest.query.filter_by(consultation_id=consultation.id).all()

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/consultation_detail.html',
                           patient=patient, consultation=consultation,
                           linked_rx=linked_rx, linked_labs=linked_labs,
                           notif_count=notif_count)


# ─────────────────────────────────────────────────────────────
# MY PRESCRIPTIONS
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/prescriptions')
@login_required
@role_required('Patient')
def prescriptions():
    patient = _require_patient()
    if not patient:
        return render_template('portal/not_linked.html')

    rxs = Prescription.query.filter_by(
        patient_id=patient.id
    ).order_by(Prescription.created_at.desc()).all()

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/prescriptions.html',
                           patient=patient, prescriptions=rxs, notif_count=notif_count)


@portal_bp.route('/prescriptions/<int:prescription_id>')
@login_required
@role_required('Patient')
def prescription_detail(prescription_id):
    patient = _require_patient()
    if not patient:
        abort(403)

    rx = Prescription.query.get_or_404(prescription_id)
    if rx.patient_id != patient.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('portal.prescriptions'))

    verify_url = request.host_url.rstrip('/') + url_for('prescriptions.verify_prescription', prescription_code=rx.prescription_code)
    qr_base64 = generate_prescription_qr_base64(verify_url)

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/prescription_detail.html',
                           patient=patient, rx=rx,
                           qr_base64=qr_base64, verify_url=verify_url,
                           notif_count=notif_count)


# ─────────────────────────────────────────────────────────────
# MY LAB REPORTS
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/lab-reports')
@login_required
@role_required('Patient')
def lab_reports():
    patient = _require_patient()
    if not patient:
        return render_template('portal/not_linked.html')

    labs = LabRequest.query.filter_by(
        patient_id=patient.id
    ).order_by(LabRequest.created_at.desc()).all()

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/lab_reports.html',
                           patient=patient, lab_requests=labs, notif_count=notif_count)


@portal_bp.route('/lab-reports/<int:request_id>')
@login_required
@role_required('Patient')
def lab_report_detail(request_id):
    patient = _require_patient()
    if not patient:
        abort(403)

    lab_req = LabRequest.query.get_or_404(request_id)
    if lab_req.patient_id != patient.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('portal.lab_reports'))

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/lab_report_detail.html',
                           patient=patient, lab_request=lab_req,
                           notif_count=notif_count)


# ─────────────────────────────────────────────────────────────
# MY BILLS & PAYMENTS
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/bills')
@login_required
@role_required('Patient')
def bills():
    patient = _require_patient()
    if not patient:
        return render_template('portal/not_linked.html')

    patient_bills = Bill.query.filter_by(
        patient_id=patient.id
    ).order_by(Bill.created_at.desc()).all()

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/bills.html',
                           patient=patient, bills=patient_bills, notif_count=notif_count)


@portal_bp.route('/bills/<int:bill_id>')
@login_required
@role_required('Patient')
def bill_detail(bill_id):
    patient = _require_patient()
    if not patient:
        abort(403)

    bill = Bill.query.get_or_404(bill_id)
    if bill.patient_id != patient.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('portal.bills'))

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/bill_detail.html',
                           patient=patient, bill=bill, notif_count=notif_count)


# ─────────────────────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/notifications')
@login_required
@role_required('Patient')
def notifications():
    patient = _require_patient()
    if not patient:
        return render_template('portal/not_linked.html')

    type_filter = request.args.get('type', 'ALL')
    query = Notification.query.filter_by(patient_id=patient.id)
    if type_filter != 'ALL':
        query = query.filter_by(type=type_filter)
    notifs = query.order_by(Notification.created_at.desc()).all()

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/notifications.html',
                           patient=patient, notifications=notifs,
                           type_filter=type_filter, notif_count=notif_count)


# ─────────────────────────────────────────────────────────────
# MEDICAL RECORDS (EHR Timeline)
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/medical-records')
@login_required
@role_required('Patient')
def medical_records():
    patient = _require_patient()
    if not patient:
        return render_template('portal/not_linked.html')

    from app.ehr.timeline_builder import build_patient_ehr_timeline
    search_q = request.args.get('q', '').strip()
    event_filter = request.args.get('type', 'ALL').strip()
    timeline_events = build_patient_ehr_timeline(patient.id, search_term=search_q, event_filter=event_filter)

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/medical_records.html',
                           patient=patient, events=timeline_events,
                           search_q=search_q, event_filter=event_filter,
                           notif_count=notif_count)


# ─────────────────────────────────────────────────────────────
# ACCOUNT & SECURITY
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/account')
@login_required
@role_required('Patient')
def account():
    patient = _require_patient()
    if not patient:
        return render_template('portal/not_linked.html')

    notif_count = Notification.query.filter_by(patient_id=patient.id, status='PENDING').count()
    return render_template('portal/account.html',
                           patient=patient, notif_count=notif_count)


@portal_bp.route('/account/change-password', methods=['POST'])
@login_required
@role_required('Patient')
def change_password():
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if not current_user.check_password(current_pw):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('portal.account'))

    if len(new_pw) < 8:
        flash('New password must be at least 8 characters.', 'danger')
        return redirect(url_for('portal.account'))

    if new_pw != confirm_pw:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('portal.account'))

    current_user.set_password(new_pw)
    db.session.commit()
    flash('Password changed successfully.', 'success')
    return redirect(url_for('portal.account'))
