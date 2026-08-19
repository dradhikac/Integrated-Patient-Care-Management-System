from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import current_user
from app.extensions import db
from app.doctors.models import Doctor
from app.auth.models import User, Role
from app.patients.models import Patient
from app.appointments.models import Appointment
from app.appointments.slot_generator import generate_doctor_slots

doctors_bp = Blueprint('doctors', __name__, template_folder='templates')

@doctors_bp.route('/api/doctors', methods=['GET'])
def get_doctors_api():
    """
    Returns list of active doctors for frontend dynamic rendering.
    """
    doctors = Doctor.query.filter_by(is_active=True).order_by(Doctor.id.asc()).all()
    return jsonify({
        'success': True,
        'count': len(doctors),
        'doctors': [d.to_dict() for d in doctors]
    })


@doctors_bp.route('/api/doctors/<int:doctor_id>', methods=['GET'])
def get_doctor_profile_api(doctor_id):
    """
    Returns detailed profile for a specific doctor.
    """
    doctor = Doctor.query.get_or_404(doctor_id)
    return jsonify({
        'success': True,
        'doctor': doctor.to_dict()
    })


@doctors_bp.route('/api/doctors/<int:doctor_id>/availability', methods=['GET'])
def get_doctor_availability_api(doctor_id):
    """
    Returns available appointment slots for a doctor on a given date.
    Query param: ?date=YYYY-MM-DD (defaults to today)
    """
    doctor = Doctor.query.get_or_404(doctor_id)
    date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    # User ID for doctor shift check
    user_id = doctor.user_id if doctor.user_id else doctor.id
    slot_info = generate_doctor_slots(user_id, target_date)

    # Format slot objects for clean JSON output
    formatted_slots = []
    for s in slot_info.get('slots', []):
        formatted_slots.append({
            'time_24h': s['time'].strftime('%H:%M'),
            'time_12h': s['time_str'],
            'is_available': s['is_available'],
            'reason': s['reason']
        })

    return jsonify({
        'success': True,
        'doctor_id': doctor.id,
        'doctor_name': doctor.name,
        'date': target_date.strftime('%Y-%m-%d'),
        'is_holiday': slot_info['is_holiday'],
        'holiday_reason': slot_info['holiday_reason'],
        'slots': formatted_slots
    })


@doctors_bp.route('/api/doctors/<int:doctor_id>/book', methods=['POST'])
def book_doctor_appointment_api(doctor_id):
    """
    API Endpoint to validate & book an appointment with a doctor.
    Accepts JSON payload:
    {
      "appointment_date": "2026-08-25",
      "slot_time": "10:30",
      "patient_name": "Full Name", (optional if logged in)
      "patient_email": "email@example.com",
      "patient_mobile": "+91-9876543210",
      "reason": "Consultation details"
    }
    """
    doctor = Doctor.query.get_or_404(doctor_id)
    data = request.get_json() or request.form

    date_str = data.get('appointment_date')
    slot_time_str = data.get('slot_time')
    reason = data.get('reason', '').strip()

    if not date_str or not slot_time_str:
        return jsonify({'success': False, 'message': 'Date and slot_time are required.'}), 400

    # 1. Date Validation
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid appointment_date format. Use YYYY-MM-DD.'}), 400

    if target_date < date.today():
        return jsonify({'success': False, 'message': 'Cannot book an appointment for a past date.'}), 400

    # 2. Slot Time Validation
    try:
        slot_t = datetime.strptime(slot_time_str, '%H:%M').time()
    except ValueError:
        try:
            slot_t = datetime.strptime(slot_time_str, '%H:%M:%S').time()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid slot_time format. Use HH:MM.'}), 400

    # Past time validation for today
    if target_date == date.today() and datetime.combine(target_date, slot_t) < datetime.now():
        return jsonify({'success': False, 'message': 'Selected slot time has already passed today.'}), 400

    # 3. Doctor User Account resolution
    doctor_user_id = doctor.user_id if doctor.user_id else doctor.id

    # 4. Double Booking Check
    existing_booking = Appointment.query.filter(
        Appointment.doctor_id == doctor_user_id,
        Appointment.appointment_date == target_date,
        Appointment.slot_time == slot_t,
        Appointment.status != 'CANCELLED'
    ).first()

    if existing_booking:
        return jsonify({'success': False, 'message': f'Slot {slot_t.strftime("%I:%M %p")} is already occupied for {doctor.name}. Please select another slot.'}), 409

    # 5. Resolve Patient
    patient = None
    if current_user.is_authenticated and hasattr(current_user, 'email'):
        patient = Patient.query.filter_by(email=current_user.email).first()

    if not patient:
        p_email = data.get('patient_email', '').strip()
        p_name = data.get('patient_name', '').strip() or 'Guest Patient'
        p_mobile = data.get('patient_mobile', '').strip()

        if p_email:
            patient = Patient.query.filter_by(email=p_email).first()

        if not patient and p_name:
            parts = p_name.split(' ', 1)
            f_name = parts[0]
            l_name = parts[1] if len(parts) > 1 else 'Patient'
            # Create quick patient record for public user
            patient = Patient(
                patient_code=Patient.generate_patient_code(),
                first_name=f_name,
                last_name=l_name,
                full_name=p_name,
                email=p_email or 'guest@ipcms.com',
                mobile=p_mobile or '+91-9876543210',
                gender='Other',
                dob=date(1995, 1, 1)
            )
            db.session.add(patient)
            db.session.flush()

    if not patient:
        # Fallback to first patient or generic demo patient
        patient = Patient.query.first()
        if not patient:
            p_name = data.get('patient_name', 'Guest Patient')
            parts = p_name.split(' ', 1)
            patient = Patient(
                patient_code=Patient.generate_patient_code(),
                first_name=parts[0],
                last_name=parts[1] if len(parts) > 1 else 'Patient',
                full_name=p_name,
                email=data.get('patient_email', 'guest@ipcms.com'),
                mobile='+91-9876543210',
                gender='Other',
                dob=date(1995, 1, 1)
            )
            db.session.add(patient)
            db.session.flush()

    # 6. Save Appointment
    apt_code = Appointment.generate_appointment_code()
    appointment = Appointment(
        appointment_code=apt_code,
        patient_id=patient.id,
        doctor_id=doctor_user_id,
        appointment_date=target_date,
        slot_time=slot_t,
        booking_type='Online',
        priority='Regular',
        status='BOOKED',
        notes=reason if reason else f'Consultation with {doctor.name}'
    )

    db.session.add(appointment)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Appointment confirmed with {doctor.name}!',
        'appointment_id': appointment.id,
        'appointment_code': appointment.appointment_code,
        'doctor_id': doctor.id,
        'doctor_name': doctor.name,
        'specialization': doctor.specialization,
        'appointment_date': target_date.strftime('%A, %B %d, %Y'),
        'slot_time': slot_t.strftime('%I:%M %p'),
        'status': appointment.status
    })


@doctors_bp.route('/doctors/<int:doctor_id>')
def view_doctor_profile_page(doctor_id):
    """
    Renders dedicated HTML Doctor Profile page.
    """
    doctor = Doctor.query.get_or_404(doctor_id)
    return render_template('doctors/profile.html', doctor=doctor, today_date=date.today())
