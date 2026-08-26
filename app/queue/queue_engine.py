"""
MediCore+ Intelligent Dynamic Queue & Arrival Window Engine
Replaces rigid fixed-duration consultation slots with real patient flow,
doctor clinic availability windows, dynamic live queues, and historical wait estimation.
"""
from datetime import datetime, date, time, timedelta
from app.extensions import db
from app.auth.models import User
from app.appointments.models import DoctorAvailability, Holiday, Appointment
from app.reception.models import CheckIn
from app.consultations.models import Consultation


def get_doctor_avg_consultation_duration(doctor_id: int, fallback_minutes: float = 12.0) -> float:
    """
    Calculates historical average consultation duration in minutes for a doctor.
    Considers actual completed consultations over the last 30 days.
    """
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # 1. Try consultations with started_at and completed_at
    cns_list = Consultation.query.filter(
        Consultation.doctor_id == doctor_id,
        Consultation.created_at >= thirty_days_ago,
        Consultation.started_at.isnot(None),
        Consultation.completed_at.isnot(None)
    ).all()
    
    durations = []
    for c in cns_list:
        diff = (c.completed_at - c.started_at).total_seconds() / 60.0
        if 2.0 <= diff <= 60.0:  # Filter out outliers
            durations.append(diff)
            
    # 2. Also check check-ins with called_time and completed_time
    if len(durations) < 5:
        chk_list = CheckIn.query.filter(
            CheckIn.doctor_id == doctor_id,
            CheckIn.status == 'COMPLETED',
            CheckIn.called_time.isnot(None),
            CheckIn.completed_time.isnot(None),
            CheckIn.check_in_time >= thirty_days_ago
        ).all()
        for chk in chk_list:
            diff = (chk.completed_time - chk.called_time).total_seconds() / 60.0
            if 2.0 <= diff <= 60.0:
                durations.append(diff)
                
    if len(durations) >= 3:
        return round(sum(durations) / len(durations), 1)
    
    return fallback_minutes


