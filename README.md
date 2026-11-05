# 🛡️ DeepFake Detection V2

.venv\Scripts\Activate.ps1
>> 
(.venv) (base) PS D:\SHIVA\Documents\engineering\Project\Deepfake-Detection-V2> python app.py  

A professional full-stack AI-powered forensic application that detects whether an uploaded image is **Real** or **Fake (Deepfake)** using a hybrid deep learning architecture (**EfficientNet-B0 + 2D FFT Frequency Analysis + Attention Fusion**), backed by a secure **PostgreSQL Authentication System**.

---

## 🚀 Features

- **User Authentication**: Secure Register, Login, Logout, and Change Password powered by Flask-Login and PostgreSQL.
- **Enterprise Security**: Werkzeug password hashing, CSRF protection, session management, secure cookie handling, and open-redirect prevention.
- **AI-Based Deepfake Detection**: Dual-branch spatial and frequency domain analysis.
  - EfficientNet-B0 Spatial Feature Extraction (1280 dimensions)
  - 2D Fast Fourier Transform (FFT) Magnitude Analysis (128 dimensions)
  - Self-Gated Attention Fusion (1408 dimensions)
- **Face Localization**: Multi-stage Haar cascade face alignment with automated margin expansion and safe fallback.
- **Forensic Metrics**: Instant Real vs. Fake probabilities, confidence scoring, face detection status, and inference latency.
- **PostgreSQL Prediction History**: Automatic recording of all predictions, probabilities, timestamps, model metadata, SHA-256 image hashes, and latency metrics.
- **Secure Image Storage**: Private, sanitized, non-guessable storage paths with strict server-side ownership enforcement and anti-path-traversal protection.
- **Downloadable PDF Forensic Reports**: Dynamically generated high-resolution PDF authenticity certificates via ReportLab containing embedded images, verdict banners, case details, and forensic disclaimers.
- **User Privacy & Isolation**: Strict row-level tenancy ensuring User A can never query, inspect, download, or access User B's images, history, or PDF reports.
- **Database Migrations**: Managed PostgreSQL schema with Flask-Migrate & Alembic.

---

## 🏗️ Architecture & Tech Stack

- **Backend**: Python 3.13, Flask 3.1, Flask-SQLAlchemy, Flask-Login, Flask-Migrate, Flask-WTF, Psycopg3, ReportLab
- **Database**: PostgreSQL (Default port `5433`, database `deepfake_detection_v2`)
- **AI Engine**: PyTorch, Torchvision, Timm, OpenCV, Pillow
- **Frontend**: Responsive Jinja2 forensic interface + React 19 SPA

---

## 🗄️ Database Schema & Storage

### PostgreSQL Tables

1. **`users`**:
   - `id`: Primary key (Integer)
   - `full_name`: User's full name (VARCHAR 150)
   - `email`: Unique email address with index (VARCHAR 180)
   - `password_hash`: Werkzeug password hash (VARCHAR 256)
   - `created_at`, `updated_at`: Timezone-aware UTC timestamps

2. **`prediction_history`**:
   - `id`: Primary key (Integer)
   - `user_id`: Foreign key referencing `users.id` (ON DELETE CASCADE, indexed)
   - `original_filename`: Sanitized uploaded filename (VARCHAR 255)
   - `stored_image_path`: Relative storage path `predictions/user_<id>_<uuid>.<ext>` (VARCHAR 512)
   - `image_sha256`: SHA-256 hash of the uploaded image bytes (CHAR 64, indexed)
   - `image_format`: Verified format (JPEG, PNG, WEBP, BMP) (VARCHAR 20)
   - `image_width`, `image_height`: Pixel dimensions (Integer)
   - `predicted_label`: Categorical verdict (`REAL` or `FAKE`) (VARCHAR 10)
   - `probability_real`, `probability_fake`: Model probabilities (%) (Float)
   - `confidence`: Confidence score = `max(P_real, P_fake)` (%) (Float)
   - `threshold_used`: Classification decision boundary (Default `0.50`) (Float)
   - `inference_time_ms`: Processing time in milliseconds (Float)
   - `model_name`: Architecture name (VARCHAR 120)
   - `model_version`: Model checkpoint version (VARCHAR 50)
   - `face_detected`: Face crop alignment indicator (Boolean)
   - `created_at`: Timezone-aware UTC prediction timestamp (indexed)

### Image Storage Architecture

- **Directory**: `uploads/predictions/` (configured via `Config.UPLOAD_FOLDER`)
- **Naming Pattern**: `user_<user_id>_<uuid4_hex>.<extension>`
- **Security**: The storage directory is private and NEVER mounted as a public static directory. Images are streamed exclusively through the authenticated endpoint `/history/<id>/image` with server-side ownership verification and path traversal guards.
- **Git Protection**: `uploads/` is registered in `.gitignore` to prevent committing private evidence.

