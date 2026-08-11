from datetime import datetime
from app.extensions import db

class LabTestType(db.Model):
    __tablename__ = 'lab_test_types'

    id = db.Column(db.Integer, primary_key=True)
    test_code = db.Column(db.String(30), unique=True, nullable=False, index=True) # e.g. TST-CBC
    test_name = db.Column(db.String(100), nullable=False) # e.g. Complete Blood Count
    category = db.Column(db.String(50), default='Haematology') # Haematology, Biochemistry, Radiology, Cardiology
    unit = db.Column(db.String(30), nullable=True) # e.g. g/dL, mg/dL
    min_normal_val = db.Column(db.Float, nullable=True) # e.g. 12.0
    max_normal_val = db.Column(db.Float, nullable=True) # e.g. 16.0
    cost = db.Column(db.Float, default=500.0)
    is_active = db.Column(db.Boolean, default=True)

    def evaluate_result_flag(self, val: float) -> str:
        """Evaluates measured value against normal reference ranges."""
        if val is None:
            return 'NORMAL'
        if self.min_normal_val is not None and val < self.min_normal_val:
            return 'ABNORMAL_LOW'
        if self.max_normal_val is not None and val > self.max_normal_val:
            return 'ABNORMAL_HIGH'
        return 'NORMAL'

    def __repr__(self):
        return f"<LabTestType {self.test_code} - {self.test_name}>"


class LabRequest(db.Model):
    __tablename__ = 'lab_requests'

    id = db.Column(db.Integer, primary_key=True)
    request_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultations.id'), nullable=True)
    
    status = db.Column(db.String(30), default='REQUESTED') # REQUESTED, SAMPLE_COLLECTED, IN_TESTING, COMPLETED
    clinical_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', backref='lab_requests', lazy=True)
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='doctor_lab_requests', lazy=True)
    consultation = db.relationship('Consultation', backref='lab_requests', lazy=True)
    results = db.relationship('LabResult', backref='lab_request', cascade='all, delete-orphan', lazy=True)

    @staticmethod
    def generate_request_code():
        year = datetime.now().year
        last_req = LabRequest.query.order_by(LabRequest.id.desc()).first()
        new_num = (last_req.id + 1) if last_req else 1
        return f"LAB-{year}-{new_num:06d}"

    def __repr__(self):
        return f"<LabRequest {self.request_code} - Patient {self.patient_id}>"


class LabResult(db.Model):
    __tablename__ = 'lab_results'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('lab_requests.id'), nullable=False)
    test_type_id = db.Column(db.Integer, db.ForeignKey('lab_test_types.id'), nullable=False)
    
    result_value = db.Column(db.Float, nullable=False) # e.g. 14.5
    abnormal_flag = db.Column(db.String(30), default='NORMAL') # NORMAL, ABNORMAL_HIGH, ABNORMAL_LOW
    remarks = db.Column(db.Text, nullable=True)
    technician_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    test_type = db.relationship('LabTestType', lazy=True)
    technician = db.relationship('User', foreign_keys=[technician_id], backref='technician_lab_results', lazy=True)

    def __repr__(self):
        return f"<LabResult Test {self.test_type_id} - Val: {self.result_value} ({self.abnormal_flag})>"
