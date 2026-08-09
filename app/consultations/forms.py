from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, FloatField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Optional

class ConsultationForm(FlaskForm):
    patient_id = HiddenField('Patient ID', validators=[DataRequired()])
    check_in_id = HiddenField('Check-In ID', validators=[Optional()])
    appointment_id = HiddenField('Appointment ID', validators=[Optional()])

    symptoms = TextAreaField('Chief Complaints / Presenting Symptoms', validators=[DataRequired()])
    diagnosis = TextAreaField('Primary & Secondary Clinical Diagnoses', validators=[DataRequired()])
    treatment_plan = TextAreaField('Treatment Plan & Clinical Advice', validators=[Optional()])
    notes = TextAreaField('Doctor Private Clinical Notes', validators=[Optional()])

    # Clinical Vitals
    bp_systolic = IntegerField('BP Systolic (mmHg)', validators=[Optional()])
    bp_diastolic = IntegerField('BP Diastolic (mmHg)', validators=[Optional()])
    temperature_f = FloatField('Body Temp (°F)', validators=[Optional()])
    pulse_bpm = IntegerField('Pulse Rate (bpm)', validators=[Optional()])
    spo2_percent = IntegerField('SpO2 Saturation (%)', validators=[Optional()])

    submit = SubmitField('Complete Consultation & Save Clinical Record')
