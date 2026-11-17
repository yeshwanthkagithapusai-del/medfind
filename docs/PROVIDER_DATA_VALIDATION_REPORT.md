# Provider Data Validation Report
**MediFind Healthcare Platform — Stage 2: Data Cleansing & Validation Engine**
**Date:** November 2026 | **Author:** Senior QA Engineer & GIS Data Specialist

---

## 1. Executive Summary

This report documents the validation engine implemented in `pharmacies.importers` to ensure that only authentic, clean, geocoded healthcare data within Indian sovereign territory is permitted into the MediFind database.

---

## 2. Validation Engine Rules & Architecture

### 2.1 Geospatial Boundary Validation (`validate_indian_coordinates`)
All coordinates are strictly validated against India's WGS84 geographic bounding box:
- **Latitude Bounds:** $[6.500000^\circ\text{ N}, 37.500000^\circ\text{ N}]$
- **Longitude Bounds:** $[68.000000^\circ\text{ E}, 97.500000^\circ\text{ E}]$

#### Transposition Detection & Auto-Correction:
If a record provides swapped coordinates (e.g. Latitude ~78.48, Longitude ~17.38 for Hyderabad), the validator detects that `68.0 <= lat <= 97.5` and `6.5 <= lng <= 37.5`, logs a warning, and swaps the values back to their correct geographic order.

#### Rejection Conditions:
- `lat` or `lng` is `None` or empty.
- Coordinates outside India bounds (e.g., European, American, or oceanic coordinates).
- Non-numeric strings, `NaN`, or `Inf`.

### 2.2 Pincode Cleansing (`clean_indian_pincode`)
- Strips whitespace, hyphens, and non-digit characters.
- Requires exactly 6 digits.
- Rejects pincodes starting with `0` (invalid in the Indian Department of Posts system).

### 2.3 Provider Payload Integrity (`validate_provider_payload`)
- **Name:** Minimum 3 characters.
- **Street Address:** Minimum 5 characters.
- **City & State:** Mandatory non-empty strings.
- **Provider Type:** Restricted to `HOSPITAL` or `PHARMACY`.
- **Data Source:** Restricted to `DATA_GOV_IN`, `OSM`, `MANUAL`, `DEMO`.
- **Default Approval:** Enforces `is_approved=False` on all imported records until administrator vetting.

---

## 3. Validation Accounting & Test Results

```
========================================================================================
                               VALIDATION TEST ACCOUNTING
========================================================================================
Total Pilot Records Evaluated       : 29
  ├── Genuine Hospital Records     : 15 (data.gov.in) -> 100% VALIDATED & IMPORTED
  ├── Genuine Pharmacy Records     : 12 (OpenStreetMap) -> 100% VALIDATED & IMPORTED
  └── Intentional Test Records     : 2
        ├── Out-of-Bounds Test     : 1 (London UK: 51.5074, -0.1278) -> REJECTED (Expected)
        └── Missing Address Test   : 1 (Address: '') -> REJECTED (Expected)

Duplicate Detection Test (Re-run)  : 27 / 27 Skipped as Duplicates (100% Idempotent)
Database Integrity Violations      : 0
========================================================================================
```

---

## 4. Test Suite Execution Summary

The dedicated test suite [`tests/test_provider_extensions.py`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/tests/test_provider_extensions.py) was executed alongside platform regression suites:

```powershell
python manage.py test tests.test_provider_extensions
```
**Result:**
```
Ran 13 tests in 4.137s
OK
System check identified no issues (0 silenced).
```

### Coverage Breakdown:
1. `test_provider_creation_hospital` — Validates hospital instantiation with source tracking.
2. `test_provider_creation_pharmacy_with_owner` — Validates pharmacy owner account binding.
3. `test_provider_creation_unclaimed_public_facility` — Validates public facility with `owner=None`.
4. `test_source_identifier_uniqueness` — Validates database `UniqueConstraint` on source ID.
5. `test_valid_indian_coordinates` — Validates correct parsing of Indian geographic points.
6. `test_coordinate_transposition_correction` — Validates automatic swap of transposed Lat/Lng.
7. `test_out_of_bounds_coordinates_rejection` — Validates rejection of non-Indian coordinates.
8. `test_clean_indian_pincode` — Validates 6-digit postal code regex normalization.
9. `test_validate_provider_payload_rejections` — Validates rejection of empty/invalid fields.
10. `test_import_provider_records_success_and_deduplication` — Validates importer idempotency.
11. `test_import_provider_records_failure_handling` — Validates resilient batch failure handling.
12. `test_inventory_creation_and_workflow` — Validates existing Inventory foreign key regression.
13. `test_customer_availability_request_workflow` — Validates existing Request foreign key regression.

---
*End of Stage 2 Documentation Deliverables.*
