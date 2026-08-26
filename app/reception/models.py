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
    check_in_time = db.Column(db.DateTime, default=datetime.now)
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

    @property
    def actual_duration_minutes(self):
        """Calculates actual consultation duration in minutes."""
        if self.called_time and self.completed_time:
            return max(1.0, round((self.completed_time - self.called_time).total_seconds() / 60.0, 1))
        return None

    @property
    def waiting_duration_minutes(self):
        """Calculates actual waiting time from check-in to consultation call."""
        if self.check_in_time and self.called_time:
            return max(0.0, round((self.called_time - self.check_in_time).total_seconds() / 60.0, 1))
        elif self.check_in_time and self.status == 'WAITING':
            return max(0.0, round((datetime.now() - self.check_in_time).total_seconds() / 60.0, 1))
        return None

    def estimated_wait_minutes(self):
        """Calculates dynamic estimated wait time in minutes based on patients ahead in queue."""
        if self.status != 'WAITING':
            return 0
        priority_weights = {'Emergency': 0, 'Senior Citizen': 1, 'Pregnant Woman': 2, 'Child': 3, 'Regular': 4}
        my_weight = priority_weights.get(self.priority, 4)

        # Count higher priority or earlier checked-in patients
        all_waiting = CheckIn.query.filter(
            CheckIn.doctor_id == self.doctor_id,
            CheckIn.status == 'WAITING'
        ).all()
        
        ahead_count = 0
        for other in all_waiting:
            if other.id == self.id:
                continue
            other_weight = priority_weights.get(other.priority, 4)
            if (other_weight < my_weight) or (other_weight == my_weight and other.id < self.id):
                ahead_count += 1

        # Check if someone is in consultation right now
        in_consult = CheckIn.query.filter_by(doctor_id=self.doctor_id, status='IN_CONSULTATION').first()
        base_rem = 6 if in_consult else 0

        avg_consult_minutes = 12
        return max(5, int((ahead_count * avg_consult_minutes) + base_rem))

    def __repr__(self):
        return f"<CheckIn {self.token_no} - Patient {self.patient_id} -> Doctor {self.doctor_id}>"


class EmergencyEncounter(db.Model):
    __tablename__ = 'emergency_encounters'

    id = db.Column(db.Integer, primary_key=True)
    temp_id = db.Column(db.String(40), unique=True, nullable=False, index=True)  # e.g. TEMP-ER-2026-0001
    token_no = db.Column(db.String(20), nullable=False, index=True)             # e.g. ER-001
    
    # Patient identity link (nullable for unknown / unidentified emergency patients)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=True)
    is_identified = db.Column(db.Boolean, default=False)
    
    # Clinical & operational encounter details
    emergency_type = db.Column(db.String(80), default='Medical Emergency') 
    # e.g., Accident / Trauma, Unidentified Patient, Unconscious Patient, Pregnancy-related Emergency, Medical Emergency, Pediatric Emergency, Other Emergency
    priority = db.Column(db.String(40), default='Emergency / Critical') 
    # Emergency / Critical, Urgent, Priority
    status = db.Column(db.String(40), default='Registered')
    # Emergency Arrival, Registered, Triage, Doctor Assigned, Under Treatment, Stabilized, Admitted, Discharged, Transferred
    
    arrival_source = db.Column(db.String(60), default='Walk-In')  # Ambulance, Walk-In, Police Referral, Bystander, Other
    assigned_doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    department = db.Column(db.String(60), default='Emergency / Trauma')
    
    notes = db.Column(db.Text, nullable=True)
    
    arrival_time = db.Column(db.DateTime, default=datetime.now)
    registered_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    identified_at = db.Column(db.DateTime, nullable=True)
    identified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Optional linked checkin_id if synced with reception check-in queue
    check_in_id = db.Column(db.Integer, db.ForeignKey('check_ins.id'), nullable=True)

    # Relationships
    patient = db.relationship('Patient', backref='emergency_encounters', lazy=True)
    assigned_doctor = db.relationship('User', foreign_keys=[assigned_doctor_id], backref='assigned_emergency_encounters', lazy=True)
    registered_by = db.relationship('User', foreign_keys=[registered_by_id], backref='registered_emergency_encounters', lazy=True)
    identified_by = db.relationship('User', foreign_keys=[identified_by_id], lazy=True)
    check_in = db.relationship('CheckIn', backref=db.backref('emergency_encounter', uselist=False), lazy=True)

    @staticmethod
    def generate_temp_id():
        """Generates sequential temporary emergency ID e.g. TEMP-ER-2026-0001"""
        current_year = datetime.now().year
        prefix = f"TEMP-ER-{current_year}-"
        count = EmergencyEncounter.query.filter(
            EmergencyEncounter.temp_id.like(f"{prefix}%")
        ).count()
        return f"{prefix}{(count + 1):04d}"

    @staticmethod
    def generate_token_no():
        """Generates sequential emergency token for today e.g. ER-001, ER-002"""
        today_start = datetime.combine(date.today(), datetime.min.time())
        count = EmergencyEncounter.query.filter(
            EmergencyEncounter.arrival_time >= today_start
        ).count()
        return f"ER-{(count + 1):03d}"

    @property
    def display_name(self):
        if self.patient:
            return self.patient.full_name
        return "Unknown Emergency Patient"

    @property
    def display_code(self):
        if self.patient:
            return self.patient.patient_code
        return self.temp_id

    def __repr__(self):
        return f"<EmergencyEncounter {self.token_no} ({self.temp_id}) - Patient {self.patient_id}>"
