# MediFind – Dependency & Package Audit Report

**Author**: Senior Django Developer, DevOps Engineer & Git Version Control Specialist  
**Project**: MediFind  
**Date**: November 17, 2026  
**Python Runtime**: Python 3.11.9  
**Package Manager**: `pip` (Installed in environment)  
**Status**: Clean Baseline (No Auto-Upgrades Performed)  

---

## 1. Executive Summary

This audit cross-references the declared dependencies in `requirements.txt` against the active Python 3.11.9 environment. It identifies active packages, unused packages, potential compatibility considerations, and recommended production dependencies.

In accordance with strict DevOps protocols, **no packages were upgraded or installed automatically**.

---

## 2. Declared vs. Installed Dependencies

### 2.1 Declared Dependencies (`requirements.txt`)
```text
Django>=5.2,<6.0
Pillow>=10.0.0
python-dotenv>=1.0.0
```

### 2.2 Active Environment Inspection

| Declared Package | Declared Constraint | Installed Version | Status | Functional Role |
| :--- | :--- | :--- | :---: | :--- |
| **`Django`** | `>=5.2,<6.0` | **5.2.16 LTS** | **Active & Verified** | Core web framework, ORM, Auth, Template engine, Admin. |
| **`Pillow`** | `>=10.0.0` | **12.3.0** | **Installed / Dormant** | Image processing library. Currently dormant (no `ImageField` is declared in active models). |
| **`python-dotenv`** | `>=1.0.0` | **1.0.0** | **Installed / Unwired** | Ingests `.env` key-value pairs into `os.environ`. Installed, but not yet wired to `load_dotenv()`. |

### 2.3 Implicit Transitive Dependencies
- **`asgiref`** (v3.11.1): Core ASGI specification library required by Django for asynchronous support.
- **`sqlparse`** (v0.5.5): Non-validating SQL parser used by Django's database backend for migration and query formatting.
- **`tzdata`** (v2026.3): IANA time zone database providing accurate timezone offsets across Windows and Unix platforms.

---

## 3. Dependency Utilization Analysis

### 3.1 Active & Essential
- **Django 5.2.16**: Powering all 6 core applications (`accounts`, `medicines`, `pharmacies`, `inventory`, `requests_app`, `dashboard`), ORM migrations, URL routing, and security middleware.

### 3.2 Dormant / Unused Dependency: `Pillow`
- **Codebase Scan**: A full text search across all `models.py` files returned 0 matches for `models.ImageField`.
- **Finding**: `Pillow` is installed and required, but no models currently store user avatars, pharmacy store photos, or prescription attachments.
- **Recommendation**: Retain `Pillow` in `requirements.txt` if prescription upload or pharmacy storefront photo upload is planned for future phases; otherwise, it can be pruned to minimize build container size.

### 3.3 Unwired Dependency: `python-dotenv`
- **Finding**: Declared in `requirements.txt` and installed in the environment, but never imported in `manage.py` or `config/settings.py`.
- **Recommendation**: Add `load_dotenv()` in `manage.py` and `config/wsgi.py` upon user approval.

---

## 4. Production & Deployment Dependency Recommendations

For cloud deployment (e.g. Railway, Render, AWS, Heroku, DigitalOcean), the following production dependencies will be required:

| Recommended Package | Purpose | Justification |
| :--- | :--- | :--- |
| **`gunicorn`** | Production WSGI Server | Replaces Django's single-threaded development server with a multi-worker production server. (Currently present in global environment v26.2.0). |
| **`whitenoise`** | Static Asset Serving | Serves compressed, cache-busted static CSS/JS directly from Django without needing an external Nginx proxy. (Currently present in global environment v6.12.0). |
| **`psycopg2-binary`** | PostgreSQL DB Adapter | Enables high-concurrency production connection to PostgreSQL databases. (Currently present in global environment v2.9.12). |
| **`dj-database-url`** | `DATABASE_URL` Parser | Parses cloud standard database connection URLs into Django `DATABASES` dictionaries. (Currently present in global environment v3.1.2). |

---

## 5. Potential Compatibility & Security Risks

1. **Python Version**: Python 3.11.9 is fully supported by Django 5.2 LTS (which supports Python 3.10, 3.11, 3.12, 3.13).
2. **Pip Notice**: The system package manager emitted a minor advisory:
   ```text
   [notice] A new release of pip is available: 24.0 -> 26.3
   ```
   *Action*: No auto-upgrade performed, honoring the requirement to avoid unapproved environment mutations.
3. **Pinned Bounds**: The constraint `Django>=5.2,<6.0` correctly prevents breaking changes when Django 6.0 is eventually released.
