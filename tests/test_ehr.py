import unittest
from datetime import date, datetime
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.reception.models import CheckIn
from app.appointments.models import Appointment
from app.ehr.timeline_builder import build_patient_ehr_timeline

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class EHRTestCase(unittest.TestCase):
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

        self.receptionist = User(user_code='REC-001', name='Receptionist Test', email='rec@test.com', role_id=rec_role.id)
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
            dob=date(1998, 5, 15),
            gender='Female',
            mobile='9876543210',
            blood_group='O+'
        )
        db.session.add(self.patient)
        db.session.commit()

        # OPD Check-In
        self.check_in = CheckIn(
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            token_no='TK-001',
            department='General OPD',
            priority='Regular',
            status='COMPLETED',
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

    def test_ehr_timeline_aggregation(self):
        timeline = build_patient_ehr_timeline(self.patient.id)
        self.assertGreaterEqual(len(timeline), 2) # Registration + Check-In

        event_types = [e['event_type'] for e in timeline]
        self.assertIn('REGISTRATION', event_types)
        self.assertIn('CHECK_IN', event_types)

    def test_ehr_search_and_filter(self):
        # Filter by CHECK_IN
        filtered = build_patient_ehr_timeline(self.patient.id, event_filter='CHECK_IN')
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['event_type'], 'CHECK_IN')

        # Keyword search
        search_res = build_patient_ehr_timeline(self.patient.id, search_term='TK-001')
        self.assertEqual(len(search_res), 1)
        self.assertEqual(search_res[0]['details']['Token No'], 'TK-001')


if __name__ == '__main__':
    unittest.main()
