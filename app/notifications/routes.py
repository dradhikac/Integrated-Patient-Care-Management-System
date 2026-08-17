from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.patients.models import Patient
from app.notifications.models import Notification, NotificationLog
from app.notifications.forms import ManualNotificationForm
from app.notifications.dispatcher import dispatch_single_notification, scan_and_queue_reminders

notifications_bp = Blueprint('notifications', __name__, template_folder='templates', url_prefix='/notifications')

@notifications_bp.route('/')
@login_required
def index():
    role_name = current_user.role.name
    type_filter = request.args.get('type', 'ALL')
    status_filter = request.args.get('status', 'ALL')

    query = Notification.query

    if role_name == 'Patient':
        patient_obj = Patient.query.filter_by(email=current_user.email).first()
        if patient_obj:
            query = query.filter_by(patient_id=patient_obj.id)
        else:
            query = query.filter_by(patient_id=-1)

    if type_filter != 'ALL':
        query = query.filter_by(type=type_filter)

    if status_filter != 'ALL':
        query = query.filter_by(status=status_filter)

    notifications = query.order_by(Notification.id.desc()).all()

    # Recent Dispatch Logs
    logs = NotificationLog.query.order_by(NotificationLog.id.desc()).limit(20).all()

    # Form for custom notification dispatch
    form = ManualNotificationForm()
    patients = Patient.query.order_by(Patient.full_name.asc()).all()
    form.patient_id.choices = [(p.id, f"{p.full_name} ({p.patient_code})") for p in patients]

    # Metrics
    total_count = len(notifications)
    sent_count = sum(1 for n in notifications if n.status == 'SENT')
    pending_count = sum(1 for n in notifications if n.status == 'PENDING')
    failed_count = sum(1 for n in notifications if n.status == 'FAILED')

    return render_template('notifications/index.html',
                           notifications=notifications,
                           logs=logs,
                           form=form,
                           total_count=total_count,
                           sent_count=sent_count,
                           pending_count=pending_count,
                           failed_count=failed_count,
                           type_filter=type_filter,
                           status_filter=status_filter)


@notifications_bp.route('/send', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist', 'Doctor')
def send_manual_notification():
    form = ManualNotificationForm()
    patients = Patient.query.order_by(Patient.full_name.asc()).all()
    form.patient_id.choices = [(p.id, f"{p.full_name} ({p.patient_code})") for p in patients]

    if form.validate_on_submit():
        patient_id = form.patient_id.data
        notif_type = form.type.data
        channel = form.channel.data
        title = form.title.data.strip()
        msg = form.message.data.strip()

        notif = Notification(
            patient_id=patient_id,
            type=notif_type,
            title=title,
            message=msg,
            channel=channel,
            status='PENDING'
        )
        db.session.add(notif)
        db.session.commit()

        # Asynchronous dispatch
        dispatch_single_notification(notif.id)

        flash(f'Notification "{title}" queued and dispatched asynchronously!', 'success')
        return redirect(url_for('notifications.index'))

    flash('Failed to dispatch custom notification.', 'danger')
    return redirect(url_for('notifications.index'))


@notifications_bp.route('/trigger-job', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def trigger_background_job():
    count = scan_and_queue_reminders()
    flash(f'Background Reminder Scan completed! {count} automated notification(s) dispatched.', 'info')
    return redirect(url_for('notifications.index'))


@notifications_bp.route('/resend/<int:notif_id>', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def resend_notification(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    notif.status = 'PENDING'
    db.session.commit()

    dispatch_single_notification(notif.id)
    flash(f'Resent notification {notif.id} ({notif.title})!', 'success')
    return redirect(url_for('notifications.index'))
