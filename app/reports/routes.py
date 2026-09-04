from datetime import datetime
from flask import Blueprint, render_template, Response, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.auth.utils import role_required
from app.auth.models import User, Role
from app.patients.models import Patient
from app.appointments.models import Appointment
from app.consultations.models import Consultation
from app.lab.models import LabRequest
from app.billing.models import Bill
from app.reports.analytics import (
    get_today_admin_kpis,
    get_monthly_revenue_trend,
    get_appointment_status_breakdown,
    get_departmental_revenue_share
)
from app.reports.exporter import generate_csv_report

reports_bp = Blueprint('reports', __name__, template_folder='templates', url_prefix='/reports')

@reports_bp.route('/dashboard')
@login_required
@role_required('Admin', 'Doctor', 'Receptionist')
def dashboard():
    if current_user.role and current_user.role.name == 'Receptionist':
        return redirect(url_for('reception.daily_reports'))

    kpis = get_today_admin_kpis()
    monthly_trend = get_monthly_revenue_trend()
    status_breakdown = get_appointment_status_breakdown()
    revenue_share = get_departmental_revenue_share()

    return render_template('reports/dashboard.html',
                           kpis=kpis,
                           monthly_trend=monthly_trend,
                           status_breakdown=status_breakdown,
                           revenue_share=revenue_share,
                           now=datetime.now())


@reports_bp.route('/export/<report_type>')
@login_required
@role_required('Admin', 'Doctor', 'Receptionist')
def export_report(report_type):
    valid_types = ['patient', 'revenue', 'doctor', 'appointment', 'lab']
    if report_type not in valid_types:
        flash('Invalid report type requested.', 'danger')
        return redirect(url_for('reports.dashboard'))

    fmt = request.args.get('format', 'csv').lower()

    if fmt == 'pdf':
        # Render printable HTML report for PDF export
        now = datetime.now()
        if report_type == 'patient':
            data = Patient.query.order_by(Patient.id.desc()).all()
            return render_template('reports/patient_report_pdf.html', data=data, now=now)
        elif report_type == 'revenue':
            data = Bill.query.order_by(Bill.id.desc()).all()
            return render_template('reports/revenue_report_pdf.html', data=data, now=now)
        elif report_type == 'doctor':
            doc_role = Role.query.filter_by(name='Doctor').first()
            data = User.query.filter_by(role_id=doc_role.id).all() if doc_role else []
            return render_template('reports/doctor_report_pdf.html', data=data, now=now)
        elif report_type == 'appointment':
            data = Appointment.query.order_by(Appointment.id.desc()).all()
            return render_template('reports/appointment_report_pdf.html', data=data, now=now)
        elif report_type == 'lab':
            data = LabRequest.query.order_by(LabRequest.id.desc()).all()
            return render_template('reports/lab_report_pdf.html', data=data, now=now)

    # Default CSV Export
    csv_data = generate_csv_report(report_type)
    filename = f"ipcms_{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )
