"""
MediCore+ Dynamic Appointment Arrival Window & Slot Helper
Provides dynamic queue integration and arrival window generation.
"""
from datetime import date
from app.queue.queue_engine import get_doctor_clinic_windows

def generate_doctor_slots(doctor_id: int, target_date: date, allow_emergency: bool = False):
    """
    Generates arrival windows and live clinic queue metrics for a doctor on target_date.
    Delegates to the central queue_engine while preserving backwards compatibility.
    """
    return get_doctor_clinic_windows(doctor_id, target_date)
