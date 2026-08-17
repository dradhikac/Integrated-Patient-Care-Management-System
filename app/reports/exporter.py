import csv
import io
from datetime import datetime
from app.extensions import db
from app.auth.models import User, Role
from app.patients.models import Patient
from app.appointments.models import Appointment
from app.consultations.models import Consultation
from app.lab.models import LabRequest, LabResult
from app.billing.models import Bill, BillItem

def generate_csv_report(report_type: str):
    """
    Generates CSV export file streams for the 5 hospital reports:
    - patient
    - revenue
    - doctor
    - appointment
    - lab
    """
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == 'patient':
        writer.writerow(['Patient Code', 'Full Name', 'Gender', 'DOB', 'Mobile', 'Blood Group', 'Aadhaar Masked', 'Insurance Provider', 'Intake Date'])
        patients = Patient.query.order_by(Patient.id.desc()).all()
        for p in patients:
            writer.writerow([
                p.patient_code,
                p.full_name,
                p.gender,
                p.dob.strftime('%Y-%m-%d') if p.dob else '',
                p.mobile,
                p.blood_group or '',
                p.aadhaar_masked or '',
                p.insurance_provider or '',
                p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else ''
            ])

    elif report_type == 'revenue':
        writer.writerow(['Invoice Code', 'Patient Code', 'Patient Name', 'Billed Date', 'Subtotal (₹)', 'Discount (₹)', 'Tax (₹)', 'Grand Total (₹)', 'Paid Amount (₹)', 'Balance Due (₹)', 'Status'])
        bills = Bill.query.order_by(Bill.id.desc()).all()
        for b in bills:
            writer.writerow([
                b.invoice_code,
                b.patient.patient_code,
                b.patient.full_name,
                b.created_at.strftime('%Y-%m-%d %H:%M'),
                f"{b.subtotal:.2f}",
                f"{b.discount:.2f}",
                f"{b.tax_amount:.2f}",
                f"{b.grand_total:.2f}",
                f"{b.paid_amount:.2f}",
                f"{b.balance_due:.2f}",
                b.status
            ])

    elif report_type == 'doctor':
        writer.writerow(['Doctor Code', 'Doctor Name', 'Email', 'Consultations Conducted', 'Appointments Handled', 'Status'])
        doc_role = Role.query.filter_by(name='Doctor').first()
        doctors = User.query.filter_by(role_id=doc_role.id).all() if doc_role else []
        for d in doctors:
            cns_count = Consultation.query.filter_by(doctor_id=d.id).count()
            apt_count = Appointment.query.filter_by(doctor_id=d.id).count()
            writer.writerow([
                d.user_code,
                d.name,
                d.email,
                cns_count,
                apt_count,
                'Active' if d.is_active else 'Inactive'
            ])

    elif report_type == 'appointment':
        writer.writerow(['Appointment Code', 'Patient Code', 'Patient Name', 'Doctor Name', 'Date', 'Time Slot', 'Priority', 'Channel', 'Status'])
        appointments = Appointment.query.order_by(Appointment.id.desc()).all()
        for apt in appointments:
            writer.writerow([
                apt.appointment_code,
                apt.patient.patient_code,
                apt.patient.full_name,
                apt.doctor.name,
                apt.appointment_date.strftime('%Y-%m-%d'),
                apt.slot_time.strftime('%I:%M %p'),
                getattr(apt, 'priority', 'Regular'),
                apt.booking_type,
                apt.status
            ])

    elif report_type == 'lab':
        writer.writerow(['Lab Request Code', 'Patient Name', 'Ordering Doctor', 'Tests Requested', 'Request Date', 'Status'])
        labs = LabRequest.query.order_by(LabRequest.id.desc()).all()
        for lr in labs:
            test_names = ", ".join([res.test_type.test_name for res in lr.results])
            writer.writerow([
                lr.request_code,
                lr.patient.full_name,
                lr.doctor.name,
                test_names,
                lr.created_at.strftime('%Y-%m-%d %H:%M'),
                lr.status
            ])

    output.seek(0)
    return output.getvalue()
