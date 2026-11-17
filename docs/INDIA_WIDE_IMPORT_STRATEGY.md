# India-Wide Healthcare Data Import Strategy
**MediFind Healthcare Platform — Stage 1: Data Pipeline & Ingestion Specification**
**Date:** November 2026 | **Author:** Senior Data Integration Specialist & Django Backend Engineer

---

## 1. Executive Summary

This document specifies the Extract, Transform, and Load (ETL) data pipelines required to ingest real healthcare and pharmacy locations across India into MediFind. The strategy guarantees zero downtime, idempotency, data deduplication, strict validation of coordinates against Indian territorial boundaries, and complete rollback safety.

---

## 2. Ingestion Pipeline Architecture

```
+---------------------------------------------------------------------------------------------+
|                                DATA EXTRACTION STAGE                                        |
|                                                                                             |
|   +------------------------------------+       +----------------------------------------+   |
|   | Source 1: data.gov.in (Hospitals)  |       | Source 2: OpenStreetMap (Pharmacies)   |   |
|   | - Official CSV / JSON Exports      |       | - Overpass API JSON by State           |   |
|   | - GODL-India Open Data             |       | - Geofabrik .osm.pbf Extracts          |   |
|   +-----------------+------------------+       +-------------------+--------------------+   |
+---------------------|----------------------------------------------|------------------------+
                      |                                              |
                      v                                              v
+---------------------------------------------------------------------------------------------+
|                              DATA TRANSFORMATION & CLEANING                                 |
|                                                                                             |
|   1. Spatial Boundary Validation:                                                           |
|      - Verify: 6.5° N <= Latitude <= 37.5° N                                                |
|      - Verify: 68.0° E <= Longitude <= 97.5° E                                              |
|      - Discard (0,0), Null, NaN, or non-Indian coordinates                                  |
|                                                                                             |
|   2. Administrative Normalization:                                                          |
|      - Standardize State Names (e.g., "TG" -> "Telangana", "NCT of Delhi" -> "Delhi")       |
|      - Standardize 6-Digit Pincodes (strip spaces, regex: ^[1-9][0-9]{5}$)                  |
|      - Title-case facility and street names                                                 |
|                                                                                             |
|   3. Deduplication Engine:                                                                  |
|      - Hospitals: Natural key = `nin_code` (National Identification Number)                 |
|      - Pharmacies: Fuzzy deduplication = composite of `[name, pincode, rounded_lat_lng]`    |
+---------------------------------------------------------------------------------------------+
                      |
                      v
+---------------------------------------------------------------------------------------------+
|                                DATABASE LOADING STAGE (ETL)                                 |
|                                                                                             |
|   - Django Management Command Architecture with `--dry-run` flag                            |
|   - Atomic Batch Transactions (`transaction.atomic()` in chunks of 500 records)             |
|   - Idempotent Ingestion (`update_or_create` / `bulk_create(ignore_conflicts=True)`)         |
|   - Preserves all 6 existing demo records and existing database relationships               |
+---------------------------------------------------------------------------------------------+
```

---

## 3. Data Cleansing & Validation Rules

### 3.1 Spatial Coordinate Validation (India WGS84 Bounding Box)
India's sovereign territory lies within the following geographic bounding box:
- **Latitude Range:** $6.500000^\circ\text{ N}$ to $37.500000^\circ\text{ N}$
- **Longitude Range:** $68.000000^\circ\text{ E}$ to $97.500000^\circ\text{ E}$

Any record where coordinates fall outside this polygon, or where latitude/longitude are transposed (a common error in crowdsourced data where Lat is entered as 78° and Lng as 17°), must be flagged and corrected or set to `NULL` to avoid corrupting map center calculations.

```python
def validate_indian_coordinates(lat, lng):
    if lat is None or lng is None:
        return False, None, None
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (ValueError, TypeError):
        return False, None, None

    # Check for transposed coordinates (e.g. Lat ~78, Lng ~17)
    if (6.5 <= lng_f <= 37.5) and (68.0 <= lat_f <= 97.5):
        lat_f, lng_f = lng_f, lat_f  # Transpose correction

    # Strict territorial boundary check
    if (6.5 <= lat_f <= 37.5) and (68.0 <= lng_f <= 97.5):
        return True, round(lat_f, 6), round(lng_f, 6)
    return False, None, None
```

### 3.2 Postal Pincode Normalization
- Indian Postal Pincodes are exactly 6 digits, beginning with digits 1 through 9.
- Values must be stripped of trailing spaces, hyphens, and non-numeric characters:
  ```python
  import re
  def clean_pincode(val):
      digits = re.sub(r'\D', '', str(val or ''))
      if len(digits) == 6 and digits[0] != '0':
          return digits
      return ''
  ```

