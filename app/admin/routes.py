import os
from datetime import datetime, date, timedelta
from sqlalchemy import func
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.models import User, Role
from app.auth.utils import role_required
from app.admin.models import SystemSetting, AuditLog, Department, Equipment
from app.admin.forms import StaffUserCreateForm, MedicineForm, LabTestTypeForm, SystemSettingForm
from app.admin.backup import trigger_db_backup
from app.admin.utils import ensure_departments_seeded, ensure_equipment_seeded, run_system_health_checks
from app.patients.models import Patient
from app.appointments.models import Appointment
from app.beds.models import Bed, Ward, Admission
from app.billing.models import Bill, BillItem, Payment
from app.lab.models import LabRequest
from app.prescriptions.models import Medicine
from app.lab.models import LabTestType
from app.doctors.models import Doctor

admin_bp = Blueprint('admin', __name__, template_folder='templates', url_prefix='/admin')

@admin_bp.route('/')
@login_required
@role_required('Admin')
def index():
    today = date.today()
    yesterday = today - timedelta(days=1)
    month_start = today.replace(day=1)

    total_patients = Patient.query.count()
    prev_month_end = month_start - timedelta(days=1)
    patients_before = Patient.query.filter(Patient.created_at <= datetime.combine(prev_month_end, datetime.max.time())).count()
    patient_pct_change = round(((total_patients - patients_before) / max(1, patients_before)) * 100, 1) if patients_before > 0 else 0.0

    apts_today = Appointment.query.filter(Appointment.appointment_date == today, Appointment.status != 'CANCELLED').count()
    apts_yesterday = Appointment.query.filter(Appointment.appointment_date == yesterday, Appointment.status != 'CANCELLED').count()
    apts_change_pct = round(((apts_today - apts_yesterday) / max(1, apts_yesterday)) * 100, 1) if apts_yesterday > 0 else 0.0

    active_doctors = Doctor.query.filter_by(is_active=True).count()
    if active_doctors == 0:
        active_doctors = User.query.join(Role).filter(Role.name == 'Doctor', User.is_active == True).count()
    new_doctors_month = Doctor.query.filter(Doctor.created_at >= month_start).count()

    total_beds = Bed.query.count()
    occupied_beds = Bed.query.filter_by(status='OCCUPIED').count()
    available_beds = Bed.query.filter_by(status='AVAILABLE').count()
    maint_beds = Bed.query.filter_by(status='UNDER_CLEANING').count()
    bed_occ_pct = round((occupied_beds / max(1, total_beds)) * 100, 1) if total_beds > 0 else 0.0

    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    rev_today = db.session.query(func.sum(Payment.amount_paid)).filter(Payment.paid_at >= today_start, Payment.paid_at <= today_end).scalar() or 0.0

    users_count = User.query.count()
    medicines_count = Medicine.query.count()
    lab_tests_count = LabTestType.query.count()
    audit_logs_count = AuditLog.query.count()

    opd_count = Appointment.query.filter(Appointment.appointment_date == today).count()
    emerg_count = Appointment.query.filter(Appointment.appointment_date == today, (Appointment.priority == 'Emergency') | (Appointment.booking_type == 'Emergency')).count()
    lab_req_count = LabRequest.query.filter(func.date(LabRequest.created_at) == today).count()
    pending_lab_count = LabRequest.query.filter((LabRequest.status == 'REQUESTED') | (LabRequest.status == 'PENDING')).count()
    discharges_count = Admission.query.filter(func.date(Admission.discharged_at) == today).count()
    surgeries_count = Appointment.query.filter(Appointment.appointment_date == today, Appointment.priority == 'Surgery').count()

    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()

    return render_template('admin/index.html',
                           total_patients=total_patients,
                           patient_pct_change=patient_pct_change,
                           apts_today=apts_today,
                           apts_change_pct=apts_change_pct,
                           active_doctors=active_doctors,
                           new_doctors_month=new_doctors_month,
                           total_beds=total_beds,
                           occupied_beds=occupied_beds,
                           available_beds=available_beds,
                           maint_beds=maint_beds,
                           bed_occ_pct=bed_occ_pct,
                           rev_today=rev_today,
                           users_count=users_count,
                           medicines_count=medicines_count,
                           lab_tests_count=lab_tests_count,
                           audit_logs_count=audit_logs_count,
                           opd_count=opd_count,
                           emerg_count=emerg_count,
                           lab_req_count=lab_req_count,
                           pending_lab_count=pending_lab_count,
                           discharges_count=discharges_count,
                           surgeries_count=surgeries_count,
                           recent_logs=recent_logs)


