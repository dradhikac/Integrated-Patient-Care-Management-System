"""
Realistic Hospital Operational Data Seeder for CareHub / IPCMS
Populates comprehensive, interconnected, production-ready database records for:
- Admin Dashboard (KPIs, revenue, bed occupancy, doctor counts, audit trails)
- Receptionist Desk (Today's appointments, live queue tokens, check-ins, patient directory)
- Doctor Portal (Consultations, vitals, prescriptions, today's schedule)
- Laboratory (Test orders, verified results)
- Pharmacy & Billing (Formulary, invoices, payments, revenue)
- IPD & Beds (Wards, occupied beds, admissions)
"""

from datetime import datetime, date, timedelta, time
import random
from app.extensions import db
from app.auth.models import User, Role
from app.patients.models import Patient, PatientMedicalHistory, PatientAllergy
from app.doctors.models import Doctor
from app.beds.models import Ward, Bed, Admission
from app.appointments.models import Appointment, DoctorAvailability, Waitlist
from app.prescriptions.models import Medicine, Prescription, PrescriptionItem
from app.lab.models import LabTestType, LabRequest, LabResult
from app.billing.models import Bill, BillItem, Payment
from app.admin.models import Department, Equipment, AuditLog
from app.notifications.models import Notification
from app.reception.models import CheckIn, EmergencyEncounter
from app.consultations.models import Consultation, Vital

