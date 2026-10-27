# ME-PHYSI — Unified Healthcare Management System

A Django-rendered healthcare management application built to match the resume stack: **Python, Django, MySQL, HTML, CSS and vanilla JavaScript**. There is no React, TypeScript, Vite, Flask, Supabase or CSS framework.

## Modules
- Role-aware accounts: administrator, doctor and patient
- Patient profiles and searchable patient directory
- Doctor profiles and specialties
- Appointment booking, cancellation/status updates and basic overlapping-booking prevention
- Electronic health records: diagnosis, allergies, clinical notes and treatment plan
- Prescriptions associated with a medical record
- Django admin for trusted administrative management

## Requirements
- Python 3.11+ (Python 3.12 recommended)
- MySQL Server 8.x running locally
- Windows 10/11 or another Python-supported OS

## 1. Create the MySQL database
Open MySQL Workbench or the MySQL command line and run:

```sql
CREATE DATABASE mephysi_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'mephysi_user'@'localhost' IDENTIFIED BY 'change-this-password';
GRANT ALL PRIVILEGES ON mephysi_db.* TO 'mephysi_user'@'localhost';
FLUSH PRIVILEGES;
```

Use a strong password and keep it private. If you already have a local MySQL account, you may use that account instead and adjust `.env`.

## 2. Set up on Windows (Command Prompt)
From the folder containing `manage.py`:

```bat
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Edit `.env` with your MySQL credentials and a new `SECRET_KEY`. `DEBUG=True` is for local development only.

Then run:

```bat
python manage.py check
python manage.py makemigrations core
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/ . Sign in using the superuser you created. For the admin interface, visit http://127.0.0.1:8000/admin/ . A Django superuser has administrator access by default.

## 3. Role-based access and workflows
- Create the first administrator with `python manage.py createsuperuser`; superusers are treated as administrators.
- Sign in to the app and use **＋ Add doctor** to create a doctor login and publish weekly working hours. Only administrators can access this screen.
- Patients can self-register. Patient registration always assigns the patient role; users cannot self-select doctor or administrator roles.
- Patients can request only slots within a doctor's active published schedule. Appointment requests remain pending until the assigned doctor accepts or declines them.
- Doctors can accept/decline requests assigned to them, and mark confirmed appointments complete after the scheduled time. Patients can cancel their own future pending or confirmed appointments.
- The app checks both doctor and patient overlap, schedule-window boundaries, slot alignment, and appointment state transitions on the server. Booking actions use a database transaction and lock the doctor's profile while validating the slot.
- In-app notifications are created for request submission, doctor response, cancellation, completion, and doctor account creation. Open **Notifications** to review them and mark them read. Email/SMS delivery is not configured.
- Administrators can add more recurring schedule windows from the doctor directory. Overlapping active windows are blocked; pausing a schedule window does not silently cancel existing appointments.

## 4. Run tests
After configuring MySQL and applying migrations, run:

```bat
python manage.py test core
```

The tests cover patient booking, overlap rejection, doctor acceptance and notifications, role protection, and schedule validation. Run them against a local test database before relying on the app.

## Notes and limitations
- This is an educational project, not a certified clinical system. Use fictional data during development; do not store real patient information in a public deployment without security, privacy, backup and compliance review.
- The app provides core workflows, not emergency-care advice, e-prescription regulatory compliance, billing, insurance claims, laboratory integrations or production audit/compliance guarantees.
- The app is configured for MySQL and does not silently fall back to SQLite.
- Static assets are served by Django during development. For production, configure `DEBUG=False`, HTTPS, secure cookies, a proper WSGI/ASGI deployment and static-file serving.
