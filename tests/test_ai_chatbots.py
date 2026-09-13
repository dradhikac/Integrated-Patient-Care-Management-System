import unittest
from datetime import date, time, datetime, timedelta
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.doctors.models import Doctor
from app.admin.models import Department
from app.appointments.models import DoctorAvailability, Holiday, Appointment, Waitlist
from app.ai.tools_public import (
    public_get_departments,
    public_search_doctors,
    public_check_doctor_availability,
    public_find_available_slots,
    public_book_appointment
)
from app.ai.tools_patient import (
    patient_get_departments,
    patient_search_doctors,
    patient_find_available_slots,
    patient_get_my_appointments,
    patient_book_appointment,
    patient_reschedule_appointment,
    patient_cancel_appointment
)

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class AIChatbotTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Seed roles
        doc_role = Role(name='Doctor', description='Doctor')
        pat_role = Role(name='Patient', description='Patient')
        rec_role = Role(name='Receptionist', description='Receptionist')
        db.session.add_all([doc_role, pat_role, rec_role])
        db.session.commit()

        # Seed Department
        dept = Department(
            dept_code='DEP-CARD',
            dept_name='Cardiology',
            category='Clinical',
            operating_hours='08:00 AM - 08:00 PM',
            is_active=True
        )
        db.session.add(dept)
        db.session.commit()

        # Seed Doctor User & Profile
        self.doc_user = User(
            user_code='DOC-001',
            name='Dr. Rajesh Sharma',
            email='rajesh.sharma@carehub.test',
            role_id=doc_role.id
        )
        self.doc_user.set_password('Secret123!')
        db.session.add(self.doc_user)
        db.session.commit()

        self.doc_profile = Doctor(
            user_id=self.doc_user.id,
            doctor_code='DOC-001',
            name='Dr. Rajesh Sharma',
            department='Cardiology',
            specialization='Cardiology',
            education='MBBS, MD',
            experience='12 Years',
            consultation_fee=500.0,
            image_url='/static/images/doctors/rajesh.jpg',
            available_days='Monday - Saturday',
            rating=4.9,
            is_active=True
        )
        db.session.add(self.doc_profile)
        db.session.commit()

        # Seed Doctor Availability (All weekdays 09:00 - 17:00, slot duration 15)
        for day_idx in range(7):
            avail = DoctorAvailability(
                doctor_id=self.doc_user.id,
                day_of_week=day_idx,
                start_time=time(9, 0),
                end_time=time(17, 0),
                slot_duration_minutes=15,
                is_active=True
            )
            db.session.add(avail)
        db.session.commit()

        # Seed Patient 1 (Primary)
        self.pat_user1 = User(
            user_code='PAT-001',
            name='Ananya Verma',
            email='ananya@carehub.test',
            role_id=pat_role.id
        )
        self.pat_user1.set_password('PatientPass123!')
        db.session.add(self.pat_user1)
        db.session.commit()

        self.patient1 = Patient(
            patient_code='IPCMS-2026-000001',
            portal_user_id=self.pat_user1.id,
            first_name='Ananya',
            last_name='Verma',
            full_name='Ananya Verma',
            dob=date(1995, 4, 10),
            gender='Female',
            mobile='9876543210',
            email='ananya@carehub.test'
        )
        db.session.add(self.patient1)

        # Seed Patient 2 (Secondary, for access boundary tests)
        self.pat_user2 = User(
            user_code='PAT-002',
            name='Rahul Mehta',
            email='rahul@carehub.test',
            role_id=pat_role.id
        )
        self.pat_user2.set_password('PatientPass123!')
        db.session.add(self.pat_user2)
        db.session.commit()

        self.patient2 = Patient(
            patient_code='IPCMS-2026-000002',
            portal_user_id=self.pat_user2.id,
            first_name='Rahul',
            last_name='Mehta',
            full_name='Rahul Mehta',
            dob=date(1990, 8, 20),
            gender='Male',
            mobile='9876500000',
            email='rahul@carehub.test'
        )
        db.session.add(self.patient2)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # ==========================================
    # PUBLIC AI TOOLS TESTS
    # ==========================================

    def test_public_get_departments(self):
        depts = public_get_departments()
        self.assertGreaterEqual(len(depts), 1)
        dept_names = [d['name'] for d in depts]
        self.assertIn('Cardiology', dept_names)

    def test_public_search_doctors(self):
        doctors = public_search_doctors(query='Cardiology')
        self.assertGreaterEqual(len(doctors), 1)
        self.assertEqual(doctors[0]['name'], 'Dr. Rajesh Sharma')
        self.assertEqual(doctors[0]['department'], 'Cardiology')

    def test_public_find_available_slots(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        res = public_find_available_slots(doctor_id=self.doc_user.id, target_date_str=tomorrow)
        self.assertNotIn('error', res)
        self.assertGreater(res['available_slots_count'], 0)
        slot_times = [s['time_24h'] for s in res['slots']]
        self.assertIn('09:00', slot_times)

    def test_public_book_appointment_workflow(self):
        target_date = (date.today() + timedelta(days=2)).isoformat()
        
        # 1. Unconfirmed request returns summary for confirmation
        res_summary = public_book_appointment(
            patient_name='Ananya Verma',
            patient_mobile='9876543210',
            patient_email='ananya@carehub.test',
            doctor_id=self.doc_user.id,
            appointment_date_str=target_date,
            slot_time_str='10:00',
            reason='Routine cardiac checkup',
            confirmed=False
        )
        self.assertTrue(res_summary['success'])
        self.assertTrue(res_summary['requires_confirmation'])

        # 2. Confirmed booking for existing patient
        res_book = public_book_appointment(
            patient_name='Ananya Verma',
            patient_mobile='9876543210',
            patient_email='ananya@carehub.test',
            doctor_id=self.doc_user.id,
            appointment_date_str=target_date,
            slot_time_str='10:00',
            reason='Routine cardiac checkup',
            confirmed=True
        )
        self.assertTrue(res_book['success'])
        self.assertIn('appointment_code', res_book)

        # 3. Attempt double booking for same doctor & slot -> must fail gracefully
        res_dup = public_book_appointment(
            patient_name='New Guest',
            patient_mobile='9999999999',
            patient_email='guest@carehub.test',
            doctor_id=self.doc_user.id,
            appointment_date_str=target_date,
            slot_time_str='10:00',
            reason='Consultation',
            confirmed=True
        )
        self.assertFalse(res_dup['success'])
        self.assertIn('booked', res_dup['error'].lower())

        # 4. Book for a brand new guest patient (auto-creates patient record)
        res_new = public_book_appointment(
            patient_name='Sunita Roy',
            patient_mobile='9123456789',
            patient_email='sunita@test.com',
            doctor_id=self.doc_user.id,
            appointment_date_str=target_date,
            slot_time_str='10:15',
            reason='General checkup',
            confirmed=True
        )
        self.assertTrue(res_new['success'])
        new_pat = Patient.query.filter_by(mobile='9123456789').first()
        self.assertIsNotNone(new_pat)
        self.assertEqual(new_pat.full_name, 'Sunita Roy')

    # ==========================================
    # PUBLIC SECURITY REFUSAL ROUTE TESTS
    # ==========================================

    def test_public_chat_cancellation_refusal(self):
        res = self.client.post('/api/ai/public/chat', json={
            'messages': [{'role': 'user', 'content': 'I want to cancel my appointment for tomorrow'}]
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('sign in', data['message']['content'].lower())
        self.assertIn('cancel', data['message']['content'].lower())

    def test_public_chat_reschedule_refusal(self):
        res = self.client.post('/api/ai/public/chat', json={
            'messages': [{'role': 'user', 'content': 'Can you reschedule my appointment to Monday?'}]
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('sign in', data['message']['content'].lower())
        self.assertIn('reschedule', data['message']['content'].lower())

    def test_public_chat_ehr_refusal(self):
        res = self.client.post('/api/ai/public/chat', json={
            'messages': [{'role': 'user', 'content': 'Show my medical records and prescriptions'}]
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('signing in', data['message']['content'].lower())

    # ==========================================
    # AUTHENTICATED PATIENT AI TOOLS TESTS
    # ==========================================

    def test_patient_tools_booking_and_history(self):
        target_date = (date.today() + timedelta(days=3)).isoformat()
        
        # Book appointment as Patient 1
        book_res = patient_book_appointment(
            current_patient_id=self.patient1.id,
            doctor_id=self.doc_user.id,
            appointment_date_str=target_date,
            slot_time_str='11:00',
            reason='Follow-up cardiology consultation',
            confirmed=True
        )
        self.assertTrue(book_res['success'])
        apt_code = book_res['appointment_code']

        # Query history for Patient 1 -> Should include the newly booked appointment
        hist_res1 = patient_get_my_appointments(current_patient_id=self.patient1.id)
        self.assertEqual(hist_res1['total_active_appointments'], 1)
        self.assertEqual(hist_res1['appointments'][0]['appointment_code'], apt_code)

        # Query history for Patient 2 -> Must be empty (strict patient isolation)
        hist_res2 = patient_get_my_appointments(current_patient_id=self.patient2.id)
        self.assertEqual(hist_res2['total_active_appointments'], 0)

    def test_patient_reschedule_and_cross_patient_protection(self):
        target_date1 = (date.today() + timedelta(days=4)).isoformat()
        target_date2 = (date.today() + timedelta(days=5)).isoformat()

        # Create appointment for Patient 1
        appt = Appointment(
            appointment_code='APT-P1-001',
            patient_id=self.patient1.id,
            doctor_id=self.doc_user.id,
            appointment_date=date.fromisoformat(target_date1),
            slot_time=time(14, 0),
            status='BOOKED',
            booking_type='Online',
            notes='Initial consultation'
        )
        db.session.add(appt)
        db.session.commit()

        # Attempt to reschedule Patient 1's appointment using Patient 2's ID -> Must fail
        hack_res = patient_reschedule_appointment(
            current_patient_id=self.patient2.id,
            appointment_id=appt.id,
            new_date_str=target_date2,
            new_slot_time_str='15:00',
            confirmed=True
        )
        self.assertFalse(hack_res['success'])
        self.assertIn('Access denied', hack_res['error'])

        # Reschedule using Patient 1's authentic ID -> Must succeed
        valid_res = patient_reschedule_appointment(
            current_patient_id=self.patient1.id,
            appointment_id=appt.id,
            new_date_str=target_date2,
            new_slot_time_str='15:00',
            reason='Schedule conflict',
            confirmed=True
        )
        self.assertTrue(valid_res['success'])
        self.assertEqual(valid_res['appointment_code'], 'APT-P1-001')

    def test_patient_cancel_and_waitlist_promotion(self):
        target_date = (date.today() + timedelta(days=6)).isoformat()

        # Create booked appointment for Patient 1
        appt = Appointment(
            appointment_code='APT-P1-002',
            patient_id=self.patient1.id,
            doctor_id=self.doc_user.id,
            appointment_date=date.fromisoformat(target_date),
            slot_time=time(16, 0),
            status='BOOKED',
            booking_type='Online',
            notes='Consultation'
        )
        db.session.add(appt)
        db.session.commit()

        # Add Patient 2 to Waitlist for same doctor and date
        waitlist_entry = Waitlist(
            patient_id=self.patient2.id,
            doctor_id=self.doc_user.id,
            preferred_date=date.fromisoformat(target_date),
            status='WAITING'
        )
        db.session.add(waitlist_entry)
        db.session.commit()

        # Patient 2 tries to cancel Patient 1's appointment -> Must fail
        tamper_res = patient_cancel_appointment(
            current_patient_id=self.patient2.id,
            appointment_id=appt.id,
            confirmed=True
        )
        self.assertFalse(tamper_res['success'])
        self.assertIn('Access denied', tamper_res['error'])

        # Patient 1 cancels own appointment -> Must succeed and promote waitlist entry
        cancel_res = patient_cancel_appointment(
            current_patient_id=self.patient1.id,
            appointment_id=appt.id,
            confirmed=True
        )
        self.assertTrue(cancel_res['success'])
        self.assertTrue(cancel_res['waitlist_promoted'])

        # Check that waitlist entry was offered slot
        updated_wl = Waitlist.query.get(waitlist_entry.id)
        self.assertEqual(updated_wl.status, 'OFFERED')
        self.assertEqual(updated_wl.offered_slot_time, time(16, 0))


if __name__ == '__main__':
    unittest.main()
