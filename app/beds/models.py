from datetime import datetime
from app.extensions import db

class Ward(db.Model):
    __tablename__ = 'wards'

    id = db.Column(db.Integer, primary_key=True)
    ward_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    ward_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), default='General Ward') # 'ICU', 'General Ward', 'Private Suite', 'Semi-Private'
    daily_rate = db.Column(db.Float, nullable=False, default=1000.0)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    beds = db.relationship('Bed', backref='ward', lazy=True)

    def total_beds_count(self):
        return len(self.beds)

    def available_beds_count(self):
        return sum(1 for b in self.beds if b.status == 'AVAILABLE')


class Bed(db.Model):
    __tablename__ = 'beds'

    id = db.Column(db.Integer, primary_key=True)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=False)
    bed_code = db.Column(db.String(30), unique=True, nullable=False, index=True) # e.g. BED-ICU-01
    status = db.Column(db.String(30), default='AVAILABLE') # 'AVAILABLE', 'OCCUPIED', 'UNDER_CLEANING'
    notes = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<Bed {self.bed_code} ({self.status})>"


class Admission(db.Model):
    __tablename__ = 'admissions'

    id = db.Column(db.Integer, primary_key=True)
    admission_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bed_id = db.Column(db.Integer, db.ForeignKey('beds.id'), nullable=False)
    
    admitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    discharged_at = db.Column(db.DateTime, nullable=True)
    diagnosis = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default='ADMITTED') # 'ADMITTED', 'DISCHARGED'
    discharge_notes = db.Column(db.Text, nullable=True)

    # Relationships
    patient = db.relationship('Patient', backref='admissions', lazy=True)
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='doctor_admissions', lazy=True)
    bed = db.relationship('Bed', backref='admissions', lazy=True)

    @staticmethod
    def generate_admission_code():
        year = datetime.now().year
        last_adm = Admission.query.order_by(Admission.id.desc()).first()
        new_num = (last_adm.id + 1) if last_adm else 1
        return f"ADM-{year}-{new_num:06d}"

    @property
    def length_of_stay_days(self):
        end_time = self.discharged_at or datetime.utcnow()
        delta = end_time - self.admitted_at
        return max(1, delta.days)


class BedTransfer(db.Model):
    __tablename__ = 'bed_transfers'

    id = db.Column(db.Integer, primary_key=True)
    admission_id = db.Column(db.Integer, db.ForeignKey('admissions.id', ondelete='CASCADE'), nullable=False)
    from_bed_id = db.Column(db.Integer, db.ForeignKey('beds.id'), nullable=False)
    to_bed_id = db.Column(db.Integer, db.ForeignKey('beds.id'), nullable=False)
    transferred_at = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(255), nullable=True)
    transferred_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    admission = db.relationship('Admission', backref=db.backref('transfers', cascade='all, delete-orphan', lazy=True))
    from_bed = db.relationship('Bed', foreign_keys=[from_bed_id], lazy=True)
    to_bed = db.relationship('Bed', foreign_keys=[to_bed_id], lazy=True)
    transferred_by = db.relationship('User', foreign_keys=[transferred_by_id], lazy=True)
