import os
import click
from flask import Flask
from app.config import Config
from app.extensions import db, login_manager, bcrypt, migrate, csrf

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Register Blueprints
    from app.auth.routes import auth_bp
    from app.patients.routes import patients_bp
    from app.reception.routes import reception_bp
    from app.appointments.routes import appointments_bp
    from app.queue_mgmt.routes import queue_bp
    from app.ehr.routes import ehr_bp
    from app.consultations.routes import consultations_bp
    from app.prescriptions.routes import prescriptions_bp
    from app.lab.routes import lab_bp
    from app.billing.routes import billing_bp
    from app.beds.routes import beds_bp
    from app.analytics.routes import analytics_bp
    from app.notifications.routes import notifications_bp
    from app.reports.routes import reports_bp
    from app.admin.routes import admin_bp
    from app.doctors.routes import doctors_bp
    from app.portal import portal_bp
    from app.doctor_portal import doctor_portal_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(reception_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(queue_bp)
    app.register_blueprint(ehr_bp)
    app.register_blueprint(consultations_bp)
    app.register_blueprint(prescriptions_bp)
    app.register_blueprint(lab_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(beds_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(doctors_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(doctor_portal_bp)

    csrf.exempt(doctors_bp)

    # Jinja2 globals
    from datetime import datetime as _dt
    app.jinja_env.globals['now'] = _dt.now
    app.jinja_env.globals['enumerate'] = enumerate


    def _run_seed():
        from app.auth.models import Role, User
        from app.admin.models import SystemSetting
        from app.prescriptions.models import Medicine
        from app.lab.models import LabTestType
        from app.beds.models import Ward, Bed
        from app.doctors.models import Doctor

        try:
            db.create_all()

            # Seed Roles
            roles_data = [
                ('Admin', 'System administrator with full control'),
                ('Receptionist', 'Front desk check-in and queue operator'),
                ('Doctor', 'Consultation, EHR timeline, and digital prescriptions'),
                ('Lab Technician', 'Laboratory test requests and report uploads'),
                ('Patient', 'Patient health portal access')
            ]
            roles_dict = {}
            for r_name, r_desc in roles_data:
                role = Role.query.filter_by(name=r_name).first()
                if not role:
                    role = Role(name=r_name, description=r_desc)
                    db.session.add(role)
                    db.session.flush()
                roles_dict[r_name] = role
            db.session.commit()

            # Seed Demo Users
            sample_users = [
                ('ADM-001', 'System Administrator', 'admin@ipcms.com', 'Admin'),
                ('REC-001', 'Reception Desk Officer', 'reception@ipcms.com', 'Receptionist'),
                ('DOC-001', 'Dr. Rajesh Sharma', 'doctor@ipcms.com', 'Doctor'),
                ('LAB-001', 'Suresh Kumar (Lab Tech)', 'lab@ipcms.com', 'Lab Technician'),
                ('PAT-001', 'Ananya Verma', 'patient@ipcms.com', 'Patient')
            ]
            for code, name, email, role_name in sample_users:
                user = User.query.filter_by(email=email).first()
                if not user:
                    user = User(
                        user_code=code,
                        name=name,
                        email=email,
                        role_id=roles_dict[role_name].id,
                        mobile='+91-9876543210',
                        is_active=True
                    )
                    user.set_password('Password@123')
                    db.session.add(user)
                else:
                    user.role_id = roles_dict[role_name].id
                    user.set_password('Password@123')
            db.session.commit()
        except Exception as e:
            db.session.rollback()

    with app.app_context():
        try:
            if not app.config.get('TESTING'):
                _run_seed()
            else:
                db.create_all()
        except Exception:
            pass

    # CLI Command to seed database roles and demo users
    @app.cli.command("seed-db")
    def seed_db():
        """Seeds initial database roles and sample accounts for all 5 roles."""
        from app.auth.models import Role, User
        from app.patients.models import Patient, PatientMedicalHistory, PatientAllergy
        from app.reception.models import CheckIn
        from app.appointments.models import DoctorAvailability, Holiday, Appointment, Waitlist
        from app.queue_mgmt.models import QueuePriorityRule
        from app.consultations.models import Consultation, Vital
        from app.prescriptions.models import Medicine, Prescription, PrescriptionItem
        from app.lab.models import LabTestType, LabRequest, LabResult
        from app.billing.models import Bill, BillItem, Payment
        from app.beds.models import Ward, Bed, Admission, BedTransfer
        from app.notifications.models import Notification, NotificationLog
        from app.admin.models import SystemSetting, AuditLog

        db.create_all()

        # Seed System Settings
        default_settings = [
            ('hospital_name', 'IPCMS Healthcare Hospital', 'Official Hospital Name'),
            ('opd_consultation_fee', '500.0', 'Standard OPD Consultation Fee'),
            ('ipd_bed_rate_general', '1500.0', 'General Ward Bed Daily Rate'),
            ('ipd_bed_rate_icu', '5000.0', 'ICU Ward Bed Daily Rate'),
            ('gst_tax_rate', '18.0', 'GST / Service Tax Percentage'),
            ('emergency_surcharge', '1000.0', 'Emergency Care Surcharge')
        ]
        for skey, sval, sdesc in default_settings:
            if not SystemSetting.query.filter_by(setting_key=skey).first():
                db.session.add(SystemSetting(setting_key=skey, setting_value=sval, description=sdesc))
        db.session.commit()

        roles_data = [
            ('Admin', 'System administrator with full control'),
            ('Receptionist', 'Front desk check-in and queue operator'),
            ('Doctor', 'Consultation, EHR timeline, and digital prescriptions'),
            ('Lab Technician', 'Laboratory test requests and report uploads'),
            ('Patient', 'Patient health portal access')
        ]

        roles_dict = {}
        for r_name, r_desc in roles_data:
            role = Role.query.filter_by(name=r_name).first()
            if not role:
                role = Role(name=r_name, description=r_desc)
                db.session.add(role)
                db.session.flush()
                click.echo(f"Created role: {r_name}")
            roles_dict[r_name] = role

        db.session.commit()

        # Seed initial Drug Master catalog if empty
        if Medicine.query.count() == 0:
            sample_meds = [
                ('Dolo 650', 'Paracetamol', 'Tablet', '650mg'),
                ('Crocin 500', 'Paracetamol', 'Tablet', '500mg'),
                ('Mox 500', 'Amoxicillin', 'Capsule', '500mg'),
                ('Azee 500', 'Azithromycin', 'Tablet', '500mg'),
                ('Cetzine', 'Cetirizine', 'Tablet', '10mg'),
                ('Pan 40', 'Pantoprazole', 'Tablet', '40mg'),
                ('Benadryl', 'Diphenhydramine', 'Syrup', '100ml')
            ]
            for b_name, g_name, form_type, strn in sample_meds:
                med = Medicine(brand_name=b_name, generic_name=g_name, dosage_form=form_type, strength=strn)
                db.session.add(med)
            click.echo("Seeded initial Drug Master catalog with common medications.")
            db.session.commit()

        # Seed initial Lab Test Types catalog if empty
        if LabTestType.query.count() == 0:
            sample_tests = [
                ('TST-CBC-HB', 'Hemoglobin (Hb)', 'Haematology', 'g/dL', 12.0, 16.0, 300.0),
                ('TST-CBC-WBC', 'Total Leucocyte Count (TLC)', 'Haematology', 'cells/mcL', 4000.0, 11000.0, 350.0),
                ('TST-FBS', 'Fasting Blood Sugar (FBS)', 'Biochemistry', 'mg/dL', 70.0, 100.0, 250.0),
                ('TST-KFT-CREAT', 'Serum Creatinine', 'Biochemistry', 'mg/dL', 0.6, 1.2, 400.0),
                ('TST-LFT-BIL', 'Total Bilirubin', 'Biochemistry', 'mg/dL', 0.2, 1.2, 450.0),
                ('TST-LIP-CHOL', 'Serum Cholesterol', 'Biochemistry', 'mg/dL', 125.0, 200.0, 500.0),
                ('TST-XRAY-CHEST', 'Chest X-Ray PA View', 'Radiology', 'Scan', None, None, 600.0),
                ('TST-ECG-12', 'ECG 12-Lead Standard', 'Cardiology', 'Graph', None, None, 450.0)
            ]
            for t_code, t_name, cat, unit, min_n, max_n, cst in sample_tests:
                tt = LabTestType(test_code=t_code, test_name=t_name, category=cat, unit=unit, min_normal_val=min_n, max_normal_val=max_n, cost=cst)
                db.session.add(tt)
            click.echo("Seeded initial Lab Test Types master catalog.")
            db.session.commit()

        # Seed initial Ward catalog & Bed capacity if empty
        if Ward.query.count() == 0:
            sample_wards = [
                ('WRD-ICU', 'Intensive Care Unit (ICU)', 'ICU', 2500.0, [f"BED-ICU-{i:02d}" for i in range(1, 6)]),
                ('WRD-GEN-A', 'General Ward A (Male)', 'General Ward', 800.0, [f"BED-GEN-A-{i:02d}" for i in range(1, 9)]),
                ('WRD-GEN-B', 'General Ward B (Female)', 'General Ward', 800.0, [f"BED-GEN-B-{i:02d}" for i in range(1, 9)]),
                ('WRD-PVT-01', 'Private Deluxe Suites', 'Private Suite', 3500.0, [f"BED-PVT-{i:02d}" for i in range(1, 5)])
            ]
            for w_code, w_name, cat, rate, bed_codes in sample_wards:
                ward = Ward(ward_code=w_code, ward_name=w_name, category=cat, daily_rate=rate)
                db.session.add(ward)
                db.session.flush()
                for b_code in bed_codes:
                    bed = Bed(ward_id=ward.id, bed_code=b_code, status='AVAILABLE')
                    db.session.add(bed)
            click.echo("Seeded initial Ward catalog & Bed capacity.")
            db.session.commit()

        # Seed sample users for each role
        sample_users = [
            ('ADM-001', 'System Administrator', 'admin@ipcms.com', 'Admin'),
            ('REC-001', 'Reception Desk Officer', 'reception@ipcms.com', 'Receptionist'),
            ('DOC-001', 'Dr. Rajesh Sharma', 'doctor@ipcms.com', 'Doctor'),
            ('LAB-001', 'Suresh Kumar (Lab Tech)', 'lab@ipcms.com', 'Lab Technician'),
            ('PAT-001', 'Ananya Verma', 'patient@ipcms.com', 'Patient')
        ]

        for code, name, email, role_name in sample_users:
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    user_code=code,
                    name=name,
                    email=email,
                    role_id=roles_dict[role_name].id,
                    mobile='+91-9876543210',
                    is_active=True
                )
                user.set_password('Password@123')
                db.session.add(user)
                click.echo(f"Created demo user: {email} ({role_name})")
            else:
                user.role_id = roles_dict[role_name].id
                user.set_password('Password@123')
                user.is_active = True

        db.session.commit()

        # Seed sample doctors catalog
        from app.doctors.models import Doctor
        doc_role = roles_dict.get('Doctor')

        sample_doctors = [
            {'code': 'DOC-101', 'name': 'Dr. Ananya Sharma', 'specialization': 'Cardiologist', 'education': 'MBBS, MD (General Medicine), DM (Cardiology)', 'experience': '5+ Years', 'department': 'Cardiology & Heart Institute', 'bio': 'Experienced cardiologist specializing in non-invasive cardiac care, preventive cardiology, heart failure management, and echocardiography.', 'fee': 800.0, 'image_url': '/static/images/doctors/dr_ananya_sharma.jpg', 'email': 'ananya.sharma@medicore.com'},
            {'code': 'DOC-102', 'name': 'Dr. Rahul Verma', 'specialization': 'Neurologist', 'education': 'MBBS, MD (General Medicine), DM (Neurology)', 'experience': '10+ Years', 'department': 'Neurology & Spine Care', 'bio': 'Senior neurologist with expertise in acute stroke care, epilepsy management, Parkinson\'s disease, and neuro-critical care.', 'fee': 1000.0, 'image_url': '/static/images/doctors/dr_rahul_verma.jpg', 'email': 'rahul.verma@medicore.com'},
            {'code': 'DOC-103', 'name': 'Dr. Priya Nair', 'specialization': 'Gynecologist & Obstetrician', 'education': 'MBBS, MD (Obstetrics & Gynecology)', 'experience': '20+ Years', 'department': 'Obstetrics & Gynecology', 'bio': 'Leading specialist in high-risk pregnancies, minimal access laparoscopic surgery, and comprehensive maternal and reproductive healthcare.', 'fee': 900.0, 'image_url': '/static/images/doctors/dr_priya_nair.jpg', 'email': 'priya.nair@medicore.com'},
            {'code': 'DOC-104', 'name': 'Dr. Arjun Mehta', 'specialization': 'Orthopedic Surgeon', 'education': 'MBBS, MS (Orthopedics)', 'experience': '20+ Years', 'department': 'Orthopedics & Joint Care', 'bio': 'Renowned orthopedic surgeon with extensive experience in Mako robotic joint replacements, complex fracture trauma, and sports medicine.', 'fee': 1100.0, 'image_url': '/static/images/doctors/dr_arjun_mehta.jpg', 'email': 'arjun.mehta@medicore.com'},
            {'code': 'DOC-105', 'name': 'Dr. Kavya Rao', 'specialization': 'Pediatrician', 'education': 'MBBS, MD (Pediatrics)', 'experience': '8+ Years', 'department': 'Pediatrics & Child Care', 'bio': 'Compassionate pediatrician dedicated to newborn care, child growth and development, childhood immunizations, and pediatric emergency medicine.', 'fee': 700.0, 'image_url': '/static/images/doctors/dr_kavya_rao.jpg', 'email': 'kavya.rao@medicore.com'},
            {'code': 'DOC-106', 'name': 'Dr. Vikram Desai', 'specialization': 'Radiologist', 'education': 'MBBS, MD (Radiodiagnosis)', 'experience': '10+ Years', 'department': 'Diagnostics & Radiology', 'bio': 'Expert radiologist specializing in 3T MRI, 512-slice Spectral CT scans, cross-sectional diagnostic imaging, and interventional radiology.', 'fee': 850.0, 'image_url': '/static/images/doctors/dr_vikram_desai.jpg', 'email': 'vikram.desai@medicore.com'},
            {'code': 'DOC-001', 'name': 'Dr. Rajesh Sharma', 'specialization': 'General Medicine', 'education': 'MBBS, MD (Internal Medicine)', 'experience': '12+ Years', 'department': 'General OPD', 'bio': 'Senior Consultant in General Medicine with comprehensive expertise in adult acute care and preventative health.', 'fee': 500.0, 'image_url': '/static/images/doctors/dr_rajesh_kumar.jpg', 'email': 'doctor@ipcms.com'}
        ]

        for data in sample_doctors:
            usr = User.query.filter_by(email=data['email']).first()
            if not usr:
                usr = User(user_code=data['code'], name=data['name'], email=data['email'], role_id=doc_role.id, mobile='+91-9876543210')
                usr.set_password('Password@123')
                db.session.add(usr)
                db.session.flush()

            doc = Doctor.query.filter_by(doctor_code=data['code']).first()
            if not doc:
                doc = Doctor(user_id=usr.id, doctor_code=data['code'], name=data['name'], specialization=data['specialization'], education=data['education'], experience=data['experience'], department=data['department'], bio=data['bio'], consultation_fee=data['fee'], image_url=data['image_url'], available_days='Monday - Saturday', rating=4.9, is_active=True)
                db.session.add(doc)

        db.session.commit()
        click.echo("[SUCCESS] Database seeding completed successfully! All demo users created with password: Password@123")

    return app
