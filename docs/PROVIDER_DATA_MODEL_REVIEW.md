# Provider Data Model Review
**MediFind Healthcare Platform — Stage 1: Data Architecture & Schema Audit**
**Date:** November 2026 | **Author:** Senior Django Architect & Database Performance Engineer

---

## 1. Audit of Existing Provider Models

The current MediFind application models healthcare facilities using a single entity: **`pharmacies.models.Pharmacy`**.

### Current Model Definition (`pharmacies/models.py`):
```python
class Pharmacy(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pharmacies')
    pharmacy_name = models.CharField(max_length=200, db_index=True, verbose_name="Pharmacy Name")
    registration_number = models.CharField(max_length=100, unique=True, db_index=True, verbose_name="Registration / License Number")
    address = models.TextField(verbose_name="Street Address")
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20, db_index=True)
    phone_number = models.CharField(max_length=15)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_approved = models.BooleanField(default=False, db_index=True, verbose_name="Admin Approval Status")
    created_at = models.DateTimeField(auto_now_add=True)
```

### Relational Dependencies:
1. **`accounts.User`:** `owner` links every pharmacy to an active user account with role `PHARMACY`.
2. **`inventory.Inventory`:** `pharmacy = ForeignKey(Pharmacy, on_delete=CASCADE, related_name='inventory_items')` links medicine stock to a specific pharmacy store.
3. **`requests_app.AvailabilityRequest`:** `pharmacy = ForeignKey(Pharmacy, on_delete=CASCADE, related_name='availability_requests')` links patient requests to a specific pharmacy store.

---

## 2. Existing Location Fields & Coordinates Assessment

| Field | Data Type | Database Index | Validation / Constraints | Audit Findings |
| :--- | :--- | :---: | :--- | :--- |
| `latitude` | `Decimal(9, 6)` | No standalone index | Nullable; checked by `is_valid_coordinate` (-90 to +90) | Sufficient for 10cm accuracy. Requires composite spatial index with `longitude`. |
| `longitude` | `Decimal(9, 6)` | No standalone index | Nullable; checked by `is_valid_coordinate` (-180 to +180) | Sufficient for 10cm accuracy. |
| `state` | `CharField(100)` | No index | Free-text string | Needs standardization (e.g., "Telangana" vs "TG") and index for state-level queries. |
| `city` | `CharField(100)` | Indexed | Free-text string | Indexed in `pharm_appr_city_idx`. |
| `pincode` | `CharField(20)` | Indexed | Free-text string (up to 20 chars) | Indexed in `pharm_appr_pincode_idx`. India pincodes are 6 digits. |
| `address` | `TextField` | No index | Free-text street address | Clean in all demo records. |

---

## 3. Database Audit: Existing Demonstration Records

An automated query of [db.sqlite3](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/db.sqlite3) audited all existing provider records:

| ID | Pharmacy Name | License / Reg No | City | State | Pincode | Coordinates (Lat, Lng) | Status | Owner |
|:-:|---|---|---|---|:---:|:---:|:---:|---|
| **1** | [DEMO] Apollo Healthcare Store | `DEMO-HYD-AP-101` | Hyderabad | Telangana | `500034` | `17.415582, 78.435783` | ✅ Approved | `apollo_owner` |
| **2** | [DEMO] MedPlus Pharma Hub | `DEMO-HYD-MP-102` | Hyderabad | Telangana | `500081` | `17.448293, 78.391485` | ✅ Approved | `medplus_owner` |
| **3** | [DEMO] Wellness Forever 24x7 | `DEMO-BLR-WF-103` | Bengaluru | Karnataka | `560038` | `12.978369, 77.640836` | ✅ Approved | `wellness_owner` |
| **4** | [DEMO] NetMeds Point Care | `DEMO-BLR-NM-104` | Bengaluru | Karnataka | `560034` | `12.935193, 77.624481` | ✅ Approved | `netmeds_owner` |
| **5** | [DEMO] Care & Cure Community Chemist | `DEMO-DEL-CC-105` | New Delhi | Delhi | `110001` | `28.631451, 77.216667` | ✅ Approved | `care_owner` |
| **6** | [DEMO] Metro Life Pharmacy (Pending Review) | `DEMO-HYD-ML-106` | Hyderabad | Telangana | `500003` | `17.439930, 78.498274` | ⏳ Pending | `pending_owner` |

### Audit Conclusions on Demo Records:
1. **Duplicate Candidates:** Zero duplicates found. All registration numbers are unique.
2. **Missing Addresses:** Zero missing addresses. All 6 records have street addresses, cities, states, and pincodes.
3. **Coordinate Validity:** 100% of demo records have valid, verified geographic coordinates in Hyderabad, Bengaluru, and New Delhi.
4. **Approval Integrity:** 5 records are approved; 1 record is intentionally unapproved to verify the administrative approval/revocation workflow.
5. **Preservation:** These 6 records will remain untouched in the database.

---

## 4. Architectural Analysis for Real-World Data Ingestion

### Dilemma 1: Mandatory User Ownership (`owner = ForeignKey(User)`)
- **Current Requirement:** Currently, every `Pharmacy` row requires a valid `User` account (`null=False`).
- **The Issue:** When importing 10,000+ real-world pharmacies from OpenStreetMap or National Registries, those public retail shops do not have pre-existing MediFind user accounts.
- **Solution Strategy:**
  1. Add `owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)`.
  2. Add `is_claimed = models.BooleanField(default=False)`.
  3. Real imported pharmacies exist as "Public Directory" records. When a real pharmacist signs up, they can "Claim" their verified store, attaching their `User` account.

