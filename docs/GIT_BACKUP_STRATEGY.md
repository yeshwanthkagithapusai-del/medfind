# MediFind – Git Version Control & Backup Strategy

**Author**: Senior Django Developer, DevOps Engineer & Git Version Control Specialist  
**Project**: MediFind (Location-Based Medicine Availability & Pharmacy Inventory Platform)  
**Date**: November 17, 2026  
**Status**: Pre-Development Baseline Strategy  

---

## 1. Executive Summary

This document establishes the version control workflow and disaster recovery backup protocols for the MediFind project prior to executing any code modifications. It outlines the current Git repository state, step-by-step Git initialization procedures, checkpoint commit recommendations, and an enterprise-grade SQLite online backup architecture.

---

## 2. Git Repository State & Audit

A diagnostic execution of `git status` within the project root (`c:\Users\yeshw\OneDrive\Desktop\medfind_project`) confirmed:

```text
fatal: not a git repository (or any of the parent directories): .git
```

### 2.1 Git Status Analysis
- **Current State**: Git is **NOT initialized**.
- **Working Tree**: Standalone directory containing project apps, documentation, database, and templates.
- **Safety Rule Observed**: Per strict DevOps instructions, Git initialization was **NOT performed automatically**. Explicit user approval is required prior to executing `git init`.

### 2.2 `.gitignore` Integrity Review
The existing `.gitignore` in the project root was inspected:

```gitignore
*.pyc
__pycache__/
*.sqlite3
db.sqlite3
media/
.env
.venv/
```

#### Observations & Recommended Additions:
1. **Secrets & Environment**: `.env` is correctly excluded from version control, preventing accidental credential leaks.
2. **Binary Database**: `db.sqlite3` and `*.sqlite3` are correctly excluded from Git commits, preventing repository bloat and merge conflicts.
3. **Recommended Additions**:
   - `*.zip`: Prevents generated project archives from being committed into Git history.
   - `staticfiles/`: Excludes collected static assets generated during deployment.
   - `scratch/`: Excludes temporary exploration or audit helper scripts.

---

## 3. Recommended Git Initialization & Checkpoint Protocol

Upon user authorization, the following sequence should be executed to establish a clean version control baseline:

```bash
# Step 1: Initialize Git repository
git init

# Step 2: Set default branch to main
git branch -M main

# Step 3: Verify staging area honors .gitignore
git status

# Step 4: Stage all foundational application files and documentation
git add .gitignore requirements.txt manage.py .env.example
git add accounts/ medicines/ pharmacies/ inventory/ requests_app/ dashboard/ config/
git add templates/ static/ tests/ docs/

# Step 5: Create Initial Baseline Checkpoint Commit
git commit -m "chore(baseline): initial project structure and working MVP architecture"
```

### 3.1 Recommended Branching Strategy

To isolate upcoming upgrade phases and prevent disruption to the working application, the following feature-branch convention is recommended:

```
main (Production / Stable Baseline)
  │
  └── dev (Integration Branch)
        │
        ├── feature/phase-1-security-hardening
        ├── feature/phase-2-data-model-validation
        ├── feature/phase-3-query-pagination
        ├── feature/phase-4-feature-polish
        └── feature/phase-5-test-expansion
```

---

## 4. Comprehensive Backup Strategy

### 4.1 Asset Protection Matrix

| Asset Class | Files Protected | Retention / Target Location | Backup Frequency |
| :--- | :--- | :--- | :--- |
| **Source Code** | Python files in all 6 apps + `config/` | Git repo + `backups/src_backup_<date>.zip` | Prior to every phase |
| **Templates** | HTML files in `templates/` | Git repo + `backups/src_backup_<date>.zip` | Prior to every phase |
| **Static Assets** | CSS, JS, Images in `static/` | Git repo + `backups/src_backup_<date>.zip` | Prior to every phase |
| **Migrations** | `*/migrations/0001_initial.py` | Git repo + `backups/src_backup_<date>.zip` | Prior to every migration |
| **Documentation** | All markdown files in `docs/` | Git repo + `backups/src_backup_<date>.zip` | Continuous |
| **Database** | Seeded demonstration database (`db.sqlite3`) | Point-in-time SQLite snapshot via backup API | Daily & pre-migration |
| **Environment** | Configuration schema (`.env.example`) | Git repo (zero secrets included) | On configuration change |

---

## 5. SQLite Consistent Database Backup Protocol

### 5.1 The Danger of Naive File Copying
Copying an active SQLite database (`copy db.sqlite3 db_backup.sqlite3`) while the Django development server is running risks **corrupting the backup** due to dirty writes, partial page flushes, or concurrent read/write locks in Write-Ahead Logging (WAL) or rollback journals.

### 5.2 Consistent Point-in-Time Online Backup (Python API)
The safe, non-destructive, and atomic method to create a consistent SQLite backup without stopping the server utilizes Python's built-in `sqlite3.Connection.backup()` API:

```python
"""
scripts/backup_database.py - Non-blocking atomic SQLite backup
"""
import os
import sqlite3
from datetime import datetime

def create_sqlite_backup(source_db="db.sqlite3", backup_dir="backups"):
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"medfind_db_{timestamp}.sqlite3")

    print(f"[*] Initiating atomic backup from '{source_db}'...")
    
    # Establish connection
    source_conn = sqlite3.connect(source_db)
    target_conn = sqlite3.connect(backup_file)

    # Perform online non-blocking backup with progress locking
    with target_conn:
        source_conn.backup(target_conn, pages=100)

    source_conn.close()
    target_conn.close()

    size_kb = os.path.getsize(backup_file) / 1024
    print(f"[+] Backup completed successfully: '{backup_file}' ({size_kb:.1f} KB)")
    return backup_file

if __name__ == "__main__":
    create_sqlite_backup()
```

### 5.3 Point-in-Time SQLite CLI Alternative
If the SQLite command-line tool is installed:
```bash
sqlite3 db.sqlite3 ".backup 'backups/db_backup_manual.sqlite3'"
```

---

## 6. Disaster Recovery & Rollback Runbook

If a critical failure occurs during any upcoming development phase:

1. **Reverting Code & Templates**:
   ```bash
   git reset --hard HEAD
   # Or checkout the previous checkpoint commit:
   git checkout main
   ```
2. **Restoring the Database**:
   - Stop the local development server (`CTRL+C`).
   - Replace `db.sqlite3` with the latest timestamped backup from `backups/`:
     ```bash
     copy backups\medfind_db_<timestamp>.sqlite3 db.sqlite3
     ```
   - Run system checks and verify integrity:
     ```bash
     python manage.py check
     python manage.py test
     ```
3. **Secret Security Guarantee**:
   - Actual passwords, API keys, or production secret values are **never** committed to Git or stored in plain-text backup logs.
