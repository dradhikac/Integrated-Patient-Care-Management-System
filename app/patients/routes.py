from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.patients.models import Patient, PatientMedicalHistory, PatientAllergy
from app.patients.forms import PatientRegistrationForm
from app.patients.duplicate_check import check_for_duplicates

patients_bp = Blueprint('patients', __name__, template_folder='templates', url_prefix='/patients')

@patients_bp.route('/')
@login_required
@role_required('Admin', 'Receptionist', 'Doctor', 'Lab Technician')
def list_patients():
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    
    patient_query = Patient.query
    if query:
        search_filter = f"%{query}%"
        patient_query = patient_query.filter(
            (Patient.patient_code.ilike(search_filter)) |
            (Patient.full_name.ilike(search_filter)) |
            (Patient.mobile.ilike(search_filter)) |
            (Patient.aadhaar_masked.ilike(search_filter))
        )
    
    pagination = patient_query.order_by(Patient.id.desc()).paginate(page=page, per_page=15, error_out=False)
    patients = pagination.items
    
    return render_template('patients/index.html', patients=patients, pagination=pagination, query=query)


@patients_bp.route('/register', methods=['GET', 'POST'])
def register_patient():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.register'))
    if current_user.role.name not in ['Admin', 'Receptionist']:
        flash('Permission denied. Receptionist or Admin access required.', 'danger')
        return redirect(url_for('auth.dashboard'))
    form = PatientRegistrationForm()
    force_create = request.args.get('force_create', '0') == '1'

    if form.validate_on_submit():
        first_name = form.first_name.data.strip()
        last_name = form.last_name.data.strip()
        dob = form.dob.data
        mobile = form.mobile.data.strip()
        aadhaar_raw = form.aadhaar_number.data.strip() if form.aadhaar_number.data else None

        # Check for duplicates unless receptionist explicitly chooses force_create
        if not force_create:
            is_dup, dup_matches = check_for_duplicates(first_name, last_name, dob, mobile, aadhaar_raw)
            if is_dup:
                return render_template('patients/duplicate_alert.html',
                                       form_data=request.form,
                                       form=form,
                                       dup_matches=dup_matches)

        # Create New Patient Record
        patient = Patient(
            patient_code=Patient.generate_patient_code(),
            first_name=first_name,
            last_name=last_name,
            full_name=f"{first_name} {last_name}",
            dob=dob,
            gender=form.gender.data,
            mobile=mobile,
            email=form.email.data.strip() if form.email.data else None,
            address=form.address.data.strip() if form.address.data else None,
            blood_group=form.blood_group.data if form.blood_group.data else None,
            emergency_contact_name=form.emergency_contact_name.data.strip() if form.emergency_contact_name.data else None,
            emergency_contact_mobile=form.emergency_contact_mobile.data.strip() if form.emergency_contact_mobile.data else None,
            insurance_provider=form.insurance_provider.data.strip() if form.insurance_provider.data else None,
            insurance_policy_no=form.insurance_policy_no.data.strip() if form.insurance_policy_no.data else None,
            height_cm=form.height_cm.data,
            weight_kg=form.weight_kg.data,
            vaccination_records=form.vaccination_records.data.strip() if form.vaccination_records.data else None,
            preferred_language=form.preferred_language.data,
            registered_by_id=current_user.id
        )

        patient.set_aadhaar(aadhaar_raw)
        patient.calculate_bmi()

        db.session.add(patient)
        db.session.flush() # Populate patient.id

        # Save Allergies
        if form.allergies.data:
            allergen_list = [a.strip() for a in form.allergies.data.split(',') if a.strip()]
            for item in allergen_list:
                allergy = PatientAllergy(
                    patient_id=patient.id,
                    allergen=item,
                    severity='Moderate'
                )
                db.session.add(allergy)

        # Save Medical History / Chronic Diseases
        if form.chronic_diseases.data:
            history = PatientMedicalHistory(
                patient_id=patient.id,
                condition_type='Chronic Disease',
                description=form.chronic_diseases.data.strip()
            )
            db.session.add(history)

        db.session.commit()

        flash(f'Patient {patient.full_name} registered successfully with Code: {patient.patient_code}!', 'success')
        return redirect(url_for('patients.view_patient', patient_id=patient.id))

    return render_template('patients/register.html', form=form)


@patients_bp.route('/<int:patient_id>')
@login_required
@role_required('Admin', 'Receptionist', 'Doctor', 'Lab Technician')
def view_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    return render_template('patients/view.html', patient=patient)


@patients_bp.route('/<int:patient_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Receptionist')
def edit_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    form = PatientRegistrationForm(obj=patient)

    if form.validate_on_submit():
        patient.first_name = form.first_name.data.strip()
        patient.last_name = form.last_name.data.strip()
        patient.full_name = f"{patient.first_name} {patient.last_name}"
        patient.dob = form.dob.data
        patient.gender = form.gender.data
        patient.mobile = form.mobile.data.strip()
        patient.email = form.email.data.strip() if form.email.data else None
        patient.address = form.address.data.strip() if form.address.data else None
        patient.blood_group = form.blood_group.data
        patient.emergency_contact_name = form.emergency_contact_name.data
        patient.emergency_contact_mobile = form.emergency_contact_mobile.data
        patient.insurance_provider = form.insurance_provider.data
        patient.insurance_policy_no = form.insurance_policy_no.data
        patient.height_cm = form.height_cm.data
        patient.weight_kg = form.weight_kg.data
        patient.preferred_language = form.preferred_language.data
        
        if form.aadhaar_number.data:
            patient.set_aadhaar(form.aadhaar_number.data.strip())

        patient.calculate_bmi()
        db.session.commit()

        flash(f'Patient profile for {patient.patient_code} updated successfully!', 'success')
        return redirect(url_for('patients.view_patient', patient_id=patient.id))

    return render_template('patients/edit.html', form=form, patient=patient)
