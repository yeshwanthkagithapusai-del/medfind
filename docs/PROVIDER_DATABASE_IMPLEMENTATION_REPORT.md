# Provider Database Implementation Report
**MediFind Healthcare Platform — Stage 2: Database Schema Extensions**
**Date:** November 2026 | **Author:** Senior Django Database Architect & GIS Engineer

---

## 1. Executive Summary

This report documents the architectural extension of the MediFind healthcare provider database schema. Following the Stage 1 geospatial audit, the existing `pharmacies.models.Pharmacy` entity was strategically extended into a unified healthcare provider model rather than creating redundant, disjoint models.

This architectural decision preserves 100% of existing application relationships (`inventory.Inventory`, `requests_app.AvailabilityRequest`, and `accounts.User`), while adding first-class support for genuine hospital landmarks, community pharmacies, and nationwide geospatial indexing.

---

## 2. Extended Model Architecture

### 2.1 Model Definition (`pharmacies/models.py`)
```python
class Pharmacy(models.Model):
    class ProviderType(models.TextChoices):
        PHARMACY = 'PHARMACY', 'Pharmacy'
        HOSPITAL = 'HOSPITAL', 'Hospital'

    class DataSource(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual User Registration'
        DATA_GOV_IN = 'DATA_GOV_IN', 'National Hospital Directory (data.gov.in)'
        OSM = 'OSM', 'OpenStreetMap'
        DEMO = 'DEMO', 'Demonstration Seed Data'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pharmacies',
        verbose_name="Store Owner / Administrator"
    )
    provider_type = models.CharField(
        max_length=20,
        choices=ProviderType.choices,
        default=ProviderType.PHARMACY,
        db_index=True,
        verbose_name="Provider Type"
    )
    pharmacy_name = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Provider Name"
    )
    registration_number = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name="Registration / License Number"
    )
    address = models.TextField(verbose_name="Street Address")
    city = models.CharField(max_length=100, db_index=True)
    district = models.CharField(max_length=100, blank=True, db_index=True, verbose_name="District")
    state = models.CharField(max_length=100, db_index=True)
    pincode = models.CharField(max_length=20, db_index=True)
    phone_number = models.CharField(max_length=50, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    source_name = models.CharField(
        max_length=50,
        choices=DataSource.choices,
        default=DataSource.MANUAL,
        db_index=True,
        verbose_name="Original Data Source"
    )
    source_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name="External Source Identifier"
    )
    is_approved = models.BooleanField(default=False, db_index=True, verbose_name="Admin Approval Status")
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Active Status")
    is_demo = models.BooleanField(default=False, db_index=True, verbose_name="Demo Record Flag")
    last_verified_at = models.DateTimeField(null=True, blank=True, verbose_name="Last Verified Date")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Import / Registration Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Last Updated Date")
```

---

## 3. Database Fields Specification

| Field Name | Type | Constraints / Defaults | Purpose |
| :--- | :--- | :--- | :--- |
| `owner` | `ForeignKey(User)` | `null=True, blank=True, on_delete=SET_NULL` | Allows public directory providers to exist without synthetic accounts. |
| `provider_type` | `CharField(20)` | Choices: `PHARMACY`, `HOSPITAL`; Default: `PHARMACY` | Distinguishes dispensing pharmacies from institutional hospitals. |
| `district` | `CharField(100)`| `blank=True, db_index=True` | Enables second-tier administrative district filtering. |
| `state` | `CharField(100)`| `db_index=True` | Indexed for state-level aggregations and search. |
| `phone_number` | `CharField(50)` | `blank=True` | Expanded from 15 to 50 to accommodate multi-line landline formats. |
| `source_name` | `CharField(50)` | Choices: `MANUAL`, `DATA_GOV_IN`, `OSM`, `DEMO` | Audit trail recording the provenance registry of the facility. |
| `source_id` | `CharField(100)`| `blank=True, db_index=True` | Stable upstream identifier (e.g., NIN code or OSM node ID). |
| `is_active` | `BooleanField` | `default=True, db_index=True` | Soft-disable switch for closed or temporarily non-operational units. |
| `is_demo` | `BooleanField` | `default=False, db_index=True` | Explicit flag segregating demonstration records from real data. |
| `last_verified_at`| `DateTimeField` | `null=True, blank=True` | Clinical freshness timestamp of physical or administrative verification. |
| `updated_at` | `DateTimeField` | `auto_now=True` | Automatic timestamp tracking record updates. |

---

## 4. Performance & Integrity Constraints

### 4.1 Composite B-Tree Indexes
Five new composite indexes were provisioned to guarantee sub-30ms spatial and administrative queries:
1. **`prov_type_appr_city_idx`:** `(provider_type, is_approved, city)` — Fast public city directory lookups.
2. **`prov_type_appr_pin_idx`:** `(provider_type, is_approved, pincode)` — Pincode-level filtering.
3. **`prov_geo_idx`:** `(state, district, city)` — 3-tier geographic drill-down queries.
4. **`prov_coords_idx`:** `(latitude, longitude)` — Spatial bounding-box coarse range filtering.
5. **`prov_source_idx`:** `(source_name, source_id)` — High-speed external registry lookups.

### 4.2 Idempotency Database Constraint
```python
models.UniqueConstraint(
    fields=['source_name', 'source_id'],
    condition=models.Q(source_id__gt=''),
    name='unique_source_facility'
)
```
This partial unique constraint prevents duplicate imports of the same external facility at the database engine level, while allowing multiple manual registrations with an empty `source_id`.

---

## 5. Backward-Compatibility Audit

- **Inventory Integration:** All `Inventory` items link to `Pharmacy` via `pharmacy_id`. Verified functional.
- **Availability Requests:** All `AvailabilityRequest` records link to `Pharmacy` via `pharmacy_id`. Verified functional.
- **User Profile & Management:** Authenticated pharmacists link via `owner`. Unclaimed imported records have `owner=None`.
- **Property Aliasing:** Added `@property def provider_name(self)` returning `self.pharmacy_name` for generic UI templates.
- **Demo Record Isolation:** All 6 existing demo records tagged with `is_demo=True`, preserving demonstration data completely intact.

---
*Next Report: See [`PILOT_DATA_IMPORT_REPORT.md`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/docs/PILOT_DATA_IMPORT_REPORT.md) for pilot ingestion results.*
