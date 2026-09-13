"""
CareHub Authenticated Patient AI Tools — Controlled server-side tools for authenticated patient portal assistant.
Strictly isolated to current_patient_id derived from the authenticated session.
"""
from datetime import datetime, date, time, timedelta
from app.extensions import db
from app.auth.models import User
from app.patients.models import Patient
from app.doctors.models import Doctor
from app.admin.models import Department, AuditLog
from app.appointments.models import Appointment, Waitlist
from app.queue.queue_engine import get_doctor_clinic_windows
from app.notifications.models import Notification

def patient_get_departments():
    """Returns active hospital clinical departments."""
    from app.ai.tools_public import public_get_departments
    return public_get_departments()

def patient_search_doctors(department_or_specialty=None, query=None):
    """Searches doctors in CareHub."""
    from app.ai.tools_public import public_search_doctors
    return public_search_doctors(department_or_specialty, query)

def patient_find_available_slots(doctor_id: int, target_date_str: str):
    """Finds available 15-minute arrival slots for a doctor on target_date (YYYY-MM-DD)."""
    from app.ai.tools_public import public_find_available_slots
    return public_find_available_slots(doctor_id, target_date_str)

def patient_get_my_appointments(current_patient_id: int):
    """
    Retrieves upcoming and active appointments for the currently authenticated patient only.
    """
    if not current_patient_id:
        return {'error': 'Patient session identity missing.'}

    appointments = Appointment.query.filter(
        Appointment.patient_id == current_patient_id,
        Appointment.status.in_(['BOOKED', 'CHECKED_IN'])
    ).order_by(Appointment.appointment_date.asc(), Appointment.slot_time.asc()).all()

    results = []
    for apt in appointments:
        doc = apt.doctor
        results.append({
            'appointment_id': apt.id,
            'appointment_code': apt.appointment_code,
            'doctor_id': apt.doctor_id,
            'doctor_name': doc.name if doc else 'Attending Physician',
            'department': doc.department if doc else 'General OPD',
            'specialization': doc.specialization if doc else 'Doctor',
            'appointment_date': apt.appointment_date.strftime('%Y-%m-%d'),
            'appointment_date_formatted': apt.appointment_date.strftime('%A, %d %B %Y'),
            'slot_time': apt.slot_time.strftime('%I:%M %p'),
            'status': apt.status,
            'notes': apt.notes
        })

    return {
        'total_active_appointments': len(results),
        'appointments': results
    }

