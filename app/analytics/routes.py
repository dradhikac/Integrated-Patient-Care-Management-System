from datetime import datetime
from flask import Blueprint, render_template, Response, redirect, url_for, flash
from flask_login import login_required, current_user
from app.auth.utils import role_required
from app.analytics.reports import get_hospital_analytics_summary, generate_invoices_csv_report, generate_patients_csv_report

analytics_bp = Blueprint('analytics', __name__, template_folder='templates', url_prefix='/analytics')

@analytics_bp.route('/')
@login_required
@role_required('Admin', 'Doctor', 'Receptionist')
def index():
    summary = get_hospital_analytics_summary()
    return render_template('analytics/index.html', summary=summary, now=datetime.now())


@analytics_bp.route('/export/invoices')
@login_required
@role_required('Admin', 'Receptionist')
def export_invoices_csv():
    csv_data = generate_invoices_csv_report()
    filename = f"ipcms_invoices_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )


@analytics_bp.route('/export/patients')
@login_required
@role_required('Admin', 'Receptionist', 'Doctor')
def export_patients_csv():
    csv_data = generate_patients_csv_report()
    filename = f"ipcms_patients_registry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )


@analytics_bp.route('/print')
@login_required
@role_required('Admin', 'Doctor')
def print_executive_summary():
    summary = get_hospital_analytics_summary()
    return render_template('analytics/print_executive_summary.html', summary=summary, now=datetime.now())
