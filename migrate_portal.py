"""
One-shot migration: add portal columns to patients and password_resets.
Safe to run multiple times (IF NOT EXISTS checks).
"""
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        # --- patients table ---
        try:
            conn.execute(text(
                "ALTER TABLE patients ADD COLUMN portal_status VARCHAR(20) NOT NULL DEFAULT 'NOT_ACTIVATED'"
            ))
            print("+ Added patients.portal_status")
        except Exception as e:
            print(f"  patients.portal_status skip: {e}")

        try:
            conn.execute(text(
                "ALTER TABLE patients ADD COLUMN portal_user_id INT NULL"
            ))
            print("+ Added patients.portal_user_id")
        except Exception as e:
            print(f"  patients.portal_user_id skip: {e}")

        try:
            conn.execute(text(
                "ALTER TABLE password_resets MODIFY COLUMN user_id INT NULL"
            ))
            print("+ Made password_resets.user_id nullable")
        except Exception as e:
            print(f"  password_resets.user_id modify skip: {e}")

        try:
            conn.execute(text(
                "ALTER TABLE password_resets ADD COLUMN patient_id INT NULL"
            ))
            print("+ Added password_resets.patient_id")
        except Exception as e:
            print(f"  password_resets.patient_id skip: {e}")

        try:
            conn.execute(text(
                "ALTER TABLE password_resets ADD COLUMN purpose VARCHAR(30) NOT NULL DEFAULT 'PASSWORD_RESET'"
            ))
            print("+ Added password_resets.purpose")
        except Exception as e:
            print(f"  password_resets.purpose skip: {e}")

        conn.commit()

    print("\nMigration complete.")
