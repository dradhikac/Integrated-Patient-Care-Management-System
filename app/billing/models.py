from datetime import datetime
from app.extensions import db

class Bill(db.Model):
    __tablename__ = 'bills'

    id = db.Column(db.Integer, primary_key=True)
    invoice_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultations.id'), nullable=True)
    
    subtotal = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    grand_total = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default='UNPAID') # 'UNPAID', 'PARTIALLY_PAID', 'PAID'
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', backref='bills', lazy=True)
    consultation = db.relationship('Consultation', backref='bills', lazy=True)

    @staticmethod
    def generate_invoice_code():
        year = datetime.now().year
        last_bill = Bill.query.order_by(Bill.id.desc()).first()
        new_num = (last_bill.id + 1) if last_bill else 1
        return f"INV-{year}-{new_num:06d}"

    @property
    def balance_due(self):
        return max(0.0, round(self.grand_total - self.paid_amount, 2))

    def update_totals(self):
        self.subtotal = sum(item.total_price for item in self.items)
        self.grand_total = max(0.0, round(self.subtotal - self.discount + self.tax_amount, 2))
        if self.paid_amount >= self.grand_total and self.grand_total > 0:
            self.status = 'PAID'
        elif self.paid_amount > 0:
            self.status = 'PARTIALLY_PAID'
        else:
            self.status = 'UNPAID'


class BillItem(db.Model):
    __tablename__ = 'bill_items'

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id', ondelete='CASCADE'), nullable=False)
    item_type = db.Column(db.String(50), nullable=False) # 'REGISTRATION', 'CONSULTATION', 'LAB_TEST', 'MEDICINE', 'MISC'
    item_description = db.Column(db.String(255), nullable=False)
    unit_price = db.Column(db.Float, nullable=False, default=0.0)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    total_price = db.Column(db.Float, nullable=False, default=0.0)

    bill = db.relationship('Bill', backref=db.backref('items', cascade='all, delete-orphan', lazy=True))


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id', ondelete='CASCADE'), nullable=False)
    payment_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    payment_method = db.Column(db.String(50), nullable=False) # 'Cash', 'UPI', 'Credit Card', 'Debit Card', 'Insurance Claim'
    amount_paid = db.Column(db.Float, nullable=False)
    transaction_ref = db.Column(db.String(100), nullable=True) # Transaction ID / Cheque / Ref No.
    recorded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    paid_at = db.Column(db.DateTime, default=datetime.utcnow)

    bill = db.relationship('Bill', backref=db.backref('payments', cascade='all, delete-orphan', lazy=True))
    recorded_by = db.relationship('User', backref='recorded_payments', lazy=True)

    @staticmethod
    def generate_payment_code():
        year = datetime.now().year
        last_pay = Payment.query.order_by(Payment.id.desc()).first()
        new_num = (last_pay.id + 1) if last_pay else 1
        return f"PAY-{year}-{new_num:06d}"
