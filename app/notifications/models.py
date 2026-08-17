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
