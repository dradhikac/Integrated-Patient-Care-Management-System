from app.extensions import db
from app.patients.models import Patient
from app.consultations.models import Consultation
from app.prescriptions.models import Prescription
from app.lab.models import LabRequest
from app.billing.models import Bill, BillItem

def generate_auto_bill_for_patient(patient_id: int, consultation_id: int = None, discount: float = 0.0, tax_percent: float = 5.0, notes: str = None) -> Bill:
    """
    Automated Charges Aggregator:
    Aggregates OPD consultation, prescribed medications, and ordered lab tests
    into an itemized hospital invoice.
    """
    patient = Patient.query.get(patient_id)
    if not patient:
        return None

    invoice_code = Bill.generate_invoice_code()
    bill = Bill(
        invoice_code=invoice_code,
        patient_id=patient_id,
        consultation_id=consultation_id,
        discount=discount,
        notes=notes or "Automated hospital charges compilation"
    )
    db.session.add(bill)
    db.session.flush()

    subtotal = 0.0

    # 1. Base OPD Consultation Fee
    consult_fee = 500.0
    cns_desc = "OPD Consultation Fee"
    if consultation_id:
        cns = Consultation.query.get(consultation_id)
        if cns:
            cns_desc = f"OPD Consultation — {cns.doctor.name} ({cns.consultation_code})"

    item_cns = BillItem(
        bill_id=bill.id,
        item_type='CONSULTATION',
        item_description=cns_desc,
        unit_price=consult_fee,
        quantity=1,
        total_price=consult_fee
    )
    db.session.add(item_cns)
    subtotal += consult_fee

    # 2. Prescribed Medications (from linked or recent prescriptions)
    rx_query = Prescription.query.filter_by(patient_id=patient_id)
    if consultation_id:
        rx_query = rx_query.filter_by(consultation_id=consultation_id)
    
    prescriptions = rx_query.all()
    for rx in prescriptions:
        for p_item in rx.items:
            med_price = 150.0 # Default standard prescription item price
            if p_item.medicine and hasattr(p_item.medicine, 'cost') and p_item.medicine.cost:
                med_price = p_item.medicine.cost
            
            med_total = med_price * 1
            item_med = BillItem(
                bill_id=bill.id,
                item_type='MEDICINE',
                item_description=f"Rx Medicine: {p_item.medicine_name} ({p_item.dosage_frequency or '1-0-1'}, {p_item.duration or '5 Days'})",
                unit_price=med_price,
                quantity=1,
                total_price=med_total
            )
            db.session.add(item_med)
            subtotal += med_total

    # 3. Lab Investigations (from linked or recent lab requests)
    lab_query = LabRequest.query.filter_by(patient_id=patient_id)
    if consultation_id:
        lab_query = lab_query.filter_by(consultation_id=consultation_id)
    
    lab_requests = lab_query.all()
    for lr in lab_requests:
        for res in lr.results:
            lab_cost = res.test_type.cost if (res.test_type and res.test_type.cost) else 400.0
            item_lab = BillItem(
                bill_id=bill.id,
                item_type='LAB_TEST',
                item_description=f"Lab Investigation: {res.test_type.test_name} [{res.test_type.category}]",
                unit_price=lab_cost,
                quantity=1,
                total_price=lab_cost
            )
            db.session.add(item_lab)
            subtotal += lab_cost

    # Calculate Tax & Grand Total
    bill.subtotal = subtotal
    bill.tax_amount = round(subtotal * (tax_percent / 100.0), 2)
    bill.grand_total = max(0.0, round(subtotal - discount + bill.tax_amount, 2))
    bill.status = 'UNPAID'

    db.session.commit()
    return bill
