"""
Database Seeding Script
Executes full hospital data seeding inside Flask app context.
"""
from app import create_app
from app.extensions import db
from app.admin.seed_live_data import seed_full_hospital_data

app = create_app()

with app.app_context():
    seed_full_hospital_data()
    print("ALL SEEDING COMPLETED SUCCESSFULLY!")