@admin_bp.route('/api/dashboard-stats')
@login_required
@role_required('Admin')
def get_dashboard_stats_api():
    today = date.today()
    yesterday = today - timedelta(days=1)
    month_start = today.replace(day=1)

    # 1. Total Patients & Growth
    total_patients = Patient.query.count()
    prev_month_end = month_start - timedelta(days=1)
    patients_before_this_month = Patient.query.filter(Patient.created_at <= datetime.combine(prev_month_end, datetime.max.time())).count()
    patient_pct_change = round(((total_patients - patients_before_this_month) / max(1, patients_before_this_month)) * 100, 1) if patients_before_this_month > 0 else 0.0

    # 2. Appointments Today & Yesterday comparison
    apts_today = Appointment.query.filter(Appointment.appointment_date == today, Appointment.status != 'CANCELLED').count()
    apts_yesterday = Appointment.query.filter(Appointment.appointment_date == yesterday, Appointment.status != 'CANCELLED').count()
    apts_change_pct = round(((apts_today - apts_yesterday) / max(1, apts_yesterday)) * 100, 1) if apts_yesterday > 0 else 0.0

    # 3. Doctors Active & New this month
    active_doctors = Doctor.query.filter_by(is_active=True).count()
    if active_doctors == 0:
        active_doctors = User.query.join(Role).filter(Role.name == 'Doctor', User.is_active == True).count()
    new_doctors_month = Doctor.query.filter(Doctor.created_at >= month_start).count()

    # 4. Bed Occupancy
    total_beds = Bed.query.count()
    occupied_beds = Bed.query.filter_by(status='OCCUPIED').count()
    available_beds = Bed.query.filter_by(status='AVAILABLE').count()
    maint_beds = Bed.query.filter_by(status='UNDER_CLEANING').count()
    bed_occ_pct = round((occupied_beds / max(1, total_beds)) * 100, 1) if total_beds > 0 else 0.0

    # Ward category breakdown
    general_beds_occ = Bed.query.join(Ward).filter(Ward.category == 'General Ward', Bed.status == 'OCCUPIED').count()
    general_beds_tot = Bed.query.join(Ward).filter(Ward.category == 'General Ward').count()
    icu_beds_occ = Bed.query.join(Ward).filter(Ward.category.ilike('%ICU%'), Bed.status == 'OCCUPIED').count()
    icu_beds_tot = Bed.query.join(Ward).filter(Ward.category.ilike('%ICU%')).count()
    private_beds_occ = Bed.query.join(Ward).filter(Ward.category.ilike('%Private%'), Bed.status == 'OCCUPIED').count()
    private_beds_tot = Bed.query.join(Ward).filter(Ward.category.ilike('%Private%')).count()

    # 5. Today's Revenue
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    yesterday_start = datetime.combine(yesterday, datetime.min.time())
    yesterday_end = datetime.combine(yesterday, datetime.max.time())

    rev_today = db.session.query(func.sum(Payment.amount_paid)).filter(Payment.paid_at >= today_start, Payment.paid_at <= today_end).scalar() or 0.0

    rev_yesterday = db.session.query(func.sum(Payment.amount_paid)).filter(Payment.paid_at >= yesterday_start, Payment.paid_at <= yesterday_end).scalar() or 0.0
    rev_change_pct = round(((rev_today - rev_yesterday) / max(1.0, rev_yesterday)) * 100, 1) if rev_yesterday > 0 else 0.0

    # 6. Appointments Weekly Trend (Mon-Sun)
    start_of_week = today - timedelta(days=today.weekday())
    weekly_apts = []
    week_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for i in range(7):
        day_date = start_of_week + timedelta(days=i)
        cnt = Appointment.query.filter(Appointment.appointment_date == day_date, Appointment.status != 'CANCELLED').count()
        weekly_apts.append(cnt)

    # 7. Today's Operations
    opd_count = Appointment.query.filter(Appointment.appointment_date == today).count()
    emerg_count = Appointment.query.filter(Appointment.appointment_date == today, (Appointment.priority == 'Emergency') | (Appointment.booking_type == 'Emergency')).count()
    lab_req_count = LabRequest.query.filter(func.date(LabRequest.created_at) == today).count()
    pending_lab_count = LabRequest.query.filter((LabRequest.status == 'REQUESTED') | (LabRequest.status == 'PENDING')).count()
    discharges_count = Admission.query.filter(func.date(Admission.discharged_at) == today).count()
    surgeries_count = Appointment.query.filter(Appointment.appointment_date == today, Appointment.priority == 'Surgery').count()

    # 8. Revenue Trend (Last 6 Months)
    monthly_labels = []
    opd_rev = []
    ipd_rev = []
    lab_rev = []
    pharm_rev = []

    for i in range(5, -1, -1):
        m_date = today - timedelta(days=i * 30)
        m_str = m_date.strftime('%b')
        monthly_labels.append(m_str)
        
        m_start = datetime(m_date.year, m_date.month, 1)
        if m_date.month == 12:
            m_end = datetime(m_date.year + 1, 1, 1) - timedelta(seconds=1)
        else:
            m_end = datetime(m_date.year, m_date.month + 1, 1) - timedelta(seconds=1)

        cns = db.session.query(func.sum(BillItem.total_price)).join(Bill).filter(BillItem.item_type == 'CONSULTATION', Bill.created_at >= m_start, Bill.created_at <= m_end).scalar() or 0.0
        med = db.session.query(func.sum(BillItem.total_price)).join(Bill).filter(BillItem.item_type == 'MEDICINE', Bill.created_at >= m_start, Bill.created_at <= m_end).scalar() or 0.0
        lab = db.session.query(func.sum(BillItem.total_price)).join(Bill).filter(BillItem.item_type == 'LAB_TEST', Bill.created_at >= m_start, Bill.created_at <= m_end).scalar() or 0.0
        ipd = db.session.query(func.sum(BillItem.total_price)).join(Bill).filter(BillItem.item_type == 'BED_CHARGE', Bill.created_at >= m_start, Bill.created_at <= m_end).scalar() or 0.0

        opd_rev.append(round(cns, 2))
        pharm_rev.append(round(med, 2))
        lab_rev.append(round(lab, 2))
        ipd_rev.append(round(ipd, 2))

    # 9. Dynamic System Alerts
    alerts = []
    # Formulary alert if under active review
    total_meds_count = Medicine.query.count()
    if total_meds_count > 0:
        alerts.append({
            'type': 'warning',
            'icon': 'bi-capsule',
            'message': f"{total_meds_count} active formulary medicines synchronized in pharmacy catalog",
            'module': 'Pharmacy Inventory',
            'time': '10 min ago',
            'link': url_for('admin.master_medicines')
        })

    # Equipment maintenance due
    maint_eq = Equipment.query.filter(Equipment.next_maintenance <= today).all()
    if maint_eq:
        alerts.append({
            'type': 'danger',
            'icon': 'bi-tools',
            'message': f"{len(maint_eq)} equipment maintenance due",
            'module': 'Equipment Management',
            'time': '30 min ago',
            'link': url_for('admin.index')
        })

    # Pending lab reports
    if pending_lab_count > 0:
        alerts.append({
            'type': 'info',
            'icon': 'bi-journal-medical',
            'message': f"{pending_lab_count} lab reports are pending review",
            'module': 'Laboratory',
            'time': '45 min ago',
            'link': url_for('admin.master_lab_tests')
        })

    # Beds unavailable
    if maint_beds > 0:
        alerts.append({
            'type': 'secondary',
            'icon': 'bi-door-closed-fill',
            'message': f"{maint_beds} beds are marked as unavailable / maintenance",
            'module': 'Bed Management',
            'time': '1 hr ago',
            'link': url_for('admin.index')
        })

    if not alerts:
        alerts.append({
            'type': 'success',
            'icon': 'bi-check-circle-fill',
            'message': 'All inventory stock and equipment are in normal state',
            'module': 'System Status',
            'time': 'Just now',
            'link': url_for('admin.index')
        })

    # 10. System Overview & Health Probes
    health = run_system_health_checks()
    active_staff_count = User.query.filter_by(is_active=True).count()
    total_lab_types = LabTestType.query.count()
    total_medicines = Medicine.query.count()
    today_audit_logs = AuditLog.query.filter(AuditLog.timestamp >= today_start).count()

    return jsonify({
        'success': True,
        'kpis': {
            'total_patients': total_patients,
            'patient_pct_change': patient_pct_change,
            'apts_today': apts_today,
            'apts_change_pct': apts_change_pct,
            'active_doctors': active_doctors,
            'new_doctors_month': new_doctors_month,
            'bed_occ_pct': bed_occ_pct,
            'occupied_beds': occupied_beds,
            'total_beds': total_beds,
            'available_beds': available_beds,
            'maint_beds': maint_beds,
            'rev_today': rev_today,
            'rev_change_pct': rev_change_pct
        },
        'bed_breakdown': {
            'general_occ': general_beds_occ,
            'general_tot': general_beds_tot,
            'icu_occ': icu_beds_occ,
            'icu_tot': icu_beds_tot,
            'private_occ': private_beds_occ,
            'private_tot': private_beds_tot,
            'emergency_occ': Bed.query.join(Ward).filter(Ward.category.ilike('%Emergency%'), Bed.status == 'OCCUPIED').count(),
            'emergency_tot': Bed.query.join(Ward).filter(Ward.category.ilike('%Emergency%')).count(),
            'maint_cnt': maint_beds
        },
        'operations_today': {
            'opd_appointments': opd_count,
            'emergency_patients': emerg_count,
            'lab_requests': lab_req_count,
            'pending_lab_reports': pending_lab_count,
            'discharges': discharges_count,
            'surgeries': surgeries_count
        },
        'weekly_appointments': {
            'labels': week_days,
            'counts': weekly_apts
        },
        'revenue_trend': {
            'labels': monthly_labels,
            'opd': opd_rev,
            'ipd': ipd_rev,
            'lab': lab_rev,
            'pharmacy': pharm_rev
        },
        'alerts': alerts,
        'system_overview': {
            'active_staff': active_staff_count,
            'lab_tests': total_lab_types,
            'medicines': total_medicines,
            'today_audit_logs': today_audit_logs,
            'health': health
        }
    })



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


