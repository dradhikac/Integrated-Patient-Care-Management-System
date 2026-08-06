from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, FloatField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Email, Length, Regexp

class PatientRegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    dob = DateField('Date of Birth', validators=[DataRequired()], format='%Y-%m-%d')
    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], validators=[DataRequired()])
    mobile = StringField('Mobile Number', validators=[DataRequired(), Regexp(r'^\+?[0-9]{10,15}$', message="Enter a valid 10-15 digit mobile number.")])
    email = StringField('Email Address', validators=[Optional(), Email()])
    address = TextAreaField('Residential Address', validators=[Optional()])
    
    # Aadhaar (12 digits)
    aadhaar_number = StringField('Aadhaar Number (12 Digits)', validators=[Optional(), Regexp(r'^\d{12}$', message="Aadhaar must be exactly 12 digits.")])
    
    blood_group = SelectField('Blood Group', choices=[
        ('', '-- Select Blood Group --'),
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-')
    ], validators=[Optional()])
    
    emergency_contact_name = StringField('Emergency Contact Name', validators=[Optional()])
    emergency_contact_mobile = StringField('Emergency Contact Mobile', validators=[Optional()])
    
    insurance_provider = StringField('Insurance Provider', validators=[Optional()])
    insurance_policy_no = StringField('Policy / TPA Card No.', validators=[Optional()])
    
    # Vitals Baseline
    height_cm = FloatField('Height (cm)', validators=[Optional()])
    weight_kg = FloatField('Weight (kg)', validators=[Optional()])
    
    allergies = StringField('Known Allergies (Comma separated)', validators=[Optional()])
    chronic_diseases = TextAreaField('Medical History / Chronic Diseases', validators=[Optional()])
    vaccination_records = TextAreaField('Vaccination History', validators=[Optional()])
    preferred_language = SelectField('Preferred Language', choices=[
        ('English', 'English'), ('Hindi', 'Hindi'), ('Tamil', 'Tamil'),
        ('Telugu', 'Telugu'), ('Kannada', 'Kannada'), ('Marathi', 'Marathi'),
        ('Bengali', 'Bengali'), ('Gujarati', 'Gujarati'), ('Other', 'Other')
    ], default='English')
    
    submit = SubmitField('Register Patient')
