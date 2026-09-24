import unittest
from datetime import date, timedelta
from app import create_app
from app.extensions import db
from app.doctors.models import Doctor
from app.auth.models import Role, User
from app.appointments.models import Appointment
from app.patients.models import Patient
from app.notifications.models import Notification, NotificationLog

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

    def test_schedule_followup_and_notification(self):
        with self.app.app_context():
            doc_user = User.query.filter_by(user_code='TEST-DOC-999').first()
            patient = Patient(
                patient_code='IPCMS-TEST-001',
                first_name='Radhika',
                last_name='Chougale',
                full_name='Radhika D Chougale',
                dob=date(2006, 4, 11),
                gender='Female',
                mobile='7019669582',
                email='dcradhika004@gmail.com'
            )
            db.session.add(patient)
            db.session.commit()
            patient_id = patient.id
            doc_id = doc_user.id

        # Log in as Doctor
        self.client.post('/login', data={'email': 'test.doctor@medicore.com', 'password': 'Password@123'})

        # Schedule Follow-up
        future_date = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')
        post_data = {
            'followup_date': future_date,
            'slot_time': '10:30:00',
            'priority': 'Regular',
            'notes': 'Check BP and review blood panel reports after 1 week.'
        }
        resp = self.client.post(f'/doctor/patients/{patient_id}/schedule-followup', data=post_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            # 1. Verify Appointment created
            apt = Appointment.query.filter_by(patient_id=patient_id, doctor_id=doc_id, booking_type='Follow-Up').first()
            self.assertIsNotNone(apt)
            self.assertEqual(apt.status, 'BOOKED')
            self.assertIn('Check BP and review', apt.notes)

            # 2. Verify Patient Notification created and sent
            notif = Notification.query.filter_by(patient_id=patient_id, type='FOLLOWUP_REMINDER').first()
            self.assertIsNotNone(notif)
            self.assertEqual(notif.status, 'SENT')
            self.assertIn('Follow-Up Scheduled', notif.title)
            self.assertIn('Check BP and review', notif.message)

            # 3. Verify NotificationLog generated for SMS and/or EMAIL
            logs = NotificationLog.query.filter_by(notification_id=notif.id).all()
            self.assertGreaterEqual(len(logs), 1)

    def test_doctor_available_slots_endpoint(self):
        # Log in as Doctor
        self.client.post('/login', data={'email': 'test.doctor@medicore.com', 'password': 'Password@123'})
        target_date = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')
        resp = self.client.get(f'/doctor/available-slots?date={target_date}')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('slots', data)

if __name__ == '__main__':
    unittest.main()
