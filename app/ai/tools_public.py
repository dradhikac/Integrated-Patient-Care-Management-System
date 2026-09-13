"""
CareHub Public AI Tools — Controlled server-side tools for unauthenticated landing-page booking assistant.
"""
from datetime import datetime, date, time, timedelta
from app.extensions import db
from app.auth.models import User, Role
from app.patients.models import Patient
from app.doctors.models import Doctor
from app.admin.models import Department, AuditLog
from app.appointments.models import Appointment, Holiday
from app.queue.queue_engine import get_doctor_clinic_windows
from app.patients.duplicate_check import check_for_duplicates
from app.notifications.models import Notification

def public_get_departments():
    """Returns list of active clinical departments at CareHub."""
    depts = Department.query.filter_by(is_active=True).all()
    if not depts:
        # Fallback from doctor records if departments table is not populated
        docs = Doctor.query.filter_by(is_active=True).all()
        dept_names = sorted(list(set(d.department for d in docs if d.department)))
        return [{'name': name, 'category': 'Clinical'} for name in dept_names]
    
    return [
        {
            'dept_code': d.dept_code,
            'name': d.dept_name,
            'category': d.category,
            'operating_hours': d.operating_hours,
            'description': d.description
        }
        for d in depts
    ]

def public_search_doctors(department_or_specialty=None, query=None):
    """
    Finds verified doctors by department, specialization, or name.
    """
    doc_query = Doctor.query.filter_by(is_active=True)
    
    if department_or_specialty:
        term = f"%{department_or_specialty.strip()}%"
        doc_query = doc_query.filter(
            (Doctor.department.ilike(term)) | 
            (Doctor.specialization.ilike(term))
        )
        
    if query:
        term = f"%{query.strip()}%"
        doc_query = doc_query.filter(
            (Doctor.name.ilike(term)) | 
            (Doctor.specialization.ilike(term)) | 
            (Doctor.department.ilike(term))
        )
        
    doctors = doc_query.all()
    
    results = []
    for d in doctors:
        # Resolve doctor's User id for appointment booking
        user_id = d.user_id
        if not user_id and d.user:
            user_id = d.user.id
        elif not user_id:
            user_obj = User.query.filter_by(user_code=d.doctor_code).first()
            if user_obj:
                user_id = user_obj.id

        results.append({
            'doctor_id': user_id or d.id,
            'doctor_code': d.doctor_code,
            'name': d.name,
            'specialization': d.specialization,
            'department': d.department,
            'education': d.education,
            'experience': d.experience,
            'consultation_fee': d.consultation_fee,
            'rating': d.rating,
            'available_days': d.available_days
        })
    return results

def public_check_doctor_availability(doctor_id: int, target_date_str: str):
    """
    Checks if a doctor is working on a specific date (YYYY-MM-DD) and returns clinic hours.
    """
    try:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    except ValueError:
        return {'error': 'Invalid date format. Use YYYY-MM-DD.'}

    if target_date < date.today():
        return {'available': False, 'reason': 'Cannot book appointments for past dates.'}

    windows = get_doctor_clinic_windows(doctor_id, target_date)
    return {
        'doctor_id': doctor_id,
        'date': target_date_str,
        'is_holiday': windows.get('is_holiday', False),
        'holiday_reason': windows.get('holiday_reason'),
        'has_availability': windows.get('has_availability', False),
        'clinic_hours': windows.get('clinic_hours_str', 'Not Scheduled')
    }

def public_find_available_slots(doctor_id: int, target_date_str: str):
    """
    Returns actual 15-minute available arrival slots for a doctor on a given date (YYYY-MM-DD).
    """
    try:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    except ValueError:
        return {'error': 'Invalid date format. Use YYYY-MM-DD.'}

    if target_date < date.today():
        return {'error': 'Cannot query slots for past dates.', 'slots': []}

    windows = get_doctor_clinic_windows(doctor_id, target_date)
    
    if windows.get('is_holiday'):
        return {
            'is_holiday': True,
            'holiday_reason': windows.get('holiday_reason'),
            'slots': []
        }

    slots = []
    for w in windows.get('arrival_windows', []):
        if w.get('is_available'):
            slots.append({
                'time_24h': w.get('time_24h'),
                'time_12h': w.get('time_str'),
                'recommended_reporting_time': w.get('recommended_arrival_str')
            })

    return {
        'doctor_id': doctor_id,
        'date': target_date_str,
        'clinic_hours': windows.get('clinic_hours_str'),
        'available_slots_count': len(slots),
        'slots': slots
    }

