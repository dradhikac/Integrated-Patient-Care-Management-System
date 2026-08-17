import unittest
from datetime import date, datetime
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.notifications.models import Notification, NotificationLog
from app.notifications.dispatcher import dispatch_single_notification, scan_and_queue_reminders

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class NotificationsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed role & user
        admin_role = Role(name='Admin', description='Admin')
        db.session.add(admin_role)
        db.session.commit()

        self.admin = User(user_code='ADM-001', name='System Admin', email='admin@test.com', role_id=admin_role.id)
        self.admin.set_password('Secret123!')
        db.session.add(self.admin)
        db.session.commit()

        # Patient
        self.patient = Patient(
            patient_code='IPCMS-2026-000001',
            first_name='Ananya',
            last_name='Verma',
            full_name='Ananya Verma',
            dob=date(1995, 4, 10),
            gender='Female',
            mobile='9876543210',
            email='ananya@test.com'
        )
        db.session.add(self.patient)
        db.session.commit()

        self.client = self.app.test_client()
        self.client.post('/login', data={'email': 'admin@test.com', 'password': 'Secret123!'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_notification_creation_and_async_dispatch(self):
        notif = Notification(
            patient_id=self.patient.id,
            type='APPOINTMENT_REMINDER',
            title='Test Appointment Reminder',
            message='Your appointment is scheduled for tomorrow at 10:00 AM.',
            channel='BOTH',
            status='PENDING'
        )
        db.session.add(notif)
        db.session.commit()

        self.assertEqual(notif.status, 'PENDING')

        # Execute dispatch
        dispatch_single_notification(notif.id)

        updated_notif = db.session.get(Notification, notif.id)
        self.assertEqual(updated_notif.status, 'SENT')

        # Verify logs in notification_log
        logs = NotificationLog.query.filter_by(notification_id=notif.id).all()
        self.assertEqual(len(logs), 2) # Email + SMS
        channels = [l.channel for l in logs]
        self.assertIn('EMAIL', channels)
        self.assertIn('SMS', channels)

    def test_trigger_job_route(self):
        res = self.client.post('/notifications/trigger-job', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertTrue('Background Reminder Scan completed' in res.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
