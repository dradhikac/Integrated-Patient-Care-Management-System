import unittest
from datetime import date, datetime
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.patients.models import Patient
from app.consultations.models import Consultation
from app.billing.models import Bill, BillItem, Payment
from app.billing.aggregator import generate_auto_bill_for_patient

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class BillingTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed roles & users
        admin_role = Role(name='Admin', description='Admin')
        rec_role = Role(name='Receptionist', description='Reception')
        doc_role = Role(name='Doctor', description='Doctor')
        db.session.add_all([admin_role, rec_role, doc_role])
        db.session.commit()

        self.receptionist = User(user_code='REC-001', name='Receptionist Mary', email='rec@test.com', role_id=rec_role.id)
        self.receptionist.set_password('Secret123!')
        
        self.doctor = User(user_code='DOC-001', name='Dr. Sharma', email='doc@test.com', role_id=doc_role.id)
        self.doctor.set_password('Secret123!')
        
        db.session.add_all([self.receptionist, self.doctor])
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
        self.client.post('/login', data={'email': 'rec@test.com', 'password': 'Secret123!'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_auto_bill_generation_and_totals(self):
        bill = generate_auto_bill_for_patient(
            patient_id=self.patient.id,
            discount=50.0,
            tax_percent=10.0,
            notes='Test invoice compilation'
        )
        self.assertIsNotNone(bill)
        self.assertTrue(bill.invoice_code.startswith('INV-2026-'))
        # Subtotal baseline (OPD Consultation = ₹500)
        self.assertEqual(bill.subtotal, 500.0)
        # Tax = 10% of 500 = 50.0
        self.assertEqual(bill.tax_amount, 50.0)
        # Grand total = 500 - 50 (discount) + 50 (tax) = 500.0
        self.assertEqual(bill.grand_total, 500.0)
        self.assertEqual(bill.status, 'UNPAID')
        self.assertEqual(bill.balance_due, 500.0)

    def test_payment_recording_and_status_transitions(self):
        bill = generate_auto_bill_for_patient(patient_id=self.patient.id, discount=0.0, tax_percent=0.0)
        # Grand Total = ₹500.0
        self.assertEqual(bill.grand_total, 500.0)

        # 1. Partial Payment of ₹200 via UPI
        res1 = self.client.post(f'/billing/{bill.id}/payment', data={
            'payment_method': 'UPI',
            'amount_paid': 200.0,
            'transaction_ref': 'UPI1234567890'
        }, follow_redirects=True)
        self.assertEqual(res1.status_code, 200)

        updated_bill = db.session.get(Bill, bill.id)
        self.assertEqual(updated_bill.paid_amount, 200.0)
        self.assertEqual(updated_bill.balance_due, 300.0)
        self.assertEqual(updated_bill.status, 'PARTIALLY_PAID')

        # 2. Final Payment of ₹300 via Cash
        res2 = self.client.post(f'/billing/{bill.id}/payment', data={
            'payment_method': 'Cash',
            'amount_paid': 300.0,
            'transaction_ref': 'CASH-001'
        }, follow_redirects=True)
        self.assertEqual(res2.status_code, 200)

        final_bill = db.session.get(Bill, bill.id)
        self.assertEqual(final_bill.paid_amount, 500.0)
        self.assertEqual(final_bill.balance_due, 0.0)
        self.assertEqual(final_bill.status, 'PAID')


if __name__ == '__main__':
    unittest.main()
