import unittest
from datetime import date, datetime, timedelta
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.reception.models import CheckIn
from app.queue_mgmt.models import QueuePriorityRule
from app.queue_mgmt.priority_engine import sort_queue_by_priority, calculate_rolling_avg_consultation_time

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class QueueTestCase(unittest.TestCase):
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

        self.receptionist = User(user_code='REC-001', name='Reception', email='rec@test.com', role_id=rec_role.id)
        self.receptionist.set_password('Secret123!')
        
        self.doctor = User(user_code='DOC-001', name='Dr. Sharma', email='doc@test.com', role_id=doc_role.id)
        self.doctor.set_password('Secret123!')
        
        db.session.add_all([self.receptionist, self.doctor])
        db.session.commit()

        # Seed patients
        self.patient_reg = Patient(patient_code='IPCMS-2026-000001', first_name='Regular', last_name='Pat', full_name='Regular Pat', dob=date(1990, 1, 1), gender='Male', mobile='9999900001')
        self.patient_emg = Patient(patient_code='IPCMS-2026-000002', first_name='Emergency', last_name='Pat', full_name='Emergency Pat', dob=date(1992, 2, 2), gender='Female', mobile='9999900002')
        self.patient_snr = Patient(patient_code='IPCMS-2026-000003', first_name='Senior', last_name='Pat', full_name='Senior Pat', dob=date(1950, 3, 3), gender='Male', mobile='9999900003')

        db.session.add_all([self.patient_reg, self.patient_emg, self.patient_snr])
        db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_priority_sorting_engine(self):
        now = datetime.utcnow()
        c_reg = CheckIn(patient_id=self.patient_reg.id, doctor_id=self.doctor.id, token_no='TK-001', priority='Regular', check_in_time=now, checked_in_by_id=self.receptionist.id)
        c_emg = CheckIn(patient_id=self.patient_emg.id, doctor_id=self.doctor.id, token_no='TK-002', priority='Emergency', check_in_time=now + timedelta(minutes=5), checked_in_by_id=self.receptionist.id)
        c_snr = CheckIn(patient_id=self.patient_snr.id, doctor_id=self.doctor.id, token_no='TK-003', priority='Senior Citizen', check_in_time=now + timedelta(minutes=2), checked_in_by_id=self.receptionist.id)

        queue_list = [c_reg, c_emg, c_snr]
        sorted_q = sort_queue_by_priority(queue_list)

        # Expected order: Emergency (TK-002) -> Senior (TK-003) -> Regular (TK-001)
        self.assertEqual(sorted_q[0].token_no, 'TK-002')
        self.assertEqual(sorted_q[1].token_no, 'TK-003')
        self.assertEqual(sorted_q[2].token_no, 'TK-001')

    def test_rolling_avg_consultation_time(self):
        now = datetime.utcnow()
        # Visit 1: 12 minutes duration
        v1 = CheckIn(
            patient_id=self.patient_reg.id, doctor_id=self.doctor.id, token_no='TK-001', status='COMPLETED',
            called_time=now - timedelta(minutes=20), completed_time=now - timedelta(minutes=8),
            checked_in_by_id=self.receptionist.id
        )
        # Visit 2: 8 minutes duration
        v2 = CheckIn(
            patient_id=self.patient_emg.id, doctor_id=self.doctor.id, token_no='TK-002', status='COMPLETED',
            called_time=now - timedelta(minutes=10), completed_time=now - timedelta(minutes=2),
            checked_in_by_id=self.receptionist.id
        )
        db.session.add_all([v1, v2])
        db.session.commit()

        avg_mins = calculate_rolling_avg_consultation_time(self.doctor.id)
        # (12 + 8) / 2 = 10.0 mins
        self.assertEqual(avg_mins, 10.0)

    def test_live_status_api(self):
        res = self.client.get('/queue/api/live-status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('now_serving', data)
        self.assertIn('next_token', data)
        self.assertIn('waiting_count', data)


if __name__ == '__main__':
    unittest.main()
