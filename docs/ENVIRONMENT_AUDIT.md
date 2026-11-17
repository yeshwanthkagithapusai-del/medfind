# MediFind – Environment & Settings Configuration Audit

**Author**: Senior Django Developer, DevOps Engineer & Git Version Control Specialist  
**Project**: MediFind  
**Date**: November 17, 2026  
**Target Settings**: `config/settings.py` & `.env.example`  
**Security Status**: Safe Development Baseline (Production Hardening Required)  

---

## 1. Executive Summary

This audit evaluates the configuration posture of MediFind across development and production environments. It assesses environment variable decoupling, secret management, debugging flags, host header filters, database connections, static/media asset serving, and HTTP security headers.

No actual production secrets or cryptographic keys are exposed within this document.

---

## 2. Configuration Analysis Matrix

| Configuration Directive | Current Implementation in `settings.py` | Specification in `.env.example` | Evaluation / Status | Severity |
| :--- | :--- | :--- | :--- | :---: |
| **`SECRET_KEY`** | `os.environ.get('SECRET_KEY', '<dev-fallback>')` | Provided via example template | **PASS (Dev)** / **WARN (Prod)**: Fallback key present for zero-config local run, but production must require an explicit external secret. | MEDIUM |
| **`DEBUG`** | `os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')` | `DEBUG=True` | **PASS**: Decoupled from hardcoding; casts string truthiness properly. Default is `True` when unset. | LOW |
| **`ALLOWED_HOSTS`** | `[h.strip() for h in os.environ.get('ALLOWED_HOSTS', '*').split(',') if h.strip()]` | `ALLOWED_HOSTS=localhost,127.0.0.1` | **PASS (Dev)** / **WARN (Prod)**: Default wildcard `*` allows zero-friction local testing, but must be restricted in production. | MEDIUM |
| **`DATABASES`** | `ENGINE: 'django.db.backends.sqlite3'`, `NAME: BASE_DIR / 'db.sqlite3'` | None (implicitly SQLite) | **PASS (Dev)**: Self-contained, portable, zero-configuration. Needs PostgreSQL adapter (`dj-database-url`) for enterprise deployments. | MEDIUM |
| **`STATIC_URL`** | `'/static/'` | N/A | **PASS**: Standard Django static routing. | PASS |
| **`STATICFILES_DIRS`** | `[BASE_DIR / 'static']` | N/A | **PASS**: Correctly binds project-level static assets. | PASS |
| **`STATIC_ROOT`** | `BASE_DIR / 'staticfiles'` | N/A | **PASS**: Pre-configured for `python manage.py collectstatic`. | PASS |
| **`MEDIA_URL` & `ROOT`** | `'/media/'`, `BASE_DIR / 'media'` | N/A | **PASS**: Configured; served conditionally under `DEBUG=True` in `config/urls.py`. | PASS |
| **`AUTH_USER_MODEL`**| `'accounts.User'` | N/A | **EXCELLENT**: Bound to custom user model prior to initial migrations. | PASS |
| **`dotenv` Loading** | Not called in `manage.py` or `settings.py` | File exists (`.env.example`) | **DEFECT**: `python-dotenv` is listed in requirements, but `load_dotenv()` is never invoked automatically on boot. | HIGH |

---

## 3. Granular Findings & Environmental Gaps

### 3.1 Defect: Automatic `.env` File Ingestion Missing
- **Current Behavior**:
  Although `python-dotenv` is declared in `requirements.txt`, neither `manage.py`, `wsgi.py`, nor `settings.py` calls `dotenv.load_dotenv()`.
- **Impact**:
  If a developer or deployment administrator creates a `.env` file from `.env.example`, Django does **not** automatically ingest the environment variables. The application falls back to defaults unless an external runner (e.g. `pipenv`, `foreman`, or shell export) is used.
- **Recommended Remediation**:
  In `manage.py` and `config/wsgi.py`, add:
  ```python
  from dotenv import load_dotenv
  from pathlib import Path
  load_dotenv(Path(__file__).resolve().parent / '.env')
  ```

---

### 3.2 Security Header & Cookie Flags in Production
In `config/settings.py`, HTTP security flags are currently absent (standard for local development). For production deployments with SSL/TLS (HTTPS), the following settings must be conditionally enforced:

```python
if not DEBUG:
    # SSL/HTTPS Redirection
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Cookie Security
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    
    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Content Sniffing & XSS Defense
    SECURE_CONTENT_TYPE_NOSNIFF = True
```

---

### 3.3 Database Engine Configuration (Development vs. Production)
- **Current State**:
  The database configuration is hardcoded to SQLite:
  ```python
  DATABASES = {
      'default': {
          'ENGINE': 'django.db.backends.sqlite3',
          'NAME': BASE_DIR / 'db.sqlite3',
      }
  }
  ```
- **Limitation**:
  While SQLite is ideal for development, testing, and collegiate examinations, high-concurrency production deployments suffer from database-level file write locking.
- **Production Recommendation**:
  Utilize `dj-database-url` to support transparent environment-based database switching:
  ```python
  import dj_database_url
  
  DATABASES = {
      'default': dj_database_url.config(
          default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
          conn_max_age=600
      )
  }
  ```

---

### 3.4 Email Backend Configuration
- **Current State**: No `EMAIL_BACKEND` is explicitly configured; Django defaults to `django.core.mail.backends.smtp.EmailBackend`.
- **Impact**: Any future notification or password-reset feature attempting to send emails without SMTP credentials will raise an `SMTPConnectError` or connection timeout.
- **Recommendation**:
  For development, explicitly declare:
  ```python
  EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
  ```

---

## 4. Production Readiness Checklist

- [x] Custom User model configured before initial migration.
- [x] Static files collected root (`STATIC_ROOT`) configured.
- [x] Media upload directory configured.
- [x] Dynamic `DEBUG` flag parsing.
- [x] Dynamic `ALLOWED_HOSTS` parsing.
- [ ] Automated `.env` ingestion via `load_dotenv()`.
- [ ] Production HTTPS / HSTS security headers gated behind `DEBUG=False`.
- [ ] Database configuration switchable via `DATABASE_URL`.
- [ ] Explicit console `EMAIL_BACKEND` for development.
