import unittest
from datetime import date, datetime
from app import create_app
from app.config import Config
from app.extensions import db
from app.auth.models import Role, User
from app.admin.models import SystemSetting, AuditLog
from app.admin.backup import trigger_db_backup
from app.prescriptions.models import Medicine
from app.lab.models import LabTestType

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class AdminTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed roles & admin user
        admin_role = Role(name='Admin', description='Admin')
        doc_role = Role(name='Doctor', description='Doctor')
        db.session.add_all([admin_role, doc_role])
        db.session.commit()

        self.admin = User(user_code='ADM-001', name='System Admin', email='admin@test.com', role_id=admin_role.id)
        self.admin.set_password('Secret123!')
        db.session.add(self.admin)
        db.session.commit()

        self.client = self.app.test_client()
        self.client.post('/login', data={'email': 'admin@test.com', 'password': 'Secret123!'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_system_settings_and_audit_logs(self):
        SystemSetting.set_val('hospital_name', 'Test Hospital', 'Test Description')
        val = SystemSetting.get_val('hospital_name')
        self.assertEqual(val, 'Test Hospital')

        log = AuditLog(user_id=self.admin.id, action='TEST_ACTION', entity_type='System', entity_id=1, details='Test details')
        db.session.add(log)
        db.session.commit()

        fetched = AuditLog.query.filter_by(action='TEST_ACTION').first()
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.details, 'Test details')

    def test_staff_creation_and_toggle(self):
        doc_role = Role.query.filter_by(name='Doctor').first()
        res = self.client.post('/admin/users', data={
            'name': 'Dr. Test Doctor',
            'email': 'drtest@test.com',
            'password': 'Password123!',
            'role_id': doc_role.id,
            'phone': '9876543210',
            'specialization': 'General Medicine'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        created_user = User.query.filter_by(email='drtest@test.com').first()
        self.assertIsNotNone(created_user)
        self.assertTrue(created_user.is_active)

        # Toggle status
        toggle_res = self.client.post(f'/admin/users/toggle/{created_user.id}', follow_redirects=True)
        self.assertEqual(toggle_res.status_code, 200)
        updated_user = db.session.get(User, created_user.id)
        self.assertFalse(updated_user.is_active)

    def test_master_data_medicines_and_lab_tests(self):
        res_med = self.client.post('/admin/master-data/medicines', data={
            'brand_name': 'TestMed 500',
            'generic_name': 'TestGeneric',
            'category': 'Tablet',
            'dosage': '500mg',
            'unit_price': 25.0,
            'stock_quantity': 100,
            'manufacturer': 'TestPharma'
        }, follow_redirects=True)
        self.assertEqual(res_med.status_code, 200)
        med = Medicine.query.filter_by(brand_name='TestMed 500').first()
        self.assertIsNotNone(med)

        res_lab = self.client.post('/admin/master-data/lab-tests', data={
            'test_code': 'LAB-TST',
            'test_name': 'Test Lab Examination',
            'category': 'Hematology',
            'price': 300.0,
            'normal_range': '10-20',
            'unit': 'units'
        }, follow_redirects=True)
        self.assertEqual(res_lab.status_code, 200)
        lab = LabTestType.query.filter_by(test_code='LAB-TST').first()
        self.assertIsNotNone(lab)

    def test_db_backup_trigger(self):
        result = trigger_db_backup(admin_user_id=self.admin.id)
        self.assertIn('filename', result)
        self.assertIn('file_size_kb', result)
        self.assertTrue(result['filename'].startswith('ipcms_backup_'))


if __name__ == '__main__':
    unittest.main()
