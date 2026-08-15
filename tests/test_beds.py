import unittest
from datetime import date, datetime
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.beds.models import Ward, Bed, Admission, BedTransfer

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class BedsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed roles & users
        rec_role = Role(name='Receptionist', description='Reception')
        doc_role = Role(name='Doctor', description='Doctor')
        db.session.add_all([rec_role, doc_role])
        db.session.commit()

        self.receptionist = User(user_code='REC-001', name='Receptionist Mary', email='rec@test.com', role_id=rec_role.id)
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

        # Ward & Beds
        self.ward = Ward(ward_code='WRD-ICU', ward_name='Intensive Care Unit', category='ICU', daily_rate=2500.0)
        db.session.add(self.ward)
        db.session.flush()

        self.bed1 = Bed(ward_id=self.ward.id, bed_code='BED-ICU-01', status='AVAILABLE')
        self.bed2 = Bed(ward_id=self.ward.id, bed_code='BED-ICU-02', status='AVAILABLE')
        db.session.add_all([self.bed1, self.bed2])
        db.session.commit()

        self.client = self.app.test_client()
        self.client.post('/login', data={'email': 'rec@test.com', 'password': 'Secret123!'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_inpatient_admission_and_discharge(self):
        adm_code = Admission.generate_admission_code()
        self.assertTrue(adm_code.startswith('ADM-2026-'))

        # 1. Admit Patient to Bed 1
        adm = Admission(
            admission_code=adm_code,
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            bed_id=self.bed1.id,
            diagnosis='Acute Respiratory Distress',
            status='ADMITTED'
        )
        self.bed1.status = 'OCCUPIED'
        db.session.add(adm)
        db.session.commit()

        self.assertEqual(db.session.get(Bed, self.bed1.id).status, 'OCCUPIED')
        self.assertEqual(adm.length_of_stay_days, 1)

        # 2. Discharge Patient
        res = self.client.post(f'/beds/admission/{adm.id}/discharge', data={'discharge_notes': 'Patient recovered'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        updated_adm = db.session.get(Admission, adm.id)
        self.assertEqual(updated_adm.status, 'DISCHARGED')
        self.assertEqual(db.session.get(Bed, self.bed1.id).status, 'AVAILABLE')

    def test_bed_transfer(self):
        adm = Admission(
            admission_code=Admission.generate_admission_code(),
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            bed_id=self.bed1.id,
            diagnosis='Observation',
            status='ADMITTED'
        )
        self.bed1.status = 'OCCUPIED'
        db.session.add(adm)
        db.session.commit()

        # Transfer from Bed 1 to Bed 2
        res = self.client.post(f'/beds/admission/{adm.id}/transfer', data={
            'target_bed_id': self.bed2.id,
            'reason': 'Shifted for specialized monitoring'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        self.assertEqual(db.session.get(Bed, self.bed1.id).status, 'AVAILABLE')
        self.assertEqual(db.session.get(Bed, self.bed2.id).status, 'OCCUPIED')
        self.assertEqual(db.session.get(Admission, adm.id).bed_id, self.bed2.id)


if __name__ == '__main__':
    unittest.main()
