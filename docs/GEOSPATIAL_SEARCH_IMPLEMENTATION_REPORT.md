# Geospatial Search Implementation Report
**MediFind Healthcare Platform — Stage 3: Backend Geospatial Search Services**
**Date:** November 2026 | **Author:** Senior Django Backend Architect & GIS Engineer

---

## 1. Executive Summary

This report documents the backend geospatial search service layer implemented in `pharmacies.services`. The new architecture unifies hospital discovery, pharmacy discovery, administrative spatial filtering (State, District, City, Pincode), spherical Haversine distance calculations, and Leaflet pin serialization into a high-performance, reusable service.

---

## 2. Core Service Architecture (`pharmacies/services.py`)

### 2.1 `discover_healthcare_providers(...)`
The primary discovery engine coordinates query compilation, distance calculation, radius cutoff, and pagination:

```python
def discover_healthcare_providers(
    user_lat: Optional[Any] = None,
    user_lng: Optional[Any] = None,
    radius_km: Optional[Any] = None,
    city: str = '',
    district: str = '',
    state: str = '',
    pincode: str = '',
    search_query: str = '',
    provider_type: str = 'ALL',
    verification_status: str = 'approved',
    only_approved: bool = False,
    sort_by: str = 'distance',
    page: int = 1,
    per_page: int = 9,
) -> Tuple[Page, bool, List[Dict[str, Any]], int, Optional[Dict[str, float]]]:
```

#### Query Execution Pipeline:
1. **Active Filter:** `qs = Pharmacy.objects.filter(is_active=True)` ensures inactive/closed facilities are excluded.
2. **Provider Type:** When `provider_type` is `'HOSPITAL'` or `'PHARMACY'`, applies exact index filter on `provider_type`. When `'ALL'`, queries both categories.
3. **Verification Filter:**
   - If `only_approved=True` or `verification_status == 'approved'`: filters strictly by `is_approved=True`.
   - If `verification_status == 'pending'`: filters by `is_approved=False`.
   - If `verification_status == 'all'`: returns both verified and directory facilities with distinct verification flags.
4. **Keyword Filter:** Case-insensitive `Q` filter across `pharmacy_name`, `address`, `registration_number`, `city`, `district`, `state`.
5. **Administrative Hierarchy:** Exact or substring filters on `state`, `district`, `city`, `pincode`.
6. **Haversine Distance Math:** Executed if `is_valid_coordinate(user_lat, user_lng)` is True.
7. **Radius Boundary Filter:** Excludes facilities where `distance_km > radius_km`.
8. **Distance Sorting:** Nulls placed last; nearest facilities sorted first.
9. **Map Pin Serialization:** Serializes facility ID, name, provider type, distinct marker color, coordinates, phone, and distance for Leaflet.js.
10. **Pagination:** Paginates results to 9 items per page (3x3 grid) for optimal desktop and mobile rendering.

---

## 3. Backward Compatibility & Regressions

### 3.1 `discover_nearby_pharmacies(...)`
To guarantee zero breakage across pre-existing views and test suites, `discover_nearby_pharmacies` is maintained as a clean wrapper:
```python
def discover_nearby_pharmacies(
    user_lat=None, user_lng=None, radius_km=None, city='', pincode='',
    search_query='', sort_by='distance', only_approved=True, page=1, per_page=10, **kwargs
):
    return discover_healthcare_providers(
        user_lat=user_lat, user_lng=user_lng, radius_km=radius_km,
        city=city, district=kwargs.get('district', ''), state=kwargs.get('state', ''),
        pincode=pincode, search_query=search_query,
        provider_type=kwargs.get('provider_type', Pharmacy.ProviderType.PHARMACY),
        verification_status=kwargs.get('verification_status', 'approved' if only_approved else 'all'),
        only_approved=only_approved, sort_by=sort_by, page=page, per_page=per_page,
    )
```

### 3.2 Regression Verification:
All 15 legacy tests in [`tests/test_location_discovery.py`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/tests/test_location_discovery.py) executed and passed with **0 failures and 0 errors** (`Ran 15 tests in 32.448s — OK`).

---

## 4. Query Performance & Optimization

- **Database Indexes Leveraged:**
  - `prov_type_appr_city_idx` on `(provider_type, is_approved, city)`
  - `prov_type_appr_pin_idx` on `(provider_type, is_approved, pincode)`
  - `prov_geo_idx` on `(state, district, city)`
  - `prov_coords_idx` on `(latitude, longitude)`
  - `prov_source_idx` on `(source_name, source_id)`
- **Query Count:** Single `SELECT` query per search request; zero N+1 database queries.
- **Client Footprint:** Embedded map pins JSON is streamed via Django's secure `json_script` template filter.

---

## 5. Test Suite Results

The dedicated Stage 3 test suite [`tests/test_geospatial_discovery_frontend.py`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/tests/test_geospatial_discovery_frontend.py) verified all 13 core vectors:

```powershell
python manage.py test tests.test_geospatial_discovery_frontend
```

**Results:**
```
Ran 13 tests in 15.246s
OK
System check identified no issues (0 silenced).
```

### Test Vector Verification Table:
| Vector | Test Method | Result | Notes |
| :--- | :--- | :---: | :--- |
| **Hospital Search** | `test_hospital_search_filtering` | ✅ PASSED | Returns only hospitals when `type=HOSPITAL`. |
| **Pharmacy Search** | `test_pharmacy_search_filtering` | ✅ PASSED | Returns only pharmacies when `type=PHARMACY`. |
| **Combined Search** | `test_combined_search` | ✅ PASSED | Returns both hospitals and pharmacies when `type=ALL`. |
| **State Filter** | `test_state_filtering` | ✅ PASSED | Filters correctly by State (e.g. Telangana). |
| **District Filter**| `test_district_filtering` | ✅ PASSED | Filters correctly by District (e.g. Bengaluru Urban). |
| **City Filter** | `test_city_filtering` | ✅ PASSED | Filters correctly by City (e.g. New Delhi). |
| **Pincode Filter** | `test_pincode_filtering` | ✅ PASSED | Filters correctly by postal PIN code (e.g. 500033). |
| **Nearby Search** | `test_nearby_search_and_distance_calculation` | ✅ PASSED | Calculates Haversine distance and respects 5 km radius. |
| **Invalid Coords** | `test_invalid_coordinates_fallback` | ✅ PASSED | Gracefully falls back to manual search on bad coordinates. |
| **Verification** | `test_unverified_provider_badges_and_exclusion`| ✅ PASSED | Excludes unverified by default; displays directory badge on 'all'. |
| **Map Data** | `test_map_data_pins_payload` | ✅ PASSED | Validates distinct `hospital` vs `pharmacy` map pins. |
| **Hospital Detail**| `test_hospital_detail_view` | ✅ PASSED | Confirms public access to hospital profile with NIN & emergency guidance. |
| **Medicine Search**| `test_medicine_search_regression` | ✅ PASSED | Confirms stock search remains fully linked to approved pharmacies. |

---
*End of Stage 3 Documentation Deliverables.*
