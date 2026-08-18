from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, FloatField, IntegerField, TextAreaField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange

class StaffUserCreateForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    role_id = SelectField('Role Assignment', coerce=int, validators=[DataRequired()])
    phone = StringField('Mobile Number', validators=[Optional(), Length(max=20)])
    specialization = StringField('Doctor Specialization / Department', validators=[Optional(), Length(max=100)])
    submit = SubmitField('Create Staff Account')


class MedicineForm(FlaskForm):
    brand_name = StringField('Brand / Trade Name', validators=[DataRequired(), Length(max=120)])
    generic_name = StringField('Generic Active Ingredient', validators=[DataRequired(), Length(max=120)])
    category = SelectField('Category', choices=[
        ('Tablet', 'Tablet'),
        ('Capsule', 'Capsule'),
        ('Syrup', 'Syrup / Liquid'),
        ('Injection', 'Injection'),
        ('Ointment', 'Ointment / Cream'),
        ('Drops', 'Drops')
    ], validators=[DataRequired()])
    dosage = StringField('Dosage Strength (e.g. 500mg)', validators=[DataRequired(), Length(max=50)])
    unit_price = FloatField('Unit Price (₹)', validators=[DataRequired(), NumberRange(min=0)])
    stock_quantity = IntegerField('Current Stock Quantity', validators=[DataRequired(), NumberRange(min=0)])
    manufacturer = StringField('Manufacturer', validators=[Optional(), Length(max=100)])
    submit = SubmitField('Save Medicine')


class LabTestTypeForm(FlaskForm):
    test_code = StringField('Test Code (e.g. LAB-CBC)', validators=[DataRequired(), Length(max=50)])
    test_name = StringField('Test Name', validators=[DataRequired(), Length(max=100)])
    category = SelectField('Category', choices=[
        ('Hematology', 'Hematology'),
        ('Biochemistry', 'Biochemistry'),
        ('Microbiology', 'Microbiology'),
        ('Radiology', 'Radiology / Imaging'),
        ('Pathology', 'General Pathology')
    ], validators=[DataRequired()])
    price = FloatField('Standard Test Price (₹)', validators=[DataRequired(), NumberRange(min=0)])
    normal_range = StringField('Reference Normal Range', validators=[Optional(), Length(max=100)])
    unit = StringField('Measurement Unit (e.g. mg/dL)', validators=[Optional(), Length(max=50)])
    submit = SubmitField('Save Lab Test Type')


class SystemSettingForm(FlaskForm):
    hospital_name = StringField('Hospital Name', validators=[DataRequired(), Length(max=150)])
    opd_consultation_fee = FloatField('OPD Consultation Fee (₹)', validators=[DataRequired(), NumberRange(min=0)])
    ipd_bed_rate_general = FloatField('General Ward Bed Daily Rate (₹)', validators=[DataRequired(), NumberRange(min=0)])
    ipd_bed_rate_icu = FloatField('ICU Ward Bed Daily Rate (₹)', validators=[DataRequired(), NumberRange(min=0)])
    gst_tax_rate = FloatField('GST / Service Tax Rate (%)', validators=[DataRequired(), NumberRange(min=0, max=100)])
    emergency_surcharge = FloatField('Emergency Surcharge Fee (₹)', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Save System Settings')
