from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional

class AdmissionForm(FlaskForm):
    patient_id = SelectField('Select Patient', coerce=int, validators=[DataRequired()])
    doctor_id = SelectField('Admitting Doctor', coerce=int, validators=[DataRequired()])
    ward_id = SelectField('Select Ward', coerce=int, validators=[DataRequired()])
    bed_id = SelectField('Select Available Bed', coerce=int, validators=[DataRequired()])
    diagnosis = TextAreaField('Admission Diagnosis / Clinical Reason', validators=[DataRequired()])
    submit = SubmitField('Admit Patient to Bed')


class BedTransferForm(FlaskForm):
    target_bed_id = SelectField('Select New Destination Bed', coerce=int, validators=[DataRequired()])
    reason = StringField('Transfer Reason / Medical Rationale', validators=[DataRequired()])
    submit = SubmitField('Transfer Patient')


class DischargeForm(FlaskForm):
    discharge_notes = TextAreaField('Discharge Summary Notes', validators=[Optional()])
    submit = SubmitField('Confirm Inpatient Discharge')