def get_doctor_clinic_windows(doctor_id: int, target_date: date):
    """
    Generates arrival window checkpoints within a doctor's active clinic period.
    Returns:
    {
        'is_holiday': bool,
        'holiday_reason': str,
        'has_availability': bool,
        'shift_start_str': str,
        'shift_end_str': str,
        'clinic_hours_str': str,
        'is_clinic_live_now': bool,
        'current_waiting_count': int,
        'avg_consult_duration': float,
        'estimated_wait_str': str,
        'arrival_windows': list of dicts,
        'slots': list of dicts (for backwards compatibility)
    }
    """
    # 1. Holiday Check
    holiday = Holiday.query.filter_by(holiday_date=target_date).first()
    if holiday:
        return {
            'is_holiday': True,
            'holiday_reason': holiday.description,
            'has_availability': False,
            'clinic_hours_str': 'Closed (Hospital Holiday)',
            'is_clinic_live_now': False,
            'current_waiting_count': 0,
            'avg_consult_duration': 12.0,
            'estimated_wait_str': 'N/A',
            'arrival_windows': [],
            'slots': []
        }

    # 2. Availability Schedule
    day_of_week = target_date.weekday()
    availabilities = DoctorAvailability.query.filter_by(
        doctor_id=doctor_id,
        day_of_week=day_of_week,
        is_active=True
    ).all()

    has_any_schedule = DoctorAvailability.query.filter_by(
        doctor_id=doctor_id,
        is_active=True
    ).first()

    if not availabilities:
        if has_any_schedule or day_of_week == 6:
            return {
                'is_holiday': False,
                'holiday_reason': None,
                'has_availability': False,
                'clinic_hours_str': 'Not Scheduled / Day Off',
                'is_clinic_live_now': False,
                'current_waiting_count': 0,
                'avg_consult_duration': 12.0,
                'estimated_wait_str': 'N/A',
                'arrival_windows': [],
                'slots': []
            }
        shift_start = time(9, 0)
        shift_end = time(13, 0)
    else:
        shift_start = availabilities[0].start_time
        shift_end = availabilities[0].end_time

    # Calculate end datetime
    current_dt = datetime.combine(target_date, shift_start)
    if shift_end <= shift_start or shift_end == time(0, 0):
        end_dt = datetime.combine(target_date + timedelta(days=1), shift_end)
    else:
        end_dt = datetime.combine(target_date, shift_end)

    shift_start_str = shift_start.strftime('%I:%M %p')
    shift_end_str = 'Midnight' if shift_end == time(0, 0) else shift_end.strftime('%I:%M %p')
    clinic_hours_str = f"{shift_start_str} – {shift_end_str}"

    # 3. Live Clinic Status (if target_date is today)
    today = date.today()
    now_dt = datetime.now()
    is_today = (target_date == today)
    is_clinic_live_now = False
    
    if is_today:
        is_clinic_live_now = (current_dt <= now_dt <= end_dt)

    # 4. Live Queue Metrics for this doctor today
    today_start = datetime.combine(today, datetime.min.time())
    active_checkins = CheckIn.query.filter(
        CheckIn.doctor_id == doctor_id,
        CheckIn.status.in_(['WAITING', 'IN_CONSULTATION']),
        CheckIn.check_in_time >= today_start
    ).all() if is_today else []
    
    current_waiting_count = len(active_checkins)
    avg_duration = get_doctor_avg_consultation_duration(doctor_id)
    
    if current_waiting_count == 0:
        estimated_wait_str = "No wait · Doctor ready" if is_clinic_live_now else "Queue clear"
    elif current_waiting_count == 1:
        estimated_wait_str = "~5–10 min (1 patient ahead)"
    else:
        min_est = int(current_waiting_count * (avg_duration * 0.8))
        max_est = int(current_waiting_count * (avg_duration * 1.2))
        estimated_wait_str = f"~{min_est}–{max_est} min ({current_waiting_count} in queue)"

    # 5. Booked arrival windows
    booked_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == target_date,
        Appointment.status.notin_(['CANCELLED'])
    ).all()
    booked_times = {apt.slot_time for apt in booked_appointments}

    # Step: 15-minute arrival checkpoints (patients book expected arrival time)
    step = timedelta(minutes=15)
    arrival_windows = []
    slots_compat = []
    
    while current_dt < end_dt:
        window_time = current_dt.time()
        time_str = current_dt.strftime('%I:%M %p')
        time_24h = current_dt.strftime('%H:%M')
        time_raw = current_dt.strftime('%H:%M:%S')

        # Recommended reporting time (10 min prior)
        rec_arrival_dt = current_dt - timedelta(minutes=10)
        rec_arrival_str = rec_arrival_dt.strftime('%I:%M %p')

        is_past = (current_dt < now_dt) if is_today else (target_date < today)
        is_booked = window_time in booked_times

        if is_past:
            is_avail = False
            reason = 'Past'
        elif is_booked:
            is_avail = False
            reason = 'Booked'
        else:
            is_avail = True
            reason = 'Available'

        w_dict = {
            'time': window_time,
            'time_str': time_str,
            'time_24h': time_24h,
            'time_raw': time_raw,
            'recommended_arrival': rec_arrival_str,
            'is_available': is_avail,
            'is_booked': not is_avail,
            'reason': reason
        }
        arrival_windows.append(w_dict)
        slots_compat.append(w_dict)

        current_dt += step

    return {
        'is_holiday': False,
        'holiday_reason': None,
        'has_availability': True,
        'shift_start_str': shift_start_str,
        'shift_end_str': shift_end_str,
        'clinic_hours_str': clinic_hours_str,
        'is_clinic_live_now': is_clinic_live_now,
        'current_waiting_count': current_waiting_count,
        'avg_consult_duration': avg_duration,
        'estimated_wait_str': estimated_wait_str,
        'arrival_windows': arrival_windows,
        'slots': slots_compat,
        'is_scheduled': True
    }


