from flask_wtf import FlaskForm
from wtforms import SelectField, FloatField, StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange

class CreateBillForm(FlaskForm):
    patient_id = SelectField('Select Patient', coerce=int, validators=[DataRequired()])
    consultation_id = SelectField('Link Consultation (Optional)', coerce=int, validators=[Optional()])
    discount = FloatField('Discount Amount (₹)', default=0.0, validators=[Optional(), NumberRange(min=0)])
    tax_percent = FloatField('Tax / GST (%)', default=5.0, validators=[Optional(), NumberRange(min=0, max=100)])
    notes = TextAreaField('Billing Notes / Remarks', validators=[Optional()])
    submit = SubmitField('Generate Hospital Invoice')


class ProcessPaymentForm(FlaskForm):
    payment_method = SelectField('Payment Method', choices=[
        ('Cash', 'Cash Payment'),
        ('UPI', 'UPI / QR Scan'),
        ('Credit Card', 'Credit Card'),
        ('Debit Card', 'Debit Card'),
        ('Insurance Claim', 'Insurance Claim')
    ], validators=[DataRequired()])
    amount_paid = FloatField('Amount to Pay (₹)', validators=[DataRequired(), NumberRange(min=0.01)])
    transaction_ref = StringField('Transaction Ref / UTR / Check No.', validators=[Optional()])
    submit = SubmitField('Record Payment')
