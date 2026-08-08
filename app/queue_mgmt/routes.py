from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.reception.models import CheckIn
from app.queue_mgmt.priority_engine import sort_queue_by_priority, calculate_rolling_avg_consultation_time

queue_bp = Blueprint('queue', __name__, template_folder='templates', url_prefix='/queue')

@queue_bp.route('/display')
def public_display_board():
    """Public Full-Screen TV OPD Display Board"""
    today_start = datetime.combine(date.today(), datetime.min.time())
    
    # Query currently active check-ins
    now_serving = CheckIn.query.filter(
        CheckIn.check_in_time >= today_start,
        CheckIn.status == 'IN_CONSULTATION'
    ).order_by(CheckIn.called_time.desc()).first()

    waiting_items = CheckIn.query.filter(
        CheckIn.check_in_time >= today_start,
        CheckIn.status == 'WAITING'
    ).all()

    sorted_waiting = sort_queue_by_priority(waiting_items)
    next_token = sorted_waiting[0] if sorted_waiting else None
    waiting_count = len(sorted_waiting)

    return render_template('queue_mgmt/display_board.html',
                           now_serving=now_serving,
                           next_token=next_token,
                           waiting_count=waiting_count,
                           sorted_waiting=sorted_waiting[:5])


@queue_bp.route('/doctor')
@login_required
@role_required('Admin', 'Doctor')
def doctor_queue_desk():
    """Doctor's Live OPD Queue Desk"""
    today_start = datetime.combine(date.today(), datetime.min.time())
    doc_id = current_user.id

    # If Admin, allow selecting doctor via query param
    if current_user.role.name == 'Admin':
        doc_id = request.args.get('doctor_id', type=int) or current_user.id

    rolling_avg = calculate_rolling_avg_consultation_time(doc_id)

    # Fetch doctor's currently consulting patient
    current_patient = CheckIn.query.filter(
        CheckIn.doctor_id == doc_id,
        CheckIn.check_in_time >= today_start,
        CheckIn.status == 'IN_CONSULTATION'
    ).order_by(CheckIn.called_time.desc()).first()

    # Fetch doctor's waiting queue
    raw_waiting = CheckIn.query.filter(
        CheckIn.doctor_id == doc_id,
        CheckIn.check_in_time >= today_start,
        CheckIn.status == 'WAITING'
    ).all()

    priority_queue = sort_queue_by_priority(raw_waiting)

    # Today's completed count
    completed_count = CheckIn.query.filter(
        CheckIn.doctor_id == doc_id,
        CheckIn.check_in_time >= today_start,
        CheckIn.status == 'COMPLETED'
    ).count()

    return render_template('queue_mgmt/doctor_queue.html',
                           current_patient=current_patient,
                           priority_queue=priority_queue,
                           rolling_avg=rolling_avg,
                           completed_count=completed_count)


@queue_bp.route('/api/live-status')
def api_live_status():
    """JSON API endpoint for real-time TV display board polling"""
    today_start = datetime.combine(date.today(), datetime.min.time())
    
    now_serving = CheckIn.query.filter(
        CheckIn.check_in_time >= today_start,
        CheckIn.status == 'IN_CONSULTATION'
    ).order_by(CheckIn.called_time.desc()).first()

    waiting_items = CheckIn.query.filter(
        CheckIn.check_in_time >= today_start,
        CheckIn.status == 'WAITING'
    ).all()

    sorted_waiting = sort_queue_by_priority(waiting_items)
    next_token = sorted_waiting[0] if sorted_waiting else None

    return jsonify({
        'now_serving': {
            'token_no': now_serving.token_no if now_serving else '--',
            'patient_name': now_serving.patient.full_name if now_serving else 'None',
            'doctor_name': now_serving.doctor.name if now_serving else 'None',
            'department': now_serving.department if now_serving else '--'
        },
        'next_token': next_token.token_no if next_token else '--',
        'waiting_count': len(sorted_waiting),
        'timestamp': datetime.now().strftime('%I:%M:%S %p')
    })
