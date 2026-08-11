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
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(reception_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(queue_bp)
    app.register_blueprint(ehr_bp)
    app.register_blueprint(consultations_bp)
    app.register_blueprint(prescriptions_bp)
    app.register_blueprint(lab_bp)

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

        db.create_all()

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
                    mobile='+91-9876543210'
                )
                user.set_password('Password@123')
                db.session.add(user)
                click.echo(f"Created demo user: {email} ({role_name})")

        db.session.commit()
        click.echo("[SUCCESS] Database seeding completed successfully! All demo users created with password: Password@123")

    return app
