from datetime import datetime
from app.extensions import db

class Medicine(db.Model):
    __tablename__ = 'medicines'

    id = db.Column(db.Integer, primary_key=True)
    brand_name = db.Column(db.String(100), nullable=False, index=True)
    generic_name = db.Column(db.String(100), nullable=False)
    dosage_form = db.Column(db.String(50), default='Tablet') # Tablet, Capsule, Syrup, Injection, Ointment
    strength = db.Column(db.String(50), nullable=True) # e.g. 500mg, 10mg
    default_instructions = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Medicine {self.brand_name} ({self.generic_name})>"


class Prescription(db.Model):
    __tablename__ = 'prescriptions'

    id = db.Column(db.Integer, primary_key=True)
    prescription_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultations.id'), nullable=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    general_advice = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', backref='prescriptions', lazy=True)
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='doctor_prescriptions', lazy=True)
    consultation = db.relationship('Consultation', backref='prescription', uselist=False, lazy=True)
    items = db.relationship('PrescriptionItem', backref='prescription', cascade='all, delete-orphan', lazy=True)

    @staticmethod
    def generate_prescription_code():
        year = datetime.now().year
        last_rx = Prescription.query.order_by(Prescription.id.desc()).first()
        new_num = (last_rx.id + 1) if last_rx else 1
        return f"RX-{year}-{new_num:06d}"

    def __repr__(self):
        return f"<Prescription {self.prescription_code} - Patient {self.patient_id}>"


class PrescriptionItem(db.Model):
    __tablename__ = 'prescription_items'

    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=True)
    
    medicine_name = db.Column(db.String(150), nullable=False)
    frequency = db.Column(db.String(50), nullable=False, default='1-0-1') # 1-0-1, 1-0-0, 0-0-1, 1-1-1, SOS
    duration = db.Column(db.String(50), nullable=False, default='5 Days')
    food_relation = db.Column(db.String(50), default='After Food') # After Food, Before Food, With Food
    instructions = db.Column(db.Text, nullable=True)

    medicine = db.relationship('Medicine', lazy=True)

    def __repr__(self):
        return f"<PrescriptionItem {self.medicine_name} - {self.frequency}>"
