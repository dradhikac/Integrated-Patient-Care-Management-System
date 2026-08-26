from datetime import datetime, date, timedelta
from app.extensions import db
from app.notifications.models import StaffNotification
from app.reception.models import CheckIn
from app.appointments.models import Appointment
from app.patients.models import Patient
from app.consultations.models import Consultation
from app.billing.models import Bill

CATEGORY_CONFIG = {
    'CHECK_IN': {
        'icon': 'bi-person-check-fill',
        'color': '#2563EB', # Blue
        'default_title': 'Patient Checked In'
    },
    'QUEUE': {
        'icon': 'bi-hourglass-split',
        'color': '#F59E0B', # Amber
        'default_title': 'Patient Waiting in Queue'
    },
    'APPOINTMENT': {
        'icon': 'bi-calendar-check-fill',
        'color': '#8B5CF6', # Purple
        'default_title': 'Appointment Update'
    },
    'PATIENT': {
        'icon': 'bi-person-plus-fill',
        'color': '#10B981', # Emerald Green
        'default_title': 'New Patient Registration'
    },
    'PAYMENT': {
        'icon': 'bi-credit-card-fill',
        'color': '#D97706', # Warm Amber/Gold
        'default_title': 'Payment Status'
    },
    'EMERGENCY': {
        'icon': 'bi-exclamation-octagon-fill',
        'color': '#EF4444', # Red
        'default_title': 'Emergency Alert'
    }
}


def create_reception_notification(category: str, title: str, message: str,
                                 icon: str = None, color: str = None,
                                 link: str = None, patient_id: int = None,
                                 reference_code: str = None, is_read: bool = False,
                                 created_at: datetime = None) -> StaffNotification:
    """Creates a role-targeted receptionist operational notification."""
    config = CATEGORY_CONFIG.get(category, {
        'icon': 'bi-bell-fill',
        'color': '#2563EB',
        'default_title': 'Operational Notification'
    })

    notif = StaffNotification(
        role_target='Receptionist',
        category=category,
        title=title or config['default_title'],
        message=message,
        icon=icon or config['icon'],
        color=color or config['color'],
        link=link or '/reception/dashboard',
        patient_id=patient_id,
        reference_code=reference_code,
        is_read=is_read,
        created_at=created_at or datetime.now()
    )
    db.session.add(notif)
    db.session.commit()
    return notif


def get_reception_unread_count() -> int:
    """Returns number of unread notifications for Receptionist."""
    sync_reception_operational_events()
    return StaffNotification.query.filter_by(
        role_target='Receptionist',
        is_read=False
    ).count()


def get_reception_notifications(limit: int = 15, unread_only: bool = False,
                                category: str = None, search: str = None):
    """Fetches receptionist notifications with optional filtering."""
    sync_reception_operational_events()
    query = StaffNotification.query.filter_by(role_target='Receptionist')

    if unread_only:
        query = query.filter_by(is_read=False)

    if category and category.upper() != 'ALL':
        query = query.filter(StaffNotification.category.ilike(category))

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (StaffNotification.title.ilike(s)) |
            (StaffNotification.message.ilike(s)) |
            (StaffNotification.reference_code.ilike(s))
        )

    query = query.order_by(StaffNotification.created_at.desc())
    if limit:
        return query.limit(limit).all()
    return query.all()


def mark_reception_notification_read(notif_id: int) -> bool:
    """Marks a single receptionist notification as read."""
    notif = StaffNotification.query.filter_by(
        id=notif_id,
        role_target='Receptionist'
    ).first()
    if notif:
        notif.is_read = True
        db.session.commit()
        return True
    return False


