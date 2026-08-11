from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.patients.models import Patient
from app.consultations.models import Consultation
from app.lab.models import LabTestType, LabRequest, LabResult
from app.lab.forms import LabRequestForm, LabResultForm

lab_bp = Blueprint('lab', __name__, template_folder='templates', url_prefix='/lab')

@lab_bp.route('/')
@login_required
def list_requests():
    role_name = current_user.role.name
    query = LabRequest.query

    if role_name == 'Doctor':
        query = query.filter_by(doctor_id=current_user.id)
    elif role_name == 'Patient':
        pat_obj = Patient.query.filter_by(email=current_user.email).first()
        if pat_obj:
            query = query.filter_by(patient_id=pat_obj.id)
        else:
            query = query.filter_by(patient_id=-1)

    requests_list = query.order_by(LabRequest.id.desc()).all()
    return render_template('lab/list.html', requests_list=requests_list)


@lab_bp.route('/order', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Doctor')
def order_test():
    patient_id = request.args.get('patient_id', type=int)
    consultation_id = request.args.get('consultation_id', type=int)

    consultation = db.session.get(Consultation, consultation_id) if consultation_id else None
    if consultation:
        patient_id = consultation.patient_id

    if not patient_id:
        flash('Please select a patient to order lab tests.', 'warning')
        return redirect(url_for('patients.list_patients'))

    patient = Patient.query.get_or_404(patient_id)
    test_types = LabTestType.query.filter_by(is_active=True).order_by(LabTestType.category, LabTestType.test_name).all()

    form = LabRequestForm()
    if request.method == 'GET':
        form.patient_id.data = patient.id
        if consultation_id: form.consultation_id.data = consultation_id

    if request.method == 'POST':
        selected_test_ids = request.form.getlist('test_type_ids')
        notes = request.form.get('clinical_notes', '').strip()

        if not selected_test_ids:
            flash('Please select at least one lab test to order.', 'danger')
            return render_template('lab/order_test.html', form=form, patient=patient, consultation=consultation, test_types=test_types)

        req_code = LabRequest.generate_request_code()
        lab_req = LabRequest(
            request_code=req_code,
            patient_id=patient.id,
            doctor_id=current_user.id,
            consultation_id=consultation.id if consultation else None,
            status='REQUESTED',
            clinical_notes=notes
        )
        db.session.add(lab_req)
        db.session.flush()

        for t_id in selected_test_ids:
            res_placeholder = LabResult(
                request_id=lab_req.id,
                test_type_id=int(t_id),
                result_value=0.0,
                abnormal_flag='NORMAL',
                technician_id=None
            )
            db.session.add(res_placeholder)

        db.session.commit()
        flash(f'Lab Test Request {lab_req.request_code} issued successfully!', 'success')
        return redirect(url_for('lab.list_requests'))

    return render_template('lab/order_test.html',
                           form=form,
                           patient=patient,
                           consultation=consultation,
                           test_types=test_types)


@lab_bp.route('/tech-desk')
@login_required
@role_required('Admin', 'Lab Technician')
def tech_desk():
    """Lab Technician Operational Desk"""
    pending_requests = LabRequest.query.filter(
        LabRequest.status.in_(['REQUESTED', 'SAMPLE_COLLECTED', 'IN_TESTING'])
    ).order_by(LabRequest.id.desc()).all()

    completed_requests = LabRequest.query.filter_by(status='COMPLETED').order_by(LabRequest.id.desc()).limit(10).all()

    return render_template('lab/tech_desk.html',
                           pending_requests=pending_requests,
                           completed_requests=completed_requests)


@lab_bp.route('/update-status/<int:request_id>', methods=['POST'])
@login_required
@role_required('Admin', 'Lab Technician')
def update_status(request_id):
    lab_req = LabRequest.query.get_or_404(request_id)
    new_status = request.form.get('status')
    if new_status in ['SAMPLE_COLLECTED', 'IN_TESTING', 'COMPLETED', 'CANCELLED']:
        lab_req.status = new_status
        db.session.commit()
        flash(f'Status for {lab_req.request_code} updated to {new_status}.', 'success')
    return redirect(url_for('lab.tech_desk'))


@lab_bp.route('/results/<int:request_id>', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Lab Technician')
def enter_results(request_id):
    lab_req = LabRequest.query.get_or_404(request_id)

    if request.method == 'POST':
        results = lab_req.results
        all_filled = True

        for res in results:
            field_val = request.form.get(f'result_val_{res.id}')
            remarks_val = request.form.get(f'remarks_{res.id}', '').strip()

            if field_val is not None and field_val != '':
                val_float = float(field_val)
                res.result_value = val_float
                res.abnormal_flag = res.test_type.evaluate_result_flag(val_float)
                res.remarks = remarks_val
                res.technician_id = current_user.id
                res.completed_at = datetime.utcnow()
            else:
                all_filled = False

        if all_filled:
            lab_req.status = 'COMPLETED'
        else:
            lab_req.status = 'IN_TESTING'

        db.session.commit()
        flash(f'Lab Test Results saved for {lab_req.request_code}!', 'success')
        return redirect(url_for('lab.view_report', request_id=lab_req.id))

    return render_template('lab/enter_results.html', lab_req=lab_req)


@lab_bp.route('/report/<int:request_id>')
@login_required
def view_report(request_id):
    lab_req = LabRequest.query.get_or_404(request_id)

    if current_user.role.name == 'Patient' and lab_req.patient.email != current_user.email:
        flash('Access denied. You can only view your own health records.', 'danger')
        return redirect(url_for('auth.dashboard'))

    return render_template('lab/view_report.html', lab_req=lab_req)


@lab_bp.route('/report/<int:request_id>/print')
@login_required
def print_report(request_id):
    lab_req = LabRequest.query.get_or_404(request_id)
    return render_template('lab/print_report.html', lab_req=lab_req)
