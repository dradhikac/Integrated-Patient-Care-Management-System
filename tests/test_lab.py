import unittest
from datetime import date
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.lab.models import LabTestType, LabRequest, LabResult

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class LabTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed roles & users
        doc_role = Role(name='Doctor', description='Doctor')
        tech_role = Role(name='Lab Technician', description='Lab Tech')
        db.session.add_all([doc_role, tech_role])
        db.session.commit()

        self.doctor = User(user_code='DOC-001', name='Dr. Sharma', email='doc@test.com', role_id=doc_role.id)
        self.doctor.set_password('Secret123!')
        
        self.tech = User(user_code='LAB-001', name='Tech Suresh', email='tech@test.com', role_id=tech_role.id)
        self.tech.set_password('Secret123!')
        
        db.session.add_all([self.doctor, self.tech])
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

        # Lab Test Type
        self.test_type = LabTestType(
            test_code='TST-CBC-HB',
            test_name='Hemoglobin (Hb)',
            category='Haematology',
            unit='g/dL',
            min_normal_val=12.0,
            max_normal_val=16.0
        )
        db.session.add(self.test_type)
        db.session.commit()

        self.client = self.app.test_client()
        self.client.post('/login', data={'email': 'tech@test.com', 'password': 'Secret123!'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_eval_result_flag(self):
        # 14.0 g/dL -> NORMAL
        self.assertEqual(self.test_type.evaluate_result_flag(14.0), 'NORMAL')
        # 18.0 g/dL -> ABNORMAL_HIGH
        self.assertEqual(self.test_type.evaluate_result_flag(18.0), 'ABNORMAL_HIGH')
        # 10.0 g/dL -> ABNORMAL_LOW
        self.assertEqual(self.test_type.evaluate_result_flag(10.0), 'ABNORMAL_LOW')

    def test_lab_request_and_results(self):
        req_code = LabRequest.generate_request_code()
        self.assertTrue(req_code.startswith('LAB-2026-'))

        req = LabRequest(
            request_code=req_code,
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            status='REQUESTED'
        )
        db.session.add(req)
        db.session.flush()

        res = LabResult(
            request_id=req.id,
            test_type_id=self.test_type.id,
            result_value=18.5,
            abnormal_flag=self.test_type.evaluate_result_flag(18.5),
            technician_id=self.tech.id
        )
        db.session.add(res)
        req.status = 'COMPLETED'
        db.session.commit()

        saved_req = db.session.get(LabRequest, req.id)
        self.assertEqual(saved_req.status, 'COMPLETED')
        self.assertEqual(saved_req.results[0].abnormal_flag, 'ABNORMAL_HIGH')


if __name__ == '__main__':
    unittest.main()
