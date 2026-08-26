from datetime import datetime
from app.extensions import db

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(50), nullable=False) # 'APPOINTMENT_REMINDER', 'LAB_READY', 'PRESCRIPTION_READY', 'PAYMENT_REMINDER', 'FOLLOWUP_REMINDER'
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(30), default='BOTH') # 'EMAIL', 'SMS', 'BOTH'
    status = db.Column(db.String(30), default='PENDING') # 'PENDING', 'SENT', 'FAILED'
    scheduled_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', backref=db.backref('notifications', cascade='all, delete-orphan', lazy=True))

    def __repr__(self):
        return f"<Notification {self.id} {self.type} - {self.status}>"


class NotificationLog(db.Model):
    __tablename__ = 'notification_log'

    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey('notifications.id', ondelete='CASCADE'), nullable=False)
    channel = db.Column(db.String(30), nullable=False) # 'EMAIL', 'SMS'
    recipient = db.Column(db.String(150), nullable=False)
    payload = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default='SUCCESS') # 'SUCCESS', 'FAILED'
    error_message = db.Column(db.Text, nullable=True)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    notification = db.relationship('Notification', backref=db.backref('logs', cascade='all, delete-orphan', lazy=True))

    def __repr__(self):
        return f"<NotificationLog {self.id} {self.channel} -> {self.recipient} ({self.status})>"


class StaffNotification(db.Model):
    __tablename__ = 'staff_notifications'

    id = db.Column(db.Integer, primary_key=True)
    role_target = db.Column(db.String(50), default='Receptionist', index=True) # 'Receptionist', 'Doctor', 'LabTech', 'Admin'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    category = db.Column(db.String(50), nullable=False, default='CHECK_IN') # 'CHECK_IN', 'QUEUE', 'APPOINTMENT', 'PATIENT', 'PAYMENT', 'EMERGENCY'
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(50), default='bi-bell-fill')
    color = db.Column(db.String(30), default='#2563EB')
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True)
    reference_code = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)

    # Relationships
    patient = db.relationship('Patient', backref='staff_notifications', lazy=True)

    @property
    def time_ago(self):
        """Returns user-friendly relative time string e.g. '2 min ago', '15 min ago', '10:30 PM'"""
        if not self.created_at:
            return 'Just now'
        delta = datetime.now() - self.created_at
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return 'Just now'
        elif seconds < 3600:
            mins = seconds // 60
            return f"{mins} min ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h ago"
        else:
            return self.created_at.strftime('%d %b, %I:%M %p')

    def __repr__(self):
        return f"<StaffNotification {self.id} [{self.role_target}] {self.title} - Read={self.is_read}>"

