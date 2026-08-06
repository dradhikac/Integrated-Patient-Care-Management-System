import unittest
from datetime import date
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.patients.security import encrypt_aadhaar, decrypt_aadhaar, mask_aadhaar
from app.patients.duplicate_check import check_for_duplicates, calculate_name_similarity

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class PatientTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed role and user
        rec_role = Role(name='Receptionist', description='Reception desk')
        db.session.add(rec_role)
        db.session.commit()

        self.user = User(user_code='REC-001', name='Receptionist Test', email='rec@test.com', role_id=rec_role.id)
        self.user.set_password('Secret123!')
        db.session.add(self.user)
        db.session.commit()

        self.client = self.app.test_client()
        self.client.post('/login', data={'email': 'rec@test.com', 'password': 'Secret123!'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_aadhaar_security(self):
        raw_aadhaar = '123456789012'
        encrypted = encrypt_aadhaar(raw_aadhaar)
        self.assertNotEqual(raw_aadhaar, encrypted)
        
        decrypted = decrypt_aadhaar(encrypted)
        self.assertEqual(raw_aadhaar, decrypted)
        
        masked = mask_aadhaar(raw_aadhaar)
        self.assertEqual(masked, 'XXXX-XXXX-9012')

    def test_bmi_calculation(self):
        patient = Patient(
            patient_code='IPCMS-2026-000001',
            first_name='Ananya',
            last_name='Verma',
            full_name='Ananya Verma',
            dob=date(1998, 5, 15),
            gender='Female',
            mobile='9876543210',
            height_cm=160.0,
            weight_kg=64.0
        )
        patient.calculate_bmi()
        # BMI = 64 / (1.6 * 1.6) = 64 / 2.56 = 25.0
        self.assertEqual(patient.bmi, 25.0)
        self.assertEqual(patient.get_bmi_category(), 'Overweight')

    def test_fuzzy_duplicate_detection(self):
        # Create existing patient
        existing = Patient(
            patient_code='IPCMS-2026-000001',
            first_name='Rajesh',
            last_name='Kumar',
            full_name='Rajesh Kumar',
            dob=date(1985, 8, 20),
            gender='Male',
            mobile='9876543210'
        )
        existing.set_aadhaar('999988887777')
        db.session.add(existing)
        db.session.commit()

        # Case 1: Exact Aadhaar match
        is_dup, matches = check_for_duplicates('Raj', 'Kumar', date(1985, 8, 20), '9000000000', '999988887777')
        self.assertTrue(is_dup)
        self.assertEqual(matches[0]['similarity_score'], 100)

        # Case 2: Exact Mobile & DOB match
        is_dup, matches = check_for_duplicates('Rajesh', 'Kumar', date(1985, 8, 20), '9876543210')
        self.assertTrue(is_dup)

        # Case 3: Completely distinct person
        is_dup, matches = check_for_duplicates('Priya', 'Sharma', date(2000, 1, 1), '8888877777')
        self.assertFalse(is_dup)


if __name__ == '__main__':
    unittest.main()
