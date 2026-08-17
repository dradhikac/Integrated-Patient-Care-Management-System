import unittest
from datetime import date, datetime
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.analytics.reports import get_hospital_analytics_summary, generate_invoices_csv_report, generate_patients_csv_report

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class AnalyticsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed roles & users
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
            mobile='9876543210'
        )
        db.session.add(self.patient)
        db.session.commit()

        self.client = self.app.test_client()
        self.client.post('/login', data={'email': 'admin@test.com', 'password': 'Secret123!'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_analytics_summary_kpis(self):
        summary = get_hospital_analytics_summary()
        self.assertIsNotNone(summary)
        self.assertEqual(summary['total_patients'], 1)
        self.assertIn('total_billed', summary)
        self.assertIn('total_collected', summary)
        self.assertIn('occupancy_rate', summary)

    def test_csv_export_reports(self):
        inv_csv = generate_invoices_csv_report()
        self.assertTrue('Invoice Code' in inv_csv)

        pat_csv = generate_patients_csv_report()
        self.assertTrue('Patient Code' in pat_csv)
        self.assertTrue('Ananya Verma' in pat_csv)

    def test_export_routes(self):
        res_inv = self.client.get('/analytics/export/invoices')
        self.assertEqual(res_inv.status_code, 200)
        self.assertEqual(res_inv.mimetype, 'text/csv')

        res_pat = self.client.get('/analytics/export/patients')
        self.assertEqual(res_pat.status_code, 200)
        self.assertEqual(res_pat.mimetype, 'text/csv')


if __name__ == '__main__':
    unittest.main()