def mark_all_reception_notifications_read() -> int:
    """Marks all unread receptionist notifications as read."""
    updated = StaffNotification.query.filter_by(
        role_target='Receptionist',
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    return updated


def sync_reception_operational_events():
    """
    Syncs today's live operational events into receptionist notifications if they don't already exist.
    Ensures real-time front desk events (Check-ins, Queue, Appointments, Registrations, Payments)
    are always reflected in the receptionist bell dropdown without any administrative clutter.
    """
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())

    # 1. Today's Check-ins
    today_checkins = CheckIn.query.filter(
        CheckIn.check_in_time >= today_start
    ).order_by(CheckIn.check_in_time.asc()).all()

    for chk in today_checkins:
        ref_code = f"CHK-{chk.id}"
        exists = StaffNotification.query.filter_by(
            role_target='Receptionist',
            reference_code=ref_code
        ).first()

        if not exists and chk.patient and chk.doctor:
            if chk.priority == 'Emergency':
                cat = 'EMERGENCY'
                title = 'Emergency Walk-In Token Issued'
                msg = f"{chk.patient.full_name} issued Emergency token {chk.token_no} for Dr. {chk.doctor.name}."
                icon = 'bi-exclamation-octagon-fill'
                color = '#EF4444'
            else:
                cat = 'CHECK_IN'
                title = 'New Patient Checked In'
                msg = f"{chk.patient.full_name} has checked in for Dr. {chk.doctor.name} (Token {chk.token_no})."
                icon = 'bi-person-check-fill'
                color = '#2563EB'

            notif = StaffNotification(
                role_target='Receptionist',
                category=cat,
                title=title,
                message=msg,
                icon=icon,
                color=color,
                link=f"/reception/dashboard#checkInDesk",
                patient_id=chk.patient_id,
                reference_code=ref_code,
                is_read=False,
                created_at=chk.check_in_time or datetime.now()
            )
            db.session.add(notif)

    # 2. Today's Appointments Booked / Updated
    today_apts = Appointment.query.filter(
        Appointment.appointment_date == today
    ).order_by(Appointment.created_at.asc()).all()

    for apt in today_apts:
        ref_code = f"APT-{apt.id}"
        exists = StaffNotification.query.filter_by(
            role_target='Receptionist',
            reference_code=ref_code
        ).first()

        if not exists and apt.patient and apt.doctor:
            title = 'Appointment Scheduled'
            msg = f"{apt.patient.full_name} scheduled for Dr. {apt.doctor.name} at {apt.slot_time.strftime('%I:%M %p')} ({apt.appointment_code})."
            notif = StaffNotification(
                role_target='Receptionist',
                category='APPOINTMENT',
                title=title,
                message=msg,
                icon='bi-calendar-check-fill',
                color='#8B5CF6',
                link=f"/reception/appointments",
                patient_id=apt.patient_id,
                reference_code=ref_code,
                is_read=False,
                created_at=apt.created_at or datetime.now()
            )
            db.session.add(notif)

    # 3. New Patients Registered Today
    today_patients = Patient.query.filter(
        Patient.created_at >= today_start
    ).all()

    for p in today_patients:
        ref_code = f"PAT-REG-{p.id}"
        exists = StaffNotification.query.filter_by(
            role_target='Receptionist',
            reference_code=ref_code
        ).first()

        if not exists:
            notif = StaffNotification(
                role_target='Receptionist',
                category='PATIENT',
                title='New Patient Registered',
                message=f"{p.full_name} (UHID: {p.patient_code}) was registered at front desk.",
                icon='bi-person-plus-fill',
                color='#10B981',
                link=f"/reception/patients/{p.id}",
                patient_id=p.id,
                reference_code=ref_code,
                is_read=False,
                created_at=p.created_at or datetime.now()
            )
            db.session.add(notif)

    # 4. Completed Consultations with Pending Payment
    today_consultations = Consultation.query.filter(
        Consultation.created_at >= today_start
    ).all()

    for cns in today_consultations:
        ref_code = f"CNS-PAY-{cns.id}"
        exists = StaffNotification.query.filter_by(
            role_target='Receptionist',
            reference_code=ref_code
        ).first()

        if not exists and cns.patient and cns.doctor:
            notif = StaffNotification(
                role_target='Receptionist',
                category='PAYMENT',
                title='Consultation Completed · Billing Ready',
                message=f"Dr. {cns.doctor.name} completed visit for {cns.patient.full_name}. Collect consultation fee.",
                icon='bi-credit-card-fill',
                color='#D97706',
                link=f"/reception/dashboard#billingDesk",
                patient_id=cns.patient_id,
                reference_code=ref_code,
                is_read=False,
                created_at=cns.completed_at or cns.created_at or datetime.now()
            )
            db.session.add(notif)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
