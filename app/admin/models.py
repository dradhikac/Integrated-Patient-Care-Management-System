from datetime import datetime
from app.extensions import db

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_val(cls, key: str, default_val: str = '') -> str:
        setting = cls.query.filter_by(setting_key=key).first()
        return setting.setting_value if setting else default_val

    @classmethod
    def set_val(cls, key: str, value: str, description: str = None):
        setting = cls.query.filter_by(setting_key=key).first()
        if not setting:
            setting = cls(setting_key=key, setting_value=str(value), description=description)
            db.session.add(setting)
        else:
            setting.setting_value = str(value)
            if description:
                setting.description = description
        db.session.commit()


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='audit_logs', lazy=True)


class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    dept_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    dept_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), default='Clinical')
    description = db.Column(db.Text, nullable=True)
    operating_hours = db.Column(db.String(100), default='08:00 AM - 08:00 PM')
    room_numbers = db.Column(db.String(100), nullable=True)
    head_doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    head_doctor = db.relationship('User', foreign_keys=[head_doctor_id], lazy=True)


class Equipment(db.Model):
    __tablename__ = 'equipment'

    id = db.Column(db.Integer, primary_key=True)
    equipment_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    manufacturer = db.Column(db.String(100), nullable=True)
    purchase_date = db.Column(db.Date, nullable=True)
    warranty_until = db.Column(db.Date, nullable=True)
    last_maintenance = db.Column(db.Date, nullable=True)
    next_maintenance = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), default='OPERATIONAL')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

