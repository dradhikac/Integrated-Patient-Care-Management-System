import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.models import User, Role
from app.auth.utils import role_required
from app.admin.models import SystemSetting, AuditLog
from app.admin.forms import StaffUserCreateForm, MedicineForm, LabTestTypeForm, SystemSettingForm
from app.admin.backup import trigger_db_backup
from app.prescriptions.models import Medicine
from app.lab.models import LabTestType

admin_bp = Blueprint('admin', __name__, template_folder='templates', url_prefix='/admin')

@admin_bp.route('/')
@login_required
@role_required('Admin')
def index():
    users_count = User.query.count()
    medicines_count = Medicine.query.count()
    lab_tests_count = LabTestType.query.count()
    audit_logs_count = AuditLog.query.count()

    # Get recent audit logs
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()

    return render_template('admin/index.html',
                           users_count=users_count,
                           medicines_count=medicines_count,
                           lab_tests_count=lab_tests_count,
                           audit_logs_count=audit_logs_count,
                           recent_logs=recent_logs)


@admin_bp.route('/users', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def users():
    form = StaffUserCreateForm()
    roles = Role.query.all()
    form.role_id.choices = [(r.id, r.name) for r in roles]

    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('A user with this email address already exists.', 'danger')
        else:
            role = Role.query.get(form.role_id.data)
            prefix_map = {'Admin': 'ADM', 'Doctor': 'DOC', 'Receptionist': 'REC', 'Lab Technician': 'LAB', 'Patient': 'PAT'}
            prefix = prefix_map.get(role.name if role else 'STAFF', 'STF')
            count = User.query.count() + 1
            user_code = f"{prefix}-{count:03d}"

            new_user = User(
                user_code=user_code,
                name=form.name.data,
                email=form.email.data,
                role_id=form.role_id.data,
                mobile=form.phone.data or None,
                is_active=True
            )
            new_user.set_password(form.password.data)
            db.session.add(new_user)
            db.session.commit()

            # Audit log
            log = AuditLog(
                user_id=current_user.id,
                action='CREATE_STAFF_USER',
                entity_type='User',
                entity_id=new_user.id,
                details=f"Created staff account {new_user.user_code} ({new_user.name}) with role {role.name}."
            )
            db.session.add(log)
            db.session.commit()

            flash(f"Staff account {new_user.user_code} ({new_user.name}) created successfully!", 'success')
            return redirect(url_for('admin.users'))

    staff_users = User.query.order_by(User.id.desc()).all()
    return render_template('admin/users.html', form=form, staff_users=staff_users, roles=roles)


@admin_bp.route('/users/toggle/<int:user_id>', methods=['POST'])
@login_required
@role_required('Admin')
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own administrative account!', 'warning')
        return redirect(url_for('admin.users'))

    user.is_active = not user.is_active
    db.session.commit()

    status_str = 'Activated' if user.is_active else 'Deactivated'
    log = AuditLog(
        user_id=current_user.id,
        action='TOGGLE_STAFF_STATUS',
        entity_type='User',
        entity_id=user.id,
        details=f"{status_str} staff account {user.user_code} ({user.name})."
    )
    db.session.add(log)
    db.session.commit()

    flash(f"User {user.name} has been {status_str.lower()}.", 'info')
    return redirect(url_for('admin.users'))


@admin_bp.route('/master-data/medicines', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def master_medicines():
    form = MedicineForm()
    if form.validate_on_submit():
        med = Medicine(
            brand_name=form.brand_name.data,
            generic_name=form.generic_name.data,
            dosage_form=form.category.data,
            strength=form.dosage.data
        )
        db.session.add(med)
        db.session.commit()

        log = AuditLog(
            user_id=current_user.id,
            action='CREATE_MEDICINE',
            entity_type='Medicine',
            entity_id=med.id,
            details=f"Added medicine {med.brand_name} ({med.strength or ''}) to formulary."
        )
        db.session.add(log)
        db.session.commit()

        flash(f"Medicine {med.brand_name} added to master formulary!", 'success')
        return redirect(url_for('admin.master_medicines'))

    medicines = Medicine.query.order_by(Medicine.id.desc()).all()
    return render_template('admin/medicines.html', form=form, medicines=medicines)


@admin_bp.route('/master-data/lab-tests', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def master_lab_tests():
    form = LabTestTypeForm()
    if form.validate_on_submit():
        test_type = LabTestType(
            test_code=form.test_code.data,
            test_name=form.test_name.data,
            category=form.category.data,
            cost=form.price.data,
            unit=form.unit.data
        )
        db.session.add(test_type)
        db.session.commit()

        log = AuditLog(
            user_id=current_user.id,
            action='CREATE_LAB_TEST_TYPE',
            entity_type='LabTestType',
            entity_id=test_type.id,
            details=f"Added lab test type {test_type.test_name} ({test_type.test_code}) to catalog."
        )
        db.session.add(log)
        db.session.commit()

        flash(f"Lab test type {test_type.test_name} added to catalog!", 'success')
        return redirect(url_for('admin.master_lab_tests'))

    lab_tests = LabTestType.query.order_by(LabTestType.id.desc()).all()
    return render_template('admin/lab_tests.html', form=form, lab_tests=lab_tests)


@admin_bp.route('/master-data/settings', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def settings():
    form = SystemSettingForm()
    if request.method == 'GET':
        form.hospital_name.data = SystemSetting.get_val('hospital_name', 'IPCMS Healthcare Hospital')
        form.opd_consultation_fee.data = float(SystemSetting.get_val('opd_consultation_fee', '500.0'))
        form.ipd_bed_rate_general.data = float(SystemSetting.get_val('ipd_bed_rate_general', '1500.0'))
        form.ipd_bed_rate_icu.data = float(SystemSetting.get_val('ipd_bed_rate_icu', '5000.0'))
        form.gst_tax_rate.data = float(SystemSetting.get_val('gst_tax_rate', '18.0'))
        form.emergency_surcharge.data = float(SystemSetting.get_val('emergency_surcharge', '1000.0'))

    if form.validate_on_submit():
        SystemSetting.set_val('hospital_name', form.hospital_name.data, 'Official Hospital Name')
        SystemSetting.set_val('opd_consultation_fee', form.opd_consultation_fee.data, 'Standard OPD Consultation Fee')
        SystemSetting.set_val('ipd_bed_rate_general', form.ipd_bed_rate_general.data, 'General Ward Bed Daily Rate')
        SystemSetting.set_val('ipd_bed_rate_icu', form.ipd_bed_rate_icu.data, 'ICU Ward Bed Daily Rate')
        SystemSetting.set_val('gst_tax_rate', form.gst_tax_rate.data, 'GST / Service Tax Percentage')
        SystemSetting.set_val('emergency_surcharge', form.emergency_surcharge.data, 'Emergency Care Surcharge')

        log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_SYSTEM_SETTINGS',
            entity_type='SystemSetting',
            entity_id=0,
            details="Updated hospital fee structure and system settings."
        )
        db.session.add(log)
        db.session.commit()

        flash('System settings and fee structure updated successfully!', 'success')
        return redirect(url_for('admin.settings'))

    return render_template('admin/settings.html', form=form)


@admin_bp.route('/audit-trail')
@login_required
@role_required('Admin')
def audit_trail():
    q = request.args.get('q', '').strip()
    action_filter = request.args.get('action', '').strip()

    query = AuditLog.query

    if action_filter:
        query = query.filter_by(action=action_filter)
    if q:
        query = query.filter(AuditLog.details.ilike(f"%{q}%"))

    audit_logs = query.order_by(AuditLog.timestamp.desc()).limit(200).all()
    actions = db.session.query(AuditLog.action).distinct().all()
    action_list = [a[0] for a in actions]

    return render_template('admin/audit_trail.html',
                           audit_logs=audit_logs,
                           actions=action_list,
                           q=q,
                           action_filter=action_filter)


@admin_bp.route('/backup', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def backup():
    backup_dir = os.path.join(os.getcwd(), 'backups')
    backup_files = []

    if os.path.exists(backup_dir):
        for fname in os.listdir(backup_dir):
            if fname.endswith('.json') or fname.endswith('.sql'):
                fpath = os.path.join(backup_dir, fname)
                stat = os.stat(fpath)
                backup_files.append({
                    'filename': fname,
                    'size_kb': round(stat.st_size / 1024, 2),
                    'created_at': datetime.fromtimestamp(stat.st_mtime)
                })

    backup_files.sort(key=lambda x: x['created_at'], reverse=True)

    return render_template('admin/backup.html', backup_files=backup_files)


@admin_bp.route('/backup/trigger', methods=['POST'])
@login_required
@role_required('Admin')
def trigger_backup():
    result = trigger_db_backup(admin_user_id=current_user.id)
    flash(f"Database snapshot generated successfully! ({result['filename']}, {result['file_size_kb']} KB)", 'success')
    return redirect(url_for('admin.backup'))


@admin_bp.route('/backup/download/<filename>')
@login_required
@role_required('Admin')
def download_backup(filename):
    backup_dir = os.path.join(os.getcwd(), 'backups')
    return send_from_directory(backup_dir, filename, as_attachment=True)
