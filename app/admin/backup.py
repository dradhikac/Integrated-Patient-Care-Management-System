import os
import json
from datetime import datetime
from app.extensions import db
from app.auth.models import User, Role
from app.admin.models import AuditLog
from app.patients.models import Patient
from app.appointments.models import Appointment
from app.consultations.models import Consultation
from app.billing.models import Bill
from app.beds.models import Admission

def trigger_db_backup(admin_user_id: int = None) -> dict:
    """
    Generates a timestamped JSON database snapshot of key hospital tables,
    saves it to the `backups/` directory, and logs the execution in `audit_logs`.
    """
    backup_dir = os.path.join(os.getcwd(), 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"ipcms_backup_{timestamp}.json"
    filepath = os.path.join(backup_dir, filename)

    snapshot_data = {
        'timestamp': datetime.now().isoformat(),
        'generated_by_user_id': admin_user_id,
        'summary': {
            'users_count': User.query.count(),
            'patients_count': Patient.query.count(),
            'appointments_count': Appointment.query.count(),
            'consultations_count': Consultation.query.count(),
            'bills_count': Bill.query.count(),
            'admissions_count': Admission.query.count()
        }
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(snapshot_data, f, indent=2)

    file_size_kb = round(os.path.getsize(filepath) / 1024, 2)

    # Log in audit_logs
    if admin_user_id:
        log_entry = AuditLog(
            user_id=admin_user_id,
            action='BACKUP_DATABASE',
            entity_type='Database',
            entity_id=0,
            details=f"Manual DB Backup triggered. Snapshot saved to {filename} ({file_size_kb} KB)."
        )
        db.session.add(log_entry)
        db.session.commit()

    return {
        'filename': filename,
        'filepath': filepath,
        'file_size_kb': file_size_kb,
        'timestamp': timestamp
    }
