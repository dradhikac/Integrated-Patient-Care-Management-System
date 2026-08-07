from flask_wtf import FlaskForm
from wtforms import SelectField, HiddenField, SubmitField
from wtforms.validators import DataRequired

class CheckInForm(FlaskForm):
    patient_id = HiddenField('Patient ID', validators=[DataRequired()])
    doctor_id = SelectField('Assigned Doctor', coerce=int, validators=[DataRequired()])
    department = SelectField('Department', choices=[
        ('General OPD', 'General OPD'),
        ('Cardiology', 'Cardiology'),
        ('Orthopedics', 'Orthopedics'),
        ('Pediatrics', 'Pediatrics'),
        ('Gynaecology', 'Gynaecology'),
        ('Dermatology', 'Dermatology'),
        ('Emergency Triage', 'Emergency Triage')
    ], default='General OPD', validators=[DataRequired()])
    
    priority = SelectField('Patient Priority Level', choices=[
        ('Regular', 'Regular Patient'),
        ('Emergency', '🔴 Emergency (Immediate)'),
        ('Senior Citizen', '👴 Senior Citizen'),
        ('Pregnant Woman', '🤰 Pregnant Woman'),
        ('Child', '👶 Child')
    ], default='Regular', validators=[DataRequired()])

    submit = SubmitField('Check-In Patient & Issue Token')