---

## ⚙️ Environment Configuration

Copy `.env.example` to `.env` and configure your credentials:

```bash
cp .env.example .env
```

Ensure `.env` contains:

```ini
FLASK_APP=backend/app.py
FLASK_ENV=development
SECRET_KEY=your-secure-random-secret-key
DATABASE_URL=postgresql://postgres:your_password@localhost:5433/deepfake_detection_v2
MODEL_PATH=backend/models/best_model_v4.pth
UPLOAD_FOLDER=uploads
```

> **Security Note:** `.env` contains sensitive secrets and is excluded from version control via `.gitignore`. Never commit `.env` files.

---

## 📦 Installation & Setup

### 1. Set Up Virtual Environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r backend/requirements.txt
pip install Flask-SQLAlchemy Flask-Login Flask-Migrate Flask-WTF "psycopg[binary]" python-dotenv email-validator pytest reportlab httpx
```

### 3. Database Migration

Ensure PostgreSQL is running on port `5433` and apply schema migrations:

```powershell
$env:PYTHONPATH="."
flask --app backend.app db upgrade
```

To create a new migration after schema changes:

```powershell
flask --app backend.app db migrate -m "Migration description"
flask --app backend.app db upgrade
```

---

## 🏃 Running the Application

Start the Flask server:

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONPATH="."
python backend/app.py
```

### Application URLs

- 🔑 **Login**: [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login)
- 📝 **Register**: [http://127.0.0.1:5000/register](http://127.0.0.1:5000/register)
- 📊 **Forensic Dashboard / Detector**: [http://127.0.0.1:5000/](http://127.0.0.1:5000/) (Protected)
- 📜 **Prediction History**: [http://127.0.0.1:5000/history](http://127.0.0.1:5000/history) (Protected)
- 🔍 **Prediction Details**: `http://127.0.0.1:5000/history/<id>` (Protected, owner-only)
- 📄 **Download PDF Report**: `http://127.0.0.1:5000/history/<id>/download` (Protected, owner-only)
- 🖼️ **Secure Image Stream**: `http://127.0.0.1:5000/history/<id>/image` (Protected, owner-only)
- 🔒 **Change Password**: [http://127.0.0.1:5000/change-password](http://127.0.0.1:5000/change-password) (Protected)
- 🟢 **API Status**: [http://127.0.0.1:5000/api/status](http://127.0.0.1:5000/api/status)

---

## 🧪 Automated Testing

Run the full automated test suite (including registration, login, logout, password change, CSRF protection, prediction history persistence, image isolation, cross-user denial, and PDF generation):

```powershell
$env:PYTHONPATH="."
pytest -v tests/
```

Or run using Python's built-in test runner:

```powershell
$env:PYTHONPATH="."
python -m unittest discover -s tests -p "test_*.py"
```

To run individual test modules:

```powershell
python -m unittest tests/test_history.py
python -m unittest tests/test_auth.py
python -m unittest tests/test_detection.py
```

---

## 💾 Backup & Disaster Recovery

### PostgreSQL Database Backup
To perform an automated backup of the PostgreSQL database:

```powershell
pg_dump -U postgres -h localhost -p 5433 -d deepfake_detection_v2 -F c -b -v -f "backup_deepfake_$(Get-Date -Format 'yyyyMMdd_HHmmss').dump"
```

To restore from a backup:

```powershell
pg_restore -U postgres -h localhost -p 5433 -d deepfake_detection_v2 -v "backup_file.dump"
```

### Uploaded Images Backup
Because prediction images and database records are synchronized via `stored_image_path`:
1. Always back up the `uploads/predictions/` directory in tandem with the PostgreSQL database dump.
2. Maintain snapshot consistency so that image files match the foreign keys and storage keys in the `prediction_history` table.

---

## 🔒 Security Architecture

1. **Password Hashing**: Passwords are encrypted using Werkzeug's secure hashing algorithms (`scrypt`/`pbkdf2`) with unique cryptographic salts.
2. **CSRF Protection**: All web forms include tamper-proof CSRF tokens enforced by Flask-WTF.
3. **Session Hardening**: Cookies are configured with `HttpOnly` and `SameSite=Lax` to mitigate XSS and CSRF attack vectors.
4. **Open Redirect Prevention**: Login redirects validate target hostnames against the application host before navigation.
5. **Route Protection**: Private pages and prediction APIs require an active authenticated user session.
6. **Strict Row-Level Tenancy**: All history queries filter directly by `current_user.id`. Inaccessible prediction IDs return 404 to avoid enumeration.
7. **Path Traversal Guards**: Image requests are validated against `Config.UPLOAD_FOLDER` boundary using absolute path checks.
8. **Forensic Integrity**: Uploaded images are hashed with SHA-256 upon reception and recorded alongside the verdict for evidentiary chain-of-custody.