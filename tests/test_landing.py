import unittest
from app import create_app
from app.config import Config
from app.extensions import db

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class LandingPageTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_landing_page_renders(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'MediCore+', response.data)
        self.assertIn(b'Your Health,', response.data)
        self.assertIn(b'Book an Appointment', response.data)
        self.assertIn(b'Sign In / Sign Up', response.data)
        self.assertIn(b'hero_doctor_patient.jpg', response.data)


if __name__ == '__main__':
    unittest.main()
