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
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(reception_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(queue_bp)
    app.register_blueprint(ehr_bp)
    app.register_blueprint(consultations_bp)

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
