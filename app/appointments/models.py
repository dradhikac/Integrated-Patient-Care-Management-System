from datetime import datetime, date, time, timedelta
from app.extensions import db

class DoctorAvailability(db.Model):
    __tablename__ = 'doctor_availability'

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False) # 0=Monday, 1=Tuesday ... 6=Sunday
    start_time = db.Column(db.Time, nullable=False, default=time(9, 0))
    end_time = db.Column(db.Time, nullable=False, default=time(13, 0))
    slot_duration_minutes = db.Column(db.Integer, default=15)
    is_active = db.Column(db.Boolean, default=True)

    doctor = db.relationship('User', backref='availabilities', lazy=True)

    def day_name(self):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return days[self.day_of_week] if 0 <= self.day_of_week <= 6 else "Unknown"


class Holiday(db.Model):
    __tablename__ = 'holidays'

    id = db.Column(db.Integer, primary_key=True)
    holiday_date = db.Column(db.Date, unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)


class Appointment(db.Model):
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    appointment_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False, index=True)
    slot_time = db.Column(db.Time, nullable=False)
    booking_type = db.Column(db.String(20), default='Online') # 'Walk-In', 'Online', 'Emergency'
    priority = db.Column(db.String(30), default='Regular') # 'Emergency', 'Senior Citizen', 'Pregnant Woman', 'Child', 'Regular'
    status = db.Column(db.String(30), default='BOOKED') # 'BOOKED', 'CHECKED_IN', 'COMPLETED', 'CANCELLED', 'NO_SHOW'
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', backref='appointments', lazy=True)
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='doctor_appointments', lazy=True)

    @staticmethod
    def generate_appointment_code():
        year = datetime.now().year
        last_apt = Appointment.query.order_by(Appointment.id.desc()).first()
        new_num = (last_apt.id + 1) if last_apt else 1
        return f"APT-{year}-{new_num:06d}"

    @property
    def payment_info(self):
        cns = self.consultation
        if not cns:
            from app.consultations.models import Consultation
            cns = Consultation.query.filter_by(appointment_id=self.id).first()
        
        if not cns:
            from app.consultations.models import Consultation
            cns = Consultation.query.filter(
                Consultation.patient_id == self.patient_id,
                Consultation.doctor_id == self.doctor_id,
                Consultation.created_at >= datetime.combine(self.appointment_date, datetime.min.time()),
                Consultation.created_at <= datetime.combine(self.appointment_date, datetime.max.time())
            ).first()

        if not cns:
            return {'has_consultation': False, 'status': 'NO_CONSULTATION', 'is_paid': False, 'bill': None, 'cns': None, 'balance_due': 500.0, 'grand_total': 500.0}

        from app.billing.models import Bill
        bill = Bill.query.filter_by(consultation_id=cns.id).first()
        if not bill:
            bill = Bill.query.filter(
                Bill.patient_id == cns.patient_id,
                Bill.created_at >= datetime.combine(self.appointment_date, datetime.min.time()),
                Bill.created_at <= datetime.combine(self.appointment_date, datetime.max.time())
            ).first()

        if bill:
            return {
                'has_consultation': True,
                'status': bill.status,
                'is_paid': (bill.status == 'PAID'),
                'bill': bill,
                'cns': cns,
                'grand_total': bill.grand_total,
                'paid_amount': bill.paid_amount,
                'balance_due': bill.balance_due
            }
        else:
            return {
                'has_consultation': True,
                'status': 'UNPAID',
                'is_paid': False,
                'bill': None,
                'cns': cns,
                'grand_total': 500.0,
                'paid_amount': 0.0,
                'balance_due': 500.0
            }

    @property
    def recommended_arrival_time(self):
        """Recommended reporting time (10 mins prior to expected arrival slot)."""
        if self.slot_time and self.appointment_date:
            dt = datetime.combine(self.appointment_date, self.slot_time) - timedelta(minutes=10)
            return dt.strftime('%I:%M %p')
        return None

    @property
    def arrival_window_str(self):
        """Expected arrival time window description."""
        if self.slot_time:
            return f"{self.slot_time.strftime('%I:%M %p')} (Expected Arrival)"
        return "Expected Arrival"

    @property
    def queue_info(self):
        """Dynamic queue position and wait estimation for this appointment."""
        from app.queue.queue_engine import get_doctor_live_queue
        return get_doctor_live_queue(self.doctor_id, self.appointment_date)

    def __repr__(self):
        return f"<Appointment {self.appointment_code} - {self.appointment_date} {self.slot_time}>"


class Waitlist(db.Model):
    __tablename__ = 'waitlist'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    preferred_date = db.Column(db.Date, nullable=False)
    offered_slot_time = db.Column(db.Time, nullable=True)
    status = db.Column(db.String(30), default='WAITING') # 'WAITING', 'OFFERED', 'ACCEPTED', 'DECLINED', 'EXPIRED'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', backref='waitlists', lazy=True)
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='doctor_waitlists', lazy=True)
