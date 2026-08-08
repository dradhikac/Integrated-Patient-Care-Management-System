from datetime import datetime, date
from app.reception.models import CheckIn
from app.queue_mgmt.models import QueuePriorityRule

def sort_queue_by_priority(check_ins):
    """
    Sorts check-in queue items based on healthcare priority rules:
    Primary Sort: Priority Weight (Emergency > Senior Citizen > Pregnant > Child > Regular)
    Secondary Sort: Check-In Timestamp (First In First Out)
    """
    def get_sort_key(item: CheckIn):
        weight = QueuePriorityRule.get_priority_weight(item.priority)
        # Invert weight so higher weight comes first, then earlier check_in_time
        return (-weight, item.check_in_time)

    return sorted(check_ins, key=get_sort_key)


def calculate_rolling_avg_consultation_time(doctor_id: int) -> float:
    """
    Calculates rolling average consultation duration (in minutes) for a doctor from today's completed visits.
    Defaults to 10.0 minutes if no visits completed yet today.
    """
    today_start = datetime.combine(date.today(), datetime.min.time())
    completed_visits = CheckIn.query.filter(
        CheckIn.doctor_id == doctor_id,
        CheckIn.check_in_time >= today_start,
        CheckIn.status == 'COMPLETED',
        CheckIn.called_time.isnot(None),
        CheckIn.completed_time.isnot(None)
    ).all()

    if not completed_visits:
        return 10.0 # Default baseline 10 minutes

    total_minutes = 0.0
    for visit in completed_visits:
        duration = (visit.completed_time - visit.called_time).total_seconds() / 60.0
        total_minutes += max(1.0, duration) # At least 1 minute

    avg_minutes = total_minutes / len(completed_visits)
    return round(avg_minutes, 1)