def seed_full_hospital_data():
    """Seeds rich, realistic hospital data for all portals."""
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
        ('ADM-001', 'CareHub Administrator', 'admin@ipcms.com', 'Admin', 'Password@123'),
        ('ADM-888', 'Hospital Super Admin', 'administrator@medicore.com', 'Admin', 'Admin@123'),
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
        ('DOC-001', 'Dr. Rajesh Sharma', 'doctor@ipcms.com', 'General Medicine & Cardiology', 'MBBS, MD (General Medicine)', '15+ Years', 'Cardiology & Heart Institute', 'Senior consultant physician and cardiologist with 15+ years of clinical excellence in patient care.', 600.0, '/static/images/doctors/dr_rajesh_sharma.jpg'),
        ('DOC-101', 'Dr. Ananya Sharma', 'ananya.sharma@medicore.com', 'Cardiologist', 'MBBS, MD, DM (Cardiology)', '12+ Years', 'Cardiology & Heart Institute', 'Specialist in non-invasive cardiology and heart health.', 800.0, '/static/images/doctors/dr_ananya_sharma.jpg'),
        ('DOC-102', 'Dr. Rahul Verma', 'rahul.verma@medicore.com', 'Neurologist', 'MBBS, MD, DM (Neurology)', '15+ Years', 'Neurology & Spine Care', 'Senior consultant neurologist specializing in stroke and epilepsy.', 1000.0, '/static/images/doctors/dr_rahul_verma.jpg'),
        ('DOC-103', 'Dr. Priya Nair', 'priya.nair@medicore.com', 'Gynecologist & Obstetrician', 'MBBS, MD (Obstetrics & Gynecology)', '10+ Years', 'Obstetrics & Gynecology', 'Expert in maternal healthcare and laparoscopic surgeries.', 900.0, '/static/images/doctors/dr_priya_nair.jpg'),
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
        else:
            doc.user_id = u.id
            doc.name = name
            doc.specialization = spec
            doc.department = dept
            doc.education = edu
            doc.is_active = True
    db.session.commit()

    # 5. Doctor Availability / Clinic Schedules (Monday - Sunday for all doctors)
    for doc_u in doctor_users:
        for day_num in range(7):  # 0=Monday to 6=Sunday
            avail = DoctorAvailability.query.filter_by(doctor_id=doc_u.id, day_of_week=day_num).first()
            if not avail:
                avail = DoctorAvailability(
                    doctor_id=doc_u.id,
                    day_of_week=day_num,
                    start_time=time(9, 0),
                    end_time=time(23, 0),
                    slot_duration_minutes=15,
                    is_active=True
                )
                db.session.add(avail)
            else:
                avail.start_time = time(9, 0)
                avail.end_time = time(23, 0)
                avail.is_active = True
    db.session.commit()

    # 6. Medicines Formulary
    medicines_list = [
        ('Paracetamol', 'Paracetamol', 'Tablet', '650mg'),
        ('Cetirizine', 'Cetirizine Hydrochloride', 'Tablet', '10mg'),
        ('Vitamin C', 'Ascorbic Acid', 'Tablet', '500mg'),
        ('Dolo 650', 'Paracetamol', 'Tablet', '650mg'),
        ('Augmentin 625', 'Amoxicillin + Clavulanic Acid', 'Tablet', '625mg'),
        ('Azithral 500', 'Azithromycin', 'Tablet', '500mg'),
        ('Pan 40', 'Pantoprazole', 'Tablet', '40mg'),
        ('Lipitor 20', 'Atorvastatin', 'Tablet', '20mg'),
        ('Lantus Solostar', 'Insulin Glargine', 'Injectable', '100 IU/ml'),
        ('Telma 40', 'Telmisartan', 'Tablet', '40mg'),
        ('Glycomet GP 1', 'Metformin + Glimepiride', 'Tablet', '500mg/1mg'),
        ('Montair LC', 'Montelukast + Levocetirizine', 'Tablet', '10mg/5mg'),
        ('Allegra 120', 'Fexofenadine', 'Tablet', '120mg'),
        ('Combiflam', 'Ibuprofen + Paracetamol', 'Tablet', '400mg/325mg'),
        ('Ceftum 500', 'Cefuroxime Axetil', 'Tablet', '500mg'),
        ('Ascoril LS', 'Levosalbutamol + Ambroxol', 'Syrup', '100ml'),
        ('Omez 20', 'Omeprazole', 'Capsule', '20mg'),
        ('Supradyn Daily', 'Multivitamin + Minerals', 'Tablet', 'Daily Multi')
    ]
    for b_name, g_name, form, strn in medicines_list:
        m = Medicine.query.filter_by(brand_name=b_name).first()
        if not m:
            m = Medicine(brand_name=b_name, generic_name=g_name, dosage_form=form, strength=strn, default_instructions=f"Take 1 {form} after meals as directed.", is_active=True)
            db.session.add(m)
    db.session.commit()

    # 7. Lab Test Types Master
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

    # 8. Wards & Beds Infrastructure
    if Ward.query.count() == 0:
        wards_data = [
            ('WRD-GEN-A', 'General Ward A (Male)', 'General Ward', 800.0, 25, 18),
            ('WRD-GEN-B', 'General Ward B (Female)', 'General Ward', 800.0, 25, 19),
            ('WRD-ICU', 'Intensive Care Unit (ICU)', 'ICU', 3500.0, 12, 9),
            ('WRD-PVT-01', 'Private Deluxe Suites', 'Private Suite', 2500.0, 10, 7),
            ('WRD-EMER-01', 'Emergency Observation Bay', 'Emergency', 1200.0, 8, 5)
        ]
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
        db.session.commit()

    # 9. Patients Directory
    patient_records = [
        ("Radhika D C", "hougale", date(1990, 6, 15), "Female", "+91 98765 43210", "radhika@carehub.com", "B+", "Bengaluru"),
        ("Rohan", "Sharma", date(1985, 4, 12), "Male", "+91 98112 23344", "rohan.sharma@gmail.com", "B+", "Mumbai"),
        ("Meera", "Patel", date(1992, 8, 25), "Female", "+91 98223 34455", "meera.patel@yahoo.com", "O+", "Ahmedabad"),
        ("Vikram", "Singh", date(1978, 11, 3), "Male", "+91 98334 45566", "vikram.singh@gmail.com", "A+", "Delhi"),
        ("Sneha", "Roy", date(1996, 2, 18), "Female", "+91 98445 56677", "sneha.roy@outlook.com", "AB+", "Kolkata"),
        ("Amit", "Joshi", date(1980, 6, 30), "Male", "+91 98556 67788", "amit.joshi@gmail.com", "O-", "Pune"),
        ("Priya", "Kapoor", date(1989, 9, 14), "Female", "+91 98667 78899", "priya.kapoor@gmail.com", "B+", "Bengaluru"),
        ("Rajesh", "Gupta", date(1965, 1, 22), "Male", "+91 98778 89900", "rajesh.gupta@gmail.com", "A-", "Jaipur"),
        ("Anita", "Deshmukh", date(1974, 7, 9), "Female", "+91 98889 90011", "anita.deshmukh@gmail.com", "O+", "Nagpur"),
        ("Sunita", "Reddy", date(1982, 12, 5), "Female", "+91 98990 01122", "sunita.reddy@gmail.com", "B-", "Hyderabad"),
        ("Suresh", "Nair", date(1970, 3, 17), "Male", "+91 98001 12233", "suresh.nair@gmail.com", "AB-", "Kochi"),
        ("Karthik", "Menon", date(1994, 5, 29), "Male", "+91 97112 23344", "karthik.menon@gmail.com", "A+", "Chennai"),
        ("Deepa", "Iyer", date(1988, 10, 11), "Female", "+91 97223 34455", "deepa.iyer@gmail.com", "O+", "Bengaluru"),
        ("Sanjay", "Kulkarni", date(1962, 8, 19), "Male", "+91 97334 45566", "sanjay.k@gmail.com", "B+", "Pune"),
        ("Rahul", "Bhatia", date(1990, 4, 7), "Male", "+91 97445 56677", "rahul.bhatia@gmail.com", "A+", "Gurgaon"),
        ("Neha", "Bansal", date(1995, 11, 23), "Female", "+91 97556 67788", "neha.bansal@gmail.com", "O+", "Noida"),
        ("Manish", "Verma", date(1983, 2, 14), "Male", "+91 97667 78899", "manish.v@gmail.com", "B+", "Lucknow"),
        ("Geeta", "Tripathi", date(1968, 9, 2), "Female", "+91 97778 89900", "geeta.t@gmail.com", "AB+", "Varanasi"),
        ("Deepak", "Agarwal", date(1975, 6, 16), "Male", "+91 97889 90011", "deepak.agarwal@gmail.com", "O-", "Indore"),
        ("Shweta", "Mishra", date(1998, 1, 27), "Female", "+91 97990 01122", "shweta.m@gmail.com", "A+", "Bhopal"),
        ("Harish", "Choudhury", date(1972, 12, 19), "Male", "+91 97001 12233", "harish.c@gmail.com", "B-", "Chandigarh")
    ]

    created_patients = []
    current_year = datetime.now().year
    today = date.today()
    for idx, (fn, ln, dob, gnd, mob, em, bg, city) in enumerate(patient_records, start=1):
        p_code = f"IPCMS-{current_year}-{idx:06d}"
        p = Patient.query.filter((Patient.patient_code == p_code) | (Patient.email == em)).first()
        
        # Make the first 6 patients registered today so Today's KPI shows live registrations
        if idx <= 6:
            patient_created_at = datetime.utcnow() - timedelta(minutes=idx * 25)
        else:
            patient_created_at = datetime.utcnow() - timedelta(days=idx % 30)

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
                address=f"#{idx * 12}, 4th Cross, {city}",
                blood_group=bg,
                emergency_contact_name=f"{fn}'s Family",
                emergency_contact_mobile=mob,
                insurance_provider="Star Health & Allied Insurance",
                insurance_policy_no=f"POL-SH-2026-{idx:04d}",
                height_cm=165.0 + (idx % 20),
                weight_kg=60.0 + (idx % 30),
                created_at=patient_created_at
            )
            p.set_aadhaar(f"{1000 + idx} {2000 + idx} {3000 + idx}")
            p.calculate_bmi()
            db.session.add(p)
            db.session.flush()
        else:
            if idx <= 6:
                p.created_at = patient_created_at
        created_patients.append(p)
    db.session.commit()

    # 10. Inpatient Admissions
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

    # 11. Today's Appointments & Live Queue Tokens
    rec_user = User.query.filter_by(email='reception@ipcms.com').first() or User.query.first()

    today_slots_plan = [
        (0, 0, time(9, 0), 'COMPLETED', 'Regular'),
        (1, 1, time(9, 30), 'COMPLETED', 'Regular'),
        (2, 0, time(10, 0), 'IN_CONSULTATION', 'Regular'),
        (3, 1, time(10, 30), 'CHECKED_IN', 'Emergency'),
        (4, 2, time(11, 0), 'CHECKED_IN', 'Senior Citizen'),
        (5, 3, time(11, 30), 'CHECKED_IN', 'Pregnant Woman'),
        (6, 4, time(14, 0), 'CHECKED_IN', 'Child'),
        (7, 0, time(15, 0), 'BOOKED', 'Regular'),
        (8, 1, time(16, 0), 'BOOKED', 'Regular'),
        (9, 2, time(17, 0), 'BOOKED', 'Regular'),
    ]

    for idx, (p_idx, d_idx, sl_t, status, prio) in enumerate(today_slots_plan, start=1):
        pat = created_patients[p_idx % len(created_patients)]
        doc = doctor_users[d_idx % len(doctor_users)]
        apt_code = f"APT-{current_year}-{idx:05d}"
        
        apt = Appointment.query.filter_by(appointment_code=apt_code).first()
        if not apt:
            apt = Appointment(
                appointment_code=apt_code,
                patient_id=pat.id,
                doctor_id=doc.id,
                appointment_date=today,
                slot_time=sl_t,
                booking_type='Walk-In' if 'Emergency' in prio else 'Online',
                priority=prio,
                status=status,
                notes=f"Consultation with {doc.name} regarding symptoms.",
                created_at=datetime.combine(today, sl_t) - timedelta(hours=2)
            )
            db.session.add(apt)
            db.session.flush()
        else:
            apt.appointment_date = today
            apt.slot_time = sl_t
            apt.status = status
            apt.priority = prio
            apt.created_at = datetime.combine(today, sl_t) - timedelta(hours=2)

        # Seed Check-In token for today's queue
        t_num = f"TK-{idx:03d}"
        cin = CheckIn.query.filter_by(token_no=t_num).first()
        cin_status = 'COMPLETED' if status == 'COMPLETED' else ('IN_CONSULTATION' if status == 'IN_CONSULTATION' else 'WAITING')
        
        if not cin:
            cin = CheckIn(
                patient_id=pat.id,
                doctor_id=doc.id,
                token_no=t_num,
                department=doc.doctor_profile[0].department if doc.doctor_profile else 'General OPD',
                status=cin_status,
                priority=prio,
                check_in_time=datetime.combine(today, sl_t) - timedelta(minutes=15),
                called_time=datetime.combine(today, sl_t) if status in ['IN_CONSULTATION', 'COMPLETED'] else None,
                completed_time=datetime.combine(today, sl_t) + timedelta(minutes=15) if status == 'COMPLETED' else None,
                checked_in_by_id=rec_user.id
            )
            db.session.add(cin)
            db.session.flush()
        else:
            cin.check_in_time = datetime.combine(today, sl_t) - timedelta(minutes=15)
            cin.status = cin_status
            cin.priority = prio
            cin.called_time = datetime.combine(today, sl_t) if status in ['IN_CONSULTATION', 'COMPLETED'] else None
            cin.completed_time = datetime.combine(today, sl_t) + timedelta(minutes=15) if status == 'COMPLETED' else None

        # If completed, seed consultation & prescription & vitals
        if status in ['COMPLETED', 'IN_CONSULTATION']:
            cns = Consultation.query.filter_by(appointment_id=apt.id).first()
            if not cns:
                cns = Consultation(
                    consultation_code=f"CNS-{current_year}-{idx:05d}",
                    patient_id=pat.id,
                    doctor_id=doc.id,
                    appointment_id=apt.id,
                    check_in_id=cin.id,
                    symptoms="Mild chest tightness, occasional cough, fatigue for 3 days.",
                    diagnosis="Upper Respiratory Tract Infection & Mild Hypertension",
                    treatment_plan="5 days antibiotic course, rest, hydration, blood pressure monitoring.",
                    notes="Patient advised to follow up after 5 days if fever persists.",
                    started_at=datetime.combine(today, sl_t),
                    completed_at=datetime.combine(today, sl_t) + timedelta(minutes=15) if status == 'COMPLETED' else None,
                    created_at=datetime.combine(today, sl_t)
                )
                db.session.add(cns)
                db.session.flush()

                # Vitals
                vital = Vital(
                    consultation_id=cns.id,
                    bp_systolic=124,
                    bp_diastolic=82,
                    temperature_f=98.6,
                    pulse_bpm=74,
                    spo2_percent=99,
                    recorded_at=datetime.combine(today, sl_t)
                )
                db.session.add(vital)

                # Prescription
                rx_code = f"RX-{current_year}-{idx:06d}"
                rx = Prescription.query.filter_by(prescription_code=rx_code).first()
                if not rx:
                    rx = Prescription(
                        prescription_code=rx_code,
                        consultation_id=cns.id,
                        patient_id=pat.id,
                        doctor_id=doc.id,
                        general_advice="Take plenty of fluids, avoid cold food, take medications on time.",
                        created_at=datetime.combine(today, sl_t) + timedelta(minutes=12)
                    )
                    db.session.add(rx)
                    db.session.flush()

                    # Prescription items
                    db.session.add(PrescriptionItem(prescription_id=rx.id, medicine_name='Paracetamol 650 mg', frequency='1 - 0 - 1', duration='5 Days', food_relation='After Food', instructions='Take if temperature exceeds 99°F'))
                    db.session.add(PrescriptionItem(prescription_id=rx.id, medicine_name='Cetirizine 10 mg', frequency='0 - 0 - 1', duration='5 Days', food_relation='After Food', instructions='Take before bedtime'))
                    db.session.add(PrescriptionItem(prescription_id=rx.id, medicine_name='Vitamin C 500 mg', frequency='1 - 0 - 1', duration='5 Days', food_relation='After Food', instructions='Chewable tablet'))
            else:
                cns.started_at = datetime.combine(today, sl_t)
                cns.completed_at = datetime.combine(today, sl_t) + timedelta(minutes=15) if status == 'COMPLETED' else None
                cns.created_at = datetime.combine(today, sl_t)

    # Emergency Encounters for Reception Triage
    er_enc = EmergencyEncounter.query.filter_by(token_no='ER-001').first()
    if not er_enc and created_patients and doctor_users:
        er_enc = EmergencyEncounter(
            temp_id=f"TEMP-ER-{current_year}-0001",
            token_no='ER-001',
            patient_id=created_patients[3].id,
            is_identified=True,
            emergency_type='Acute Asthma / Respiratory Distress',
            priority='Emergency / Critical',
            status='Stabilized',
            arrival_source='Ambulance',
            assigned_doctor_id=doctor_users[0].id,
            department='Emergency / Trauma',
            notes='Patient arrived with acute wheezing. Nebulization administered immediately.',
            arrival_time=datetime.combine(today, time(8, 45)),
            registered_by_id=rec_user.id
        )
        db.session.add(er_enc)
    elif er_enc:
        er_enc.arrival_time = datetime.combine(today, time(8, 45))

    er_enc2 = EmergencyEncounter.query.filter_by(token_no='ER-002').first()
    if not er_enc2 and created_patients and doctor_users:
        er_enc2 = EmergencyEncounter(
            temp_id=f"TEMP-ER-{current_year}-0002",
            token_no='ER-002',
            patient_id=created_patients[4].id,
            is_identified=True,
            emergency_type='Road Traffic Accident / Trauma',
            priority='Emergency / Critical',
            status='In Triage',
            arrival_source='Walk-In / Bystander',
            assigned_doctor_id=doctor_users[1].id,
            department='Emergency / Trauma',
            notes='Laceration wound on forearm, vitals stable, wound dressing in progress.',
            arrival_time=datetime.combine(today, time(11, 15)),
            registered_by_id=rec_user.id
        )
        db.session.add(er_enc2)
    elif er_enc2:
        er_enc2.arrival_time = datetime.combine(today, time(11, 15))

    db.session.commit()

    # 12. Billing & Payments for Today and This Month
    for idx, pat in enumerate(created_patients[:10], start=1):
        inv_code = f"INV-{current_year}-{idx:05d}"
        b = Bill.query.filter_by(invoice_code=inv_code).first()
        consult_fee = 600.0
        lab_cost = 450.0
        med_cost = 320.0
        subtot = consult_fee + lab_cost + med_cost
        tax = round(subtot * 0.05, 2)
        gtot = round(subtot + tax, 2)
        bill_created_at = datetime.combine(today, time(9, 30)) - timedelta(hours=idx % 6)

        if not b:
            b = Bill(
                invoice_code=inv_code,
                patient_id=pat.id,
                subtotal=subtot,
                discount=0.0,
                tax_amount=tax,
                grand_total=gtot,
                paid_amount=gtot,
                status='PAID',
                notes='OPD Consultation & Pharmacy receipt',
                created_at=bill_created_at
            )
            db.session.add(b)
            db.session.flush()

            db.session.add(BillItem(bill_id=b.id, item_type='CONSULTATION', item_description="OPD Doctor Specialist Consultation", unit_price=consult_fee, quantity=1, total_price=consult_fee))
            db.session.add(BillItem(bill_id=b.id, item_type='LAB_TEST', item_description="Complete Blood Count & Sugar Test", unit_price=lab_cost, quantity=1, total_price=lab_cost))
            db.session.add(BillItem(bill_id=b.id, item_type='MEDICINE', item_description="Prescription Pharmacy Medications", unit_price=med_cost, quantity=1, total_price=med_cost))

            pm = Payment(
                payment_code=f"PAY-{current_year}-{idx:05d}",
                bill_id=b.id,
                amount_paid=gtot,
                payment_method=random.choice(['UPI', 'CARD', 'CASH', 'INSURANCE']),
                transaction_ref=f"TXN-CAREHUB-{idx:06d}",
                recorded_by_id=rec_user.id,
                paid_at=bill_created_at + timedelta(minutes=10)
            )
            db.session.add(pm)
        else:
            b.created_at = bill_created_at
            b.paid_amount = b.grand_total
            b.status = 'PAID'
            pm = Payment.query.filter_by(bill_id=b.id).first()
            if pm:
                pm.paid_at = bill_created_at + timedelta(minutes=10)
                pm.amount_paid = b.grand_total
            else:
                pm = Payment(
                    payment_code=f"PAY-{current_year}-{idx:05d}",
                    bill_id=b.id,
                    amount_paid=b.grand_total,
                    payment_method=random.choice(['UPI', 'CARD', 'CASH', 'INSURANCE']),
                    transaction_ref=f"TXN-CAREHUB-{idx:06d}",
                    recorded_by_id=rec_user.id,
                    paid_at=bill_created_at + timedelta(minutes=10)
                )
                db.session.add(pm)
    db.session.commit()

    # 13. Lab Requests & Verified Results
    lab_types = LabTestType.query.all()
    lab_tech = User.query.filter_by(email='lab@ipcms.com').first() or User.query.first()
    for idx, pat in enumerate(created_patients[:8], start=1):
        doc = doctor_users[idx % len(doctor_users)]
        req_code = f"LAB-REQ-{current_year}-{idx:04d}"
        lr = LabRequest.query.filter_by(request_code=req_code).first()
        status = 'COMPLETED' if idx <= 5 else 'REQUESTED'
        req_created_at = datetime.combine(today, time(9, 0)) - timedelta(hours=idx)

        if not lr:
            lr = LabRequest(
                request_code=req_code,
                patient_id=pat.id,
                doctor_id=doc.id,
                status=status,
                clinical_notes=f"Clinical diagnostic evaluation requested by {doc.name}",
                created_at=req_created_at
            )
            db.session.add(lr)
            db.session.flush()

            if status == 'COMPLETED' and lab_types:
                tt = lab_types[idx % len(lab_types)]
                lres = LabResult(
                    request_id=lr.id,
                    test_type_id=tt.id,
                    result_value=round(random.uniform(tt.min_normal_val or 12.0, tt.max_normal_val or 16.0), 2),
                    abnormal_flag='NORMAL',
                    remarks="Specimen verified against standard diagnostic calibration.",
                    technician_id=lab_tech.id,
                    completed_at=datetime.combine(today, time(10, 0))
                )
                db.session.add(lres)
        else:
            lr.created_at = req_created_at
            lr.status = status
            lres = LabResult.query.filter_by(request_id=lr.id).first()
            if lres:
                lres.completed_at = datetime.combine(today, time(10, 0))
    db.session.commit()

    # 14. Audit Logs
    actions = [
        ('USER_LOGIN', 'Auth', 1, 'Admin signed in successfully from management console'),
        ('CHECK_IN_PROCESSED', 'Reception', 2, 'Generated Queue Token TK-001 for Dr. Rajesh Sharma'),
        ('INVOICE_GENERATED', 'Billing', 1, 'Generated Invoice INV-2026-00001 for OPD consultation'),
        ('PRESCRIPTION_CREATED', 'Prescription', 1, 'Dr. Rajesh Sharma issued digital prescription RX-2026-000001'),
        ('LAB_RESULT_VERIFIED', 'Laboratory', 1, 'Technician verified Complete Blood Count results'),
        ('BED_ALLOCATION', 'Beds', 4, 'Allocated Bed BED-ICU-01 to emergency patient'),
        ('BACKUP_CREATED', 'System', 1, 'Automated database health snapshot generated')
    ]
    for act, ent_type, ent_id, det in actions:
        db.session.add(AuditLog(
            user_id=1,
            action=act,
            entity_type=ent_type,
            entity_id=ent_id,
            details=det,
            ip_address='127.0.0.1',
            timestamp=datetime.utcnow() - timedelta(minutes=random.randint(5, 180))
        ))
    db.session.commit()

    # 15. Notifications
    if Notification.query.count() < 5 and created_patients:
        notifs = [
            (created_patients[0].id, "APPOINTMENT_REMINDER", "Upcoming Consultation Reminder", "Your consultation with Dr. Rajesh Sharma is confirmed for today."),
            (created_patients[1].id, "LAB_READY", "Laboratory Test Results Ready", "Your Complete Blood Count test results have been verified."),
            (created_patients[2].id, "PRESCRIPTION_READY", "Digital E-Prescription Dispensed", "Your prescribed medications are ready at the CareHub Pharmacy."),
            (created_patients[3].id, "PAYMENT_REMINDER", "Invoice Payment Receipt Generated", "Payment of ₹1,438.50 received with transaction reference TXN-CAREHUB-000001.")
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

    print("[SEEDER] Full hospital database seeding completed successfully!")
