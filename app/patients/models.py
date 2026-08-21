from datetime import datetime
from app.extensions import db
from app.patients.security import mask_aadhaar, encrypt_aadhaar, decrypt_aadhaar

class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    patient_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    full_name = db.Column(db.String(105), nullable=False, index=True)
    dob = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    mobile = db.Column(db.String(20), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    
    # Aadhaar security
    aadhaar_encrypted = db.Column(db.Text, nullable=True)
    aadhaar_masked = db.Column(db.String(20), nullable=True)
    
    photo_path = db.Column(db.String(255), nullable=True, default='img/default_avatar.png')
    blood_group = db.Column(db.String(10), nullable=True)
    
    # Emergency & Insurance
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_mobile = db.Column(db.String(20), nullable=True)
    insurance_provider = db.Column(db.String(100), nullable=True)
    insurance_policy_no = db.Column(db.String(100), nullable=True)
    
    # Vitals baseline
    height_cm = db.Column(db.Float, nullable=True)
    weight_kg = db.Column(db.Float, nullable=True)
    bmi = db.Column(db.Float, nullable=True)
    
    vaccination_records = db.Column(db.Text, nullable=True)
    preferred_language = db.Column(db.String(50), default='English')
    
    registered_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Patient Portal Access
    portal_status = db.Column(db.String(20), default='NOT_ACTIVATED', nullable=False)
    # Possible values: 'NOT_ACTIVATED', 'PENDING', 'ACTIVE', 'LOCKED'
    portal_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationships
    medical_histories = db.relationship('PatientMedicalHistory', backref='patient', cascade='all, delete-orphan', lazy=True)
    allergies = db.relationship('PatientAllergy', backref='patient', cascade='all, delete-orphan', lazy=True)
    registered_by = db.relationship('User', backref='registered_patients', foreign_keys=[registered_by_id])
    portal_user = db.relationship('User', backref='patient_profile', foreign_keys=[portal_user_id], uselist=False)

    def calculate_bmi(self):
        """Calculates BMI = weight_kg / ((height_cm / 100) ** 2)"""
        if self.height_cm and self.weight_kg and self.height_cm > 0:
            height_m = self.height_cm / 100.0
            self.bmi = round(self.weight_kg / (height_m ** 2), 2)
        else:
            self.bmi = None
        return self.bmi

    def get_bmi_category(self):
        """Return clinical BMI category description"""
        if not self.bmi:
            return "N/A"
        if self.bmi < 18.5:
            return "Underweight"
        elif 18.5 <= self.bmi < 25.0:
            return "Normal Weight"
        elif 25.0 <= self.bmi < 30.0:
            return "Overweight"
        else:
            return "Obese (High Risk)"

    def set_aadhaar(self, aadhaar_raw):
        if aadhaar_raw:
            self.aadhaar_encrypted = encrypt_aadhaar(aadhaar_raw)
            self.aadhaar_masked = mask_aadhaar(aadhaar_raw)
        else:
            self.aadhaar_encrypted = None
            self.aadhaar_masked = "N/A"

    def get_decrypted_aadhaar(self):
        return decrypt_aadhaar(self.aadhaar_encrypted)

    @staticmethod
    def generate_patient_code():
        """Generate format: IPCMS-2026-000001"""
        year = datetime.now().year
        last_patient = Patient.query.order_by(Patient.id.desc()).first()
        new_num = (last_patient.id + 1) if last_patient else 1
        return f"IPCMS-{year}-{new_num:06d}"

    def __repr__(self):
        return f"<Patient {self.patient_code} - {self.full_name}>"


class PatientMedicalHistory(db.Model):
    __tablename__ = 'patient_medical_history'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    condition_type = db.Column(db.String(50), nullable=False) # 'Chronic Disease', 'Family History', 'Past Surgery'
    description = db.Column(db.Text, nullable=False)
    diagnosed_year = db.Column(db.Integer, nullable=True)


class PatientAllergy(db.Model):
    __tablename__ = 'patient_allergies'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    allergen = db.Column(db.String(100), nullable=False)
    severity = db.Column(db.String(20), default='Moderate') # 'Mild', 'Moderate', 'Severe'
    reaction = db.Column(db.String(255), nullable=True)
