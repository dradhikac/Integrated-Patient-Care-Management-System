import unittest
from datetime import date, datetime
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.reception.models import CheckIn

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ReceptionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed roles
        rec_role = Role(name='Receptionist', description='Reception')
        doc_role = Role(name='Doctor', description='Doctor')
        db.session.add_all([rec_role, doc_role])
        db.session.commit()

        # Users
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

        self.client = self.app.test_client()
        self.client.post('/login', data={'email': 'rec@test.com', 'password': 'Secret123!'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_token_generation_and_check_in(self):
        token1 = CheckIn.generate_token_number()
        self.assertEqual(token1, 'TK-001')

        check_in1 = CheckIn(
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            token_no=token1,
            department='General OPD',
            priority='Regular',
            status='WAITING',
            check_in_time=datetime.now(),
            checked_in_by_id=self.receptionist.id
        )
        db.session.add(check_in1)
        db.session.commit()

        token2 = CheckIn.generate_token_number()
        self.assertEqual(token2, 'TK-002')

    def test_status_update_flow(self):
        check_in = CheckIn(
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            token_no='TK-001',
            department='Cardiology',
            status='WAITING',
            checked_in_by_id=self.receptionist.id
        )
        db.session.add(check_in)
        db.session.commit()

        # Update status to IN_CONSULTATION
        res = self.client.post(f'/reception/update-status/{check_in.id}', data={'status': 'IN_CONSULTATION'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        
        updated = db.session.get(CheckIn, check_in.id)
        self.assertEqual(updated.status, 'IN_CONSULTATION')
        self.assertIsNotNone(updated.called_time)


if __name__ == '__main__':
    unittest.main()