### 3.3 State & District Canonical Mapping
State names from disparate sources will be resolved against an official canonical lookup dictionary to prevent fragmented filter dropdowns:
- `"TG"` / `"Telengana"` $\rightarrow$ `"Telangana"`
- `"NCT of Delhi"` / `"New Delhi"` $\rightarrow$ `"Delhi"`
- `"KA"` / `"Mysore State"` $\rightarrow$ `"Karnataka"`
- `"MH"` / `"Bombay State"` $\rightarrow$ `"Maharashtra"`

---

## 4. Pipeline A: National Hospital Directory Ingestion Runbook

### Source Specification:
- **Format:** CSV / JSON export from `data.gov.in`.
- **Target Model:** Proposed `Hospital` model.
- **Natural Key:** `nin_code` (Unique National Identification Number).

### Step-by-Step Execution Plan:
1. **Download:** Download latest snapshot file `national_hospitals_latest.csv` to `data/imports/`.
2. **Pre-flight Dry Run:**
   ```powershell
   python manage.py import_hospitals --file data/imports/national_hospitals_latest.csv --dry-run
   ```
   Outputs total records scanned, valid coordinates, invalid coordinates, and duplicate counts without writing to the database.
3. **Execution with Batching:**
   ```powershell
   python manage.py import_hospitals --file data/imports/national_hospitals_latest.csv --batch-size 500
   ```
4. **Idempotency Guarantee:**
   Uses `Hospital.objects.update_or_create(nin_code=row['nin'], defaults={...})`. Re-running the script updates modified fields without creating duplicate rows.

---

## 5. Pipeline B: OpenStreetMap (OSM) Pharmacy Ingestion Runbook

### Source Specification:
- **Interface:** Overpass API or Geofabrik `.osm.pbf` extract.
- **Target Model:** Existing `Pharmacy` model (with `owner=None` and `source_name='OSM'`).
- **Target Tags:** `[amenity=pharmacy]`, `[healthcare=pharmacy]`.

### Query Sharding Strategy:
To avoid Overpass API timeouts (25-second limit), queries are executed **State-by-State** or **Metro-by-Metro**:

```overpass
[out:json][timeout:60];
area["name"="Telangana"]["admin_level"="4"]->.state;
(
  node["amenity"="pharmacy"](area.state);
  way["amenity"="pharmacy"](area.state);
);
out center tags;
```

### Transformation & Matching:
- **Name:** Extract `name` tag. If missing, default to `"Medical & General Store"`.
- **Registration Number:** Generate synthetic deterministic identifier: `OSM-NODE-<id>` to prevent collisions with official drug retail licenses.
- **Approval Status:** Default to `is_approved=True` for verified public directory visibility, or `False` pending administrative verification.
- **Deduplication:** Check proximity to existing pharmacies within 30 meters sharing similar names to prevent double-counting.

---

## 6. Phased Rollout Schedule (Safe Staging)

To avoid overloading development environments or ballooning SQLite file size, the rollout should be executed in controlled regional tiers:

| Phase | Geographic Target | Estimated Records | Purpose |
| :---: | :--- | :---: | :--- |
| **Stage 1 (Current)** | Audit & Planning Only | **0 (Zero)** | Verification, risk assessment, architectural design. |
| **Stage 2A** | Pilot Metro: Hyderabad (Telangana) | ~800 Facilities | Initial pilot verification of bounding box queries & UI clustering. |
| **Stage 2B** | South Zone (Bengaluru, Chennai, Hyderabad) | ~5,000 Facilities | Multi-state drill-down testing and performance benchmarking. |
| **Stage 2C** | Pan-India Metros (Delhi NCR, Mumbai, Kolkata) | ~15,000 Facilities | Scale validation on PostgreSQL production environment. |
| **Stage 2D** | Full National Import (All 28 States & 8 UTs) | ~60,000+ Facilities | Nationwide production operation. |

---

## 7. Rollback & Disaster Recovery Runbook

1. **Pre-Import Backup:**
   Execute an automated timestamped backup of the database before running any import batch:
   ```powershell
   python -c "import shutil, datetime; shutil.copy2('db.sqlite3', f'db.sqlite3.pre_import_{datetime.datetime.now().strftime(\"%Y%m%d_%H%M%S\")}')"
   ```
2. **Atomic Rollback:**
   Each batch is wrapped in `with transaction.atomic():`. Any database exception triggers an immediate transaction rollback, leaving the database uncorrupted.
3. **Source Tag Purge Command:**
   A dedicated purge switch allows removing imported records without affecting demo or user-created records:
   ```powershell
   python manage.py purge_imported_facilities --source OSM --dry-run
   ```

---
*Next Deliverable: See [`LOCATION_DATA_RISK_REPORT.md`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/docs/LOCATION_DATA_RISK_REPORT.md) for risk mitigations.*
