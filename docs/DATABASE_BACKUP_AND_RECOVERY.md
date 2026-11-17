# Database Backup & Disaster Recovery Guide
**MediFind – Phase 10: Production Deployment Preparation**

---

## 1. Overview

This document provides disaster recovery, scheduled backup, and manual restoration procedures for both the development SQLite database and the production managed PostgreSQL database.

---

## 2. Part A: Development Database (SQLite) Procedures

### 2.1 Manual SQLite Backup on Windows (PowerShell)

To create a timestamped backup copy of `db.sqlite3` without locking active reads:

```powershell
# Navigate to project root
cd c:\Users\yeshw\OneDrive\Desktop\medfind_project

# Create a timestamped backup file
$timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
Copy-Item db.sqlite3 "db_backup_$timestamp.sqlite3"

Write-Host "Backup successfully created: db_backup_$timestamp.sqlite3"
```

### 2.2 Complete SQL Dump (Logical Export)
To export the complete schema and all records as pure SQL statements:

```powershell
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 2 > datadump.json
```

### 2.3 Restore from Backup on Windows
To restore `db.sqlite3` from a previous backup:

```powershell
# 1. Stop local development server (Ctrl + C)
# 2. Replace current database with backup
Copy-Item "db_backup_20261117_154500.sqlite3" db.sqlite3 -Force

# 3. Verify database integrity
python manage.py check
```

---

## 3. Part B: Production Database (PostgreSQL on Render / Cloud)

### 3.1 Automated Cloud Backups (Render)
- On Render's managed PostgreSQL service, automated daily backups are generated and stored offsite.
- Retention:
  - Starter Plan (\$7/mo): 7 days of daily automated snapshots.
  - Standard Plan (\$20/mo): 30 days of point-in-time recovery (PITR).

### 3.2 Manual Remote PostgreSQL Export (`pg_dump`)
Run from your local terminal or administrative workstation:

```bash
# Export complete database into compressed binary archive
pg_dump "postgres://medifind_user:PASSWORD@HOST.oregon-postgres.render.com/medifind" -F c -b -v -f "medifind_prod_$(date +%Y%m%d).dump"
```

### 3.3 Manual Remote PostgreSQL Restore (`pg_restore`)
To restore an archive dump into a clean PostgreSQL database:

```bash
pg_restore -d "postgres://medifind_user:PASSWORD@HOST.oregon-postgres.render.com/medifind" --clean --no-owner "medifind_prod_20261117.dump"
```

---

## 4. Disaster Recovery Runbook

In the event of database corruption, accidental record deletion, or service failure:

```mermaid
flowchart TD
    A["Incident Detected\n(Data Corruption / Loss)"] --> B["Step 1: Put Application in Maintenance Mode\n(Block Incoming Writes)"]
    B --> C["Step 2: Inspect Database Status & Recent Logs"]
    C --> D["Step 3: Identify Latest Clean Backup\n(Render Snapshot / pg_dump file)"]
    D --> E["Step 4: Restore Backup to Fresh Database"]
    E --> F["Step 5: Run Schema Consistency Check\npython manage.py migrate --check"]
    F --> G["Step 6: Execute Sanity Tests\npython manage.py test tests.test_e2e_workflows"]
    G --> H["Step 7: Route Web Traffic & Disable Maintenance"]
```

1. **Isolate**: Set `ALLOWED_HOSTS` or pause web service in Render dashboard to prevent partial or corrupted writes.
2. **Verify**: Check the Render database metrics and determine the last known good transaction time.
3. **Restore**: Restore from the latest automated snapshot or uploaded `.dump` file.
4. **Validate**: Run `python manage.py check` and smoke test the customer/pharmacy search workflows.
5. **Resume**: Re-enable traffic and verify real-time monitoring logs.
