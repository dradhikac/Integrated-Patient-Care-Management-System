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

    # 6. Laboratory Investigations & Diagnostics
    from app.lab.models import LabRequest
    lab_requests = LabRequest.query.filter_by(patient_id=patient_id).all()
    for lreq in lab_requests:
        test_names = ", ".join([res.test_type.test_name for res in lreq.results])
        events.append({
            'event_type': 'LAB_TEST',
            'title': f"Laboratory Investigation — {lreq.request_code}",
            'timestamp': lreq.created_at,
            'date_str': lreq.created_at.strftime('%d %b %Y, %I:%M %p'),
            'badge_color': 'warning',
            'icon_class': 'bi-flask',
            'actor': lreq.doctor.name,
            'summary': f"Tests ({len(lreq.results)}): {test_names} | Status: {lreq.status}",
            'details': {
                'Lab Request Code': lreq.request_code,
                'Ordering Doctor': lreq.doctor.name,
                'Ordered Tests': test_names,
                'Status': lreq.status,
                'Clinical Notes': lreq.clinical_notes or 'None'
            }
        })

    # 7. Billing & Financial Invoices
    from app.billing.models import Bill
    bills = Bill.query.filter_by(patient_id=patient_id).all()
    for b in bills:
        events.append({
            'event_type': 'BILLING',
            'title': f"Hospital Tax Invoice Generated — {b.invoice_code}",
            'timestamp': b.created_at,
            'date_str': b.created_at.strftime('%d %b %Y, %I:%M %p'),
            'badge_color': 'secondary',
            'icon_class': 'bi-receipt',
            'actor': 'Hospital Billing Desk',
            'summary': f"Grand Total: ₹{b.grand_total:.2f} | Paid: ₹{b.paid_amount:.2f} | Status: {b.status}",
            'details': {
                'Invoice Code': b.invoice_code,
                'Grand Total': f"₹{b.grand_total:.2f}",
                'Paid Amount': f"₹{b.paid_amount:.2f}",
                'Balance Due': f"₹{b.balance_due:.2f}",
                'Status': b.status
            }
        })

    # 8. Inpatient Admissions & Discharges
    from app.beds.models import Admission
    admissions = Admission.query.filter_by(patient_id=patient_id).all()
    for adm in admissions:
        events.append({
            'event_type': 'INPATIENT',
            'title': f"Inpatient Admission (IPD) — {adm.admission_code}",
            'timestamp': adm.admitted_at,
            'date_str': adm.admitted_at.strftime('%d %b %Y, %I:%M %p'),
            'badge_color': 'danger',
            'icon_class': 'bi-hospital',
            'actor': adm.doctor.name,
            'summary': f"Admitted to {adm.bed.ward.ward_name} ({adm.bed.bed_code}) | Diagnosis: {adm.diagnosis[:60]}...",
            'details': {
                'Admission Code': adm.admission_code,
                'Admitting Doctor': adm.doctor.name,
                'Allocated Bed': f"{adm.bed.bed_code} ({adm.bed.ward.ward_name})",
                'Diagnosis': adm.diagnosis,
                'Status': adm.status
            }
        })

    # 9. Dispatched Notifications & Reminders
    from app.notifications.models import Notification
    notifications = Notification.query.filter_by(patient_id=patient_id).all()
    for n in notifications:
        events.append({
            'event_type': 'NOTIFICATION',
            'title': f"Notification Dispatched — {n.title}",
            'timestamp': n.created_at,
            'date_str': n.created_at.strftime('%d %b %Y, %I:%M %p'),
            'badge_color': 'info',
            'icon_class': 'bi-bell-fill',
            'actor': 'Notification Dispatcher System',
            'summary': f"Category: {n.type} | Channel: {n.channel} | Status: {n.status}",
            'details': {
                'Subject': n.title,
                'Message Body': n.message,
                'Channel': n.channel,
                'Status': n.status
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
