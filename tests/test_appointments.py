import unittest
from datetime import date, time, datetime, timedelta
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.appointments.models import DoctorAvailability, Holiday, Appointment, Waitlist
from app.appointments.slot_generator import generate_doctor_slots

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class AppointmentTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed roles
        doc_role = Role(name='Doctor', description='Doctor')
        pat_role = Role(name='Patient', description='Patient')
        db.session.add_all([doc_role, pat_role])
        db.session.commit()

        # Users
        self.doctor = User(user_code='DOC-001', name='Dr. Sharma', email='doc@test.com', role_id=doc_role.id)
        self.doctor.set_password('Secret123!')
        
        self.patient_user = User(user_code='PAT-001', name='Ananya Verma', email='patient@test.com', role_id=pat_role.id)
        self.patient_user.set_password('Secret123!')
        
        db.session.add_all([self.doctor, self.patient_user])
        db.session.commit()

        # Patients
        self.patient1 = Patient(
            patient_code='IPCMS-2026-000001',
            first_name='Ananya',
            last_name='Verma',
            full_name='Ananya Verma',
            dob=date(1995, 4, 10),
            gender='Female',
            mobile='9876543210',
            email='patient@test.com'
        )
        self.patient2 = Patient(
            patient_code='IPCMS-2026-000002',
            first_name='Rahul',
            last_name='Mehta',
            full_name='Rahul Mehta',
            dob=date(1990, 8, 20),
            gender='Male',
            mobile='9876500000',
            email='rahul@test.com'
        )
        db.session.add_all([self.patient1, self.patient2])
        db.session.commit()

        self.client = self.app.test_client()
        self.client.post('/login', data={'email': 'doc@test.com', 'password': 'Secret123!'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_slot_generator_and_holiday(self):
        target_date = date(2026, 9, 10) # Thursday
        
        # Test normal slot generation
        slot_data = generate_doctor_slots(self.doctor.id, target_date)
        self.assertTrue(slot_data['has_availability'])
        self.assertFalse(slot_data['is_holiday'])
        self.assertGreater(len(slot_data['slots']), 0)

        # Test emergency slot reservation
        emergency_slots = [s for s in slot_data['slots'] if s['is_emergency_reserved']]
        self.assertGreater(len(emergency_slots), 0)
        self.assertEqual(emergency_slots[0]['reason'], 'Emergency Held')

        # Add holiday and re-test
        holiday = Holiday(holiday_date=target_date, description='National Holiday')
        db.session.add(holiday)
        db.session.commit()

        holiday_slot_data = generate_doctor_slots(self.doctor.id, target_date)
        self.assertTrue(holiday_slot_data['is_holiday'])
        self.assertEqual(holiday_slot_data['holiday_reason'], 'National Holiday')
        self.assertEqual(len(holiday_slot_data['slots']), 0)

    def test_appointment_booking_and_auto_waitlist_promotion(self):
        target_date = date(2026, 9, 15)
        slot_t = time(10, 0)

        # Book Appointment for Patient 1
        apt1 = Appointment(
            appointment_code=Appointment.generate_appointment_code(),
            patient_id=self.patient1.id,
            doctor_id=self.doctor.id,
            appointment_date=target_date,
            slot_time=slot_t,
            booking_type='Online',
            status='BOOKED'
        )
        db.session.add(apt1)
        db.session.commit()

        # Add Patient 2 to Waitlist for same doctor and date
        waitlist_entry = Waitlist(
            patient_id=self.patient2.id,
            doctor_id=self.doctor.id,
            preferred_date=target_date,
            status='WAITING'
        )
        db.session.add(waitlist_entry)
        db.session.commit()

        # Cancel Appointment 1 -> Auto-Promote Patient 2!
        res = self.client.post(f'/appointments/cancel/{apt1.id}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify Apt 1 status is CANCELLED
        updated_apt1 = db.session.get(Appointment, apt1.id)
        self.assertEqual(updated_apt1.status, 'CANCELLED')

        # Verify Waitlist entry is PROMOTED
        updated_waitlist = db.session.get(Waitlist, waitlist_entry.id)
        self.assertEqual(updated_waitlist.status, 'PROMOTED')

        # Verify new appointment created for Patient 2 in slot 10:00 AM
        promoted_apt = Appointment.query.filter_by(patient_id=self.patient2.id, appointment_date=target_date).first()
        self.assertIsNotNone(promoted_apt)
        self.assertEqual(promoted_apt.slot_time, slot_t)


if __name__ == '__main__':
    unittest.main()
