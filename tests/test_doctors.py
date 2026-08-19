import unittest
from datetime import date, timedelta
from app import create_app
from app.extensions import db
from app.doctors.models import Doctor
from app.auth.models import Role, User
from app.appointments.models import Appointment

class DoctorsApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            doc_role = Role.query.filter_by(name='Doctor').first()
            if not doc_role:
                doc_role = Role(name='Doctor', description='Consultation')
                db.session.add(doc_role)
                db.session.flush()

            usr = User.query.filter_by(user_code='TEST-DOC-999').first()
            if not usr:
                usr = User(user_code='TEST-DOC-999', name='Dr. Test Doctor', email='test.doctor@medicore.com', role_id=doc_role.id)
                usr.set_password('Password@123')
                db.session.add(usr)
                db.session.flush()

            doc = Doctor.query.filter_by(doctor_code='TEST-DOC-999').first()
            if not doc:
                doc = Doctor(
                    user_id=usr.id,
                    doctor_code='TEST-DOC-999',
                    name='Dr. Test Doctor',
                    specialization='Cardiologist',
                    education='MBBS, MD, DM',
                    experience='5+ Years',
                    department='Cardiology & Heart Institute',
                    bio='Experienced cardiologist.',
                    consultation_fee=800.0,
                    image_url='/static/images/doctors/dr_ananya_sharma.jpg',
                    available_days='Monday - Saturday',
                    is_active=True
                )
                db.session.add(doc)
                db.session.commit()
            self.test_doctor_id = doc.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_get_doctors_api(self):
        response = self.client.get('/api/doctors')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(len(data['doctors']), 1)

    def test_get_doctor_profile_api(self):
        response = self.client.get(f'/api/doctors/{self.test_doctor_id}')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['doctor']['specialization'], 'Cardiologist')

    def test_get_doctor_availability_api(self):
        target_date = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
        response = self.client.get(f'/api/doctors/{self.test_doctor_id}/availability?date={target_date}')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('slots', data)

    def test_book_appointment_api_validation_and_success(self):
        future_date = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        
        # 1. Past date check
        past_date = (date.today() - timedelta(days=2)).strftime('%Y-%m-%d')
        resp_past = self.client.post(f'/api/doctors/{self.test_doctor_id}/book', json={
            'appointment_date': past_date,
            'slot_time': '10:00',
            'patient_name': 'Test Patient',
            'patient_email': 'test@example.com'
        })
        self.assertEqual(resp_past.status_code, 400)

        # 2. Valid booking
        resp_success = self.client.post(f'/api/doctors/{self.test_doctor_id}/book', json={
            'appointment_date': future_date,
            'slot_time': '10:00',
            'patient_name': 'John Doe',
            'patient_email': 'johndoe@example.com',
            'patient_mobile': '+91-9999988888',
            'reason': 'Regular Cardiac Checkup'
        })
        self.assertEqual(resp_success.status_code, 200)
        data_success = resp_success.get_json()
        self.assertTrue(data_success['success'])
        self.assertEqual(data_success['status'], 'BOOKED')

        # 3. Double booking prevention
        resp_double = self.client.post(f'/api/doctors/{self.test_doctor_id}/book', json={
            'appointment_date': future_date,
            'slot_time': '10:00',
            'patient_name': 'Jane Doe',
            'patient_email': 'janedoe@example.com'
        })
        self.assertEqual(resp_double.status_code, 409)

    def test_view_doctor_profile_page(self):
        response = self.client.get(f'/doctors/{self.test_doctor_id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Cardiologist', response.data)

if __name__ == '__main__':
    unittest.main()
