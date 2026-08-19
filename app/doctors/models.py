from datetime import datetime
from app.extensions import db

class Doctor(db.Model):
    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    doctor_code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    education = db.Column(db.String(255), nullable=False)
    experience = db.Column(db.String(50), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    consultation_fee = db.Column(db.Float, default=500.0)
    image_url = db.Column(db.String(255), nullable=False)
    available_days = db.Column(db.String(100), default="Monday - Saturday")
    rating = db.Column(db.Float, default=4.9)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='doctor_profile', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'doctor_code': self.doctor_code,
            'name': self.name,
            'specialization': self.specialization,
            'education': self.education,
            'experience': self.experience,
            'department': self.department,
            'bio': self.bio,
            'consultation_fee': self.consultation_fee,
            'image_url': self.image_url,
            'available_days': self.available_days,
            'rating': self.rating,
            'is_active': self.is_active
        }

    def __repr__(self):
        return f"<Doctor {self.doctor_code} - {self.name}>"
