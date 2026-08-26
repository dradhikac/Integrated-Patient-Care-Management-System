from datetime import datetime
from app.extensions import db

class Consultation(db.Model):
    __tablename__ = 'consultations'

    id = db.Column(db.Integer, primary_key=True)
    consultation_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    check_in_id = db.Column(db.Integer, db.ForeignKey('check_ins.id'), nullable=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=True)
    
    symptoms = db.Column(db.Text, nullable=False)
    diagnosis = db.Column(db.Text, nullable=False)
    treatment_plan = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Relationships
    patient = db.relationship('Patient', backref='consultations', lazy=True)
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='doctor_consultations', lazy=True)
    check_in = db.relationship('CheckIn', backref='consultation', uselist=False, lazy=True)
    appointment = db.relationship('Appointment', foreign_keys=[appointment_id], backref=db.backref('consultation', uselist=False), lazy=True)
    vital = db.relationship('Vital', backref='consultation', uselist=False, cascade='all, delete-orphan', lazy=True)

    @property
    def actual_duration_minutes(self):
        """Calculates actual consultation duration in minutes from real timestamps."""
        st = self.started_at
        et = self.completed_at or self.created_at
        if not st and self.check_in and self.check_in.called_time:
            st = self.check_in.called_time
        if st and et:
            return max(1.0, round((et - st).total_seconds() / 60.0, 1))
        return None

    @staticmethod
    def generate_consultation_code():
        year = datetime.now().year
        last_cns = Consultation.query.order_by(Consultation.id.desc()).first()
        new_num = (last_cns.id + 1) if last_cns else 1
        return f"CNS-{year}-{new_num:06d}"

    def __repr__(self):
        return f"<Consultation {self.consultation_code} - Patient {self.patient_id}>"


class Vital(db.Model):
    __tablename__ = 'vitals'

    id = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultations.id'), nullable=False)
    bp_systolic = db.Column(db.Integer, nullable=True) # e.g. 120
    bp_diastolic = db.Column(db.Integer, nullable=True) # e.g. 80
    temperature_f = db.Column(db.Float, nullable=True) # e.g. 98.6
    pulse_bpm = db.Column(db.Integer, nullable=True) # e.g. 72
    spo2_percent = db.Column(db.Integer, nullable=True) # e.g. 98
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_bp_string(self):
        if self.bp_systolic and self.bp_diastolic:
            return f"{self.bp_systolic}/{self.bp_diastolic} mmHg"
        return "N/A"

    def get_vitals_summary(self):
        return f"BP: {self.get_bp_string()} | Temp: {self.temperature_f or 'N/A'}°F | Pulse: {self.pulse_bpm or 'N/A'} bpm | SpO2: {self.spo2_percent or 'N/A'}%"
