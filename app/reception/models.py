from datetime import datetime, date
from app.extensions import db

class CheckIn(db.Model):
    __tablename__ = 'check_ins'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token_no = db.Column(db.String(20), nullable=False, index=True)
    department = db.Column(db.String(50), default='General OPD')
    status = db.Column(db.String(20), default='WAITING') # WAITING, IN_CONSULTATION, COMPLETED, NO_SHOW, CANCELLED
    priority = db.Column(db.String(20), default='Regular') # Emergency, Senior Citizen, Pregnant Woman, Child, Regular
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    called_time = db.Column(db.DateTime, nullable=True)
    completed_time = db.Column(db.DateTime, nullable=True)
    checked_in_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Relationships
    patient = db.relationship('Patient', backref='check_ins', lazy=True)
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='assigned_check_ins', lazy=True)
    checked_in_by = db.relationship('User', foreign_keys=[checked_in_by_id], backref='processed_check_ins', lazy=True)

    @staticmethod
    def generate_token_number():
        """Generates sequential token for today e.g. TK-001, TK-002"""
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_count = CheckIn.query.filter(
            (CheckIn.check_in_time >= today_start) | (CheckIn.check_in_time.is_(None))
        ).count()
        return f"TK-{(today_count + 1):03d}"

    def estimated_wait_minutes(self):
        """Calculates estimated wait time in minutes based on patients ahead in queue for the same doctor"""
        patients_ahead = CheckIn.query.filter(
            CheckIn.doctor_id == self.doctor_id,
            CheckIn.status == 'WAITING',
            CheckIn.id < self.id
        ).count()
        avg_consult_minutes = 10
        return max(5, patients_ahead * avg_consult_minutes)

    def __repr__(self):
        return f"<CheckIn {self.token_no} - Patient {self.patient_id} -> Doctor {self.doctor_id}>"
