import csv
import io
from datetime import datetime, timedelta
from app.extensions import db
from app.patients.models import Patient
from app.reception.models import CheckIn
from app.appointments.models import Appointment
from app.consultations.models import Consultation
from app.prescriptions.models import Prescription, PrescriptionItem
from app.lab.models import LabRequest, LabResult
from app.billing.models import Bill, BillItem, Payment
from app.beds.models import Ward, Bed, Admission

def get_hospital_analytics_summary():
    """
    Compiles executive-level KPIs across all hospital departments.
    """
    # 1. Patient Demographics KPIs
    total_patients = Patient.query.count()
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    new_patients_30d = Patient.query.filter(Patient.created_at >= thirty_days_ago).count()

    # 2. Financial & Revenue KPIs
    all_bills = Bill.query.all()
    total_billed = sum(b.grand_total for b in all_bills)
    total_collected = sum(b.paid_amount for b in all_bills)
    total_pending = sum(b.balance_due for b in all_bills)

    # Departmental Revenue Breakdown
    consultation_rev = db.session.query(db.func.sum(BillItem.total_price)).filter(BillItem.item_type == 'CONSULTATION').scalar() or 0.0
    medicine_rev = db.session.query(db.func.sum(BillItem.total_price)).filter(BillItem.item_type == 'MEDICINE').scalar() or 0.0
    lab_rev = db.session.query(db.func.sum(BillItem.total_price)).filter(BillItem.item_type == 'LAB_TEST').scalar() or 0.0

    # 3. Clinical & OPD Volume KPIs
    total_checkins = CheckIn.query.count()
    completed_checkins = CheckIn.query.filter_by(status='COMPLETED').count()
    total_consultations = Consultation.query.count()
    total_prescriptions = Prescription.query.count()
    total_lab_requests = LabRequest.query.count()

    # 4. Bed Occupancy & IPD Capacity KPIs
    total_beds = Bed.query.count()
    occupied_beds = Bed.query.filter_by(status='OCCUPIED').count()
    occupancy_rate = (occupied_beds / total_beds * 100.0) if total_beds > 0 else 0.0
    active_admissions = Admission.query.filter_by(status='ADMITTED').count()

    # 5. Top Prescribed Medicines
    top_meds_query = db.session.query(
        PrescriptionItem.medicine_name,
        db.func.count(PrescriptionItem.id).label('med_count')
    ).group_by(PrescriptionItem.medicine_name).order_by(db.desc('med_count')).limit(5).all()

    top_meds = [{'name': name, 'count': count} for name, count in top_meds_query]

    return {
        'total_patients': total_patients,
        'new_patients_30d': new_patients_30d,
        'total_billed': total_billed,
        'total_collected': total_collected,
        'total_pending': total_pending,
        'consultation_rev': consultation_rev,
        'medicine_rev': medicine_rev,
        'lab_rev': lab_rev,
        'total_checkins': total_checkins,
        'completed_checkins': completed_checkins,
        'total_consultations': total_consultations,
        'total_prescriptions': total_prescriptions,
        'total_lab_requests': total_lab_requests,
        'total_beds': total_beds,
        'occupied_beds': occupied_beds,
        'occupancy_rate': round(occupancy_rate, 1),
        'active_admissions': active_admissions,
        'top_meds': top_meds
    }


def generate_invoices_csv_report():
    """Generates CSV stream for hospital billing invoices."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Invoice Code', 'Patient Code', 'Patient Name', 'Billed Date', 'Subtotal', 'Discount', 'Tax Amount', 'Grand Total', 'Paid Amount', 'Balance Due', 'Status'])

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

    output.seek(0)
    return output.getvalue()


def generate_patients_csv_report():
    """Generates CSV stream for patient registry."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Patient Code', 'Full Name', 'Gender', 'DOB', 'Mobile', 'Blood Group', 'Aadhaar Masked', 'Insurance Provider', 'Registered Date'])

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

    output.seek(0)
    return output.getvalue()