def patient_book_appointment(current_patient_id: int, doctor_id: int,
                             appointment_date_str: str, slot_time_str: str,
                             reason: str = None, confirmed: bool = False):
    """
    Books an appointment for the currently authenticated patient.
    """
    patient = Patient.query.get(current_patient_id)
    if not patient:
        return {'success': False, 'error': 'Patient profile not found.'}

    try:
        apt_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
    except ValueError:
        return {'success': False, 'error': 'Invalid date format. Expected YYYY-MM-DD.'}

    if apt_date < date.today():
        return {'success': False, 'error': 'Cannot book an appointment for a past date.'}

    doctor_user = User.query.get(doctor_id)
    if not doctor_user:
        doc_profile = Doctor.query.get(doctor_id)
        if doc_profile and doc_profile.user_id:
            doctor_user = User.query.get(doc_profile.user_id)
        elif doc_profile:
            doctor_user = User.query.filter_by(user_code=doc_profile.doctor_code).first()

    if not doctor_user:
        return {'success': False, 'error': f'Doctor with ID {doctor_id} not found.'}

    slot_t = None
    for fmt in ('%H:%M:%S', '%H:%M', '%I:%M %p', '%I:%M%p'):
        try:
            slot_t = datetime.strptime(slot_time_str.strip(), fmt).time()
            break
        except ValueError:
            pass

    if not slot_t:
        return {'success': False, 'error': f'Invalid slot time: {slot_time_str}.'}

    if not confirmed:
        return {
            'success': True,
            'requires_confirmation': True,
            'booking_summary': {
                'patient_name': patient.full_name,
                'patient_code': patient.patient_code,
                'doctor_name': doctor_user.name,
                'department': doctor_user.department or 'General OPD',
                'appointment_date': apt_date.strftime('%Y-%m-%d'),
                'appointment_date_formatted': apt_date.strftime('%A, %d %B %Y'),
                'slot_time': slot_t.strftime('%I:%M %p'),
                'reason': reason or 'General Consultation'
            },
            'confirmation_prompt': f"Please confirm: Book an appointment with {doctor_user.name} ({doctor_user.department or 'General OPD'}) on {apt_date.strftime('%A, %d %B %Y')} at {slot_t.strftime('%I:%M %p')}?"
        }

    # Double-booking check
    existing = Appointment.query.filter(
        Appointment.doctor_id == doctor_user.id,
        Appointment.appointment_date == apt_date,
        Appointment.slot_time == slot_t,
        Appointment.status != 'CANCELLED'
    ).first()

    if existing:
        return {
            'success': False,
            'error': f'Slot {slot_t.strftime("%I:%M %p")} on {apt_date.strftime("%d %b %Y")} was just taken. Please choose another available slot.'
        }

    apt_code = Appointment.generate_appointment_code()
    appointment = Appointment(
        appointment_code=apt_code,
        patient_id=patient.id,
        doctor_id=doctor_user.id,
        appointment_date=apt_date,
        slot_time=slot_t,
        booking_type='Online',
        priority='Regular',
        status='BOOKED',
        notes=f"[Patient Portal AI] {reason}" if reason else "[Patient Portal AI]"
    )
    db.session.add(appointment)
    db.session.flush()

    audit = AuditLog(
        user_id=patient.portal_user_id,
        action='AI_PATIENT_BOOKING',
        entity_type='Appointment',
        entity_id=appointment.id,
        details=f"Patient Portal AI booked appointment {apt_code} with {doctor_user.name} for {apt_date} at {slot_t}"
    )
    db.session.add(audit)

    notif = Notification(
        patient_id=patient.id,
        type='APPOINTMENT_REMINDER',
        title=f'Appointment Confirmed: {apt_code}',
        message=f'Your appointment with {doctor_user.name} is confirmed for {apt_date.strftime("%d %b %Y")} at {slot_t.strftime("%I:%M %p")}.',
        channel='EMAIL' if patient.email else 'SMS',
        status='PENDING'
    )
    db.session.add(notif)

    db.session.commit()

    return {
        'success': True,
        'appointment_code': apt_code,
        'doctor_name': doctor_user.name,
        'department': doctor_user.department or 'General OPD',
        'appointment_date': apt_date.strftime('%A, %d %B %Y'),
        'slot_time': slot_t.strftime('%I:%M %p'),
        'message': f"🎉 Appointment {apt_code} booked successfully with {doctor_user.name} on {apt_date.strftime('%A, %d %B %Y')} at {slot_t.strftime('%I:%M %p')}!"
    }

def patient_reschedule_appointment(current_patient_id: int, appointment_id: int,
                                   new_date_str: str, new_slot_time_str: str,
                                   reason: str = None, confirmed: bool = False):
    """
    Reschedules an existing appointment belonging to the authenticated patient.
    """
    apt = Appointment.query.get(appointment_id)
    if not apt:
        return {'success': False, 'error': f'Appointment ID {appointment_id} not found.'}

    # Strict authorization isolation
    if apt.patient_id != current_patient_id:
        return {'success': False, 'error': 'Access denied. You can only manage your own appointments.'}

    if apt.status not in ('BOOKED',):
        return {'success': False, 'error': f'Cannot reschedule an appointment with status: {apt.status}.'}

    try:
        new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
    except ValueError:
        return {'success': False, 'error': 'Invalid date format. Expected YYYY-MM-DD.'}

    if new_date < date.today():
        return {'success': False, 'error': 'Cannot reschedule to a past date.'}

    slot_t = None
    for fmt in ('%H:%M:%S', '%H:%M', '%I:%M %p', '%I:%M%p'):
        try:
            slot_t = datetime.strptime(new_slot_time_str.strip(), fmt).time()
            break
        except ValueError:
            pass

    if not slot_t:
        return {'success': False, 'error': f'Invalid slot time: {new_slot_time_str}.'}

    doc = apt.doctor
    if not confirmed:
        return {
            'success': True,
            'requires_confirmation': True,
            'reschedule_summary': {
                'appointment_code': apt.appointment_code,
                'doctor_name': doc.name if doc else 'Doctor',
                'old_date': apt.appointment_date.strftime('%A, %d %B %Y'),
                'old_slot_time': apt.slot_time.strftime('%I:%M %p'),
                'new_date': new_date.strftime('%Y-%m-%d'),
                'new_date_formatted': new_date.strftime('%A, %d %B %Y'),
                'new_slot_time': slot_t.strftime('%I:%M %p'),
                'reason': reason or 'Patient Request'
            },
            'confirmation_prompt': f"Please confirm: Reschedule appointment {apt.appointment_code} with {doc.name if doc else 'Doctor'} to {new_date.strftime('%A, %d %B %Y')} at {slot_t.strftime('%I:%M %p')}?"
        }

    # Conflict check
    conflict = Appointment.query.filter(
        Appointment.doctor_id == apt.doctor_id,
        Appointment.appointment_date == new_date,
        Appointment.slot_time == slot_t,
        Appointment.status != 'CANCELLED',
        Appointment.id != apt.id
    ).first()

    if conflict:
        return {
            'success': False,
            'error': f'Slot {slot_t.strftime("%I:%M %p")} on {new_date.strftime("%d %b %Y")} is already reserved. Please choose another window.'
        }

    old_date_str = apt.appointment_date.strftime('%d %b %Y')
    old_time_str = apt.slot_time.strftime('%I:%M %p')

    apt.appointment_date = new_date
    apt.slot_time = slot_t
    if reason:
        apt.notes = f"{apt.notes or ''} [Rescheduled via AI: {reason}]".strip()

    audit = AuditLog(
        user_id=apt.patient.portal_user_id if apt.patient else None,
        action='AI_PATIENT_RESCHEDULE',
        entity_type='Appointment',
        entity_id=apt.id,
        details=f"Patient Portal AI rescheduled {apt.appointment_code} from {old_date_str} {old_time_str} to {new_date} {slot_t}"
    )
    db.session.add(audit)

    notif = Notification(
        patient_id=apt.patient_id,
        type='APPOINTMENT_REMINDER',
        title=f'Appointment Rescheduled: {apt.appointment_code}',
        message=f'Your appointment has been rescheduled to {new_date.strftime("%d %b %Y")} at {slot_t.strftime("%I:%M %p")}.',
        channel='EMAIL' if (apt.patient and apt.patient.email) else 'SMS',
        status='PENDING'
    )
    db.session.add(notif)

    db.session.commit()

    return {
        'success': True,
        'appointment_code': apt.appointment_code,
        'doctor_name': doc.name if doc else 'Doctor',
        'new_appointment_date': new_date.strftime('%A, %d %B %Y'),
        'new_slot_time': slot_t.strftime('%I:%M %p'),
        'message': f"✅ Appointment {apt.appointment_code} successfully rescheduled to {new_date.strftime('%A, %d %B %Y')} at {slot_t.strftime('%I:%M %p')}!"
    }

