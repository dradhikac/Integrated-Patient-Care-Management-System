import unittest
from datetime import datetime, timedelta
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import User, Role, LoginLog, PasswordResetToken

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed roles
        self.admin_role = Role(name='Admin', description='Admin role')
        self.doctor_role = Role(name='Doctor', description='Doctor role')
        db.session.add_all([self.admin_role, self.doctor_role])
        db.session.commit()

        # Seed admin user
        self.admin_user = User(
            user_code='ADM-100',
            name='Test Admin',
            email='admin@test.com',
            role_id=self.admin_role.id
        )
        self.admin_user.set_password('Secret123!')
        db.session.add(self.admin_user)
        db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        self.assertTrue(self.admin_user.check_password('Secret123!'))
        self.assertFalse(self.admin_user.check_password('WrongPassword'))

    def test_successful_login(self):
        response = self.client.post('/login', data={
            'email': 'admin@test.com',
            'password': 'Secret123!'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome back', response.data)
        
        # Verify LoginLog entry
        log = LoginLog.query.filter_by(email_attempted='admin@test.com').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, 'SUCCESS')

    def test_failed_login_and_lockout(self):
        # 5 failed login attempts
        for i in range(5):
            self.client.post('/login', data={
                'email': 'admin@test.com',
                'password': 'WrongPassword'
            })
        
        updated_user = User.query.filter_by(email='admin@test.com').first()
        self.assertTrue(updated_user.is_account_locked())
        
        # 6th attempt should return locked account error message
        response = self.client.post('/login', data={
            'email': 'admin@test.com',
            'password': 'Secret123!'
        }, follow_redirects=True)
        
        self.assertIn(b'Account locked', response.data)

    def test_forgot_password_otp_flow(self):
        response = self.client.post('/forgot-password', data={
            'email': 'admin@test.com'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Check token created in DB
        token_record = PasswordResetToken.query.filter_by(user_id=self.admin_user.id).first()
        self.assertIsNotNone(token_record)
        self.assertEqual(len(token_record.otp_code), 6)

        # Submit valid OTP and new password
        reset_response = self.client.post(f'/reset-password?token={token_record.token}', data={
            'otp_code': token_record.otp_code,
            'password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!'
        }, follow_redirects=True)
        
        self.assertIn(b'password has been successfully reset', reset_response.data)
        self.assertTrue(self.admin_user.check_password('NewPassword123!'))


if __name__ == '__main__':
    unittest.main()
