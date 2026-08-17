from datetime import datetime, date, timedelta
from sqlalchemy import func
from app.extensions import db
from app.auth.models import User, Role
from app.patients.models import Patient
from app.reception.models import CheckIn
from app.appointments.models import Appointment, DoctorAvailability
from app.consultations.models import Consultation
from app.prescriptions.models import Prescription
from app.lab.models import LabRequest, LabResult
from app.billing.models import Bill, BillItem, Payment

def get_today_admin_kpis():
    """
    Calculates real-time today's KPI metrics for the Admin Dashboard:
    - Patients Today
    - Revenue Today (₹)
    - Doctors Available Today
    - Appointments Today
    - Emergency Cases Today
    """
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # 1. Patients Registered Today
    patients_today = Patient.query.filter(
        Patient.created_at >= today_start,
        Patient.created_at <= today_end
    ).count()

    # 2. Revenue Today (Sum of payments recorded today + bills generated today)
    payments_today_sum = db.session.query(func.sum(Payment.amount_paid)).filter(
        Payment.paid_at >= today_start,
        Payment.paid_at <= today_end
    ).scalar() or 0.0

    bills_today_sum = db.session.query(func.sum(Bill.grand_total)).filter(
        Bill.created_at >= today_start,
        Bill.created_at <= today_end
    ).scalar() or 0.0

    revenue_today = max(payments_today_sum, bills_today_sum)

    # 3. Doctors Available Today
    avail_doc_ids = db.session.query(DoctorAvailability.doctor_id).filter(
        DoctorAvailability.day_of_week == today.weekday(),
        DoctorAvailability.is_active == True
    ).distinct().all()
    
    doctors_available = len(avail_doc_ids) if avail_doc_ids else User.query.join(Role).filter(Role.name == 'Doctor').count()

    # 4. Appointments Today
    appointments_today = Appointment.query.filter(
        Appointment.appointment_date == today,
        Appointment.status != 'CANCELLED'
    ).count()

    # 5. Emergency Cases Today (Priority='Emergency' or Booking Channel='Emergency')
    emergency_apts = Appointment.query.filter(
        Appointment.appointment_date == today,
        (Appointment.priority == 'Emergency') | (Appointment.booking_type == 'Emergency')
    ).count()

    emergency_checkins = CheckIn.query.filter(
        CheckIn.check_in_time >= today_start,
        CheckIn.priority == 'Emergency'
    ).count()

    emergency_cases_today = emergency_apts + emergency_checkins

    return {
        'patients_today': patients_today,
        'revenue_today': revenue_today,
        'doctors_available': doctors_available,
        'appointments_today': appointments_today,
        'emergency_cases_today': emergency_cases_today
    }


def get_monthly_revenue_trend():
    """
    Plain SQL aggregation:
    Aggregates historical billing data (`Bill.grand_total`) grouped by Month
    for Chart.js line chart visualization.
    """
    bills = Bill.query.order_by(Bill.created_at.asc()).all()

    monthly_map = {}
    for b in bills:
        month_str = b.created_at.strftime('%b %Y')
        monthly_map[month_str] = monthly_map.get(month_str, 0.0) + b.grand_total

    if not monthly_map:
        current_month = datetime.utcnow().strftime('%b %Y')
        monthly_map = {current_month: 0.0}

    labels = list(monthly_map.keys())
    values = [round(v, 2) for v in monthly_map.values()]

    return {
        'labels': labels,
        'amounts': values
    }


def get_appointment_status_breakdown():
    """
    Counts appointments grouped by status for Chart.js doughnut chart.
    """
    statuses = ['BOOKED', 'CHECKED_IN', 'COMPLETED', 'CANCELLED']
    breakdown = {}
    for st in statuses:
        breakdown[st] = Appointment.query.filter_by(status=st).count()

    return breakdown


def get_departmental_revenue_share():
    """
    Aggregates revenue totals grouped by BillItem item_type for bar chart.
    """
    cns_rev = db.session.query(func.sum(BillItem.total_price)).filter(BillItem.item_type == 'CONSULTATION').scalar() or 0.0
    med_rev = db.session.query(func.sum(BillItem.total_price)).filter(BillItem.item_type == 'MEDICINE').scalar() or 0.0
    lab_rev = db.session.query(func.sum(BillItem.total_price)).filter(BillItem.item_type == 'LAB_TEST').scalar() or 0.0

    return {
        'labels': ['OPD Consultations', 'Pharmacy Medicines', 'Lab Diagnostics'],
        'values': [round(cns_rev, 2), round(med_rev, 2), round(lab_rev, 2)]
    }
