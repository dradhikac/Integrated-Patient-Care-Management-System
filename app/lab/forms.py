from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, HiddenField, SelectMultipleField, SubmitField
from wtforms.validators import DataRequired, Optional

class LabRequestForm(FlaskForm):
    patient_id = HiddenField('Patient ID', validators=[DataRequired()])
    consultation_id = HiddenField('Consultation ID', validators=[Optional()])
    clinical_notes = TextAreaField('Doctor Clinical Indications / Reason for Test', validators=[Optional()])
    submit = SubmitField('Order Laboratory Test')


class LabResultForm(FlaskForm):
    test_type_id = HiddenField('Test Type ID', validators=[DataRequired()])
    result_value = FloatField('Measured Value', validators=[DataRequired()])
    remarks = TextAreaField('Technician Remarks / Observations', validators=[Optional()])
    submit = SubmitField('Save Lab Result')