def get_doctor_live_queue(doctor_id: int, target_date: date = None):
    """
    Returns full live queue state for a doctor's active clinic:
    - in_consultation: Patient currently with the doctor (with start time and elapsed timer)
    - next_patient: The top eligible waiting patient
    - waiting_queue: List of waiting patients in priority order
    - expected_arrivals: Scheduled appointments today not yet checked in
    - stats: queue metrics (in_consult, waiting, completed_today, avg_duration)
    """
    if not target_date:
        target_date = date.today()

    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())
    now = datetime.now()

    # 1. Fetch Today's Check-Ins
    check_ins = CheckIn.query.filter(
        CheckIn.doctor_id == doctor_id,
        CheckIn.check_in_time >= day_start,
        CheckIn.check_in_time <= day_end
    ).all()

    # Active Consultation
    in_consult_item = next((c for c in check_ins if c.status == 'IN_CONSULTATION'), None)
    in_consult_data = None
    if in_consult_item:
        start_time = in_consult_item.called_time or in_consult_item.check_in_time
        elapsed_sec = int((now - start_time).total_seconds()) if start_time else 0
        elapsed_min = elapsed_sec // 60
        elapsed_rem_sec = elapsed_sec % 60
        in_consult_data = {
            'check_in': in_consult_item,
            'patient': in_consult_item.patient,
            'token_no': in_consult_item.token_no,
            'department': in_consult_item.department,
            'priority': in_consult_item.priority,
            'start_time': start_time,
            'start_time_str': start_time.strftime('%I:%M %p') if start_time else '—',
            'elapsed_minutes': elapsed_min,
            'elapsed_str': f"{elapsed_min}m {elapsed_rem_sec:02d}s" if elapsed_min > 0 else f"{elapsed_rem_sec}s"
        }

    # Waiting Queue (Ordered by Priority: Emergency > Senior > Pregnant > Child > Regular, then check-in time)
    priority_weights = {
        'Emergency': 0,
        'Senior Citizen': 1,
        'Pregnant Woman': 2,
        'Child': 3,
        'Regular': 4
    }
    waiting_items = [c for c in check_ins if c.status == 'WAITING']
    waiting_items.sort(key=lambda c: (priority_weights.get(c.priority, 5), c.check_in_time or c.id))

    avg_duration = get_doctor_avg_consultation_duration(doctor_id)

    waiting_queue = []
    for idx, c in enumerate(waiting_items, start=1):
        wait_sec = int((now - c.check_in_time).total_seconds()) if c.check_in_time else 0
        wait_min = wait_sec // 60
        
        # Intelligent wait estimation
        # If in_consult exists, factor in remaining duration
        base_queue_ahead = idx - 1
        if in_consult_item:
            est_wait_min = int(max(3, (base_queue_ahead * avg_duration) + (avg_duration * 0.5)))
        else:
            est_wait_min = int(base_queue_ahead * avg_duration)

        est_wait_str = "Next in line (~5 min)" if idx == 1 else f"~{est_wait_min}–{est_wait_min + 10} min"

        waiting_queue.append({
            'position': idx,
            'check_in': c,
            'patient': c.patient,
            'token_no': c.token_no,
            'priority': c.priority,
            'department': c.department,
            'check_in_time': c.check_in_time,
            'check_in_time_str': c.check_in_time.strftime('%I:%M %p') if c.check_in_time else '—',
            'waited_minutes': wait_min,
            'estimated_wait_minutes': est_wait_min,
            'estimated_wait_str': est_wait_str
        })

    next_patient = waiting_queue[0] if waiting_queue else None

    # Expected Arrivals (Scheduled Appointments today that are not checked in yet)
    checked_in_patient_ids = {c.patient_id for c in check_ins}
    today_apts = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == target_date,
        Appointment.status == 'BOOKED'
    ).order_by(Appointment.slot_time.asc()).all()

    expected_arrivals = []
    for apt in today_apts:
        if apt.patient_id not in checked_in_patient_ids:
            expected_arrivals.append({
                'appointment': apt,
                'patient': apt.patient,
                'expected_arrival_str': apt.slot_time.strftime('%I:%M %p'),
                'recommended_checkin_str': (datetime.combine(target_date, apt.slot_time) - timedelta(minutes=10)).strftime('%I:%M %p'),
                'priority': apt.priority or 'Regular',
                'booking_type': apt.booking_type or 'Online'
            })

    # Completed Consultations Today
    completed_checkins = [c for c in check_ins if c.status == 'COMPLETED']

    return {
        'doctor_id': doctor_id,
        'target_date': target_date,
        'in_consultation': in_consult_data,
        'next_patient': next_patient,
        'waiting_queue': waiting_queue,
        'expected_arrivals': expected_arrivals,
        'stats': {
            'in_consult_count': 1 if in_consult_data else 0,
            'waiting_count': len(waiting_queue),
            'expected_count': len(expected_arrivals),
            'completed_count': len(completed_checkins),
            'total_seen_today': len(completed_checkins) + (1 if in_consult_data else 0),
            'avg_duration_minutes': avg_duration
        }
    }
