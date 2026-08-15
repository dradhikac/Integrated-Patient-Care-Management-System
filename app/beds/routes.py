from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.auth.models import User, Role
from app.patients.models import Patient
from app.beds.models import Ward, Bed, Admission, BedTransfer
from app.beds.forms import AdmissionForm, BedTransferForm, DischargeForm

beds_bp = Blueprint('beds', __name__, template_folder='templates', url_prefix='/beds')

@beds_bp.route('/')
@login_required
def index():
    role_name = current_user.role.name
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'ADMITTED')

    wards = Ward.query.filter_by(is_active=True).all()
    
    adm_query = Admission.query

    if role_name == 'Patient':
        patient_obj = Patient.query.filter_by(email=current_user.email).first()
        if patient_obj:
            adm_query = adm_query.filter_by(patient_id=patient_obj.id)
        else:
            adm_query = adm_query.filter_by(patient_id=-1)

    if status_filter != 'ALL':
        adm_query = adm_query.filter_by(status=status_filter)

    if search_query:
        adm_query = adm_query.join(Patient).filter(
            (Admission.admission_code.ilike(f"%{search_query}%")) |
            (Patient.full_name.ilike(f"%{search_query}%")) |
            (Patient.patient_code.ilike(f"%{search_query}%"))
        )

    admissions = adm_query.order_by(Admission.id.desc()).all()

    # Metric Counters
    total_beds = sum(w.total_beds_count() for w in wards)
    available_beds = sum(w.available_beds_count() for w in wards)
    occupied_beds = total_beds - available_beds

    return render_template('beds/index.html',
                           wards=wards,
                           admissions=admissions,
                           total_beds=total_beds,
                           available_beds=available_beds,
                           occupied_beds=occupied_beds,
                           status_filter=status_filter,
                           search_query=search_query)


@beds_bp.route('/api/available/<int:ward_id>')
@login_required
def get_available_beds_api(ward_id):
    beds = Bed.query.filter_by(ward_id=ward_id, status='AVAILABLE').all()
    return jsonify({'beds': [{'id': b.id, 'bed_code': b.bed_code} for b in beds]})


