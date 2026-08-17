from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired

class ManualNotificationForm(FlaskForm):
    patient_id = SelectField('Select Recipient Patient', coerce=int, validators=[DataRequired()])
    type = SelectField('Notification Category', choices=[
        ('APPOINTMENT_REMINDER', 'Appointment Reminder'),
        ('LAB_READY', 'Lab Report Ready Alert'),
        ('PRESCRIPTION_READY', 'Prescription Ready Alert'),
        ('PAYMENT_REMINDER', 'Payment & Invoice Reminder'),
        ('FOLLOWUP_REMINDER', 'Follow-Up Care Reminder')
    ], validators=[DataRequired()])
    channel = SelectField('Dispatch Channel', choices=[
        ('BOTH', 'Email & SMS (Both)'),
        ('EMAIL', 'Email Only'),
        ('SMS', 'SMS Only')
    ], default='BOTH')
    title = StringField('Notification Subject / Title', validators=[DataRequired()])
    message = TextAreaField('Notification Message Body', validators=[DataRequired()])
    submit = SubmitField('Dispatch Notification')
