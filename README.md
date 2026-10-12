# 🏥 Integrated Patient Care Management System (IPCMS)
### *Next-Generation Healthcare Operating System & Clinical Management Platform*

<div align="center">

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask 3.0](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MySQL 8.0](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](https://www.mysql.com/)
[![Bootstrap 5.3](https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![Groq AI](https://img.shields.io/badge/Groq_AI-LLM_Agent-F55036?style=for-the-badge&logo=openai&logoColor=white)](https://groq.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

<br/>

**CareHub IPCMS** is an enterprise-grade, full-stack hospital operating system engineered to unify outpatient clinics, inpatient bed wards, diagnostic laboratories, digital pharmacies, and patient self-service portals into a single, cohesive, real-time healthcare ecosystem.

</div>

---

## 🎥 System Walkthrough & Landing Page Demo

<div align="center">
  <img src="landing_page.gif" alt="CareHub / IPCMS Landing Page Walkthrough" width="75%" style="border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.12); border: 1px solid #e2e8f0; max-width: 780px;" />
  <p>
    <sub>🎬 <em>Live interactive walkthrough of the CareHub landing page, 24/7 doctor schedules, and patient portal access.</em></sub>
  </p>
</div>

---

## 🌟 Executive Project Overview

Modern hospitals frequently suffer from fragmented departmental silos: front desks manage isolated queues, physicians juggle handwritten prescriptions, laboratories maintain detached paper reports, and billing departments manually cross-verify inpatient days. 

**IPCMS (CareHub)** resolves this by providing an interconnected clinical workflow engine where:
- Every patient encounter generates a **Unified 360° Electronic Health Record (EHR)**.
- Front-desk intake dynamically calculates **priority queue wait times** and issues triage tokens.
- Physicians work in a dedicated clinical workspace with **live vitals recording**, **smart prescription generation**, and **Base64 QR code verification**.
- Inpatient bed management synchronizes real-time **ward occupancy grids** with billing.
- Visitors on the public landing page interact with **Maya**, an autonomous **Groq LLM-powered booking concierge** that schedules appointments conversationally through tool calling.

---

## 🚀 Dedicated Stakeholder Workspaces

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CareHub Unified Core Engine                     │
├─────────────┬─────────────┬─────────────┬──────────────┬───────────────┤
│   Patient   │   Doctor    │ Reception & │ Laboratory & │ Admin & Exec  │
│   Portal    │  Workspace  │ Smart Queue │ Diagnostics  │  Governance   │
│  (/portal)  │  (/doctor)  │ (/reception)│    (/lab)    │   (/admin)    │
└─────────────┴─────────────┴─────────────┴──────────────┴───────────────┘
```

### 👤 1. Patient Self-Service Portal (`/portal/`)
- **360° EHR Timeline**: Comprehensive visual timeline tracking consultations, vitals, prescriptions, lab results, bed transfers, and billing receipts.
- **Digital Prescriptions**: Download digital prescriptions with tamper-evident SVG QR codes for offline verification.
- **Verified Diagnostic Reports**: Real-time notifications and PDF/print downloads when laboratory results are verified.
- **Active User Authentication**: Secure portal login (`ABC@123`) with personalized health alerts and appointment reminders.

### 🩺 2. Doctor Clinical Workspace (`/doctor/`)
- **OPD Consultation Desk**: Seamless daily appointment roster, chief complaints logger, and diagnosis documentation.
- **Clinical Vitals Recorder**: Tracks Systolic/Diastolic BP, Temperature, Pulse Rate, and SpO2 with biological range highlighting.
- **Digital Prescription Builder**: Formularies autocomplete, dosage frequencies (`1-0-1`), meal relations (`After Food`), and special instructions.
- **Direct Lab Requisition**: One-click diagnostic test ordering sent directly to the technician desk.

### 📋 3. Reception & Smart Triage Desk (`/reception/`)
- **Fast-Track Intake**: Patient intake registration with SequenceMatcher fuzzy duplicate detection and encrypted demographic storage.
- **Priority Token Generator**: Daily sequential queue tokens (`TK-001`) prioritized across 5 clinical tiers (*Emergency*, *Senior Citizen*, *Pregnant Woman*, *Child*, *Regular*).
- **Dynamic Queue Estimator**: Rolling average consultation duration engine computing real-time estimated wait times.
- **Emergency Room Triage**: Instant stabilization intake for acute trauma, ambulance arrivals, and unidentified emergency patients.

### 🔬 4. Laboratory & Diagnostics Desk (`/lab/`)
- **Specimen Worklist**: Centralized tracking of pending, in-progress, and verified diagnostic test orders.
- **Automated Parameter Evaluator**: Real-time evaluation against biological reference intervals marking flags as `NORMAL`, `ABNORMAL`, or `CRITICAL`.
- **Technician Digital Signature**: Verification stamp, clinical remarks, and auto-generated printable test reports.

### 🛏️ 5. Inpatient & Bed Management (IPD) (`/beds/`)
- **Ward Occupancy Grid**: Live floor map across *General Ward A/B*, *Intensive Care Unit (ICU)*, *Private Deluxe Suites*, and *Emergency Bays*.
- **Bed Status Lifecycle**: Automated state management (`AVAILABLE` $\rightarrow$ `OCCUPIED` $\rightarrow$ `UNDER_CLEANING`).
- **Admission to Discharge Tracking**: Records admitting diagnoses, attending physicians, bed transfer logs, and length-of-stay metrics.

### 💳 6. Billing & Financial Operations (`/billing/`)
- **Automated Charges Aggregator**: Single-click consolidated invoicing aggregating doctor fees, diagnostic scans, pharmacy items, and ward bed charges.
- **Multi-Channel Payment Processing**: Reconciles transactions via *UPI*, *Credit/Debit Cards*, *Cash*, and *Insurance Claims*.
- **Printable Tax Invoices**: Standardized hospital GST invoices with itemized cost breakdowns and payment receipts.

### 🛡️ 7. Admin & Executive Governance (`/admin/`)
- **Executive KPI Dashboard**: Live monitoring of today's patients, daily revenue growth, active doctors, bed occupancy rates, and emergency cases.
- **Financial Analytics**: 15-day revenue trend curves, 6-month historical comparisons, and departmental revenue share charts powered by Chart.js.
- **System Governance**: Staff user lifecycle (activation/deactivation), master catalogs (medicines, lab test types), audit trails, and automated database backups.

---

## 🤖 Integrated AI & Clinical Intelligence

CareHub integrates a cutting-edge conversational AI layer powered by the **Groq Llama-3 / Qwen LLM** architecture:

- **Maya — The AI Booking Concierge**: Embedded directly on the public landing page, Maya conducts a natural, conversational patient booking experience.
- **Autonomous Tool-Calling Loop**: Uses server-side function calling to search 24/7 doctor rosters, check active clinic schedules, look up existing patient accounts, and book appointments without filling static forms.
- **Clinical Guardrails**: Strictly guides patients to appropriate departments (Cardiology, Neurology, Pediatrics, Orthopedics, etc.) based on described symptoms while providing emergency safety disclaimers.

---

## 🔄 End-to-End Clinical Lifecycle Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Patient
    actor Reception as Front Desk
    actor Doctor
    actor Lab as Lab Tech
    actor Billing as Accounts

    Patient->>Reception: Arrives at Hospital / Books via Maya AI
    Reception->>Reception: Validates Identity (AES Aadhaar Check) & Generates Token (TK-001)
    Reception->>Doctor: Enters Priority Queue (Emergency / Senior / Regular)
    Doctor->>Doctor: Conducts Consultation & Records Vitals (BP, SpO2, Temp)
    Doctor->>Doctor: Generates Digital Prescription (SVG QR Code)
    opt Diagnostic Scans Ordered
        Doctor->>Lab: Requisitions Lab Test (CBC, Lipid, X-Ray)
        Lab->>Lab: Evaluates Sample & Flags (Normal / Abnormal)
        Lab-->>Doctor: Results Verified & Appended to EHR
    end
    opt Inpatient Admission Required
        Doctor->>Reception: Allocates Bed (ICU / Deluxe Suite / General)
    end
    Doctor->>Billing: Consultation Completed
    Billing->>Billing: Auto-Aggregates Bill (Consultation + Labs + Meds + Beds)
    Patient->>Billing: Settles Invoice (UPI / Card / Cash / Insurance)
    Billing-->>Patient: Instant Digital Receipt & Portal Update
```

---

## 🔒 Security, Privacy & Compliance Architecture

- **Aadhaar & PII Encryption**: Patient government identification numbers are encrypted at rest using **Cryptography Fernet (AES-128/256-bit)**; masked values (`XXXX-XXXX-1234`) are displayed across public interfaces.
- **Role-Based Access Control (RBAC)**: Strict server-side route guards enforcing granular privileges across 5 system roles (`Admin`, `Doctor`, `Receptionist`, `Lab Technician`, `Patient`).
- **Tamper-Evident E-Prescriptions**: Each prescription generates an isolated Base64 SVG QR code that links to a public authenticity verification endpoint.
- **Audit Trails**: Every administrative action, bed allocation, invoice generation, and user login is immutably timestamped and recorded in the audit log.
- **Brute-Force & Session Protection**: Rate-limiting login attempts with automatic 15-minute account lockouts and CSRF token verification on all POST requests.

---

## 🛠️ Technology Stack

| Layer | Technologies & Frameworks |
| :--- | :--- |
| **Backend Core** | Python 3.11, Flask 3.0+, Jinja2 Templating Engine |
| **Database & ORM** | MySQL 8.x / SQLite, SQLAlchemy ORM 2.0+, Flask-Migrate |
| **Artificial Intelligence** | Groq API (Llama-3 / Qwen), Autonomous Tool-Calling Agent |
| **Security & Cryptography** | Werkzeug Bcrypt, Cryptography Fernet (AES), Flask-WTF CSRF |
| **UI & Presentation** | Bootstrap 5.3, Bootstrap Icons, Google Fonts (Outfit / Inter) |
| **Data Visualization** | Chart.js 4.x (Revenue Line Charts, Occupancy Doughnuts) |
| **Utilities** | Python `qrcode` (SVG Base64 Engine), `difflib` Fuzzy Matcher |
| **Testing** | Python `unittest` Test Suite (38 unit test assertions) |

---

## ⚡ Quick Start & Local Setup Guide

### 1. Prerequisites
- **Python 3.11+** installed on your machine
- **MySQL Server 8.0+** (or SQLite fallback)
- **Git**

### 2. Clone Repository & Setup Virtual Environment
```bash
# Clone the repository
git clone https://github.com/dradhikac/Integrated-Patient-Care-Management-System.git
cd Integrated-Patient-Care-Management-System

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (Command Prompt):
.\venv\Scripts\activate.bat
# Linux / macOS:
source venv/bin/activate
```

### 3. Install Required Dependencies
```bash
pip install -r requirements.txt
```

### 4. Database Configuration & Seeding
Configure your database URI in `app/config.py` or `.env`:
```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:YourPassword@127.0.0.1:3306/ipcms_db'
```

Execute the full operational database seeder (populates **15 days** of realistic hospital appointments, revenue, doctors, wards, and active patient profiles):
```bash
python seed_db.py
```

### 5. Launch Application
```bash
python run.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔑 Pre-Seeded Demo Credentials

All staff and doctor accounts are pre-configured for instant evaluation. Patient portal accounts are activated with password **`ABC@123`**:

| Role | Email / Username | Default Password | Primary Workspace |
| :--- | :--- | :--- | :--- |
| **System Admin** | `admin@ipcms.com` | `Password@123` | Executive Analytics, Governance & Settings |
| **Super Admin** | `administrator@medicore.com` | `Admin@123` | Master Catalogs & System Audit Trails |
| **Doctor** | `doctor@ipcms.com` | `Password@123` | OPD Consultation Desk & Rx Builder |
| **Receptionist** | `reception@ipcms.com` | `Password@123` | Patient Intake, Queue Tokens & ER Triage |
| **Lab Technician** | `lab@ipcms.com` | `Password@123` | Specimen Bench & Test Verification |
| **Patient Portal** | `radhika@carehub.com` | `ABC@123` | 360° EHR Health Records & Receipts |
| **Patient Demo** | `patient@ipcms.com` | `Password@123` | 1-Click Demo Patient Portal |

---

## 🧪 Verification & Unit Testing

Run the automated test suite across consultations, appointments, vitals, prescriptions, and authentication:
```bash
python -m unittest discover -s tests
```
```text
Ran 38 tests in 4.21s — OK (0 failures, 0 errors)
```

---

## 📄 License & Attribution

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for complete details.

Developed with ❤️ for modern healthcare institutions seeking seamless patient care and operational excellence.
