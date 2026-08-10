import unittest
from datetime import date
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.prescriptions.models import Medicine, Prescription, PrescriptionItem
from app.prescriptions.qr_generator import generate_prescription_qr_base64

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class PrescriptionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed roles & users
        doc_role = Role(name='Doctor', description='Doctor')
        db.session.add(doc_role)
        db.session.commit()

        self.doctor = User(user_code='DOC-001', name='Dr. Sharma', email='doc@test.com', role_id=doc_role.id)
        self.doctor.set_password('Secret123!')
        db.session.add(self.doctor)
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

        # Medicine
        self.med = Medicine(brand_name='Dolo 650', generic_name='Paracetamol', dosage_form='Tablet', strength='650mg')
        db.session.add(self.med)
        db.session.commit()

        self.client = self.app.test_client()
        self.client.post('/login', data={'email': 'doc@test.com', 'password': 'Secret123!'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_prescription_code_and_items(self):
        rx_code = Prescription.generate_prescription_code()
        self.assertTrue(rx_code.startswith('RX-2026-'))

        rx = Prescription(
            prescription_code=rx_code,
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            general_advice='Take rest and hydrate'
        )
        db.session.add(rx)
        db.session.flush()

        item1 = PrescriptionItem(
            prescription_id=rx.id,
            medicine_id=self.med.id,
            medicine_name='Dolo 650 (Paracetamol 650mg)',
            frequency='1-0-1',
            duration='5 Days',
            food_relation='After Food'
        )
        db.session.add(item1)
        db.session.commit()

        saved_rx = db.session.get(Prescription, rx.id)
        self.assertEqual(len(saved_rx.items), 1)
        self.assertEqual(saved_rx.items[0].frequency, '1-0-1')

    def test_qr_code_generation(self):
        qr_str = generate_prescription_qr_base64('http://localhost:5000/prescriptions/verify/RX-2026-000001')
        self.assertTrue(qr_str.startswith('data:image/svg+xml;base64,'))

    def test_public_verification_api(self):
        rx_code = Prescription.generate_prescription_code()
        rx = Prescription(
            prescription_code=rx_code,
            patient_id=self.patient.id,
            doctor_id=self.doctor.id
        )
        db.session.add(rx)
        db.session.flush()
        db.session.add(PrescriptionItem(prescription_id=rx.id, medicine_name='Cetzine 10mg', frequency='0-0-1', duration='3 Days'))
        db.session.commit()

        res = self.client.get(f'/prescriptions/verify/{rx_code}')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'VERIFIED_VALID')
        self.assertEqual(data['patient_name'], 'Ananya Verma')


if __name__ == '__main__':
    unittest.main()