@admin_bp.route('/departments')
@login_required
@role_required('Admin')
def departments_view():
    departments = Department.query.order_by(Department.name.asc()).all()
    return render_template('admin/departments.html', departments=departments)


@admin_bp.route('/departments/add', methods=['POST'])
@login_required
@role_required('Admin')
def add_department():
    name = request.form.get('name', '').strip()
    hod = request.form.get('hod', '').strip()
    location = request.form.get('location', '').strip()
    if name:
        dept = Department(name=name, head_of_department=hod or None, location=location or None)
        db.session.add(dept)
        db.session.commit()
        flash(f"Department '{name}' created successfully!", 'success')
    return redirect(url_for('admin.departments_view'))


@admin_bp.route('/schedules')
@login_required
@role_required('Admin')
def schedules_view():
    doctors = Doctor.query.filter_by(is_active=True).all()
    return render_template('admin/schedules.html', doctors=doctors)


@admin_bp.route('/appointments')
@login_required
@role_required('Admin')
def appointments_view():
    appointments = Appointment.query.order_by(Appointment.appointment_date.desc(), Appointment.id.desc()).limit(100).all()
    return render_template('admin/appointments.html', appointments=appointments)


@admin_bp.route('/patients')
@login_required
@role_required('Admin')
def patients_view():
    patients = Patient.query.order_by(Patient.id.desc()).limit(100).all()
    return render_template('admin/patients.html', patients=patients)


