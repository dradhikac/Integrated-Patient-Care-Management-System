from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.patients.models import Patient
from app.consultations.models import Consultation
from app.prescriptions.models import Medicine, Prescription, PrescriptionItem
from app.prescriptions.qr_generator import generate_prescription_qr_base64

prescriptions_bp = Blueprint('prescriptions', __name__, template_folder='templates', url_prefix='/prescriptions')

@prescriptions_bp.route('/')
@login_required
def list_prescriptions():
    role_name = current_user.role.name
    rx_query = Prescription.query

    if role_name == 'Doctor':
        rx_query = rx_query.filter_by(doctor_id=current_user.id)
    elif role_name == 'Patient':
        pat_obj = Patient.query.filter_by(email=current_user.email).first()
        if pat_obj:
            rx_query = rx_query.filter_by(patient_id=pat_obj.id)
        else:
            rx_query = rx_query.filter_by(patient_id=-1)

    prescriptions = rx_query.order_by(Prescription.id.desc()).all()
    return render_template('prescriptions/list.html', prescriptions=prescriptions)


@prescriptions_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Doctor')
def create_prescription():
    consultation_id = request.args.get('consultation_id', type=int)
    patient_id = request.args.get('patient_id', type=int)

    consultation = db.session.get(Consultation, consultation_id) if consultation_id else None
    if consultation:
        patient_id = consultation.patient_id

    if not patient_id:
        flash('Please select a patient or consultation to issue prescription.', 'warning')
        return redirect(url_for('consultations.list_consultations'))

    patient = Patient.query.get_or_404(patient_id)
    medicines = Medicine.query.filter_by(is_active=True).order_by(Medicine.brand_name).all()

    if request.method == 'POST':
        general_advice = request.form.get('general_advice', '').strip()
        med_names = request.form.getlist('medicine_name[]')
        frequencies = request.form.getlist('frequency[]')
        durations = request.form.getlist('duration[]')
        food_relations = request.form.getlist('food_relation[]')
        instructions_list = request.form.getlist('instructions[]')

        if not med_names or len(med_names) == 0 or not any(med_names):
            flash('Please add at least one prescribed medicine item.', 'danger')
            return render_template('prescriptions/create.html', patient=patient, consultation=consultation, medicines=medicines)

        rx_code = Prescription.generate_prescription_code()
        rx = Prescription(
            prescription_code=rx_code,
            consultation_id=consultation.id if consultation else None,
            patient_id=patient.id,
            doctor_id=current_user.id,
            general_advice=general_advice
        )
        db.session.add(rx)
        db.session.flush()

        for i in range(len(med_names)):
            m_name = med_names[i].strip()
            if m_name:
                freq = frequencies[i] if i < len(frequencies) else '1-0-1'
                dur = durations[i] if i < len(durations) else '5 Days'
                food = food_relations[i] if i < len(food_relations) else 'After Food'
                inst = instructions_list[i] if i < len(instructions_list) else ''

                item = PrescriptionItem(
                    prescription_id=rx.id,
                    medicine_name=m_name,
                    frequency=freq,
                    duration=dur,
                    food_relation=food,
                    instructions=inst
                )
                db.session.add(item)

        db.session.commit()
        flash(f'Digital Prescription {rx.prescription_code} created successfully!', 'success')
        return redirect(url_for('prescriptions.view_prescription', prescription_id=rx.id))

    return render_template('prescriptions/create.html',
                           patient=patient,
                           consultation=consultation,
                           medicines=medicines)


@prescriptions_bp.route('/<int:prescription_id>')
@login_required
def view_prescription(prescription_id):
    rx = Prescription.query.get_or_404(prescription_id)
    
    if current_user.role.name == 'Patient' and rx.patient.email != current_user.email:
        flash('Access denied. You can only view your own health records.', 'danger')
        return redirect(url_for('auth.dashboard'))

    verify_url = request.host_url.rstrip('/') + url_for('prescriptions.verify_prescription', prescription_code=rx.prescription_code)
    qr_base64 = generate_prescription_qr_base64(verify_url)

    return render_template('prescriptions/view.html', rx=rx, qr_base64=qr_base64, verify_url=verify_url)


@prescriptions_bp.route('/<int:prescription_id>/print')
@login_required
def print_prescription(prescription_id):
    rx = Prescription.query.get_or_404(prescription_id)
    verify_url = request.host_url.rstrip('/') + url_for('prescriptions.verify_prescription', prescription_code=rx.prescription_code)
    qr_base64 = generate_prescription_qr_base64(verify_url)

    return render_template('prescriptions/print_prescription.html', rx=rx, qr_base64=qr_base64)


@prescriptions_bp.route('/verify/<prescription_code>')
def verify_prescription(prescription_code):
    """Public verification endpoint for pharmacy and digital authenticity checks"""
    rx = Prescription.query.filter_by(prescription_code=prescription_code).first()
    if not rx:
        return jsonify({'status': 'INVALID', 'message': 'Prescription code not found in IPCMS registry.'}), 404

    return jsonify({
        'status': 'VERIFIED_VALID',
        'prescription_code': rx.prescription_code,
        'patient_name': rx.patient.full_name,
        'patient_code': rx.patient.patient_code,
        'doctor_name': rx.doctor.name,
        'issued_at': rx.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'items_count': len(rx.items),
        'items': [{'medicine': item.medicine_name, 'frequency': item.frequency, 'duration': item.duration} for item in rx.items]
    })


@prescriptions_bp.route('/medicines', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Doctor')
def manage_medicines():
    if request.method == 'POST':
        brand_name = request.form.get('brand_name', '').strip()
        generic_name = request.form.get('generic_name', '').strip()
        dosage_form = request.form.get('dosage_form', 'Tablet')
        strength = request.form.get('strength', '').strip()

        if brand_name and generic_name:
            med = Medicine(brand_name=brand_name, generic_name=generic_name, dosage_form=dosage_form, strength=strength)
            db.session.add(med)
            db.session.commit()
            flash(f'Medicine "{brand_name}" added to Drug Master catalog!', 'success')
            return redirect(url_for('prescriptions.manage_medicines'))

    medicines = Medicine.query.order_by(Medicine.brand_name).all()
    return render_template('prescriptions/medicines.html', medicines=medicines)
