from datetime import datetime
from app.patients.models import Patient
from app.reception.models import CheckIn
from app.appointments.models import Appointment

def build_patient_ehr_timeline(patient_id: int, search_term: str = None, event_filter: str = 'ALL'):
    """
    Compiles a unified chronological EHR timeline for a patient.
    Aggregates Registration, OPD Check-ins, Appointments, Consultations, Prescriptions, and Lab Reports.
    
    Returns a sorted list of event dictionaries (newest first).
    """
    patient = Patient.query.get(patient_id)
    if not patient:
        return []

    events = []

    # 1. Registration Event
    events.append({
        'event_type': 'REGISTRATION',
        'title': 'Initial Patient Intake & Registration',
        'timestamp': patient.created_at or datetime.utcnow(),
        'date_str': (patient.created_at or datetime.utcnow()).strftime('%d %b %Y, %I:%M %p'),
        'badge_color': 'teal',
        'icon_class': 'bi-person-plus-fill',
        'actor': patient.registered_by.name if patient.registered_by else 'Front Desk',
        'summary': f"Registered with Code {patient.patient_code}. Baseline BMI: {patient.bmi or 'N/A'} ({patient.get_bmi_category()}).",
        'details': {
            'Blood Group': patient.blood_group or 'N/A',
            'Aadhaar Masked': patient.aadhaar_masked or 'N/A',
            'Preferred Language': patient.preferred_language or 'English',
            'Emergency Contact': f"{patient.emergency_contact_name or 'N/A'} ({patient.emergency_contact_mobile or 'N/A'})"
        }
    })

    # 2. OPD Check-Ins / Visits
    check_ins = CheckIn.query.filter_by(patient_id=patient_id).all()
    for c in check_ins:
        events.append({
            'event_type': 'CHECK_IN',
            'title': f"OPD Check-In — Token {c.token_no}",
            'timestamp': c.check_in_time,
            'date_str': c.check_in_time.strftime('%d %b %Y, %I:%M %p'),
            'badge_color': 'primary',
            'icon_class': 'bi-person-check-fill',
            'actor': c.checked_in_by.name if c.checked_in_by else 'Receptionist',
            'summary': f"Department: {c.department} | Assigned Doctor: {c.doctor.name} | Status: {c.status}",
            'details': {
                'Token No': c.token_no,
                'Department': c.department,
                'Assigned Doctor': c.doctor.name,
                'Priority Tier': c.priority,
                'Status': c.status,
                'Check-In Time': c.check_in_time.strftime('%I:%M %p')
            }
        })

    # 3. Appointments
    appointments = Appointment.query.filter_by(patient_id=patient_id).all()
    for apt in appointments:
        apt_dt = datetime.combine(apt.appointment_date, apt.slot_time)
        events.append({
            'event_type': 'APPOINTMENT',
            'title': f"Appointment Scheduled — {apt.appointment_code}",
            'timestamp': apt_dt,
            'date_str': apt_dt.strftime('%d %b %Y, %I:%M %p'),
            'badge_color': 'info',
            'icon_class': 'bi-calendar-event-fill',
            'actor': apt.doctor.name if apt.doctor else 'Doctor',
            'summary': f"Doctor: {apt.doctor.name} | Booking Channel: {apt.booking_type} | Status: {apt.status}",
            'details': {
                'Appointment Code': apt.appointment_code,
                'Doctor': apt.doctor.name,
                'Booking Type': apt.booking_type,
                'Status': apt.status,
                'Notes': apt.notes or 'None'
            }
        })

    # 4. Clinical Consultations & Vitals
    from app.consultations.models import Consultation
    consultations = Consultation.query.filter_by(patient_id=patient_id).all()
    for cns in consultations:
        vitals_summary = cns.vital.get_vitals_summary() if cns.vital else "Vitals not recorded"
        events.append({
            'event_type': 'CONSULTATION',
            'title': f"Clinical Consultation — {cns.consultation_code}",
            'timestamp': cns.created_at,
            'date_str': cns.created_at.strftime('%d %b %Y, %I:%M %p'),
            'badge_color': 'success',
            'icon_class': 'bi-stethoscope',
            'actor': cns.doctor.name,
            'summary': f"Diagnosis: {cns.diagnosis} | Symptoms: {cns.symptoms[:60]}...",
            'details': {
                'Consultation Code': cns.consultation_code,
                'Doctor': cns.doctor.name,
                'Symptoms': cns.symptoms,
                'Diagnosis': cns.diagnosis,
                'Vitals': vitals_summary,
                'Treatment Plan': cns.treatment_plan or 'None'
            }
        })

    # 5. Digital Prescriptions
    from app.prescriptions.models import Prescription
    prescriptions = Prescription.query.filter_by(patient_id=patient_id).all()
    for rx in prescriptions:
        med_summary = ", ".join([f"{item.medicine_name} ({item.frequency})" for item in rx.items])
        events.append({
            'event_type': 'PRESCRIPTION',
            'title': f"Digital Prescription Issued — {rx.prescription_code}",
            'timestamp': rx.created_at,
            'date_str': rx.created_at.strftime('%d %b %Y, %I:%M %p'),
            'badge_color': 'primary',
            'icon_class': 'bi-capsule',
            'actor': rx.doctor.name,
            'summary': f"Prescribed ({len(rx.items)} meds): {med_summary[:80]}...",
            'details': {
                'Prescription Code': rx.prescription_code,
                'Doctor': rx.doctor.name,
                'Medicines': med_summary,
                'General Advice': rx.general_advice or 'None'
            }
        })

    # Filter by Event Type if specified
    if event_filter and event_filter != 'ALL':
        events = [e for e in events if e['event_type'] == event_filter]

    # Search filter across title, summary, actor, details
    if search_term:
        term = search_term.strip().lower()
        filtered = []
        for e in events:
            blob = f"{e['title']} {e['summary']} {e['actor']} {str(e['details'])}".lower()
            if term in blob:
                filtered.append(e)
        events = filtered

    # Sort newest events first
    events.sort(key=lambda x: x['timestamp'], reverse=True)

    return events