@admin_bp.route('/beds')
@login_required
@role_required('Admin')
def beds_view():
    beds = Bed.query.order_by(Bed.id.asc()).all()
    return render_template('admin/beds.html', beds=beds)


@admin_bp.route('/billing')
@login_required
@role_required('Admin')
def billing_view():
    bills = Bill.query.order_by(Bill.id.desc()).limit(100).all()
    return render_template('admin/billing.html', bills=bills)


@admin_bp.route('/emergency')
@login_required
@role_required('Admin')
def emergency_view():
    today = date.today()
    emergency_cases = Appointment.query.filter(
        (Appointment.priority == 'Emergency') | (Appointment.booking_type == 'Emergency')
    ).order_by(Appointment.id.desc()).limit(50).all()
    return render_template('admin/emergency.html', emergency_cases=emergency_cases)


@admin_bp.route('/equipment')
@login_required
@role_required('Admin')
def equipment_view():
    equipment_list = Equipment.query.order_by(Equipment.id.asc()).all()
    return render_template('admin/equipment.html', equipment_list=equipment_list)


@admin_bp.route('/equipment/add', methods=['POST'])
@login_required
@role_required('Admin')
def add_equipment():
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip()
    department = request.form.get('department', '').strip()
    if name:
        eq = Equipment(name=name, code=code or None, department=department or None, status='OPERATIONAL')
        db.session.add(eq)
        db.session.commit()
        flash(f"Equipment '{name}' registered successfully!", 'success')
    return redirect(url_for('admin.equipment_view'))


@admin_bp.route('/reports')
@login_required
@role_required('Admin')
def reports_view():
    return render_template('admin/reports.html')


@admin_bp.route('/notifications')
@login_required
@role_required('Admin')
def notifications_view():
    from app.notifications.models import Notification
    notifications = Notification.query.order_by(Notification.id.desc()).limit(50).all()
    return render_template('admin/notifications.html', notifications=notifications)