def patient_cancel_appointment(current_patient_id: int, appointment_id: int, confirmed: bool = False):
    """
    Cancels an existing appointment belonging to the authenticated patient.
    """
    apt = Appointment.query.get(appointment_id)
    if not apt:
        return {'success': False, 'error': f'Appointment ID {appointment_id} not found.'}

    if apt.patient_id != current_patient_id:
        return {'success': False, 'error': 'Access denied. You can only cancel your own appointments.'}

    if apt.status != 'BOOKED':
        return {'success': False, 'error': f'This appointment cannot be cancelled because its status is already {apt.status}.'}

    doc = apt.doctor
    if not confirmed:
        return {
            'success': True,
            'requires_confirmation': True,
            'cancel_summary': {
                'appointment_code': apt.appointment_code,
                'doctor_name': doc.name if doc else 'Doctor',
                'appointment_date': apt.appointment_date.strftime('%A, %d %B %Y'),
                'slot_time': apt.slot_time.strftime('%I:%M %p')
            },
            'confirmation_prompt': f"⚠️ Are you sure you want to cancel appointment {apt.appointment_code} with {doc.name if doc else 'Doctor'} on {apt.appointment_date.strftime('%A, %d %B %Y')} at {apt.slot_time.strftime('%I:%M %p')}?"
        }

    apt.status = 'CANCELLED'

    # Auto-Waitlist Promotion logic
    top_waitlist = Waitlist.query.filter_by(
        doctor_id=apt.doctor_id,
        preferred_date=apt.appointment_date,
        status='WAITING'
    ).order_by(Waitlist.created_at.asc()).first()

    waitlist_promoted = False
    if top_waitlist:
        top_waitlist.offered_slot_time = apt.slot_time
        top_waitlist.status = 'OFFERED'
        waitlist_promoted = True

    audit = AuditLog(
        user_id=apt.patient.portal_user_id if apt.patient else None,
        action='AI_PATIENT_CANCEL',
        entity_type='Appointment',
        entity_id=apt.id,
        details=f"Patient Portal AI cancelled appointment {apt.appointment_code} (freed slot {apt.slot_time} on {apt.appointment_date})"
    )
    db.session.add(audit)

    db.session.commit()

    return {
        'success': True,
        'appointment_code': apt.appointment_code,
        'freed_slot': apt.slot_time.strftime('%I:%M %p'),
        'appointment_date': apt.appointment_date.strftime('%A, %d %B %Y'),
        'waitlist_promoted': waitlist_promoted,
        'message': f"🚫 Appointment {apt.appointment_code} has been successfully cancelled."
    }
