from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.auth.models import User, Role, LoginLog, PasswordResetToken
from app.auth.forms import LoginForm, ForgotPasswordForm, ResetPasswordForm, PatientSelfRegistrationForm
from app.auth.utils import role_required, log_login_activity, generate_otp, generate_reset_token

auth_bp = Blueprint('auth', __name__, template_folder='templates')

@auth_bp.route('/')
def index():
    return render_template('landing.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    form = PatientSelfRegistrationForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        mobile = form.mobile.data.strip()
        full_name = form.full_name.data.strip()
        gender = form.gender.data
        dob = form.dob.data
        password = form.password.data

        # Check if user email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with this email address already exists. Please sign in.', 'danger')
            return render_template('auth/register.html', form=form)

        # Get or assign Patient role
        patient_role = Role.query.filter_by(name='Patient').first()
        if not patient_role:
            patient_role = Role(name='Patient', description='Patient user role')
            db.session.add(patient_role)
            db.session.commit()

        # Create User account
        user_code = f"PAT-{int(datetime.utcnow().timestamp()) % 1000000:06d}"
        new_user = User(
            user_code=user_code,
            name=full_name,
            email=email,
            mobile=mobile,
            role_id=patient_role.id,
            is_active=True
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        # Create Patient record if not already existing
        from app.patients.models import Patient
        existing_patient = Patient.query.filter((Patient.email == email) | (Patient.mobile == mobile)).first()
        if not existing_patient:
            name_parts = full_name.split(' ', 1)
            f_name = name_parts[0]
            l_name = name_parts[1] if len(name_parts) > 1 else f_name
            new_patient = Patient(
                patient_code=Patient.generate_patient_code(),
                first_name=f_name,
                last_name=l_name,
                full_name=full_name,
                gender=gender,
                dob=dob,
                mobile=mobile,
                email=email,
                address="Self Registered Patient"
            )
            db.session.add(new_patient)
            db.session.commit()

        login_user(new_user)
        flash(f'🎉 Account created successfully! Welcome to IPCMS, {full_name}!', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('auth/register.html', form=form)



@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data
        user = User.query.filter_by(email=email).first()

        # Fail-safe demo accounts auto-healing
        demo_emails = {
            'admin@ipcms.com': ('Admin', 'ADM-001', 'System Administrator'),
            'administrator@medicore.com': ('Admin', 'ADM-888', 'Hospital Super Admin'),
            'superadmin@ipcms.com': ('Admin', 'ADM-777', 'Chief System Administrator'),
            'reception@ipcms.com': ('Receptionist', 'REC-001', 'Reception Desk Officer'),
            'doctor@ipcms.com': ('Doctor', 'DOC-001', 'Dr. Rajesh Sharma'),
            'lab@ipcms.com': ('Lab Technician', 'LAB-001', 'Suresh Kumar (Lab Tech)'),
            'patient@ipcms.com': ('Patient', 'PAT-001', 'Ananya Verma'),
            'ananya.sharma@medicore.com': ('Doctor', 'DOC-101', 'Dr. Ananya Sharma'),
            'rahul.verma@medicore.com': ('Doctor', 'DOC-102', 'Dr. Rahul Verma'),
            'priya.nair@medicore.com': ('Doctor', 'DOC-103', 'Dr. Priya Nair'),
            'arjun.mehta@medicore.com': ('Doctor', 'DOC-104', 'Dr. Arjun Mehta'),
            'kavya.rao@medicore.com': ('Doctor', 'DOC-105', 'Dr. Kavya Rao'),
            'vikram.desai@medicore.com': ('Doctor', 'DOC-106', 'Dr. Vikram Desai')
        }

        if email in demo_emails:
            role_name, code, name = demo_emails[email]
            role = Role.query.filter_by(name=role_name).first()
            if not user and password == 'Password@123':
                user = User(
                    user_code=code,
                    name=name,
                    email=email,
                    role_id=role.id if role else 1,
                    mobile='+91-9876543210',
                    is_active=True
                )
                db.session.add(user)
                user.set_password('Password@123')
                db.session.commit()
            elif user and role:
                if user.role_id != role.id:
                    user.role_id = role.id
                if password == 'Password@123':
                    user.set_password('Password@123')
                    user.is_active = True
                    user.failed_login_attempts = 0
                    user.locked_until = None
                db.session.commit()

        if not user:
            log_login_activity(email_attempted=email, status='FAILED', failure_reason='User account not found')
            flash('Invalid email address or password.', 'danger')
            return render_template('auth/login.html', form=form)

        if not user.is_active:
            log_login_activity(email_attempted=email, status='FAILED', user=user, failure_reason='Account deactivated')
            flash('Your account has been deactivated. Please contact the administrator.', 'warning')
            return render_template('auth/login.html', form=form)

        if user.is_account_locked():
            remaining_mins = int((user.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
            log_login_activity(email_attempted=email, status='LOCKED', user=user, failure_reason='Account locked due to consecutive failed attempts')
            flash(f'Account locked due to multiple failed login attempts. Try again in {remaining_mins} minute(s).', 'danger')
            return render_template('auth/login.html', form=form)

        if user.check_password(password):
            user.reset_failed_attempts()
            login_user(user, remember=form.remember.data)
            log_login_activity(email_attempted=email, status='SUCCESS', user=user)
            flash(f'Welcome back, {user.name}! Logged in as {user.role.name}.', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('auth.dashboard'))

        else:
            user.register_failed_attempt(
                max_attempts=current_app.config.get('MAX_FAILED_LOGIN_ATTEMPTS', 5),
                lockout_minutes=current_app.config.get('ACCOUNT_LOCKOUT_MINUTES', 15)
            )
            attempts_left = current_app.config.get('MAX_FAILED_LOGIN_ATTEMPTS', 5) - user.failed_login_attempts
            
            if user.is_account_locked():
                log_login_activity(email_attempted=email, status='LOCKED', user=user, failure_reason='Locked after wrong password')
                flash('Account has been locked for 15 minutes due to 5 failed attempts.', 'danger')
            else:
                log_login_activity(email_attempted=email, status='FAILED', user=user, failure_reason='Incorrect password')
                flash(f'Invalid email or password. Remaining attempts before lockout: {attempts_left}', 'danger')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    log_login_activity(email_attempted=current_user.email, status='SUCCESS', user=current_user, failure_reason='User logged out')
    logout_user()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            otp = generate_otp()
            token = generate_reset_token()
            expires = datetime.utcnow() + timedelta(minutes=15)

            reset_record = PasswordResetToken(
                user_id=user.id,
                token=token,
                otp_code=otp,
                expires_at=expires
            )
            db.session.add(reset_record)
            db.session.commit()

            # For local testing & viva demonstration, display OTP directly in flash message!
            flash(f'[DEMO MODE] Reset OTP for {user.email} is: {otp} (Valid for 15 minutes)', 'info')
            return redirect(url_for('auth.reset_password', token=token))
        else:
            flash('If an account with that email exists, a password reset OTP has been generated.', 'info')

    return render_template('auth/forgot_password.html', form=form)


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    token = request.args.get('token')
    if not token:
        flash('Invalid password reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    reset_record = PasswordResetToken.query.filter_by(token=token, is_used=False).first()
    if not reset_record or reset_record.expires_at < datetime.utcnow():
        flash('Password reset token is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        if form.otp_code.data.strip() != reset_record.otp_code:
            flash('Invalid OTP code entered. Please check and try again.', 'danger')
            return render_template('auth/reset_password.html', form=form, token=token)

        user = reset_record.user
        user.set_password(form.password.data)
        user.failed_login_attempts = 0
        user.locked_until = None
        reset_record.is_used = True
        db.session.commit()

        flash('Your password has been successfully reset! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form, token=token)


@auth_bp.route('/dashboard')
@login_required
def dashboard():
    role_name = current_user.role.name
    if role_name == 'Admin':
        return redirect(url_for('admin.index'))
    elif role_name == 'Receptionist':
        return redirect(url_for('reception.dashboard'))
    elif role_name == 'Doctor':
        return render_template('auth/dashboards/doctor.html')
    elif role_name == 'Lab Technician':
        return render_template('auth/dashboards/lab_tech.html')
    elif role_name == 'Patient':
        return render_template('auth/dashboards/patient.html')
    else:
        flash('Unknown role assigned.', 'danger')
        return render_template('auth/dashboards/patient.html')


@auth_bp.route('/auth/audit-logs')
@login_required
@role_required('Admin')
def audit_logs():
    logs = LoginLog.query.order_by(LoginLog.timestamp.desc()).limit(100).all()
    return render_template('auth/audit_logs.html', logs=logs)
