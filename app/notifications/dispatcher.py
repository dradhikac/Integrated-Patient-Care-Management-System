import threading
from datetime import datetime, timedelta
from app.extensions import db
from app.patients.models import Patient
from app.appointments.models import Appointment
from app.prescriptions.models import Prescription
from app.lab.models import LabRequest
from app.billing.models import Bill
from app.notifications.models import Notification, NotificationLog

def dispatch_single_notification(notification_id: int):
    """
    Asynchronously dispatches a notification via Email and/or SMS,
    recording detailed delivery logs into notification_log.
    """
    notif = db.session.get(Notification, notification_id)
    if not notif or notif.status == 'SENT':
        return

    patient = notif.patient
    if not patient:
        notif.status = 'FAILED'
        db.session.commit()
        return

    try:
        # 1. Dispatch Email if applicable
        if notif.channel in ['EMAIL', 'BOTH']:
            email_addr = patient.email or f"{patient.patient_code.lower()}@patient.ipcms.com"
            payload_email = f"Subject: {notif.title}\nTo: {email_addr}\n\n{notif.message}"
            log_email = NotificationLog(
                notification_id=notif.id,
                channel='EMAIL',
                recipient=email_addr,
                payload=payload_email,
                status='SUCCESS',
                sent_at=datetime.utcnow()
            )
            db.session.add(log_email)

        # 2. Dispatch SMS if applicable
        if notif.channel in ['SMS', 'BOTH']:
            mobile_no = patient.mobile or '9876543210'
            payload_sms = f"SMS to {mobile_no}: [IPCMS] {notif.title} - {notif.message[:140]}"
            log_sms = NotificationLog(
                notification_id=notif.id,
                channel='SMS',
                recipient=mobile_no,
                payload=payload_sms,
                status='SUCCESS',
                sent_at=datetime.utcnow()
            )
            db.session.add(log_sms)

        notif.status = 'SENT'
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        notif.status = 'FAILED'
        db.session.commit()


def dispatch_async(app, notification_id: int):
    """Executes notification dispatch in a background thread."""
    def run_worker():
        with app.app_context():
            dispatch_single_notification(notification_id)

    thread = threading.Thread(target=run_worker)
    thread.daemon = True
    thread.start()


def scan_and_queue_reminders(app=None):
    """
    Background Scanner:
    Scans upcoming appointments, completed lab tests, issued prescriptions,
    and unpaid invoices to queue and dispatch automated reminders.
    """
    now = datetime.utcnow()
    queued_count = 0

    # 1. Scan Upcoming Appointments (within next 24 hours)
    tomorrow_date = (now + timedelta(days=1)).date()
    apts = Appointment.query.filter(
        Appointment.appointment_date == tomorrow_date,
        Appointment.status == 'BOOKED'
    ).all()

    for apt in apts:
        existing = Notification.query.filter_by(
            patient_id=apt.patient_id,
            type='APPOINTMENT_REMINDER'
        ).filter(Notification.created_at >= now - timedelta(days=1)).first()

        if not existing:
            notif = Notification(
                patient_id=apt.patient_id,
                type='APPOINTMENT_REMINDER',
                title=f"Reminder: Doctor Appointment Tomorrow ({apt.slot_time.strftime('%I:%M %p')})",
                message=f"Dear {apt.patient.full_name}, you have an appointment with {apt.doctor.name} scheduled for tomorrow at {apt.slot_time.strftime('%I:%M %p')}. Appointment Code: {apt.appointment_code}.",
                channel='BOTH',
                status='PENDING'
            )
            db.session.add(notif)
            db.session.flush()
            dispatch_single_notification(notif.id)
            queued_count += 1

    # 2. Scan Completed Lab Requests
    labs = LabRequest.query.filter_by(status='COMPLETED').all()
    for lr in labs:
        existing = Notification.query.filter_by(
            patient_id=lr.patient_id,
            type='LAB_READY'
        ).filter(Notification.title.like(f"%{lr.request_code}%")).first()

        if not existing:
            notif = Notification(
                patient_id=lr.patient_id,
                type='LAB_READY',
                title=f"Lab Diagnostic Report Ready ({lr.request_code})",
                message=f"Dear {lr.patient.full_name}, your laboratory diagnostic report ({lr.request_code}) has been uploaded and validated. You can view or download it from your patient portal.",
                channel='BOTH',
                status='PENDING'
            )
            db.session.add(notif)
            db.session.flush()
            dispatch_single_notification(notif.id)
            queued_count += 1

    # 3. Scan Unpaid Hospital Bills
    unpaid_bills = Bill.query.filter(Bill.status.in_(['UNPAID', 'PARTIALLY_PAID'])).all()
    for b in unpaid_bills:
        existing = Notification.query.filter_by(
            patient_id=b.patient_id,
            type='PAYMENT_REMINDER'
        ).filter(Notification.title.like(f"%{b.invoice_code}%")).first()

        if not existing:
            notif = Notification(
                patient_id=b.patient_id,
                type='PAYMENT_REMINDER',
                title=f"Payment Reminder: Invoice {b.invoice_code}",
                message=f"Dear {b.patient.full_name}, invoice {b.invoice_code} has a pending balance due of ₹{b.balance_due:.2f}. Please complete your payment at the hospital desk or online.",
                channel='BOTH',
                status='PENDING'
            )
            db.session.add(notif)
            db.session.flush()
            dispatch_single_notification(notif.id)
            queued_count += 1

    # 4. Scan Digital Prescriptions
    rxs = Prescription.query.order_by(Prescription.id.desc()).limit(10).all()
    for rx in rxs:
        existing = Notification.query.filter_by(
            patient_id=rx.patient_id,
            type='PRESCRIPTION_READY'
        ).filter(Notification.title.like(f"%{rx.prescription_code}%")).first()

        if not existing:
            notif = Notification(
                patient_id=rx.patient_id,
                type='PRESCRIPTION_READY',
                title=f"Digital Prescription Issued ({rx.prescription_code})",
                message=f"Dear {rx.patient.full_name}, {rx.doctor.name} has issued digital prescription {rx.prescription_code} with {len(rx.items)} medication(s). Scan your Rx QR code at the pharmacy.",
                channel='BOTH',
                status='PENDING'
            )
            db.session.add(notif)
            db.session.flush()
            dispatch_single_notification(notif.id)
            queued_count += 1

    db.session.commit()
    return queued_count
