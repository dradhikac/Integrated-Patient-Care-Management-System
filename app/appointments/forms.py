from flask_wtf import FlaskForm
from wtforms import StringField, DateField, TimeField, SelectField, IntegerField, TextAreaField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Optional

class BookAppointmentForm(FlaskForm):
    patient_id = SelectField('Select Patient', coerce=int, validators=[DataRequired()])
    doctor_id = SelectField('Select Doctor', coerce=int, validators=[DataRequired()])
    appointment_date = DateField('Appointment Date', validators=[DataRequired()], format='%Y-%m-%d')
    slot_time = StringField('Slot Time', validators=[DataRequired()]) # e.g. "09:15:00"
    priority = SelectField('Priority Classification', choices=[
        ('Regular', 'Regular Priority'),
        ('Emergency', 'Emergency (High Priority)'),
        ('Senior Citizen', 'Senior Citizen (Age 60+)'),
        ('Pregnant Woman', 'Pregnant Woman'),
        ('Child', 'Child (Age < 12)')
    ], default='Regular')
    booking_type = SelectField('Booking Channel', choices=[
        ('Online', 'Online Booking'),
        ('Walk-In', 'Reception Walk-In'),
        ('Emergency', 'Emergency Reserve')
    ], default='Online')
    notes = TextAreaField('Clinical Notes / Chief Complaints', validators=[Optional()])
    submit = SubmitField('Confirm Appointment Booking')


class DoctorAvailabilityForm(FlaskForm):
    day_of_week = SelectField('Day of Week', choices=[
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ], coerce=int, validators=[DataRequired()])
    start_time = TimeField('Shift Start Time', validators=[DataRequired()], format='%H:%M')
    end_time = TimeField('Shift End Time', validators=[DataRequired()], format='%H:%M')
    slot_duration_minutes = IntegerField('Slot Duration (Minutes)', default=15, validators=[DataRequired()])
    submit = SubmitField('Save Availability Schedule')


class HolidayForm(FlaskForm):
    holiday_date = DateField('Holiday Date', validators=[DataRequired()], format='%Y-%m-%d')
    description = StringField('Holiday Reason / Event Name', validators=[DataRequired()])
    submit = SubmitField('Add Hospital Holiday')
