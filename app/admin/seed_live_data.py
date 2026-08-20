"""
Realistic Hospital Operational Data Seeder for MediCore+ / IPCMS
Populates comprehensive, interconnected, and production-like database records.
"""

from datetime import datetime, date, timedelta, time
import random
from app.extensions import db
from app.auth.models import User, Role
from app.patients.models import Patient, PatientMedicalHistory, PatientAllergy
from app.doctors.models import Doctor
from app.beds.models import Ward, Bed, Admission
from app.appointments.models import Appointment, DoctorAvailability
from app.prescriptions.models import Medicine
from app.lab.models import LabTestType, LabRequest, LabResult
from app.billing.models import Bill, BillItem, Payment
from app.admin.models import Department, Equipment, AuditLog
from app.notifications.models import Notification

def seed_full_hospital_data():
    """Seeds rich, realistic hospital data if not already populated."""
    print("[SEEDER] Starting full hospital operational database seeding...")

    # 1. Departments & Equipment
    from app.admin.utils import ensure_departments_seeded, ensure_equipment_seeded
    ensure_departments_seeded()
    ensure_equipment_seeded()

    # 2. Roles
    roles_data = [
        ('Admin', 'System administrator with full control'),
        ('Receptionist', 'Front desk check-in and queue operator'),
        ('Doctor', 'Consultation, EHR timeline, and digital prescriptions'),
        ('Lab Technician', 'Laboratory test requests and report uploads'),
        ('Patient', 'Patient health portal access')
    ]
    roles_dict = {}
    for r_name, r_desc in roles_data:
        role = Role.query.filter_by(name=r_name).first()
        if not role:
            role = Role(name=r_name, description=r_desc)
            db.session.add(role)
            db.session.flush()
        roles_dict[r_name] = role
    db.session.commit()

    # 3. Staff Users
    staff_accounts = [
        ('ADM-999', 'MediCore Administrator', 'admin@ipcms.com', 'Admin', 'Password@123'),
        ('ADM-888', 'Hospital Super Admin', 'administrator@medicore.com', 'Admin', 'Admin@123'),
        ('ADM-777', 'Chief System Admin', 'superadmin@ipcms.com', 'Admin', 'Password@123'),
        ('REC-001', 'Pooja Hegde (Front Desk)', 'reception@ipcms.com', 'Receptionist', 'Password@123'),
        ('LAB-001', 'Suresh Kumar (Lab Tech)', 'lab@ipcms.com', 'Lab Technician', 'Password@123'),
        ('PAT-001', 'Ananya Verma (Patient)', 'patient@ipcms.com', 'Patient', 'Password@123')
    ]
    for code, name, email, r_name, pwd in staff_accounts:
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(user_code=code, name=name, email=email, role_id=roles_dict[r_name].id, mobile='+91-9876543210', is_active=True)
            u.set_password(pwd)
            db.session.add(u)
        else:
            u.role_id = roles_dict[r_name].id
            u.set_password(pwd)
            u.is_active = True
    db.session.commit()

    # 4. Doctors
    doctors_info = [
        ('DOC-101', 'Dr. Ananya Sharma', 'ananya.sharma@medicore.com', 'Cardiologist', 'MBBS, MD, DM (Cardiology)', '12+ Years', 'Cardiology & Heart Institute', 'Specialist in non-invasive cardiology and heart health.', 800.0, '/static/images/doctors/dr_ananya_sharma.jpg'),
        ('DOC-102', 'Dr. Rahul Verma', 'rahul.verma@medicore.com', 'Neurologist', 'MBBS, MD, DM (Neurology)', '15+ Years', 'Neurology & Spine Care', 'Senior consultant neurologist specializing in stroke and epilepsy.', 1000.0, '/static/images/doctors/dr_rahul_verma.jpg'),
        ('DOC-103', 'Dr. Priya Nair', 'priya.nair@medicore.com', 'Gynecologist', 'MBBS, MD (Obstetrics & Gynae)', '10+ Years', 'Obstetrics & Gynecology', 'Expert in maternal healthcare and laparoscopic surgeries.', 900.0, '/static/images/doctors/dr_priya_nair.jpg'),
        ('DOC-104', 'Dr. Arjun Mehta', 'arjun.mehta@medicore.com', 'Orthopedic Surgeon', 'MBBS, MS (Orthopedics)', '14+ Years', 'Orthopedics & Joint Care', 'Leading orthopedic surgeon specializing in robotic joint replacement.', 1100.0, '/static/images/doctors/dr_arjun_mehta.jpg'),
        ('DOC-105', 'Dr. Kavya Rao', 'kavya.rao@medicore.com', 'Pediatrician', 'MBBS, MD (Pediatrics)', '8+ Years', 'Pediatrics & Child Care', 'Child specialist dedicated to newborn and adolescent health.', 700.0, '/static/images/doctors/dr_kavya_rao.jpg'),
        ('DOC-106', 'Dr. Vikram Desai', 'vikram.desai@medicore.com', 'Radiologist', 'MBBS, MD (Radiodiagnosis)', '11+ Years', 'Diagnostics & Radiology', 'Chief radiologist specializing in 3T MRI and Spectral CT.', 850.0, '/static/images/doctors/dr_vikram_desai.jpg')
    ]
    doctor_users = []
    for code, name, email, spec, edu, exp, dept, bio, fee, img in doctors_info:
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(user_code=code, name=name, email=email, role_id=roles_dict['Doctor'].id, mobile='+91-9876543210', is_active=True)
            u.set_password('Password@123')
            db.session.add(u)
            db.session.flush()
        else:
            u.role_id = roles_dict['Doctor'].id
            u.set_password('Password@123')
            u.is_active = True
        doctor_users.append(u)

        doc = Doctor.query.filter_by(doctor_code=code).first()
        if not doc:
            doc = Doctor(user_id=u.id, doctor_code=code, name=name, specialization=spec, education=edu, experience=exp, department=dept, bio=bio, consultation_fee=fee, image_url=img, available_days='Monday - Saturday', rating=4.9, is_active=True)
            db.session.add(doc)
    db.session.commit()

    # 5. Medicines Formulary & Pharmacy Inventory
    if Medicine.query.count() < 10:
        medicines_list = [
            ('Dolo 650', 'Paracetamol', 'Tablet', '650mg', 'Micro Labs', 30.0, 450, 50),
            ('Augmentin 625', 'Amoxicillin + Clavulanic Acid', 'Tablet', '625mg', 'GSK', 210.0, 18, 50), # Low stock
            ('Azithral 500', 'Azithromycin', 'Tablet', '500mg', 'Alembic', 125.0, 12, 40), # Low stock
            ('Pan 40', 'Pantoprazole', 'Tablet', '40mg', 'Alkem', 95.0, 320, 50),
            ('Lipitor 20', 'Atorvastatin', 'Tablet', '20mg', 'Pfizer', 180.0, 15, 30), # Low stock
            ('Lantus Solostar', 'Insulin Glargine', 'Injectable', '100 IU/ml', 'Sanofi', 650.0, 8, 20), # Low stock
            ('Telma 40', 'Telmisartan', 'Tablet', '40mg', 'Glenmark', 110.0, 240, 40),
            ('Glycomet GP 1', 'Metformin + Glimepiride', 'Tablet', '500mg/1mg', 'USV', 140.0, 380, 50),
            ('Montair LC', 'Montelukast + Levocetirizine', 'Tablet', '10mg/5mg', 'Cipla', 165.0, 190, 30),
            ('Allegra 120', 'Fexofenadine', 'Tablet', '120mg', 'Sanofi', 175.0, 220, 30),
            ('Combiflam', 'Ibuprofen + Paracetamol', 'Tablet', '400mg/325mg', 'Sanofi', 45.0, 400, 50),
            ('Ceftum 500', 'Cefuroxime Axetil', 'Tablet', '500mg', 'GSK', 450.0, 110, 25),
            ('Ascoril LS', 'Levosalbutamol + Ambroxol', 'Syrup', '100ml', 'Glenmark', 115.0, 140, 30),
            ('Omez 20', 'Omeprazole', 'Capsule', '20mg', 'Dr. Reddy', 60.0, 300, 40),
            ('Supradyn Daily', 'Multivitamin + Minerals', 'Tablet', 'Daily Multi', 'Bayer', 55.0, 500, 50)
        ]
        for b_name, g_name, form, strn, mfr, pr, qty, reorder in medicines_list:
            m = Medicine.query.filter_by(brand_name=b_name).first()
            if not m:
                m = Medicine(brand_name=b_name, generic_name=g_name, dosage_form=form, strength=strn, default_instructions=f"Take 1 {form} after meals as directed.", is_active=True)
                db.session.add(m)
        db.session.commit()

    # 6. Lab Test Types Master
    if LabTestType.query.count() < 8:
        lab_tests_master = [
            ('TST-CBC', 'Complete Blood Count (CBC)', 'Haematology', 'cells/mcL', 4000.0, 11000.0, 350.0),
            ('TST-HB', 'Hemoglobin (Hb)', 'Haematology', 'g/dL', 12.0, 16.0, 200.0),
            ('TST-FBS', 'Fasting Blood Sugar (FBS)', 'Biochemistry', 'mg/dL', 70.0, 100.0, 150.0),
            ('TST-PPBS', 'Post Prandial Blood Sugar', 'Biochemistry', 'mg/dL', 70.0, 140.0, 150.0),
            ('TST-HBA1C', 'Glycated Hemoglobin (HbA1c)', 'Biochemistry', '%', 4.0, 5.6, 600.0),
            ('TST-LIPID', 'Lipid Profile Comprehensive', 'Biochemistry', 'mg/dL', 125.0, 200.0, 750.0),
            ('TST-LFT', 'Liver Function Test (LFT)', 'Biochemistry', 'U/L', 10.0, 40.0, 650.0),
            ('TST-KFT', 'Kidney Function Test (KFT / RFT)', 'Biochemistry', 'mg/dL', 0.6, 1.2, 550.0),
            ('TST-THYROID', 'Thyroid Profile (T3, T4, TSH)', 'Biochemistry', 'uIU/mL', 0.4, 4.0, 500.0),
            ('TST-ECG', '12-Lead Standard ECG', 'Cardiology', 'Graph', None, None, 400.0),
            ('TST-2DECHO', '2D Echocardiogram with Color Doppler', 'Cardiology', 'Imaging', None, None, 1800.0),
            ('TST-XRAY-CHEST', 'Chest X-Ray PA View', 'Radiology', 'Scan', None, None, 500.0),
            ('TST-MRI-BRAIN', '3T MRI Brain Plain + Contrast', 'Radiology', 'Scan', None, None, 6500.0),
            ('TST-CT-CHEST', 'HRCT Chest High-Resolution', 'Radiology', 'Scan', None, None, 4500.0)
        ]
        for t_code, t_name, cat, unit, min_n, max_n, cost in lab_tests_master:
            if not LabTestType.query.filter_by(test_code=t_code).first():
                tt = LabTestType(test_code=t_code, test_name=t_name, category=cat, unit=unit, min_normal_val=min_n, max_normal_val=max_n, cost=cost, is_active=True)
                db.session.add(tt)
        db.session.commit()

    # 7. Wards & Beds Infrastructure
    if Ward.query.count() == 0:
        wards_data = [
            ('WRD-GEN-A', 'General Ward A (Male)', 'General Ward', 800.0, 25, 18),
            ('WRD-GEN-B', 'General Ward B (Female)', 'General Ward', 800.0, 25, 19),
            ('WRD-ICU', 'Intensive Care Unit (ICU)', 'ICU', 3500.0, 12, 9),
            ('WRD-PVT-01', 'Private Deluxe Suites', 'Private Suite', 2500.0, 10, 7),
            ('WRD-EMER-01', 'Emergency Observation Bay', 'Emergency', 1200.0, 8, 5)
        ]
        all_created_beds = []
        for w_code, w_name, cat, rate, tot_beds, occ_count in wards_data:
            ward = Ward(ward_code=w_code, ward_name=w_name, category=cat, daily_rate=rate, is_active=True)
            db.session.add(ward)
            db.session.flush()

            for b_num in range(1, tot_beds + 1):
                b_code = f"BED-{w_code.replace('WRD-', '')}-{b_num:02d}"
                if b_num <= occ_count:
                    status = 'OCCUPIED'
                elif b_num == tot_beds:
                    status = 'UNDER_CLEANING'
                else:
                    status = 'AVAILABLE'
                
                bed = Bed(ward_id=ward.id, bed_code=b_code, status=status)
                db.session.add(bed)
                all_created_beds.append(bed)
        db.session.commit()

    # 8. Patients
    patient_records = [
        ("Rohan", "Sharma", date(1985, 4, 12), "Male", "+91-9811223344", "rohan.sharma@gmail.com", "B+", "Mumbai"),
        ("Meera", "Patel", date(1992, 8, 25), "Female", "+91-9822334455", "meera.patel@yahoo.com", "O+", "Ahmedabad"),
        ("Vikram", "Singh", date(1978, 11, 3), "Male", "+91-9833445566", "vikram.singh@gmail.com", "A+", "Delhi"),
        ("Sneha", "Roy", date(1996, 2, 18), "Female", "+91-9844556677", "sneha.roy@outlook.com", "AB+", "Kolkata"),
        ("Amit", "Joshi", date(1980, 6, 30), "Male", "+91-9855667788", "amit.joshi@gmail.com", "O-", "Pune"),
        ("Priya", "Kapoor", date(1989, 9, 14), "Female", "+91-9866778899", "priya.kapoor@gmail.com", "B+", "Bangalore"),
        ("Rajesh", "Gupta", date(1965, 1, 22), "Male", "+91-9877889900", "rajesh.gupta@gmail.com", "A-", "Jaipur"),
        ("Anita", "Deshmukh", date(1974, 7, 9), "Female", "+91-9888990011", "anita.deshmukh@gmail.com", "O+", "Nagpur"),
        ("Sunita", "Reddy", date(1982, 12, 5), "Female", "+91-9899001122", "sunita.reddy@gmail.com", "B-", "Hyderabad"),
        ("Suresh", "Nair", date(1970, 3, 17), "Male", "+91-9800112233", "suresh.nair@gmail.com", "AB-", "Kochi"),
        ("Karthik", "Menon", date(1994, 5, 29), "Male", "+91-9711223344", "karthik.menon@gmail.com", "A+", "Chennai"),
        ("Deepa", "Iyer", date(1988, 10, 11), "Female", "+91-9722334455", "deepa.iyer@gmail.com", "O+", "Bangalore"),
        ("Sanjay", "Kulkarni", date(1962, 8, 19), "Male", "+91-9733445566", "sanjay.k@gmail.com", "B+", "Pune"),
        ("Rahul", "Bhatia", date(1990, 4, 7), "Male", "+91-9744556677", "rahul.bhatia@gmail.com", "A+", "Gurgaon"),
        ("Neha", "Bansal", date(1995, 11, 23), "Female", "+91-9755667788", "neha.bansal@gmail.com", "O+", "Noida"),
        ("Manish", "Verma", date(1983, 2, 14), "Male", "+91-9766778899", "manish.v@gmail.com", "B+", "Lucknow"),
        ("Geeta", "Tripathi", date(1968, 9, 2), "Female", "+91-9777889900", "geeta.t@gmail.com", "AB+", "Varanasi"),
        ("Deepak", "Agarwal", date(1975, 6, 16), "Male", "+91-9788990011", "deepak.agarwal@gmail.com", "O-", "Indore"),
        ("Shweta", "Mishra", date(1998, 1, 27), "Female", "+91-9799001122", "shweta.m@gmail.com", "A+", "Bhopal"),
        ("Harish", "Choudhury", date(1972, 12, 19), "Male", "+91-9700112233", "harish.c@gmail.com", "B-", "Chandigarh")
    ]

    created_patients = []
    for idx, (fn, ln, dob, gnd, mob, em, bg, city) in enumerate(patient_records, start=101):
        p_code = f"PAT-{idx}"
        p = Patient.query.filter_by(patient_code=p_code).first()
        if not p:
            p = Patient(
                patient_code=p_code,
                first_name=fn,
                last_name=ln,
                full_name=f"{fn} {ln}",
                dob=dob,
                gender=gnd,
                mobile=mob,
                email=em,
                address=f"{idx} Park Street, {city}",
                blood_group=bg,
                emergency_contact_name=f"{fn}'s Family",
                emergency_contact_mobile=mob,
                insurance_provider="Star Health & Allied Insurance",
                insurance_policy_no=f"POL-SH-2026-{idx:04d}",
                height_cm=165.0 + (idx % 20),
                weight_kg=60.0 + (idx % 30),
                created_at=datetime.utcnow() - timedelta(days=idx % 30)
            )
            p.calculate_bmi()
            db.session.add(p)
            db.session.flush()
        created_patients.append(p)
    db.session.commit()

    # 9. Active Inpatient Admissions for Occupied Beds
    occupied_beds = Bed.query.filter_by(status='OCCUPIED').all()
    diagnoses_pool = [
        "Acute Anterior Wall Myocardial Infarction",
        "Type 2 Diabetes with Severe Ketoacidosis",
        "Subacute Ischemic Stroke with Left Hemiparesis",
        "Post-Operative Right Total Knee Replacement",
        "Severe Community Acquired Lobar Pneumonia",
        "Decompensated Chronic Liver Disease",
        "Acute Appendicitis with Localized Peritonitis",
        "Chronic Kidney Disease Stage 4 with Hyperkalemia",
        "Post-Operative Laparoscopic Cholecystectomy",
        "Severe Exacerbation of Bronchial Asthma"
    ]
    
    for idx, bed in enumerate(occupied_beds):
        adm = Admission.query.filter_by(bed_id=bed.id, status='ADMITTED').first()
        if not adm and created_patients and doctor_users:
            pat = created_patients[idx % len(created_patients)]
            doc = doctor_users[idx % len(doctor_users)]
            diag = diagnoses_pool[idx % len(diagnoses_pool)]
            adm = Admission(
                admission_code=f"ADM-2026-{bed.id:04d}",
                patient_id=pat.id,
                doctor_id=doc.id,
                bed_id=bed.id,
                admitted_at=datetime.utcnow() - timedelta(days=random.randint(1, 7), hours=random.randint(1, 12)),
                diagnosis=diag,
                status='ADMITTED'
            )
            db.session.add(adm)
    db.session.commit()

    # 10. Appointments across the Week & Today
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    slots = [time(9, 0), time(9, 30), time(10, 0), time(10, 30), time(11, 0), time(11, 30), time(12, 0), time(14, 0), time(15, 0), time(16, 0)]
    booking_types = ['Walk-In', 'Online', 'Emergency']
    priorities = ['Regular', 'Senior Citizen', 'Pregnant Woman', 'Child', 'Emergency']

    if Appointment.query.count() < 25:
        apt_idx = 1
        for day_offset in range(7):
            apt_date = start_of_week + timedelta(days=day_offset)
            num_apts_day = 6 if apt_date == today else random.randint(4, 8)

            for slot_i in range(num_apts_day):
                pat = created_patients[(apt_idx + slot_i) % len(created_patients)]
                doc = doctor_users[(apt_idx + slot_i) % len(doctor_users)]
                slot = slots[slot_i % len(slots)]
                
                if apt_date < today:
                    status = 'COMPLETED'
                elif apt_date == today:
                    status = random.choice(['CHECKED_IN', 'BOOKED', 'COMPLETED'])
                else:
                    status = 'BOOKED'

                b_type = 'Emergency' if slot_i == 0 and apt_date == today else random.choice(booking_types)
                prio = 'Emergency' if b_type == 'Emergency' else random.choice(priorities)

                apt = Appointment(
                    appointment_code=f"APT-2026-{apt_idx:05d}",
                    patient_id=pat.id,
                    doctor_id=doc.id,
                    appointment_date=apt_date,
                    slot_time=slot,
                    booking_type=b_type,
                    priority=prio,
                    status=status,
                    notes=f"Routine consultation with {doc.name}",
                    created_at=datetime.combine(apt_date, slot) - timedelta(days=1)
                )
                db.session.add(apt)
                apt_idx += 1
        db.session.commit()

    # 11. Bills & Payments
    if Bill.query.count() < 15:
        lab_types = LabTestType.query.all()
        for idx, pat in enumerate(created_patients[:15], start=1):
            consult_fee = 800.0
            lab_cost = 650.0
            med_cost = 450.0
            bed_cost = 1600.0 if idx % 3 == 0 else 0.0
            subtot = consult_fee + lab_cost + med_cost + bed_cost
            tax = round(subtot * 0.05, 2)
            gtot = round(subtot + tax, 2)

            bill = Bill(
                invoice_code=f"INV-2026-{idx:05d}",
                patient_id=pat.id,
                subtotal=subtot,
                discount=0.0,
                tax_amount=tax,
                grand_total=gtot,
                paid_amount=gtot,
                status='PAID',
                notes="OPD & Diagnostic billing",
                created_at=datetime.utcnow() - timedelta(days=idx % 5, hours=idx % 8)
            )
            db.session.add(bill)
            db.session.flush()

            # Bill items
            db.session.add(BillItem(bill_id=bill.id, item_type='CONSULTATION', item_description="Doctor Specialist Consultation", unit_price=consult_fee, quantity=1, total_price=consult_fee))
            db.session.add(BillItem(bill_id=bill.id, item_type='LAB_TEST', item_description="Complete Blood & Metabolic Panel", unit_price=lab_cost, quantity=1, total_price=lab_cost))
            db.session.add(BillItem(bill_id=bill.id, item_type='MEDICINE', item_description="Prescription Medications Pharmacy", unit_price=med_cost, quantity=1, total_price=med_cost))
            if bed_cost > 0:
                db.session.add(BillItem(bill_id=bill.id, item_type='BED_CHARGE', item_description="Inpatient Ward Bed Charges (2 Days)", unit_price=800.0, quantity=2, total_price=bed_cost))

            # Payment
            admin_u = User.query.filter_by(email='admin@ipcms.com').first()
            rec_id = admin_u.id if admin_u else 1
            pm = Payment(
                payment_code=f"PAY-2026-{idx:05d}",
                bill_id=bill.id,
                amount_paid=gtot,
                payment_method=random.choice(['UPI', 'CARD', 'CASH', 'INSURANCE']),
                transaction_ref=f"TXN-MEDICORE-{idx:06d}",
                recorded_by_id=rec_id,
                paid_at=bill.created_at + timedelta(minutes=15)
            )
            db.session.add(pm)
        db.session.commit()

    # 12. Lab Requests
    if LabRequest.query.count() < 10:
        lab_types = LabTestType.query.all()
        for idx, pat in enumerate(created_patients[:12], start=1):
            doc = doctor_users[idx % len(doctor_users)]
            status = 'COMPLETED' if idx > 4 else 'REQUESTED'
            lr = LabRequest(
                request_code=f"LAB-REQ-2026-{idx:04d}",
                patient_id=pat.id,
                doctor_id=doc.id,
                status=status,
                clinical_notes=f"Clinical evaluation requested by {doc.name}",
                created_at=datetime.utcnow() - timedelta(hours=idx * 2)
            )
            db.session.add(lr)
            db.session.flush()

            if status == 'COMPLETED' and lab_types:
                tt = lab_types[idx % len(lab_types)]
                lab_tech = User.query.filter_by(email='lab@ipcms.com').first()
                lres = LabResult(
                    request_id=lr.id,
                    test_type_id=tt.id,
                    result_value=round(random.uniform(tt.min_normal_val or 10.0, tt.max_normal_val or 100.0), 2),
                    abnormal_flag='NORMAL',
                    remarks="Test analyzed with verified calibration standards.",
                    technician_id=lab_tech.id if lab_tech else None,
                    completed_at=datetime.utcnow() - timedelta(hours=idx)
                )
                db.session.add(lres)
        db.session.commit()

    # 13. Audit Logs
    if AuditLog.query.count() < 10:
        admin_u = User.query.filter_by(email='admin@ipcms.com').first()
        actions = [
            ('USER_LOGIN', 'Auth', 1, 'Admin signed in successfully from local workstation'),
            ('INVOICE_GENERATED', 'Billing', 12, 'Generated Invoice INV-2026-00012 for patient admission'),
            ('BED_ALLOCATION', 'Beds', 4, 'Allocated Bed BED-ICU-04 to inpatient emergency case'),
            ('PRESCRIPTION_DISPENSED', 'Pharmacy', 3, 'Dispensed 3 medication items from pharmacy formulary'),
            ('LAB_RESULT_VERIFIED', 'Laboratory', 8, 'Technician approved CBC & Lipid profile report'),
            ('BACKUP_CREATED', 'System', 1, 'Automated system snapshot backup completed successfully')
        ]
        for act, ent_type, ent_id, det in actions:
            db.session.add(AuditLog(
                user_id=admin_u.id if admin_u else 1,
                action=act,
                entity_type=ent_type,
                entity_id=ent_id,
                details=det,
                ip_address='127.0.0.1',
                timestamp=datetime.utcnow() - timedelta(minutes=random.randint(5, 180))
            ))
        db.session.commit()

    # 14. Notifications
    if Notification.query.count() < 5 and created_patients:
        notifs = [
            (created_patients[0].id, "APPOINTMENT_REMINDER", "Upcoming Consultation Reminder", "Your consultation with Dr. Ananya Sharma is confirmed for today."),
            (created_patients[1].id, "LAB_READY", "Laboratory Test Results Ready", "Your Comprehensive Metabolic Panel test results have been verified."),
            (created_patients[2].id, "PRESCRIPTION_READY", "Digital E-Prescription Dispensed", "Your prescribed medications are ready at the MediCore+ Pharmacy."),
            (created_patients[3].id, "PAYMENT_REMINDER", "Invoice Payment Receipt Generated", "Payment of ₹1,850 received with transaction reference TXN-MEDICORE-00012.")
        ]
        for p_id, n_type, tit, msg in notifs:
            db.session.add(Notification(
                patient_id=p_id,
                type=n_type,
                title=tit,
                message=msg,
                channel='BOTH',
                status='SENT',
                created_at=datetime.utcnow() - timedelta(minutes=random.randint(10, 120))
            ))
        db.session.commit()

    print("[SEEDER] Full hospital database seeding finished successfully!")