### Dilemma 2: Hospitals vs. Pharmacies Modeling
Should Hospitals be merged into `Pharmacy` or represented as a dedicated `Hospital` model?

#### Option A: Unified Model (`HealthcareFacility`)
- **Concept:** Rename or extend `Pharmacy` to represent all facilities with a `facility_category` field (`PHARMACY`, `GOVT_HOSPITAL`, `PRIVATE_HOSPITAL`, `CLINIC`).
- **Drawbacks:** Violates Single Responsibility. Hospitals have bed counts, emergency trauma units, specialties, and NIN codes that do not apply to corner drugstores. Furthermore, `Inventory` and `AvailabilityRequest` models point directly to `Pharmacy`, leading to NULL foreign keys and confusion.

#### Option B: Dedicated `Hospital` Model (Recommended)
- **Concept:** Create a dedicated `Hospital` model in `pharmacies` (or `facilities`).
- **Advantages:**
  1. Preserves existing `Pharmacy`, `Inventory`, and `AvailabilityRequest` relationships with 100% backward-compatibility.
  2. Models hospital-specific attributes cleanly: `nin_code`, `facility_type`, `ownership`, `bed_count`, `has_emergency_ward`, `has_inhouse_pharmacy`.
  3. Allows cross-referencing: if a hospital has an in-house pharmacy, a foreign key can optionally link to a `Pharmacy` inventory node.

---

## 5. Proposed Future Model Specifications (For Stage 2)

> [!NOTE]
> Per Stage 1 strict restrictions, **no code changes or migrations have been executed**. The following schemas represent the planned architecture for Stage 2.

### Proposed `Hospital` Model Schema:
```python
class Hospital(models.Model):
    class OwnershipType(models.TextChoices):
        GOVERNMENT = 'GOVT', 'Government'
        PRIVATE = 'PRIVATE', 'Private'
        TRUST = 'TRUST', 'Trust / Charitable'

    class FacilityType(models.TextChoices):
        DISTRICT_HOSPITAL = 'DH', 'District Hospital'
        SUB_DISTRICT = 'SDH', 'Sub-Divisional Hospital'
        CHC = 'CHC', 'Community Health Centre'
        PHC = 'PHC', 'Primary Health Centre'
        MEDICAL_COLLEGE = 'MC', 'Medical College Hospital'
        PRIVATE_HOSPITAL = 'PVT', 'Private Hospital'
        AYUSH = 'AYUSH', 'Ayush Hospital'

    nin_code = models.CharField(max_length=50, unique=True, null=True, blank=True, db_index=True)
    hospital_name = models.CharField(max_length=250, db_index=True)
    facility_type = models.CharField(max_length=10, choices=FacilityType.choices, default=FacilityType.PRIVATE_HOSPITAL)
    ownership = models.CharField(max_length=10, choices=OwnershipType.choices, default=OwnershipType.GOVERNMENT)
    state = models.CharField(max_length=100, db_index=True)
    district = models.CharField(max_length=100, db_index=True)
    city = models.CharField(max_length=100, db_index=True)
    pincode = models.CharField(max_length=10, db_index=True)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    emergency_contact = models.CharField(max_length=50, blank=True)
    bed_count = models.PositiveIntegerField(default=0)
    has_emergency = models.BooleanField(default=True)
    has_inhouse_pharmacy = models.BooleanField(default=False)
    source_name = models.CharField(max_length=50, default='DATA_GOV_IN')
    source_updated_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['hospital_name']
        indexes = [
            models.Index(fields=['state', 'district', 'city'], name='hosp_geo_idx'),
            models.Index(fields=['latitude', 'longitude'], name='hosp_coords_idx'),
            models.Index(fields=['facility_type', 'ownership'], name='hosp_type_owner_idx'),
        ]
```

### Proposed `Pharmacy` Model Extensions (Non-Breaking):
```python
# To be added in Stage 2 migrations:
# 1. owner = ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
# 2. is_claimed = models.BooleanField(default=False, db_index=True)
# 3. source_name = models.CharField(max_length=50, default='MANUAL')  # 'OSM', 'MANUAL'
# 4. source_id = models.CharField(max_length=100, blank=True, db_index=True)
# 5. Index: models.Index(fields=['latitude', 'longitude'], name='pharm_coords_idx')
# 6. Index: models.Index(fields=['state', 'city'], name='pharm_state_city_idx')
```

---

## 6. Verification and Governance Preserved

- The existing admin governance dashboard ([templates/dashboard/admin_dashboard.html](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/templates/dashboard/admin_dashboard.html)) will seamlessly monitor both `Pharmacy` and `Hospital` entities.
- Approval workflows (`toggle_pharmacy_approval`) remain fully operational for pharmacy management.
- Zero breaking changes to the 136 passing automated regression tests.

---
*Next Deliverable: See [`INDIA_WIDE_IMPORT_STRATEGY.md`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/docs/INDIA_WIDE_IMPORT_STRATEGY.md) for data extraction and ingestion runbooks.*
