# MEDIFIND — ADVANCED GEOSEARCH REPORT

**Report Date:** November 17, 2026  
**Auditor & Architect:** Senior Django Architect & GIS Engineer  
**Document Code:** MF-DOC-ST5-GEOSEARCH  
**System Component:** `pharmacies/services.py` (`discover_healthcare_providers`)  

---

## 1. Executive Summary

The MediFind discovery engine provides a unified, multi-dimensional search service capable of querying, filtering, and distance-ranking healthcare facilities across India.

In Stage 5, the geosearch engine was enhanced to support:
1. Strict inventory-backed pharmacy availability filtering.
2. Expanded proximity radius thresholds ($5\text{ km}$ to $100\text{ km}$).
3. Verification tier filtering (`approved`, `all`, `pending`).
4. Facility category classification (`HOSPITAL`, `PHARMACY`, `ALL`).
5. Multi-level administrative hierarchy filtering (State, District, City, Pincode).
6. Robust coordinate validation, error tolerance, and graceful omission of unmapped facilities.

---

## 2. Geosearch Service Architecture

The core discovery service is centralized in `discover_healthcare_providers()` within `pharmacies/services.py`:

```
Input Parameters:
  - user_lat, user_lng (Optional[float])
  - radius_km (Optional[float/str]: '5', '10', '15', '25', '50', '100')
  - city, district, state, pincode (Optional[str])
  - search_query (Optional[str])
  - provider_type ('ALL', 'HOSPITAL', 'PHARMACY')
  - verification_status ('approved', 'all', 'pending')
  - availability ('all', 'in_stock')
  - sort_by ('distance', 'name', 'newest')
  - page, per_page (int)
       │
       ▼
[Database QuerySet Filtering via Django ORM]
  1. Base: Pharmacy.objects.filter(is_active=True)
  2. Provider Type: Hospital vs Pharmacy
  3. Verification Filter: is_approved == True / False / Both
  4. Medicine Availability: Subquery filter against Inventory table
  5. Text Search: Q() across name, address, reg number, city, district, state
  6. Administrative Filter: state, district, city, pincode
       │
       ▼
[In-Memory Geospatial Ranking & Proximity Filter]
  - Validate Coordinates via is_valid_coordinate()
  - Haversine Distance: d = R * 2 * atan2(√a, √(1-a))
  - Radius Cutoff Filter: d <= radius_km
  - Multi-Key Sorting: (distance_km is None, distance_km, name)
       │
       ▼
[Leaflet Map Pin Serialization & Pagination]
  - Map Pins Payload (Filtered to valid coordinate facilities)
  - Page Object (Paginator: 9 items per page)
  - User Coordinates Dict & Summary Metadata
```

---

## 3. Detailed Filter Verification

### 3.1 Facility Category Filter
- **`ALL`**: Evaluates all active healthcare institutions (tertiary hospitals, clinics, retail pharmacies).
- **`HOSPITAL`**: Strictly filters to facilities registered under `Pharmacy.ProviderType.HOSPITAL`.
- **`PHARMACY`**: Strictly filters to facilities registered under `Pharmacy.ProviderType.PHARMACY`.

### 3.2 Verification Status Filter
- **`approved`**: Exclusively returns verified partner facilities (`is_approved=True`). This is the default when searching for pharmacies to prevent misleading consumers.
- **`all`**: Returns both verified partners and official public directory listings (`is_approved=False`), with transparent badge indicators.
- **`pending`**: Returns unapproved facilities awaiting administrative review.

### 3.3 Medicine Availability Filter (Strict Inventory Invariant)
To prevent deceptive medicine stock claims:
- When `availability='in_stock'`, the engine runs an optimized subquery:
  ```python
  active_stock_pharmacy_ids = set(
      Inventory.objects.filter(
          availability_status__in=['IN_STOCK', 'LOW_STOCK'],
          quantity__gt=0
      ).values_list('pharmacy_id', flat=True).distinct()
  )
  qs = qs.filter(id__in=active_stock_pharmacy_ids, provider_type=Pharmacy.ProviderType.PHARMACY)
  ```
- **Validation Outcome**:
  - Hospitals are excluded from the retail medicine stock filter.
  - Directory pharmacies imported from OpenStreetMap or other directories with no MediFind inventory are **never** returned under this filter.
  - Verified in automated test `test_05_medicine_availability_filter_strictly_inventory_based` (PASSED).

### 3.4 Proximity Radius Filtering
Radius filtering operates seamlessly when user GPS coordinates are provided:
- Valid options: `5 km`, `10 km`, `15 km`, `25 km`, `50 km`, `100 km`.
- If user coordinates are absent, the radius filter is safely bypassed without throwing an exception, allowing fallback to manual city/state/pincode filtering.

---

## 4. Distance Calculation & Scientific Precision

### 4.1 The Haversine Formula Implementation
MediFind implements the great-circle Haversine formula assuming a spherical Earth with volumetric mean radius $R = 6,371.0\text{ km}$:

$$\Delta\phi = \phi_2 - \phi_1, \quad \Delta\lambda = \lambda_2 - \lambda_1$$

$$a = \sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)$$

$$c = 2 \cdot \text{atan2}\left(\sqrt{a}, \sqrt{1-a}\right)$$

$$d = R \cdot c$$

To protect against floating-point precision domain errors near antipodes, $a$ is clamped to $[0.0, 1.0]$.

### 4.2 Handling Missing or Invalid Coordinates
1. `is_valid_coordinate(lat, lon)` validates:
   - Values are non-null and convertible to float.
   - Values are finite (rejecting `NaN` and `Inf`).
   - Latitude in $[-90.0^\circ, 90.0^\circ]$ and Longitude in $[-180.0^\circ, 180.0^\circ]$.
2. Facilities with missing or invalid coordinates:
   - Have `p.distance_km = None`.
   - Are excluded from Leaflet `map_pins` array.
   - Are sorted at the end of distance-sorted lists.
   - Display a fallback "Coordinates not registered" label in card views without throwing 500 errors.
