from datetime import datetime, date, time, timedelta
from app.appointments.models import DoctorAvailability, Holiday, Appointment

def generate_doctor_slots(doctor_id: int, target_date: date, allow_emergency: bool = False):
    """
    Generates time slots for a doctor on a target date.
    
    Returns a dictionary:
    {
        'is_holiday': bool,
        'holiday_reason': str or None,
        'has_availability': bool,
        'slots': list of slot dicts
    }
    """
    # 1. Check if target_date is a Holiday
    holiday = Holiday.query.filter_by(holiday_date=target_date).first()
    if holiday:
        return {
            'is_holiday': True,
            'holiday_reason': holiday.description,
            'has_availability': False,
            'slots': []
        }

    # 2. Check Doctor Shift Availability for day_of_week
    day_of_week = target_date.weekday() # 0=Mon, 6=Sun
    availabilities = DoctorAvailability.query.filter_by(
        doctor_id=doctor_id,
        day_of_week=day_of_week,
        is_active=True
    ).all()

    # If no custom schedule configured, default shift is 09:00 AM to 01:00 PM (Monday-Saturday)
    if not availabilities:
        if day_of_week == 6: # Sunday default off
            return {
                'is_holiday': False,
                'holiday_reason': None,
                'has_availability': False,
                'slots': []
            }
        # Default shift
        shift_start = time(9, 0)
        shift_end = time(13, 0)
        slot_minutes = 15
    else:
        shift_start = availabilities[0].start_time
        shift_end = availabilities[0].end_time
        slot_minutes = availabilities[0].slot_duration_minutes

    # 3. Query existing booked appointments for doctor on target_date
    booked_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == target_date,
        Appointment.status != 'CANCELLED'
    ).all()
    booked_times = {apt.slot_time for apt in booked_appointments}

    # 4. Generate Slot Objects
    slots = []
    current_dt = datetime.combine(target_date, shift_start)
    end_dt = datetime.combine(target_date, shift_end)
    step = timedelta(minutes=slot_minutes)

    slot_count = 0
    now_dt = datetime.now()

    while current_dt < end_dt:
        slot_time = current_dt.time()
        time_str = current_dt.strftime('%I:%M %p')
        slot_count += 1

        # Hold back 2 slots per shift for Emergency (e.g. every 6th slot or last 2 slots)
        is_emergency = (slot_count % 6 == 0)

        # Availability logic
        is_booked = slot_time in booked_times
        is_past = (current_dt < now_dt)

        if is_past:
            is_avail = False
            reason = 'Past Time'
        elif is_booked:
            is_avail = False
            reason = 'Booked'
        elif is_emergency and not allow_emergency:
            is_avail = False
            reason = 'Emergency Held'
        else:
            is_avail = True
            reason = 'Available'

        slots.append({
            'time': slot_time,
            'time_str': time_str,
            'is_available': is_avail,
            'is_emergency_reserved': is_emergency,
            'reason': reason
        })

        current_dt += step

    return {
        'is_holiday': False,
        'holiday_reason': None,
        'has_availability': True,
        'slots': slots
    }