@beds_bp.route('/admit', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Receptionist', 'Doctor')
def admit_patient():
    form = AdmissionForm()

    patients = Patient.query.order_by(Patient.full_name.asc()).all()
    form.patient_id.choices = [(p.id, f"{p.full_name} ({p.patient_code})") for p in patients]

    doc_role = Role.query.filter_by(name='Doctor').first()
    doctors = User.query.filter_by(role_id=doc_role.id, is_active=True).all() if doc_role else []
    form.doctor_id.choices = [(d.id, f"{d.name} ({d.user_code})") for d in doctors]

    wards = Ward.query.filter_by(is_active=True).all()
    form.ward_id.choices = [(w.id, f"{w.ward_name} — {w.category} (₹{w.daily_rate}/day)") for w in wards]

    # Preselect ward and available beds
    selected_ward_id = request.args.get('ward_id', type=int) or (wards[0].id if wards else None)
    available_beds = Bed.query.filter_by(ward_id=selected_ward_id, status='AVAILABLE').all() if selected_ward_id else []
    form.bed_id.choices = [(b.id, f"{b.bed_code}") for b in available_beds]

    param_patient_id = request.args.get('patient_id', type=int)
    if param_patient_id and not form.is_submitted():
        form.patient_id.data = param_patient_id

    if form.validate_on_submit():
        patient_id = form.patient_id.data
        doctor_id = form.doctor_id.data
        bed_id = form.bed_id.data
        diagnosis = form.diagnosis.data.strip()

        # Verify bed availability
        target_bed = Bed.query.get(bed_id)
        if not target_bed or target_bed.status != 'AVAILABLE':
            flash('The selected bed is no longer available. Please select another bed.', 'danger')
            return redirect(url_for('beds.admit_patient', ward_id=selected_ward_id))

        admission = Admission(
            admission_code=Admission.generate_admission_code(),
            patient_id=patient_id,
            doctor_id=doctor_id,
            bed_id=bed_id,
            diagnosis=diagnosis,
            status='ADMITTED'
        )
        db.session.add(admission)

        # Mark bed OCCUPIED
        target_bed.status = 'OCCUPIED'
        db.session.commit()

        flash(f'Patient admitted successfully! Admission Code: {admission.admission_code} assigned to Bed {target_bed.bed_code}.', 'success')
        return redirect(url_for('beds.view_admission', admission_id=admission.id))

    return render_template('beds/admit.html',
                           form=form,
                           wards=wards,
                           selected_ward_id=selected_ward_id,
                           available_beds=available_beds)


@beds_bp.route('/admission/<int:admission_id>', methods=['GET'])
@login_required
def view_admission(admission_id):
    adm = Admission.query.get_or_404(admission_id)

    if current_user.role.name == 'Patient' and adm.patient.email != current_user.email:
        flash('Access denied.', 'danger')
        return redirect(url_for('beds.index'))

    transfer_form = BedTransferForm()
    # Available beds for transfer
    avail_beds = Bed.query.filter(Bed.status == 'AVAILABLE', Bed.id != adm.bed_id).all()
    transfer_form.target_bed_id.choices = [(b.id, f"{b.bed_code} ({b.ward.ward_name})") for b in avail_beds]

    discharge_form = DischargeForm()

    return render_template('beds/view_admission.html',
                           adm=adm,
                           transfer_form=transfer_form,
                           discharge_form=discharge_form,
                           avail_beds=avail_beds)


@beds_bp.route('/admission/<int:admission_id>/transfer', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist', 'Doctor')
def transfer_bed(admission_id):
    adm = Admission.query.get_or_404(admission_id)
    form = BedTransferForm()

    avail_beds = Bed.query.filter(Bed.status == 'AVAILABLE', Bed.id != adm.bed_id).all()
    form.target_bed_id.choices = [(b.id, f"{b.bed_code}") for b in avail_beds]

    if form.validate_on_submit():
        to_bed_id = form.target_bed_id.data
        reason = form.reason.data.strip()

        to_bed = Bed.query.get(to_bed_id)
        if not to_bed or to_bed.status != 'AVAILABLE':
            flash('Target bed is no longer available.', 'danger')
            return redirect(url_for('beds.view_admission', admission_id=adm.id))

        from_bed = adm.bed
        
        transfer_log = BedTransfer(
            admission_id=adm.id,
            from_bed_id=from_bed.id,
            to_bed_id=to_bed.id,
            reason=reason,
            transferred_by_id=current_user.id
        )
        db.session.add(transfer_log)

        # Release old bed, occupy new bed
        from_bed.status = 'AVAILABLE'
        to_bed.status = 'OCCUPIED'
        adm.bed_id = to_bed.id

        db.session.commit()

        flash(f'Patient successfully transferred from Bed {from_bed.bed_code} to Bed {to_bed.bed_code}!', 'success')
        return redirect(url_for('beds.view_admission', admission_id=adm.id))

    flash('Failed to transfer bed.', 'danger')
    return redirect(url_for('beds.view_admission', admission_id=adm.id))


@beds_bp.route('/admission/<int:admission_id>/discharge', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist', 'Doctor')
def discharge_patient(admission_id):
    adm = Admission.query.get_or_404(admission_id)
    form = DischargeForm()

    if form.validate_on_submit():
        adm.status = 'DISCHARGED'
        adm.discharged_at = datetime.utcnow()
        adm.discharge_notes = form.discharge_notes.data.strip() if form.discharge_notes.data else None

        # Release assigned bed to AVAILABLE
        if adm.bed:
            adm.bed.status = 'AVAILABLE'

        db.session.commit()

        flash(f'Patient {adm.patient.full_name} has been successfully discharged! Bed {adm.bed.bed_code} is now AVAILABLE.', 'success')
        return redirect(url_for('beds.view_admission', admission_id=adm.id))

    flash('Failed to discharge patient.', 'danger')
    return redirect(url_for('beds.view_admission', admission_id=adm.id))
