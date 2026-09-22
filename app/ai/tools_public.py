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
from app.notifications.reception_notifications import create_reception_notification

def public_lookup_patient(contact_info: str):
    """
    Looks up a returning CareHub patient by mobile phone number or email address.
    Confirms existing account status without exposing sensitive EHR records on the public website.
    """
    if not contact_info or len(contact_info.strip()) < 3:
        return {'found': False, 'message': 'Please provide a valid phone number or email address.'}

    clean_info = contact_info.strip()
    digits = ''.join(c for c in clean_info if c.isdigit())

    patient = None
    if len(digits) >= 10:
        patient = Patient.query.filter(Patient.mobile.like(f"%{digits[-10:]}%")).first()

    if not patient and '@' in clean_info:
        patient = Patient.query.filter(Patient.email.ilike(clean_info)).first()

    if patient:
        masked_mobile = f"{patient.mobile[:2]}******{patient.mobile[-2:]}" if patient.mobile and len(patient.mobile) >= 4 else patient.mobile
        masked_email = f"{patient.email[:2]}***@{patient.email.split('@')[-1]}" if patient.email and '@' in patient.email else None
        return {
            'found': True,
            'patient_id': patient.id,
            'patient_code': patient.patient_code,
            'patient_name': patient.full_name,
            'first_name': patient.first_name,
            'masked_mobile': masked_mobile,
            'masked_email': masked_email,
            'message': f"CareHub account found for {patient.full_name}."
        }
    else:
        return {
            'found': False,
            'message': "I couldn't find a matching CareHub account with that information. Would you like to try another phone number or email, or continue as a new patient?"
        }

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
    All CareHub doctors work 24/7 round-the-clock on their active days and have 1 off day per week.
    """
    try:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    except ValueError:
        return {'error': 'Invalid date format. Use YYYY-MM-DD.'}

    if target_date < date.today():
        return {'available': False, 'reason': 'Cannot book appointments for past dates.'}

    windows = get_doctor_clinic_windows(doctor_id, target_date)
    has_avail = windows.get('has_availability', False)
    weekday_name = target_date.strftime('%A')
    return {
        'doctor_id': doctor_id,
        'date': target_date_str,
        'day_of_week': weekday_name,
        'is_holiday': windows.get('is_holiday', False),
        'holiday_reason': windows.get('holiday_reason'),
        'has_availability': has_avail,
        'clinic_hours': windows.get('clinic_hours_str', 'Day Off'),
        'message': "Available 24/7 (Round-the-clock)" if has_avail else f"Doctor has their weekly day off on {weekday_name}."
    }

def public_find_available_slots(doctor_id: int, target_date_str: str):
    """
    Returns actual 15-minute available arrival slots for a doctor on a given date (YYYY-MM-DD).
    Supports 24/7 round-the-clock slots and flags weekly off-days.
    """
    try:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    except ValueError:
        return {'error': 'Invalid date format. Use YYYY-MM-DD.'}

    if target_date < date.today():
        return {'error': 'Cannot query slots for past dates.', 'slots': []}

    windows = get_doctor_clinic_windows(doctor_id, target_date)
    weekday_name = target_date.strftime('%A')
    
    if windows.get('is_holiday'):
        return {
            'is_holiday': True,
            'holiday_reason': windows.get('holiday_reason'),
            'slots': []
        }

    if not windows.get('has_availability'):
        doc_obj = Doctor.query.filter((Doctor.user_id == doctor_id) | (Doctor.id == doctor_id)).first()
        doc_name = doc_obj.name if doc_obj else f"Doctor ID {doctor_id}"
        return {
            'doctor_id': doctor_id,
            'doctor_name': doc_name,
            'date': target_date_str,
            'day_of_week': weekday_name,
            'has_availability': False,
            'status': 'DAY_OFF',
            'clinic_hours': windows.get('clinic_hours_str', 'Day Off'),
            'message': f"{doc_name} is off on {weekday_name} (Weekly Day Off). They are available 24/7 on all other days. Please select another date or choose another doctor in this department.",
            'available_slots_count': 0,
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

    # Convenient time suggestions for quick selection
    convenient_suggestions = {
        'morning': [s for s in ['09:00 AM', '10:30 AM', '11:15 AM'] if any(x['time_12h'] == s for x in slots)],
        'afternoon': [s for s in ['02:00 PM', '03:30 PM', '05:00 PM'] if any(x['time_12h'] == s for x in slots)],
        'evening_night': [s for s in ['07:30 PM', '09:00 PM', '11:00 PM'] if any(x['time_12h'] == s for x in slots)]
    }

    return {
        'doctor_id': doctor_id,
        'date': target_date_str,
        'day_of_week': weekday_name,
        'has_availability': True,
        'clinic_hours': windows.get('clinic_hours_str'),
        'available_slots_count': len(slots),
        'convenient_suggestions': convenient_suggestions,
        'popular_slots': [s['time_12h'] for s in slots[:16]]
    }

def public_book_appointment(patient_name: str, patient_mobile: str, patient_email: str = None,
                            doctor_id: int = 0, appointment_date_str: str = '', slot_time_str: str = '',
                            reason: str = None, confirmed: bool = False,
                            booked_for: str = 'Myself', patient_status: str = None,
                            date_of_birth_str: str = None):
    """
    Books a new appointment via the public Maya Booking Concierge.
    Automatically identifies existing vs new patients in the backend and dispatches receptionist notifications.
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

    dept_name = doctor_user.department or 'General OPD'

    # 2. Duplicate Detection / Patient lookup
    clean_mobile = patient_mobile.strip().replace('-', '').replace(' ', '')
    name_parts = patient_name.strip().split(' ', 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else 'Patient'

    # Check existing patient by mobile or email
    patient = None
    if len(clean_mobile) >= 10:
        patient = Patient.query.filter(Patient.mobile.like(f"%{clean_mobile[-10:]}%")).first()
    if not patient and patient_email:
        patient = Patient.query.filter_by(email=patient_email.strip()).first()

    # Determine backend patient status
    is_existing = (patient is not None)
    computed_status = 'existing' if is_existing else 'new'
    status_display = '🟢 Existing CareHub Patient' if is_existing else '🆕 New Patient'

    # If not confirmed yet, return complete summary for explicit user confirmation
    if not confirmed:
        return {
            'success': True,
            'requires_confirmation': True,
            'booking_summary': {
                'patient_name': patient_name.strip(),
                'patient_status': status_display,
                'booked_for': booked_for or 'Myself',
                'doctor_name': doctor_user.name,
                'doctor_specialization': doctor_user.specialization or (doctor_user.doctor_profile[0].specialization if doctor_user.doctor_profile else 'Consultant'),
                'department': dept_name,
                'appointment_date': apt_date.strftime('%Y-%m-%d'),
                'appointment_date_formatted': apt_date.strftime('%A, %d %B %Y'),
                'slot_time': slot_t.strftime('%I:%M %p'),
                'reason': reason or 'General Consultation',
                'patient_mobile': clean_mobile,
                'patient_email': patient_email.strip() if patient_email else None
            },
            'confirmation_prompt': (
                f"Please confirm your appointment details:\n"
                f"• Patient: {patient_name.strip()}\n"
                f"• Patient Status: {status_display}\n"
                f"• Booked For: {booked_for or 'Myself'}\n"
                f"• Department: {dept_name}\n"
                f"• Doctor: {doctor_user.name}\n"
                f"• Date: {apt_date.strftime('%A, %d %B %Y')}\n"
                f"• Time: {slot_t.strftime('%I:%M %p')}\n"
                f"• Reason: {reason or 'General Consultation'}\n"
                f"• Mobile: {clean_mobile}\n\n"
                f"Would you like me to confirm this appointment?\n"
                f"[Confirm Appointment] [Change Details]"
            )
        }

    # 3. Create new unauthenticated patient record if not already registered
    if not patient:
        parsed_dob = date(1990, 1, 1)
        if date_of_birth_str:
            for dfmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
                try:
                    parsed_dob = datetime.strptime(date_of_birth_str.strip(), dfmt).date()
                    break
                except ValueError:
                    pass

        year = datetime.now().year
        last_pat = Patient.query.order_by(Patient.id.desc()).first()
        new_id = (last_pat.id + 1) if last_pat else 1
        patient_code = f"IPCMS-{year}-{new_id:06d}"

        patient = Patient(
            patient_code=patient_code,
            first_name=first_name,
            last_name=last_name,
            full_name=f"{first_name} {last_name}",
            dob=parsed_dob,
            gender='Other',
            mobile=clean_mobile,
            email=patient_email.strip() if patient_email else None,
            address='Public AI Guest Booking (Maya Concierge)',
            portal_status='NOT_ACTIVATED'
        )
        db.session.add(patient)
        db.session.flush()

    # 4. Double booking protection check right before insertion
    existing_apt = Appointment.query.filter(
        Appointment.doctor_id == doctor_user.id,
        Appointment.appointment_date == apt_date,
        Appointment.slot_time == slot_t,
        Appointment.status != 'CANCELLED'
    ).first()

    if existing_apt:
        return {
            'success': False,
            'error': f'Slot {slot_t.strftime("%I:%M %p")} on {apt_date.strftime("%d %b %Y")} was just booked. Please choose another available slot.'
        }

    # 5. Insert Appointment with structured metadata
    apt_code = Appointment.generate_appointment_code()
    notes_meta = (
        f"[Booking Source: CareHub Website AI (Maya)] "
        f"[Patient Status: {'EXISTING PATIENT' if is_existing else 'NEW PATIENT'}] "
        f"[Booked For: {booked_for or 'Myself'}] "
        f"{reason or 'General Consultation'}"
    )

    appointment = Appointment(
        appointment_code=apt_code,
        patient_id=patient.id,
        doctor_id=doctor_user.id,
        appointment_date=apt_date,
        slot_time=slot_t,
        booking_type='Online',
        priority='Regular',
        status='BOOKED',
        notes=notes_meta
    )
    db.session.add(appointment)
    db.session.flush()

    # 6. Audit Log
    audit = AuditLog(
        user_id=None,
        action='AI_PUBLIC_BOOKING',
        entity_type='Appointment',
        entity_id=appointment.id,
        details=f"Maya (Website AI) booked appointment {apt_code} for {'EXISTING' if is_existing else 'NEW'} patient {patient.full_name} with doctor {doctor_user.name} on {apt_date} at {slot_t}"
    )
    db.session.add(audit)

    # 7. Patient Notification
    notif = Notification(
        patient_id=patient.id,
        type='APPOINTMENT_REMINDER',
        title=f'Appointment Confirmed: {apt_code}',
        message=f'Your appointment with {doctor_user.name} ({dept_name}) is confirmed for {apt_date.strftime("%d %b %Y")} at {slot_t.strftime("%I:%M %p")}. Appointment ID: {apt_code}.',
        channel='EMAIL' if patient.email else 'SMS',
        status='PENDING'
    )
    db.session.add(notif)

    # 8. Receptionist Operational Notification (Categorized & Distinguishable)
    if is_existing:
        rec_title = "🔔 New Appointment Booked"
        rec_message = (
            f"Patient: {patient.full_name}\n"
            f"Patient Status: 🟢 Existing Patient\n"
            f"Booking Source: CareHub Website AI\n"
            f"Booked For: {booked_for or 'Myself'}\n"
            f"Department: {dept_name}\n"
            f"Doctor: {doctor_user.name}\n"
            f"Date: {apt_date.strftime('%d %b %Y')}\n"
            f"Time: {slot_t.strftime('%I:%M %p')}\n"
            f"Reason: {reason or 'General Consultation'}\n"
            f"Phone: {clean_mobile}\n"
            f"Email: {patient.email or 'N/A'}\n"
            f"Appointment ID: {apt_code}\n"
            f"Status: Confirmed"
        )
        rec_icon = 'bi-calendar-check-fill'
        rec_color = '#10B981'
    else:
        rec_title = "🔔 New Appointment Booked"
        rec_message = (
            f"Patient: {patient.full_name}\n"
            f"Patient Status: 🆕 NEW PATIENT\n"
            f"Booking Source: CareHub Website AI\n"
            f"Booked For: {booked_for or 'Myself'}\n"
            f"Department: {dept_name}\n"
            f"Doctor: {doctor_user.name}\n"
            f"Date: {apt_date.strftime('%d %b %Y')}\n"
            f"Time: {slot_t.strftime('%I:%M %p')}\n"
            f"Reason: {reason or 'General Consultation'}\n"
            f"Phone: {clean_mobile}\n"
            f"Email: {patient.email or 'N/A'}\n"
            f"Appointment ID: {apt_code}\n"
            f"Action: Create/complete patient profile if required."
        )
        rec_icon = 'bi-person-plus-fill'
        rec_color = '#2563EB'

    create_reception_notification(
        category='APPOINTMENT',
        title=rec_title,
        message=rec_message,
        icon=rec_icon,
        color=rec_color,
        link=f"/reception/dashboard?q={apt_code}",
        patient_id=patient.id,
        reference_code=apt_code
    )

    db.session.commit()

    return {
        'success': True,
        'appointment_code': apt_code,
        'patient_name': patient.full_name,
        'patient_code': patient.patient_code,
        'patient_status': 'Existing Patient' if is_existing else 'New Patient',
        'booked_for': booked_for or 'Myself',
        'doctor_name': doctor_user.name,
        'department': dept_name,
        'appointment_date': apt_date.strftime('%A, %d %B %Y'),
        'slot_time': slot_t.strftime('%I:%M %p'),
        'message': (
            f"🎉 Your appointment is booked!\n\n"
            f"**{doctor_user.name}** — {dept_name}\n"
            f"**{apt_date.strftime('%A, %B %d, %Y')}** at **{slot_t.strftime('%I:%M %p')}**\n\n"
            f"Your appointment confirmation has been sent to your registered contact details.\n"
            f"**Appointment ID:** `{apt_code}`\n\n"
            f"Is there anything else I can help you with today?"
        )
    }
