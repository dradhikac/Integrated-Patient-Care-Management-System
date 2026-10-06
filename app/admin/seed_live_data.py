"""
Realistic Hospital Operational Data Seeder for CareHub / IPCMS
Populates comprehensive, interconnected, production-ready database records for:
- Admin Dashboard (KPIs, 15-day revenue, bed occupancy, doctor counts, audit trails)
- Receptionist Desk (Today's appointments, live queue tokens, check-ins, emergency triage)
- Doctor Portal (Consultations, vitals, prescriptions, today's schedule)
- Laboratory (Test orders, verified results, pending requests)
- Pharmacy & Billing (Formulary, invoices, payments, multi-day revenue)
- IPD & Beds (Wards, occupied beds, admissions, discharges)
- Patient Portal (Active patient accounts with password ABC@123)
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
    """Seeds rich, realistic hospital data across 15 days for all portals."""
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
        ('DOC-001', 'Dr. Rajesh Sharma', 'doctor@ipcms.com', 'General Physician', 'MBBS, MD (General Medicine)', '15+ Years', 'General Medicine & OPD', 'Senior consultant physician with 15+ years of clinical excellence in general medicine and comprehensive patient care.', 600.0, '/static/images/doctors/dr_rajesh_sharma.jpg'),
        ('DOC-101', 'Dr. Ananya Sharma', 'ananya.sharma@medicore.com', 'Cardiologist', 'MBBS, MD, DM (Cardiology)', '12+ Years', 'Cardiology & Heart Institute', 'Specialist in non-invasive cardiology and cardiovascular medicine.', 800.0, '/static/images/doctors/dr_ananya_sharma.jpg'),
        ('DOC-102', 'Dr. Rahul Verma', 'rahul.verma@medicore.com', 'Neurologist', 'MBBS, MD, DM (Neurology)', '15+ Years', 'Neurology & Spine Care', 'Senior consultant neurologist specializing in stroke and epilepsy.', 1000.0, '/static/images/doctors/dr_rahul_verma.jpg'),
        ('DOC-103', 'Dr. Priya Nair', 'priya.nair@medicore.com', 'Gynecologist & Obstetrician', 'MBBS, MD (Obstetrics & Gynecology)', '10+ Years', 'Obstetrics & Gynecology', 'Expert in maternal healthcare, high-risk obstetrics, and laparoscopic surgeries.', 900.0, '/static/images/doctors/dr_priya_nair.jpg'),
        ('DOC-104', 'Dr. Arjun Mehta', 'arjun.mehta@medicore.com', 'Orthopedic Surgeon', 'MBBS, MS (Orthopedics)', '14+ Years', 'Orthopedics & Joint Care', 'Leading orthopedic surgeon specializing in robotic joint replacement and trauma.', 1100.0, '/static/images/doctors/dr_arjun_mehta.jpg'),
        ('DOC-105', 'Dr. Kavya Rao', 'kavya.rao@medicore.com', 'Pediatrician', 'MBBS, MD (Pediatrics)', '8+ Years', 'Pediatrics & Child Care', 'Child specialist dedicated to newborn intensive care and adolescent health.', 700.0, '/static/images/doctors/dr_kavya_rao.jpg'),
        ('DOC-106', 'Dr. Vikram Desai', 'vikram.desai@medicore.com', 'Radiologist', 'MBBS, MD (Radiodiagnosis)', '11+ Years', 'Diagnostics & Radiology', 'Chief radiologist specializing in 3T MRI, 512-slice CT, and intervention.', 850.0, '/static/images/doctors/dr_vikram_desai.jpg')
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
            doc = Doctor(user_id=u.id, doctor_code=code, name=name, specialization=spec, education=edu, experience=exp, department=dept, bio=bio, consultation_fee=fee, image_url=img, available_days='Monday - Sunday (24/7)', rating=4.9, is_active=True)
            db.session.add(doc)
        else:
            doc.user_id = u.id
            doc.name = name
            doc.specialization = spec
            doc.department = dept
            doc.education = edu
            doc.consultation_fee = fee
            doc.available_days = 'Monday - Sunday (24/7)'
            doc.is_active = True
    db.session.commit()

    # 5. Doctor Availability (Ensure 24/7 round-the-clock availability across all days)
    for doc_u in doctor_users:
        for day_num in range(7):
            avail = DoctorAvailability.query.filter_by(doctor_id=doc_u.id, day_of_week=day_num).first()
            if not avail:
                avail = DoctorAvailability(
                    doctor_id=doc_u.id,
                    day_of_week=day_num,
                    start_time=time(0, 0),
                    end_time=time(0, 0),
                    slot_duration_minutes=15,
                    is_active=True
                )
                db.session.add(avail)
            else:
                avail.is_active = True
                avail.start_time = time(0, 0)
                avail.end_time = time(0, 0)
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

    # 8. Wards & Beds Infrastructure (Total 72 beds, ~55 occupied)
    if Ward.query.count() == 0:
        wards_data = [
            ('WRD-GEN-A', 'General Ward A (Male)', 'General Ward', 800.0, 25, 19),
            ('WRD-GEN-B', 'General Ward B (Female)', 'General Ward', 800.0, 25, 20),
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
    else:
        # Ensure occupied counts are well-balanced
        for bed in Bed.query.all():
            w = Ward.query.get(bed.ward_id)
            if not w:
                continue
            # Keep consistent occupancy
            pass

    # 9. Patients Directory & Linked User Accounts (36 Patients, all with password ABC@123)
    patient_records = [
        ("Ananya", "Verma", date(1993, 3, 20), "Female", "+91 98765 01001", "ananya.verma@carehub.com", "O+", "Bengaluru"),
        ("Radhika", "Hougale", date(1990, 6, 15), "Female", "+91 98765 43210", "radhika@carehub.com", "B+", "Bengaluru"),
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
        ("Harish", "Choudhury", date(1972, 12, 19), "Male", "+91 97001 12233", "harish.c@gmail.com", "B-", "Chandigarh"),
        ("Pooja", "Sundaram", date(1991, 5, 11), "Female", "+91 96112 33445", "pooja.sundaram@gmail.com", "A+", "Coimbatore"),
        ("Arvind", "Swamy", date(1984, 8, 22), "Male", "+91 96223 44556", "arvind.swamy@gmail.com", "O+", "Madurai"),
        ("Shalini", "Sen", date(1993, 10, 5), "Female", "+91 96334 55667", "shalini.sen@gmail.com", "B+", "Kolkata"),
        ("Vivek", "Saxena", date(1979, 3, 14), "Male", "+91 96445 66778", "vivek.saxena@gmail.com", "AB+", "Kanpur"),
        ("Kavita", "Singhania", date(1987, 7, 28), "Female", "+91 96556 77889", "kavita.s@gmail.com", "A-", "Surat"),
        ("Pranav", "Mukerjee", date(1992, 11, 17), "Male", "+91 96667 88990", "pranav.m@gmail.com", "O-", "Ranchi"),
        ("Divya", "Pillai", date(1995, 4, 3), "Female", "+91 96778 99001", "divya.pillai@gmail.com", "B+", "Thiruvananthapuram"),
        ("Alok", "Mathur", date(1976, 9, 21), "Male", "+91 96889 00112", "alok.mathur@gmail.com", "A+", "Jodhpur"),
        ("Tanvi", "Hegde", date(1997, 6, 8), "Female", "+91 96990 11223", "tanvi.hegde@gmail.com", "AB-", "Mangaluru"),
        ("Nikhil", "Rao", date(1986, 12, 1), "Male", "+91 95001 22334", "nikhil.rao@gmail.com", "O+", "Mysuru"),
        ("Ritu", "Chadha", date(1981, 2, 19), "Female", "+91 95112 33445", "ritu.chadha@gmail.com", "B+", "Amritsar"),
        ("Gaurav", "Ghosh", date(1988, 7, 12), "Male", "+91 95223 44556", "gaurav.ghosh@gmail.com", "A+", "Bhubaneswar"),
        ("Swati", "Nambiar", date(1994, 9, 30), "Female", "+91 95334 55667", "swati.n@gmail.com", "O+", "Kozhikode"),
        ("Ishaan", "Bhatt", date(2001, 1, 15), "Male", "+91 95445 66778", "ishaan.b@gmail.com", "B+", "Vadodara")
    ]

    created_patients = []
    current_year = datetime.now().year
    today = date.today()
    rec_user = User.query.filter_by(email='reception@ipcms.com').first() or User.query.first()

    for idx, (fn, ln, dob, gnd, mob, em, bg, city) in enumerate(patient_records, start=1):
        p_code = f"IPCMS-{current_year}-{idx:06d}"
        
        # Determine registration timestamp across 15-day timeline:
        # Patients 1-6 registered today (Today's KPI shows 6 new patients)
        # Patients 7-10 registered yesterday
        # Patients 11-26 registered across days -2 to -14
        # Patients 27-36 registered last month (for healthy patient growth comparison)
        if idx <= 6:
            patient_created_at = datetime.combine(today, time(8, 30)) + timedelta(minutes=idx * 25)
        elif idx <= 10:
            patient_created_at = datetime.combine(today - timedelta(days=1), time(9, 15)) + timedelta(minutes=(idx - 6) * 40)
        elif idx <= 26:
            day_back = (idx - 10) % 14 + 2
            patient_created_at = datetime.combine(today - timedelta(days=day_back), time(10, 0)) + timedelta(minutes=idx * 15)
        else:
            patient_created_at = datetime(today.year, max(1, today.month - 1), min(25, idx))

        # Create or update linked Patient User account with password ABC@123
        p_user = User.query.filter_by(email=em).first()
        u_code = f"PAT-{idx:04d}"
        if not p_user:
            p_user = User(
                user_code=u_code,
                name=f"{fn} {ln}",
                email=em,
                role_id=roles_dict['Patient'].id,
                mobile=mob,
                is_active=True,
                created_at=patient_created_at
            )
            p_user.set_password('ABC@123')
            db.session.add(p_user)
            db.session.flush()
        else:
            p_user.name = f"{fn} {ln}"
            p_user.role_id = roles_dict['Patient'].id
            p_user.mobile = mob
            p_user.is_active = True
            p_user.set_password('ABC@123')
            db.session.flush()

        # Create or update Patient record
        p = Patient.query.filter((Patient.patient_code == p_code) | (Patient.email == em)).first()
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
                address=f"#{idx * 7}, Palm Grove Layout, {city}",
                blood_group=bg,
                emergency_contact_name=f"{fn}'s Family",
                emergency_contact_mobile=mob,
                insurance_provider="Star Health & Allied Insurance" if idx % 2 == 0 else "HDFC ERGO General Insurance",
                insurance_policy_no=f"POL-CARE-2026-{idx:04d}",
                height_cm=160.0 + (idx % 25),
                weight_kg=55.0 + (idx % 35),
                portal_status='ACTIVE',
                portal_user_id=p_user.id,
                registered_by_id=rec_user.id,
                created_at=patient_created_at
            )
            p.set_aadhaar(f"{1000 + idx:04d} {2000 + idx:04d} {3000 + idx:04d}")
            p.calculate_bmi()
            db.session.add(p)
            db.session.flush()
        else:
            p.portal_status = 'ACTIVE'
            p.portal_user_id = p_user.id
            p.created_at = patient_created_at
            p.mobile = mob
            p.calculate_bmi()

        # Add clinical medical history and allergy if not already present
        if not p.medical_histories:
            hist_pool = [
                ("Chronic Disease", "Hypertension - diagnosed 3 years ago, well controlled on daily ACE inhibitors."),
                ("Chronic Disease", "Type 2 Diabetes Mellitus - on oral hypoglycemic agents, regular HbA1c monitoring."),
                ("Chronic Disease", "Mild Bronchial Asthma - occasional seasonal wheezing, uses inhaler as needed."),
                ("Chronic Disease", "Dyslipidemia - lipid elevation identified in annual checkup, on statins.")
            ]
            c_type, desc = hist_pool[idx % len(hist_pool)]
            p_hist = PatientMedicalHistory(patient_id=p.id, condition_type=c_type, description=desc, diagnosed_year=2023)
            db.session.add(p_hist)

        if not p.allergies:
            allergy_pool = [
                ("Penicillin", "Mild skin hives"),
                ("Sulfa Drugs", "Facial rash and itching"),
                ("NSAIDs (Aspirin)", "Gastric irritation"),
                ("Dust Mites & Pollen", "Sneezing and allergic rhinitis")
            ]
            allg, reac = allergy_pool[idx % len(allergy_pool)]
            p_alg = PatientAllergy(patient_id=p.id, allergen=allg, reaction=reac, severity='Moderate')
            db.session.add(p_alg)

        created_patients.append(p)
    db.session.commit()

    # 10. Inpatient Admissions across Wards
    occupied_beds = Bed.query.filter_by(status='OCCUPIED').all()
    diagnoses_pool = [
        "Acute Anterior Wall Myocardial Infarction - Post PTCA Monitoring",
        "Type 2 Diabetes Mellitus with Severe Hyperglycemic Hyperosmolar State",
        "Subacute Ischemic Stroke with Left Hemiparesis & Dysphagia",
        "Post-Operative Right Total Knee Replacement (Day 3 Post-Op)",
        "Severe Community-Acquired Lobar Pneumonia with Hypoxia",
        "Decompensated Chronic Liver Disease with Ascites",
        "Acute Appendicitis with Localized Peritonitis - Post Lap Appendectomy",
        "Chronic Kidney Disease Stage 4 with Metabolic Acidosis",
        "Post-Operative Laparoscopic Cholecystectomy (Recovery Phase)",
        "Severe Acute Exacerbation of Bronchial Asthma (Nebulized)"
    ]
    for idx, bed in enumerate(occupied_beds):
        adm = Admission.query.filter_by(bed_id=bed.id, status='ADMITTED').first()
        if not adm and created_patients and doctor_users:
            pat = created_patients[idx % len(created_patients)]
            doc = doctor_users[idx % len(doctor_users)]
            diag = diagnoses_pool[idx % len(diagnoses_pool)]
            admit_days_ago = (idx % 8) + 1
            adm = Admission(
                admission_code=f"ADM-2026-{bed.id:04d}",
                patient_id=pat.id,
                doctor_id=doc.id,
                bed_id=bed.id,
                admitted_at=datetime.combine(today - timedelta(days=admit_days_ago), time(9, 30)) + timedelta(hours=idx % 6),
                diagnosis=diag,
                status='ADMITTED'
            )
            db.session.add(adm)

    # 3-4 Discharged admissions so discharges_count is populated on dashboard
    for idx in range(3):
        disch_code = f"ADM-DISCH-2026-{idx+1:03d}"
        disch_adm = Admission.query.filter_by(admission_code=disch_code).first()
        if not disch_adm and len(created_patients) > 10 and len(doctor_users) > 3:
            avail_bed = Bed.query.filter_by(status='AVAILABLE').first() or occupied_beds[0]
            disch_adm = Admission(
                admission_code=disch_code,
                patient_id=created_patients[15 + idx].id,
                doctor_id=doctor_users[idx].id,
                bed_id=avail_bed.id,
                admitted_at=datetime.combine(today - timedelta(days=4), time(10, 0)),
                discharged_at=datetime.combine(today, time(10, 30)) - timedelta(hours=idx * 2),
                diagnosis="Acute Gastroenteritis with Severe Dehydration - Successfully Rehydrated",
                status='DISCHARGED',
                discharge_notes="Patient vitals stable, oral intake normal. Advised oral rehydration and 5 days rest."
            )
            db.session.add(disch_adm)
    db.session.commit()

    # 11. Historical 14-Day Timeline Seeding (Days -14 down to -1)
    lab_types = LabTestType.query.all()
    lab_tech = User.query.filter_by(email='lab@ipcms.com').first() or User.query.first()

    for day_offset in range(14, 0, -1):
        target_date = today - timedelta(days=day_offset)
        # 5 appointments per past day (4 COMPLETED, 1 CANCELLED on alternating days)
        daily_plan = [
            (0, 0, time(9, 30), 'COMPLETED', 'Regular'),
            (1, 1, time(10, 30), 'COMPLETED', 'Regular'),
            (2, 2, time(11, 30), 'COMPLETED', 'Senior Citizen'),
            (3, 3, time(14, 30), 'COMPLETED', 'Child'),
            (4, 4, time(16, 0), 'CANCELLED' if day_offset % 3 == 0 else 'COMPLETED', 'Regular'),
        ]
        
        # On yesterday (day_offset == 1), add 2 more completed appointments for healthy volume
        if day_offset == 1:
            daily_plan.extend([
                (5, 5, time(12, 30), 'COMPLETED', 'Regular'),
                (6, 6, time(15, 30), 'COMPLETED', 'Regular'),
                (7, 0, time(17, 0), 'COMPLETED', 'Emergency'),
            ])

        for apt_idx, (p_offset, d_offset, sl_time, apt_status, prio) in enumerate(daily_plan, start=1):
            pat = created_patients[(day_offset * 2 + p_offset) % len(created_patients)]
            doc = doctor_users[(day_offset + d_offset) % len(doctor_users)]
            doc_prof = Doctor.query.filter_by(doctor_code=doc.user_code).first()
            doc_fee = doc_prof.consultation_fee if doc_prof else 600.0

            apt_code = f"APT-HIST-{day_offset:02d}-{apt_idx:02d}"
            apt = Appointment.query.filter_by(appointment_code=apt_code).first()
            apt_created_time = datetime.combine(target_date, sl_time) - timedelta(hours=4)

            if not apt:
                apt = Appointment(
                    appointment_code=apt_code,
                    patient_id=pat.id,
                    doctor_id=doc.id,
                    appointment_date=target_date,
                    slot_time=sl_time,
                    booking_type='Walk-In' if 'Emergency' in prio else 'Online',
                    priority=prio,
                    status=apt_status,
                    notes=f"Clinical OPD consultation with {doc.name}",
                    created_at=apt_created_time
                )
                db.session.add(apt)
                db.session.flush()
            else:
                apt.appointment_date = target_date
                apt.slot_time = sl_time
                apt.status = apt_status

            if apt_status == 'COMPLETED':
                # Check-In
                t_token = f"TK-{day_offset:02d}-{apt_idx:02d}"
                cin = CheckIn.query.filter_by(token_no=t_token).first()
                if not cin:
                    cin = CheckIn(
                        patient_id=pat.id,
                        doctor_id=doc.id,
                        token_no=t_token,
                        department=doc_prof.department if doc_prof else 'General OPD',
                        status='COMPLETED',
                        priority=prio,
                        check_in_time=datetime.combine(target_date, sl_time) - timedelta(minutes=15),
                        called_time=datetime.combine(target_date, sl_time),
                        completed_time=datetime.combine(target_date, sl_time) + timedelta(minutes=15),
                        checked_in_by_id=rec_user.id
                    )
                    db.session.add(cin)
                    db.session.flush()

                # Consultation
                cns_code = f"CNS-HIST-{day_offset:02d}-{apt_idx:02d}"
                cns = Consultation.query.filter_by(consultation_code=cns_code).first()
                if not cns:
                    cns = Consultation(
                        consultation_code=cns_code,
                        patient_id=pat.id,
                        doctor_id=doc.id,
                        appointment_id=apt.id,
                        check_in_id=cin.id if cin else None,
                        symptoms="Persistent fever, fatigue, joint ache, mild headache for 4 days.",
                        diagnosis="Acute Viral Pyrexia with Mild Dehydration",
                        treatment_plan="Paracetamol 650mg SOS, Oral rehydration fluids, 4 days bed rest.",
                        notes="Vitals stable upon discharge from consultation. Follow up if symptoms persist.",
                        started_at=datetime.combine(target_date, sl_time),
                        completed_at=datetime.combine(target_date, sl_time) + timedelta(minutes=15),
                        created_at=datetime.combine(target_date, sl_time)
                    )
                    db.session.add(cns)
                    db.session.flush()

                    # Vitals
                    vital = Vital(
                        consultation_id=cns.id,
                        bp_systolic=120 + (apt_idx % 15),
                        bp_diastolic=78 + (apt_idx % 10),
                        temperature_f=98.6 + (0.4 * (apt_idx % 4)),
                        pulse_bpm=72 + (apt_idx % 12),
                        spo2_percent=98 + (apt_idx % 2),
                        recorded_at=datetime.combine(target_date, sl_time)
                    )
                    db.session.add(vital)

                    # Prescription
                    rx_code = f"RX-HIST-{day_offset:02d}-{apt_idx:02d}"
                    rx = Prescription(
                        prescription_code=rx_code,
                        consultation_id=cns.id,
                        patient_id=pat.id,
                        doctor_id=doc.id,
                        general_advice="Adequate hydration, warm water intake, complete full course of medication.",
                        created_at=datetime.combine(target_date, sl_time) + timedelta(minutes=12)
                    )
                    db.session.add(rx)
                    db.session.flush()

                    db.session.add(PrescriptionItem(prescription_id=rx.id, medicine_name='Paracetamol 650 mg', frequency='1 - 0 - 1', duration='5 Days', food_relation='After Food', instructions='Take after meals'))
                    db.session.add(PrescriptionItem(prescription_id=rx.id, medicine_name='Pan 40', frequency='1 - 0 - 0', duration='5 Days', food_relation='Before Food', instructions='Take 30 mins before breakfast'))
                    db.session.add(PrescriptionItem(prescription_id=rx.id, medicine_name='Vitamin C 500 mg', frequency='0 - 1 - 0', duration='7 Days', food_relation='After Food', instructions='Chewable daily supplement'))

                # Lab Request & Result for ~50% of consultations
                if apt_idx % 2 == 1 and lab_types:
                    tt = lab_types[(day_offset + apt_idx) % len(lab_types)]
                    lr_code = f"LAB-HIST-{day_offset:02d}-{apt_idx:02d}"
                    lr = LabRequest.query.filter_by(request_code=lr_code).first()
                    if not lr:
                        lr = LabRequest(
                            request_code=lr_code,
                            patient_id=pat.id,
                            doctor_id=doc.id,
                            status='COMPLETED',
                            clinical_notes=f"Diagnostic routine profile requested by {doc.name}",
                            created_at=datetime.combine(target_date, sl_time) - timedelta(hours=1)
                        )
                        db.session.add(lr)
                        db.session.flush()

                        lres = LabResult(
                            request_id=lr.id,
                            test_type_id=tt.id,
                            result_value=round(random.uniform(tt.min_normal_val or 12.0, tt.max_normal_val or 16.0), 2),
                            abnormal_flag='NORMAL',
                            remarks="Parameters within calibrated reference biological intervals.",
                            technician_id=lab_tech.id,
                            completed_at=datetime.combine(target_date, sl_time) + timedelta(hours=1)
                        )
                        db.session.add(lres)

                # Invoice & Payment for this past consultation
                inv_code = f"INV-HIST-{day_offset:02d}-{apt_idx:02d}"
                bill = Bill.query.filter_by(invoice_code=inv_code).first()
                lab_charge = 450.0 if apt_idx % 2 == 1 else 0.0
                med_charge = 340.0
                subtot = doc_fee + lab_charge + med_charge
                tax = round(subtot * 0.05, 2)
                gtot = round(subtot + tax, 2)
                bill_time = datetime.combine(target_date, sl_time) + timedelta(minutes=20)

                if not bill:
                    bill = Bill(
                        invoice_code=inv_code,
                        patient_id=pat.id,
                        consultation_id=cns.id if cns else None,
                        subtotal=subtot,
                        discount=0.0,
                        tax_amount=tax,
                        grand_total=gtot,
                        paid_amount=gtot,
                        status='PAID',
                        notes='OPD Medical Consultation & Diagnostics Invoice',
                        created_at=bill_time
                    )
                    db.session.add(bill)
                    db.session.flush()

                    db.session.add(BillItem(bill_id=bill.id, item_type='CONSULTATION', item_description=f"Specialist Consultation - {doc.name}", unit_price=doc_fee, quantity=1, total_price=doc_fee))
                    if lab_charge > 0:
                        db.session.add(BillItem(bill_id=bill.id, item_type='LAB_TEST', item_description="Clinical Haematology / Biochemistry Investigation", unit_price=lab_charge, quantity=1, total_price=lab_charge))
                    db.session.add(BillItem(bill_id=bill.id, item_type='MEDICINE', item_description="Prescribed Outpatient Pharmacy Medicines", unit_price=med_charge, quantity=1, total_price=med_charge))

                    pm = Payment(
                        payment_code=f"PAY-HIST-{day_offset:02d}-{apt_idx:02d}",
                        bill_id=bill.id,
                        amount_paid=gtot,
                        payment_method=random.choice(['UPI', 'CARD', 'CASH', 'INSURANCE']),
                        transaction_ref=f"TXN-HIST-{day_offset:02d}-{apt_idx:04d}",
                        recorded_by_id=rec_user.id,
                        paid_at=bill_time + timedelta(minutes=5)
                    )
                    db.session.add(pm)

        # Inpatient Bed Charge Revenue for historical days
        if day_offset in [1, 2, 4, 6, 8, 11, 13]:
            ipd_inv_code = f"INV-IPD-HIST-{day_offset:02d}"
            ipd_bill = Bill.query.filter_by(invoice_code=ipd_inv_code).first()
            if not ipd_bill and created_patients:
                ipd_pat = created_patients[(day_offset * 3) % len(created_patients)]
                bed_cost = 14000.0 if day_offset == 1 else 10500.0
                ipd_subtot = bed_cost
                ipd_tax = round(ipd_subtot * 0.05, 2)
                ipd_gtot = round(ipd_subtot + ipd_tax, 2)
                ipd_time = datetime.combine(target_date, time(14, 0))

                ipd_bill = Bill(
                    invoice_code=ipd_inv_code,
                    patient_id=ipd_pat.id,
                    subtotal=ipd_subtot,
                    discount=0.0,
                    tax_amount=ipd_tax,
                    grand_total=ipd_gtot,
                    paid_amount=ipd_gtot,
                    status='PAID',
                    notes='Inpatient Ward Care & Daily Bed Accommodation',
                    created_at=ipd_time
                )
                db.session.add(ipd_bill)
                db.session.flush()

                db.session.add(BillItem(bill_id=ipd_bill.id, item_type='BED_CHARGE', item_description="Inpatient Multi-Day Ward Accommodation & Nursing", unit_price=bed_cost, quantity=1, total_price=bed_cost))
                
                db.session.add(Payment(
                    payment_code=f"PAY-IPD-HIST-{day_offset:02d}",
                    bill_id=ipd_bill.id,
                    amount_paid=ipd_gtot,
                    payment_method='INSURANCE' if day_offset % 2 == 0 else 'CARD',
                    transaction_ref=f"TXN-IPD-{day_offset:02d}-001",
                    recorded_by_id=rec_user.id,
                    paid_at=ipd_time + timedelta(minutes=15)
                ))

        # Second IPD bill specifically for Yesterday (day_offset == 1) to anchor yesterday revenue at ~₹42,000
        if day_offset == 1:
            ipd_inv_code_2 = f"INV-IPD-HIST-01-B"
            ipd_bill_2 = Bill.query.filter_by(invoice_code=ipd_inv_code_2).first()
            if not ipd_bill_2 and len(created_patients) > 8:
                ipd_pat_2 = created_patients[8]
                bed_cost_2 = 13500.0
                tax_2 = round(bed_cost_2 * 0.05, 2)
                gtot_2 = round(bed_cost_2 + tax_2, 2)
                ipd_time_2 = datetime.combine(target_date, time(16, 30))

                ipd_bill_2 = Bill(
                    invoice_code=ipd_inv_code_2,
                    patient_id=ipd_pat_2.id,
                    subtotal=bed_cost_2,
                    discount=0.0,
                    tax_amount=tax_2,
                    grand_total=gtot_2,
                    paid_amount=gtot_2,
                    status='PAID',
                    notes='ICU Critical Care & Monitoring Package',
                    created_at=ipd_time_2
                )
                db.session.add(ipd_bill_2)
                db.session.flush()

                db.session.add(BillItem(bill_id=ipd_bill_2.id, item_type='BED_CHARGE', item_description="ICU Inpatient Room & Specialized Care", unit_price=bed_cost_2, quantity=1, total_price=bed_cost_2))
                
                db.session.add(Payment(
                    payment_code=f"PAY-IPD-HIST-01-B",
                    bill_id=ipd_bill_2.id,
                    amount_paid=gtot_2,
                    payment_method='INSURANCE',
                    transaction_ref="TXN-IPD-01-002",
                    recorded_by_id=rec_user.id,
                    paid_at=ipd_time_2 + timedelta(minutes=10)
                ))

    db.session.commit()

    # 12. Today's Appointments & Receptionist Live Queue (12 Appointments: Completed, In Consultation, Waiting, Booked)
    today_plan = [
        (0, 0, time(9, 0), 'COMPLETED', 'Regular'),
        (1, 1, time(9, 30), 'COMPLETED', 'Regular'),
        (2, 2, time(10, 0), 'COMPLETED', 'Regular'),
        (3, 3, time(10, 30), 'COMPLETED', 'Pregnant Woman'),
        (4, 4, time(11, 0), 'COMPLETED', 'Senior Citizen'),
        (5, 5, time(11, 30), 'IN_CONSULTATION', 'Child'),
        (6, 0, time(12, 0), 'CHECKED_IN', 'Emergency'),
        (7, 1, time(12, 30), 'CHECKED_IN', 'Senior Citizen'),
        (8, 2, time(14, 0), 'CHECKED_IN', 'Regular'),
        (9, 3, time(15, 0), 'BOOKED', 'Regular'),
        (10, 4, time(16, 0), 'BOOKED', 'Regular'),
        (11, 5, time(17, 0), 'BOOKED', 'Regular')
    ]

    for idx, (p_idx, d_idx, sl_t, status, prio) in enumerate(today_plan, start=1):
        pat = created_patients[p_idx % len(created_patients)]
        doc = doctor_users[d_idx % len(doctor_users)]
        doc_prof = Doctor.query.filter_by(doctor_code=doc.user_code).first()
        doc_fee = doc_prof.consultation_fee if doc_prof else 600.0

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
                notes=f"Consultation with {doc.name} regarding current clinical symptoms.",
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

        # Seed Check-In token for today's queue if checked in / in consultation / completed
        if status in ['COMPLETED', 'IN_CONSULTATION', 'CHECKED_IN']:
            t_num = f"TK-{idx:03d}"
            cin = CheckIn.query.filter_by(token_no=t_num).first()
            cin_status = 'COMPLETED' if status == 'COMPLETED' else ('IN_CONSULTATION' if status == 'IN_CONSULTATION' else 'WAITING')
            
            if not cin:
                cin = CheckIn(
                    patient_id=pat.id,
                    doctor_id=doc.id,
                    token_no=t_num,
                    department=doc_prof.department if doc_prof else 'General OPD',
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

            # Seed consultation & prescription & vitals
            if status in ['COMPLETED', 'IN_CONSULTATION']:
                cns = Consultation.query.filter_by(appointment_id=apt.id).first()
                if not cns:
                    cns = Consultation(
                        consultation_code=f"CNS-{current_year}-{idx:05d}",
                        patient_id=pat.id,
                        doctor_id=doc.id,
                        appointment_id=apt.id,
                        check_in_id=cin.id,
                        symptoms="Mild chest discomfort, seasonal dry cough, occasional dizziness.",
                        diagnosis="Upper Respiratory Tract Infection & Mild Essential Hypertension",
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
                        bp_systolic=122 + (idx % 10),
                        bp_diastolic=80 + (idx % 6),
                        temperature_f=98.6 + (0.3 * (idx % 3)),
                        pulse_bpm=74 + (idx % 8),
                        spo2_percent=99,
                        recorded_at=datetime.combine(today, sl_t)
                    )
                    db.session.add(vital)

                    # Prescription
                    if status == 'COMPLETED':
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

                            db.session.add(PrescriptionItem(prescription_id=rx.id, medicine_name='Paracetamol 650 mg', frequency='1 - 0 - 1', duration='5 Days', food_relation='After Food', instructions='Take if temperature exceeds 99°F'))
                            db.session.add(PrescriptionItem(prescription_id=rx.id, medicine_name='Cetirizine 10 mg', frequency='0 - 0 - 1', duration='5 Days', food_relation='After Food', instructions='Take before bedtime'))
                            db.session.add(PrescriptionItem(prescription_id=rx.id, medicine_name='Vitamin C 500 mg', frequency='1 - 0 - 1', duration='5 Days', food_relation='After Food', instructions='Chewable tablet'))
                else:
                    cns.started_at = datetime.combine(today, sl_t)
                    cns.completed_at = datetime.combine(today, sl_t) + timedelta(minutes=15) if status == 'COMPLETED' else None

                # Generate Paid Bill & Payment for completed appointments today
                if status == 'COMPLETED':
                    inv_code = f"INV-{current_year}-{idx:05d}"
                    b = Bill.query.filter_by(invoice_code=inv_code).first()
                    lab_cost = 450.0 if idx % 2 == 1 else 0.0
                    med_cost = 320.0
                    subtot = doc_fee + lab_cost + med_cost
                    tax = round(subtot * 0.05, 2)
                    gtot = round(subtot + tax, 2)
                    bill_created_at = datetime.combine(today, sl_t) + timedelta(minutes=20)

                    if not b:
                        b = Bill(
                            invoice_code=inv_code,
                            patient_id=pat.id,
                            consultation_id=cns.id if cns else None,
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

                        db.session.add(BillItem(bill_id=b.id, item_type='CONSULTATION', item_description=f"Specialist Consultation - {doc.name}", unit_price=doc_fee, quantity=1, total_price=doc_fee))
                        if lab_cost > 0:
                            db.session.add(BillItem(bill_id=b.id, item_type='LAB_TEST', item_description="Complete Blood Count & Sugar Test", unit_price=lab_cost, quantity=1, total_price=lab_cost))
                        db.session.add(BillItem(bill_id=b.id, item_type='MEDICINE', item_description="Prescription Pharmacy Medications", unit_price=med_cost, quantity=1, total_price=med_cost))

                        pm = Payment(
                            payment_code=f"PAY-{current_year}-{idx:05d}",
                            bill_id=b.id,
                            amount_paid=gtot,
                            payment_method=random.choice(['UPI', 'CARD', 'CASH', 'INSURANCE']),
                            transaction_ref=f"TXN-CAREHUB-TODAY-{idx:04d}",
                            recorded_by_id=rec_user.id,
                            paid_at=bill_created_at + timedelta(minutes=5)
                        )
                        db.session.add(pm)
                    else:
                        b.created_at = bill_created_at
                        b.paid_amount = b.grand_total
                        b.status = 'PAID'
                        pm = Payment.query.filter_by(bill_id=b.id).first()
                        if pm:
                            pm.paid_at = bill_created_at + timedelta(minutes=5)
                            pm.amount_paid = b.grand_total

    # Additional IPD Procedure Invoices for Today (Total Today Revenue ~₹54,000+ > Yesterday ~₹42,000)
    today_ipd_plans = [
        ('INV-IPD-TODAY-01', created_patients[0].id, 24000.0, 'ICU & Cardiac Monitoring Daily Package', 'INSURANCE', time(11, 45)),
        ('INV-IPD-TODAY-02', created_patients[1].id, 18000.0, 'Private Deluxe Suite Bed Care & Specialized Nursing', 'CARD', time(13, 15))
    ]
    for inv_c, p_id, b_charge, desc, p_meth, t_time in today_ipd_plans:
        b_ipd = Bill.query.filter_by(invoice_code=inv_c).first()
        b_tax = round(b_charge * 0.05, 2)
        b_gtot = round(b_charge + b_tax, 2)
        b_dt = datetime.combine(today, t_time)
        if not b_ipd:
            b_ipd = Bill(
                invoice_code=inv_c,
                patient_id=p_id,
                subtotal=b_charge,
                discount=0.0,
                tax_amount=b_tax,
                grand_total=b_gtot,
                paid_amount=b_gtot,
                status='PAID',
                notes='IPD Accommodation & Critical Care Charges',
                created_at=b_dt
            )
            db.session.add(b_ipd)
            db.session.flush()

            db.session.add(BillItem(bill_id=b_ipd.id, item_type='BED_CHARGE', item_description=desc, unit_price=b_charge, quantity=1, total_price=b_charge))

            pm_ipd = Payment(
                payment_code=f"PAY-{inv_c}",
                bill_id=b_ipd.id,
                amount_paid=b_gtot,
                payment_method=p_meth,
                transaction_ref=f"TXN-{inv_c}",
                recorded_by_id=rec_user.id,
                paid_at=b_dt + timedelta(minutes=10)
            )
            db.session.add(pm_ipd)
        else:
            b_ipd.created_at = b_dt
            pm_ipd = Payment.query.filter_by(bill_id=b_ipd.id).first()
            if pm_ipd:
                pm_ipd.paid_at = b_dt + timedelta(minutes=10)

    # 13. Tomorrow's Future Appointments (Day +1)
    tomorrow = today + timedelta(days=1)
    for t_idx in range(5):
        fut_code = f"APT-FUT-{current_year}-{t_idx+1:03d}"
        if not Appointment.query.filter_by(appointment_code=fut_code).first():
            db.session.add(Appointment(
                appointment_code=fut_code,
                patient_id=created_patients[t_idx + 12].id,
                doctor_id=doctor_users[t_idx % len(doctor_users)].id,
                appointment_date=tomorrow,
                slot_time=time(10 + t_idx, 0),
                booking_type='Online',
                priority='Regular',
                status='BOOKED',
                notes='Scheduled follow-up consultation.',
                created_at=datetime.combine(today, time(9, 0))
            ))

    # 14. Emergency Encounters for Reception Triage & Admin Dashboard
    emergencies_today = [
        ('ER-001', f"TEMP-ER-{current_year}-0001", created_patients[3].id, 'Acute Asthma / Respiratory Distress', 'Emergency / Critical', 'Stabilized', 'Ambulance', doctor_users[0].id, time(8, 45), 'Patient arrived with acute wheezing. Nebulization administered immediately.'),
        ('ER-002', f"TEMP-ER-{current_year}-0002", created_patients[4].id, 'Road Traffic Accident / Trauma', 'Emergency / Critical', 'In Triage', 'Walk-In / Bystander', doctor_users[1].id, time(11, 15), 'Laceration wound on forearm, vitals stable, wound dressing in progress.'),
        ('ER-003', f"TEMP-ER-{current_year}-0003", created_patients[5].id, 'Acute Chest Pain / Rule Out MI', 'Emergency / Critical', 'Doctor Assigned', 'Ambulance', doctor_users[1].id, time(12, 10), 'ECG performed immediately, cardiac markers ordered, IV access secured.')
    ]
    for tok, tmp, p_id, e_type, prio, st, src, doc_id, arr_t, nts in emergencies_today:
        er_enc = EmergencyEncounter.query.filter_by(temp_id=tmp).first()
        arr_dt = datetime.combine(today, arr_t)
        if not er_enc:
            er_enc = EmergencyEncounter(
                temp_id=tmp,
                token_no=tok,
                patient_id=p_id,
                is_identified=True,
                emergency_type=e_type,
                priority=prio,
                status=st,
                arrival_source=src,
                assigned_doctor_id=doc_id,
                department='Emergency / Trauma',
                notes=nts,
                arrival_time=arr_dt,
                registered_by_id=rec_user.id
            )
            db.session.add(er_enc)
        else:
            er_enc.arrival_time = arr_dt
            er_enc.status = st

    # 15. Today's Lab Requests (4 Completed, 2 Pending/Requested)
    for idx in range(1, 7):
        req_code = f"LAB-REQ-TODAY-{idx:03d}"
        lr = LabRequest.query.filter_by(request_code=req_code).first()
        status = 'COMPLETED' if idx <= 4 else 'REQUESTED'
        req_created_at = datetime.combine(today, time(9, 0)) + timedelta(minutes=idx * 25)

        if not lr:
            pat = created_patients[idx % len(created_patients)]
            doc = doctor_users[idx % len(doctor_users)]
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
                    completed_at=datetime.combine(today, time(10, 30)) + timedelta(minutes=idx * 15)
                )
                db.session.add(lres)
        else:
            lr.created_at = req_created_at
            lr.status = status

    # 16. Past Months Historical Revenue for 6-Month Chart (April - August 2026)
    # Builds an impressive growth trajectory in the 6-Month Revenue chart
    past_months_target = [
        (4, 2026, 185000.0),  # April
        (5, 2026, 240000.0),  # May
        (6, 2026, 310000.0),  # June
        (7, 2026, 385000.0),  # July
        (8, 2026, 460000.0),  # August
    ]
    for m_num, y_num, target_amt in past_months_target:
        m_code = f"INV-HIST-M{m_num:02d}-{y_num}"
        m_bill = Bill.query.filter_by(invoice_code=m_code).first()
        if not m_bill and created_patients:
            cns_part = round(target_amt * 0.35, 2)
            bed_part = round(target_amt * 0.35, 2)
            lab_part = round(target_amt * 0.15, 2)
            med_part = round(target_amt * 0.15, 2)
            tot_amt = cns_part + bed_part + lab_part + med_part
            m_dt = datetime(y_num, m_num, 15, 14, 0)

            m_bill = Bill(
                invoice_code=m_code,
                patient_id=created_patients[m_num % len(created_patients)].id,
                subtotal=tot_amt,
                discount=0.0,
                tax_amount=0.0,
                grand_total=tot_amt,
                paid_amount=tot_amt,
                status='PAID',
                notes=f"Consolidated Monthly Operational Billing {datetime(y_num, m_num, 1).strftime('%B %Y')}",
                created_at=m_dt
            )
            db.session.add(m_bill)
            db.session.flush()

            db.session.add(BillItem(bill_id=m_bill.id, item_type='CONSULTATION', item_description="Outpatient Clinical Consultations", unit_price=cns_part, quantity=1, total_price=cns_part))
            db.session.add(BillItem(bill_id=m_bill.id, item_type='BED_CHARGE', item_description="Inpatient Ward & ICU Care", unit_price=bed_part, quantity=1, total_price=bed_part))
            db.session.add(BillItem(bill_id=m_bill.id, item_type='LAB_TEST', item_description="Laboratory Diagnostics & Scans", unit_price=lab_part, quantity=1, total_price=lab_part))
            db.session.add(BillItem(bill_id=m_bill.id, item_type='MEDICINE', item_description="Hospital Pharmacy Formulary Dispensing", unit_price=med_part, quantity=1, total_price=med_part))

            db.session.add(Payment(
                payment_code=f"PAY-HIST-M{m_num:02d}-{y_num}",
                bill_id=m_bill.id,
                amount_paid=tot_amt,
                payment_method='INSURANCE',
                transaction_ref=f"TXN-MONTHLY-{y_num}-{m_num:02d}",
                recorded_by_id=rec_user.id,
                paid_at=m_dt + timedelta(minutes=30)
            ))

    # 17. Audit Logs
    actions = [
        ('USER_LOGIN', 'Auth', 1, 'Admin signed in successfully from management console'),
        ('CHECK_IN_PROCESSED', 'Reception', 2, 'Generated Queue Token TK-001 for Dr. Rajesh Sharma'),
        ('INVOICE_GENERATED', 'Billing', 1, 'Generated Invoice INV-2026-00001 for OPD consultation'),
        ('PRESCRIPTION_CREATED', 'Prescription', 1, 'Dr. Rajesh Sharma issued digital prescription RX-2026-000001'),
        ('LAB_RESULT_VERIFIED', 'Laboratory', 1, 'Technician verified Complete Blood Count results'),
        ('BED_ALLOCATION', 'Beds', 4, 'Allocated Bed BED-ICU-01 to emergency patient'),
        ('EMERGENCY_TRIAGE', 'Emergency', 1, 'Triage team registered critical case ER-001'),
        ('PATIENT_PORTAL_ACTIVE', 'Patient', 1, 'Patient portal credentials provisioned for Radhika Hougale'),
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
            timestamp=datetime.utcnow() - timedelta(minutes=random.randint(5, 240))
        ))

    # 18. Notifications
    if Notification.query.count() < 6 and created_patients:
        notifs = [
            (created_patients[0].id, "APPOINTMENT_REMINDER", "Upcoming Consultation Reminder", "Your consultation with Dr. Rajesh Sharma is confirmed for today."),
            (created_patients[1].id, "LAB_READY", "Laboratory Test Results Ready", "Your Complete Blood Count test results have been verified."),
            (created_patients[2].id, "PRESCRIPTION_READY", "Digital E-Prescription Dispensed", "Your prescribed medications are ready at the CareHub Pharmacy."),
            (created_patients[3].id, "PAYMENT_REMINDER", "Invoice Payment Receipt Generated", "Payment of ₹1,438.50 received with transaction reference TXN-CAREHUB-000001."),
            (created_patients[4].id, "PORTAL_ACTIVE", "Patient Portal Activated", "Your patient portal account is active. Log in with your email and password ABC@123.")
        ]
        for p_id, n_type, tit, msg in notifs:
            db.session.add(Notification(
                patient_id=p_id,
                type=n_type,
                title=tit,
                message=msg,
                channel='BOTH',
                status='SENT',
                created_at=datetime.utcnow() - timedelta(minutes=random.randint(10, 180))
            ))

    db.session.commit()
    print("[SEEDER] Full hospital database seeding completed successfully across 15 days!")
