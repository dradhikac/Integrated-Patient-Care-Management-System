from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.auth.models import User, Role, LoginLog, PasswordResetToken
from app.auth.forms import LoginForm, ForgotPasswordForm, ResetPasswordForm
from app.auth.utils import role_required, log_login_activity, generate_otp, generate_reset_token

auth_bp = Blueprint('auth', __name__, template_folder='templates')

@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data
        user = User.query.filter_by(email=email).first()

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
        return render_template('auth/dashboards/admin.html')
    elif role_name == 'Receptionist':
        return render_template('auth/dashboards/receptionist.html')
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