def public_book_appointment(patient_name: str, patient_mobile: str, patient_email: str,
                            doctor_id: int, appointment_date_str: str, slot_time_str: str,
                            reason: str = None, confirmed: bool = False):
    """
    Books a new appointment for an unauthenticated guest visitor.
    Requires confirmed=True to commit the booking.
    """
    # 1. Validation
    if not patient_name or len(patient_name.strip()) < 2:
        return {'success': False, 'error': 'Please provide a valid patient name.'}
    if not patient_mobile or len(patient_mobile.strip()) < 10:
        return {'success': False, 'error': 'Please provide a valid 10-15 digit mobile number.'}

    try:
        apt_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
    except ValueError:
        return {'success': False, 'error': 'Invalid date format. Expected YYYY-MM-DD.'}

    if apt_date < date.today():
        return {'success': False, 'error': 'Cannot book an appointment for a past date.'}

    # Resolve doctor
    doctor_user = User.query.get(doctor_id)
    if not doctor_user:
        # Check by Doctor table id
        doc_profile = Doctor.query.get(doctor_id)
        if doc_profile and doc_profile.user_id:
            doctor_user = User.query.get(doc_profile.user_id)
        elif doc_profile:
            doctor_user = User.query.filter_by(user_code=doc_profile.doctor_code).first()

    if not doctor_user:
        return {'success': False, 'error': f'Doctor with ID {doctor_id} not found.'}

    # Parse slot time
    slot_t = None
    for fmt in ('%H:%M:%S', '%H:%M', '%I:%M %p', '%I:%M%p'):
        try:
            slot_t = datetime.strptime(slot_time_str.strip(), fmt).time()
            break
        except ValueError:
            pass

    if not slot_t:
        return {'success': False, 'error': f'Invalid slot time: {slot_time_str}.'}

    # If not confirmed yet, return summary for explicit user confirmation
    if not confirmed:
        return {
            'success': True,
            'requires_confirmation': True,
            'booking_summary': {
                'patient_name': patient_name.strip(),
                'patient_mobile': patient_mobile.strip(),
                'patient_email': patient_email.strip() if patient_email else None,
                'doctor_name': doctor_user.name,
                'doctor_specialization': doctor_user.specialization or (doctor_user.doctor_profile[0].specialization if doctor_user.doctor_profile else 'Consultant'),
                'department': doctor_user.department or 'General OPD',
                'appointment_date': apt_date.strftime('%Y-%m-%d'),
                'appointment_date_formatted': apt_date.strftime('%A, %d %B %Y'),
                'slot_time': slot_t.strftime('%I:%M %p'),
                'reason': reason or 'General Consultation'
            },
            'confirmation_prompt': f"Please confirm: Book an appointment with {doctor_user.name} on {apt_date.strftime('%A, %d %B %Y')} at {slot_t.strftime('%I:%M %p')} for {patient_name.strip()}?"
        }

    # 2. Duplicate Detection / Patient lookup or creation
    clean_mobile = patient_mobile.strip().replace('-', '').replace(' ', '')
    name_parts = patient_name.strip().split(' ', 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else 'Patient'

    # Check existing patient by mobile or email
    patient = None
    if clean_mobile:
        patient = Patient.query.filter(Patient.mobile.like(f"%{clean_mobile[-10:]}%")).first()
    if not patient and patient_email:
        patient = Patient.query.filter_by(email=patient_email.strip()).first()

    if not patient:
        # Create new unauthenticated patient record
        year = datetime.now().year
        last_pat = Patient.query.order_by(Patient.id.desc()).first()
        new_id = (last_pat.id + 1) if last_pat else 1
        patient_code = f"IPCMS-{year}-{new_id:06d}"

        patient = Patient(
            patient_code=patient_code,
            first_name=first_name,
            last_name=last_name,
            full_name=f"{first_name} {last_name}",
            dob=date(1990, 1, 1), # Default placeholder for guest
            gender='Other',
            mobile=clean_mobile,
            email=patient_email.strip() if patient_email else None,
            address='Public AI Guest Booking',
            portal_status='NOT_ACTIVATED'
        )
        db.session.add(patient)
        db.session.flush()

    # 3. Double booking protection check right before insertion
    existing = Appointment.query.filter(
        Appointment.doctor_id == doctor_user.id,
        Appointment.appointment_date == apt_date,
        Appointment.slot_time == slot_t,
        Appointment.status != 'CANCELLED'
    ).first()

    if existing:
        return {
            'success': False,
            'error': f'Slot {slot_t.strftime("%I:%M %p")} on {apt_date.strftime("%d %b %Y")} was just booked. Please choose another available slot.'
        }

    # 4. Insert Appointment
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
        notes=f"[Public AI Booking] {reason}" if reason else "[Public AI Booking]"
    )
    db.session.add(appointment)
    db.session.flush()

    # 5. Audit Log & Notification
    audit = AuditLog(
        user_id=None,
        action='AI_PUBLIC_BOOKING',
        entity_type='Appointment',
        entity_id=appointment.id,
        details=f"Public AI booked appointment {apt_code} for patient {patient.full_name} with doctor {doctor_user.name} on {apt_date} at {slot_t}"
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
        'patient_name': patient.full_name,
        'patient_code': patient.patient_code,
        'doctor_name': doctor_user.name,
        'department': doctor_user.department or 'General OPD',
        'appointment_date': apt_date.strftime('%A, %d %B %Y'),
        'slot_time': slot_t.strftime('%I:%M %p'),
        'message': f"🎉 Appointment {apt_code} successfully booked with {doctor_user.name} for {apt_date.strftime('%A, %d %B %Y')} at {slot_t.strftime('%I:%M %p')}!"
    }
