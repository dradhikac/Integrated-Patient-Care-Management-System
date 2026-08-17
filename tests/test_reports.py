import unittest
from datetime import date, datetime
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.reports.analytics import (
    get_today_admin_kpis,
    get_monthly_revenue_trend,
    get_appointment_status_breakdown,
    get_departmental_revenue_share
)
from app.reports.exporter import generate_csv_report

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ReportsTestCase(unittest.TestCase):
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

    def test_admin_kpis_and_chart_datasets(self):
        kpis = get_today_admin_kpis()
        self.assertIsNotNone(kpis)
        self.assertEqual(kpis['patients_today'], 1)
        self.assertIn('revenue_today', kpis)
        self.assertIn('doctors_available', kpis)
        self.assertIn('appointments_today', kpis)

        trend = get_monthly_revenue_trend()
        self.assertIn('labels', trend)
        self.assertIn('amounts', trend)

        status_bd = get_appointment_status_breakdown()
        self.assertIn('BOOKED', status_bd)

    def test_csv_exporters(self):
        csv_pat = generate_csv_report('patient')
        self.assertTrue('Patient Code' in csv_pat)
        self.assertTrue('Ananya Verma' in csv_pat)

        csv_rev = generate_csv_report('revenue')
        self.assertTrue('Invoice Code' in csv_rev)

    def test_report_routes(self):
        res_dash = self.client.get('/reports/dashboard')
        self.assertEqual(res_dash.status_code, 200)

        for rep in ['patient', 'revenue', 'doctor', 'appointment', 'lab']:
            res_csv = self.client.get(f'/reports/export/{rep}?format=csv')
            self.assertEqual(res_csv.status_code, 200)
            self.assertEqual(res_csv.mimetype, 'text/csv')

            res_pdf = self.client.get(f'/reports/export/{rep}?format=pdf')
            self.assertEqual(res_pdf.status_code, 200)


if __name__ == '__main__':
    unittest.main()
