# Integrated Patient Care Management System (IPCMS) 🏥

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Flask 3.0](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![MySQL 8.0](https://img.shields.io/badge/MySQL-8.0-orange.svg)](https://www.mysql.com/)
[![Bootstrap 5.3](https://img.shields.io/badge/Bootstrap-5.3-purple.svg)](https://getbootstrap.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade, full-stack **Healthcare Operating System & Hospital Management Solution** engineered with **Python 3.11**, **Flask**, **SQLAlchemy ORM**, **MySQL 8.x**, **Bootstrap 5**, and **Chart.js**.

IPCMS streamlines the complete 360-degree patient care lifecycle across **15 fully integrated subsystems**: from OPD reception token generation and smart appointment slot allocation to electronic health record (EHR) timeline aggregation, digital prescription QR code verification, lab diagnostic workflows, IPD bed management, multi-channel GST billing, automated asynchronous notifications, and executive analytics.

---

## 🌟 Key Features & 15 Subsystem Modules

| Subsystem Module | Core Capabilities & Highlights |
| :--- | :--- |
| **Module 01: Auth & Access Control** | Bcrypt password hashing, rate-limiting brute-force lockouts, 5 RBAC roles (`Admin`, `Doctor`, `Receptionist`, `Lab Technician`, `Patient`), session security. |
| **Module 02: Patient Intake & Encryption** | Unique patient code generator (`IPCMS-2026-XXXXXX`), Cryptography Fernet AES-encrypted Aadhaar storage, BMI calculator, SequenceMatcher fuzzy duplicate detection. |
| **Module 03: Reception Desk & Tokens** | Daily OPD token generator (`TK-001`), estimated wait time engine, 5 priority tiers (`Emergency`, `Senior Citizen`, `Pregnant Woman`, `Child`, `Regular`). |
| **Module 04: Smart Appointments** | 15-minute slot generator (`09:00 AM` to `05:00 PM`), emergency slot protection, agreement-based waitlist promotion engine (`OFFERED` status, Accept/Decline flow). |
| **Module 05: Smart Queue & TV Display** | Priority queue sorter engine, rolling average consultation duration calculator, live TV display board (`display_board.html`) with JSON API polling (`/queue/api/live_board`). |
| **Module 06: EHR 360° Timeline** | Unified 360-degree patient timeline aggregator (`timeline_builder.py`) consolidating consultations, vitals, prescriptions, lab results, billing, bed transfers, and notifications. |
| **Module 07: Doctor Consultation Workspace** | Interactive consultation workspace (`consult.html`), clinical vitals recording (BP, Temp, Pulse, SpO2), chief complaints, and diagnosis logger. |
| **Module 08: Digital Prescription Builder** | Multi-drug builder, master formulary integration, standalone Base64 SVG QR code verification generator (`qr_generator.py`), public authenticity verification API (`/prescriptions/verify/<rx_code>`). |
| **Module 09: Laboratory & Diagnostics** | Diagnostic test request desk (`tech_desk.html`), lab result uploads, automated abnormal parameter evaluator (`evaluate_result_flag()`), printable official test reports. |
| **Module 10: Billing & Financials** | Automated charges aggregator (`generate_auto_bill_for_patient`), itemized OPD/Pharmacy/Lab billing, multi-channel payment collection (Cash, UPI, Card, Insurance), printable hospital GST tax invoice (`print_invoice.html`). |
| **Module 11: Inpatient & Bed Management (IPD)** | Live ward occupancy grid (`General`, `ICU`, `Pediatric`, `Maternity`), bed status tracking (`AVAILABLE` $\rightarrow$ `OCCUPIED`), bed transfer tracking, inpatient discharge. |
| **Module 12: Executive Analytics** | Executive KPI metric cards, departmental revenue breakdown progress bars, top prescribed pharmaceuticals ranking, CSV data exporters for billing & patients. |
| **Module 13: Notification System** | 5 notification categories (`APPOINTMENT_REMINDER`, `LAB_READY`, `PRESCRIPTION_READY`, `PAYMENT_REMINDER`, `FOLLOWUP_REMINDER`), non-blocking asynchronous thread dispatcher (`dispatch_async`), background reminder scanner. |
| **Module 14: Reports & Analytics Dashboard** | 5 exportable hospital reports (Patient, Revenue, Doctor, Appointment, Lab) in CSV and printable PDF formats. Chart.js Monthly Revenue Trend line chart & Appointment Status doughnut chart. |
| **Module 15: Admin Module** | Staff account creation/deactivation, role assignment, master data catalogs (medicines, lab test types), fee structure settings (`system_settings`), system-wide audit trail viewer (`audit_logs`), manual DB backup snapshot generator (`backups/`). |

---

## 🏗️ System Architecture

```mermaid
graph TD
    Client[Web Browser / Live TV Display / QR Scanner] --> Flask[Flask Web Core Framework]
    Flask --> Auth[Bcrypt Auth & Security Middleware]
    Flask --> Form[Flask-WTF Validation & CSRF Protection]
    Flask --> ORM[SQLAlchemy ORM]
    ORM --> MySQL[(MySQL 8.x Database 'ipcms_db')]
    
    Flask --> QR[Standalone Base64 SVG QR Generator]
    Flask --> AES[Cryptography Fernet AES Encryption]
    Flask --> Timeline[EHR 360° Timeline Builder]
    Flask --> Notif[Asynchronous Notification Dispatcher & Log Engine]
    Flask --> ChartJS[Chart.js Admin Analytics & Exporters]
    Flask --> AdminEngine[Admin Governance: Staff Lifecycle, Settings, Audit Trail & Backups]
```

---

## 🛠️ Technology Stack

- **Backend Framework**: Python 3.11, Flask 3.0+
- **Database Engine**: MySQL 8.0+ / MySQL Workbench (`ipcms_db`)
- **ORM & Migrations**: SQLAlchemy 2.0+, Flask-Migrate
- **Security & Cryptography**: Werkzeug Bcrypt, Cryptography Fernet (AES-128/256)
- **Frontend Architecture**: Jinja2 Templating, Bootstrap 5.3, Bootstrap Icons
- **Data Visualization**: Chart.js 4.x
- **Testing Framework**: Python Unittest Suite (38 unit tests covering all 15 modules)

---

## 🚀 Quick Start & Local Setup Guide

### 1. Prerequisites
Ensure you have the following installed on your system:
- Python **3.11+**
- MySQL Server **8.0+**
- Git

### 2. Clone Repository & Setup Virtual Environment
```bash
# Clone repository
git clone https://github.com/dradhikac/Integrated-Patient-Care-Management-System.git
cd Integrated-Patient-Care-Management-System

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Database Setup & Seeding
Ensure your MySQL Server is running. Configure your database credentials in `app/config.py` or `.env`:
```python
# MySQL Database Connection String
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:YourPassword@127.0.0.1:3306/ipcms_db'
```

Create database tables and seed sample accounts:
```bash
python -m flask --app run.py seed-db
```

### 5. Run Local Development Server
```bash
python run.py
```
Open your browser and navigate to **`http://127.0.0.1:5000`**.

---

## 🔑 Demo Login Accounts

All demo accounts are pre-seeded with password: **`Password@123`**

| Role | Username / Email | Default Password | Responsibilities |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@ipcms.com` | `Password@123` | Full administrative control, staff creation, settings, audit logs, DB backups. |
| **Doctor** | `doctor@ipcms.com` | `Password@123` | OPD consultation workspace, vitals recording, EHR history, digital Rx generation. |
| **Receptionist** | `reception@ipcms.com` | `Password@123` | Patient intake registration, token generation, queue manager, appointment booking. |
| **Lab Technician** | `lab@ipcms.com` | `Password@123` | Diagnostic test request desk, lab result uploads, parameter flag evaluations. |
| **Patient** | `patient@ipcms.com` | `Password@123` | Personal health portal, appointment history, lab report downloads, billing receipts. |

---

## 🧪 Running Unit Tests

Run the complete test suite across all 15 modules:
```bash
python -m unittest discover -s tests
```
**Test Results**: `Ran 38 tests — OK (0 failures, 0 errors)`

---

## 📚 Project Documentation Sitemap

Detailed implementation guides and Viva voce defense preparation guides for all 15 modules are available in the [`docs/`](file:///r:/Integrated-Patient-Care-Management-System/docs/) directory:

- 📖 [Complete Project Documentation (All 15 Modules)](file:///r:/Integrated-Patient-Care-Management-System/docs/complete_project_documentation.md)
- 🔒 [Module 01 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_01_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_01_viva_guide.md)
- 👤 [Module 02 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_02_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_02_viva_guide.md)
- 🎟️ [Module 03 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_03_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_03_viva_guide.md)
- 📅 [Module 04 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_04_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_04_viva_guide.md)
- 📺 [Module 05 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_05_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_05_viva_guide.md)
- 📂 [Module 06 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_06_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_06_viva_guide.md)
- 🩺 [Module 07 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_07_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_07_viva_guide.md)
- 💊 [Module 08 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_08_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_08_viva_guide.md)
- 🧪 [Module 09 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_09_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_09_viva_guide.md)
- 💳 [Module 10 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_10_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_10_viva_guide.md)
- 🏥 [Module 11 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_11_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_11_viva_guide.md)
- 📊 [Module 12 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_12_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_12_viva_guide.md)
- 🔔 [Module 13 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_13_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_13_viva_guide.md)
- 📈 [Module 14 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_14_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_14_viva_guide.md)
- 🛡️ [Module 15 Implementation Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_15_implementation_guide.md) \| [Viva Guide](file:///r:/Integrated-Patient-Care-Management-System/docs/module_15_viva_guide.md)

---

## 📄 License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
