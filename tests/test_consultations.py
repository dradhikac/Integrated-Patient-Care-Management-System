import unittest
from datetime import date, datetime
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.reception.models import CheckIn
from app.consultations.models import Consultation, Vital

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ConsultationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed roles and users
        rec_role = Role(name='Receptionist', description='Reception')
        doc_role = Role(name='Doctor', description='Doctor')
        db.session.add_all([rec_role, doc_role])
        db.session.commit()

        self.receptionist = User(user_code='REC-001', name='Reception Staff', email='rec@test.com', role_id=rec_role.id)
        self.receptionist.set_password('Secret123!')
        
        self.doctor = User(user_code='DOC-001', name='Dr. Sharma', email='doc@test.com', role_id=doc_role.id)
        self.doctor.set_password('Secret123!')
        
        db.session.add_all([self.receptionist, self.doctor])
        db.session.commit()

        # Patient
        self.patient = Patient(
            patient_code='IPCMS-2026-000001',
            first_name='Ananya',
            last_name='Verma',
            full_name='Ananya Verma',
            dob=date(1995, 4, 10),
            gender='Female',
            mobile='9876543210'
        )
        db.session.add(self.patient)
        db.session.commit()

        # Check-in
        self.check_in = CheckIn(
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            token_no='TK-001',
            department='General OPD',
            priority='Regular',
            status='IN_CONSULTATION',
            checked_in_by_id=self.receptionist.id
        )
        db.session.add(self.check_in)
        db.session.commit()

        self.client = self.app.test_client()
        self.client.post('/login', data={'email': 'doc@test.com', 'password': 'Secret123!'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_consultation_creation_and_vitals(self):
        cns_code = Consultation.generate_consultation_code()
        self.assertTrue(cns_code.startswith('CNS-2026-'))

        cns = Consultation(
            consultation_code=cns_code,
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            check_in_id=self.check_in.id,
            symptoms='Fever and body pain',
            diagnosis='Acute Viral Fever',
            treatment_plan='Paracetamol 500mg, Rest'
        )
        db.session.add(cns)
        db.session.flush()

        vitals = Vital(
            consultation_id=cns.id,
            bp_systolic=120,
            bp_diastolic=80,
            temperature_f=99.2,
            pulse_bpm=78,
            spo2_percent=98
        )
        db.session.add(vitals)
        
        # Mark check-in completed
        self.check_in.status = 'COMPLETED'
        db.session.commit()

        # Verify
        saved_cns = db.session.get(Consultation, cns.id)
        self.assertEqual(saved_cns.diagnosis, 'Acute Viral Fever')
        self.assertIsNotNone(saved_cns.vital)
        self.assertEqual(saved_cns.vital.get_bp_string(), '120/80 mmHg')
        self.assertEqual(db.session.get(CheckIn, self.check_in.id).status, 'COMPLETED')


if __name__ == '__main__':
    unittest.main()
