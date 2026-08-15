from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.utils import role_required
from app.patients.models import Patient
from app.consultations.models import Consultation
from app.billing.models import Bill, BillItem, Payment
from app.billing.forms import CreateBillForm, ProcessPaymentForm
from app.billing.aggregator import generate_auto_bill_for_patient

billing_bp = Blueprint('billing', __name__, template_folder='templates', url_prefix='/billing')

@billing_bp.route('/')
@login_required
def index():
    role_name = current_user.role.name
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'ALL')

    query = Bill.query

    if role_name == 'Patient':
        patient_obj = Patient.query.filter_by(email=current_user.email).first()
        if patient_obj:
            query = query.filter_by(patient_id=patient_obj.id)
        else:
            query = query.filter_by(patient_id=-1)

    if status_filter != 'ALL':
        query = query.filter_by(status=status_filter)

    if search_query:
        query = query.join(Patient).filter(
            (Bill.invoice_code.ilike(f"%{search_query}%")) |
            (Patient.full_name.ilike(f"%{search_query}%")) |
            (Patient.patient_code.ilike(f"%{search_query}%"))
        )

    bills = query.order_by(Bill.id.desc()).all()

    # Summary Financial Indicators
    total_billed = sum(b.grand_total for b in bills)
    total_collected = sum(b.paid_amount for b in bills)
    total_pending = sum(b.balance_due for b in bills)

    return render_template('billing/index.html',
                           bills=bills,
                           total_billed=total_billed,
                           total_collected=total_collected,
                           total_pending=total_pending,
                           status_filter=status_filter,
                           search_query=search_query)


@billing_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Receptionist')
def create_bill():
    form = CreateBillForm()
    
    patients = Patient.query.order_by(Patient.full_name.asc()).all()
    form.patient_id.choices = [(p.id, f"{p.full_name} ({p.patient_code})") for p in patients]

    consultations = Consultation.query.order_by(Consultation.id.desc()).all()
    form.consultation_id.choices = [(0, '-- Optional: None / Direct Billing --')] + [(c.id, f"{c.consultation_code} — {c.patient.full_name} ({c.created_at.strftime('%d %b %Y')})") for c in consultations]

    # Preselect patient if passed in URL
    param_patient_id = request.args.get('patient_id', type=int)
    if param_patient_id and not form.is_submitted():
        form.patient_id.data = param_patient_id

    param_cns_id = request.args.get('consultation_id', type=int)
    if param_cns_id and not form.is_submitted():
        form.consultation_id.data = param_cns_id

    if form.validate_on_submit():
        patient_id = form.patient_id.data
        cns_id = form.consultation_id.data if form.consultation_id.data != 0 else None
        discount = form.discount.data or 0.0
        tax_pct = form.tax_percent.data if form.tax_percent.data is not None else 5.0
        notes = form.notes.data.strip() if form.notes.data else None

        bill = generate_auto_bill_for_patient(
            patient_id=patient_id,
            consultation_id=cns_id,
            discount=discount,
            tax_percent=tax_pct,
            notes=notes
        )

        flash(f'Invoice {bill.invoice_code} created successfully for ₹{bill.grand_total:.2f}!', 'success')
        return redirect(url_for('billing.view_bill', bill_id=bill.id))

    return render_template('billing/create.html', form=form, patients=patients)


@billing_bp.route('/<int:bill_id>', methods=['GET'])
@login_required
def view_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)

    # Permission check for Patient role
    if current_user.role.name == 'Patient' and bill.patient.email != current_user.email:
        flash('Access denied. You can only view your own hospital invoices.', 'danger')
        return redirect(url_for('billing.index'))

    payment_form = ProcessPaymentForm()
    payment_form.amount_paid.data = bill.balance_due

    return render_template('billing/view.html', bill=bill, payment_form=payment_form)


@billing_bp.route('/<int:bill_id>/payment', methods=['POST'])
@login_required
@role_required('Admin', 'Receptionist')
def record_payment(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    form = ProcessPaymentForm()

    if form.validate_on_submit():
        amt = form.amount_paid.data
        method = form.payment_method.data
        ref = form.transaction_ref.data.strip() if form.transaction_ref.data else None

        if amt <= 0:
            flash('Payment amount must be greater than zero.', 'danger')
            return redirect(url_for('billing.view_bill', bill_id=bill.id))

        if amt > bill.balance_due + 0.01:
            flash(f'Payment amount (₹{amt:.2f}) cannot exceed the balance due (₹{bill.balance_due:.2f}).', 'warning')
            return redirect(url_for('billing.view_bill', bill_id=bill.id))

        payment = Payment(
            bill_id=bill.id,
            payment_code=Payment.generate_payment_code(),
            payment_method=method,
            amount_paid=amt,
            transaction_ref=ref,
            recorded_by_id=current_user.id
        )
        db.session.add(payment)

        bill.paid_amount += amt
        if bill.paid_amount >= bill.grand_total - 0.01:
            bill.status = 'PAID'
        else:
            bill.status = 'PARTIALLY_PAID'

        db.session.commit()

        flash(f'Payment of ₹{amt:.2f} via {method} recorded successfully ({payment.payment_code})!', 'success')
        return redirect(url_for('billing.view_bill', bill_id=bill.id))

    flash('Failed to record payment. Please check your inputs.', 'danger')
    return redirect(url_for('billing.view_bill', bill_id=bill.id))


@billing_bp.route('/<int:bill_id>/print', methods=['GET'])
@login_required
def print_invoice(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    
    if current_user.role.name == 'Patient' and bill.patient.email != current_user.email:
        flash('Access denied.', 'danger')
        return redirect(url_for('billing.index'))

    return render_template('billing/print_invoice.html', bill=bill, now=datetime.now())
