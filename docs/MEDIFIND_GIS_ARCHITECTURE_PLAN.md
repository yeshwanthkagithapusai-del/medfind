# MediFind GIS Architecture Plan
**National Geospatial Healthcare & Pharmacy Discovery Architecture**
**Date:** November 2026 | **Author:** Senior Django & GIS Software Architect

---

## 1. Architectural Philosophy & Constraints

This plan designs the national geospatial expansion of MediFind to support real-world hospitals and pharmacies across India. The architecture strictly adheres to core platform constraints:
1. **Preserve the Django Modular Monolith:** No microservices or external Node/Go routing services. All logic resides within the existing six applications (`accounts`, `medicines`, `pharmacies`, `inventory`, `requests_app`, `dashboard`).
2. **Dual Database Portability:** Must execute efficiently on both **SQLite** (local development/testing) and **PostgreSQL** (production deployment on Render/Railway) without requiring exotic C extensions or non-portable GIS spatial database plugins unless optionally enabled.
3. **Preserve Existing User Workflows:** Customer medicine searches, pharmacy inventory management, availability requests, and administrative approval workflows remain 100% backward-compatible.
4. **Client-Side Scalability:** Support rendering tens of thousands of national healthcare points without crashing the client browser by leveraging bounding-box server-side filtering, pagination, and Leaflet MarkerClustering.

---

## 2. High-Level System Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                              CLIENT TIER (BROWSER)                                |
|  +---------------------------+  +------------------------+  +------------------+  |
|  | HTML5 Geolocation API     |  | Leaflet.js v1.9.4 Map  |  | Leaflet Marker   |  |
|  | (GPS Lat/Lng Acquisition) |  | (OpenStreetMap Tiles)  |  | Cluster Group    |  |
|  +-------------+-------------+  +-----------+------------+  +--------+---------+  |
+----------------|----------------------------|------------------------|------------+
                 | (HTTP GET / REST query)    |                        |
                 v                            v                        v
+-----------------------------------------------------------------------------------+
|                        DJANGO APPLICATION TIER (MONOLITH)                         |
|                                                                                   |
|  [pharmacies.views / medicines.views]                                             |
|        |                                                                          |
|        v                                                                          |
|  [pharmacies.services.discover_nearby_facilities]                                 |
|        |                                                                          |
|        +---> 1. Bounding Box Filter (Spatial Coarse-Grain Index Filter)           |
|        |        [lat_min <= lat <= lat_max AND lng_min <= lng <= lng_max]         |
|        |                                                                          |
|        +---> 2. Administrative Hierarchy Filter                                   |
|        |        [State -> District -> City -> Pincode]                             |
|        |                                                                          |
|        +---> 3. Haversine Distance Calculation (Fine-Grain Spherical Distance)    |
|        |        Distance = 2 * R * asin(sqrt(h))                                  |
|        |                                                                          |
|        +---> 4. Radius Threshold Filter & Sorting                                 |
|        |        [d <= radius_km ORDER BY distance ASC]                            |
|        |                                                                          |
|        +---> 5. Django Paginator (10-25 items per page)                           |
+-----------------------------------------------------------------------------------+
                 |
                 v
+-----------------------------------------------------------------------------------+
|                              DATABASE PERSISTENCE TIER                             |
|                                                                                   |
|  +------------------------------+       +--------------------------------------+  |
|  | Pharmacy (Existing)          |       | Hospital (Proposed Model)            |  |
|  | - owner (User, nullable)     |       | - nin_code (Unique National ID)      |  |
|  | - pharmacy_name              |       | - hospital_name                      |  |
|  | - registration_number        |       | - facility_type (Govt/Private/CHC)   |  |
|  | - state, district, city      |       | - state, district, city, pincode     |  |
|  | - pincode, address           |       | - latitude, longitude (Indexed)      |  |
|  | - latitude, longitude        |       | - emergency_phone, bed_count         |  |
|  | - is_approved, is_claimed    |       | - has_inhouse_pharmacy (Boolean)     |  |
|  | - source (OSM, MANUAL)       |       | - source (DATA_GOV_IN)               |  |
|  +------------------------------+       +--------------------------------------+  |
|                                                                                   |
|  COMPOSITE INDEXES:                                                               |
|  - (state, district, city)                                                        |
|  - (pincode, is_approved)                                                         |
|  - (latitude, longitude)                                                          |
+-----------------------------------------------------------------------------------+
```

---

## 3. Spatial Query & Distance Optimization

### 3.1 The Scalability Challenge
When scaling from 6 demo pharmacies to **50,000+ national hospitals and pharmacies**, computing the Python Haversine formula across every single record in memory (`O(N)` scan) will degrade response times from 5ms to over 800ms.

### 3.2 The Bounding-Box Pre-Filtering Solution
To guarantee sub-50ms query latency on both SQLite and PostgreSQL without requiring spatial PostGIS extensions, we implement **Bounding-Box Coarse Filtering** at the database layer before applying the precise Haversine calculation:

1. **Given:** User location $(\phi, \lambda)$ and search radius $R_{km}$.
2. **Latitude Delta:**
   $$\Delta \phi = \frac{R_{km}}{111.045}$$
3. **Longitude Delta:**
   $$\Delta \lambda = \frac{R_{km}}{111.045 \times \cos(\text{radians}(\phi))}$$
4. **Bounding Box Bounds:**
   $$\phi_{min} = \phi - \Delta \phi, \quad \phi_{max} = \phi + \Delta \phi$$
   $$\lambda_{min} = \lambda - \Delta \lambda, \quad \lambda_{max} = \lambda + \Delta \lambda$$
5. **SQL Execution:**
   ```python
   # Coarse filter reduces candidate set from 50,000 down to ~50 records using DB B-Tree index:
   qs = qs.filter(
       latitude__gte=lat_min,
       latitude__lte=lat_max,
       longitude__gte=lng_min,
       longitude__lte=lng_max
   )
   ```
6. **Haversine Refinement:**
   The exact Haversine trigonometric calculation is then executed only on the ~50 candidate records, eliminating 99.9% of computation.

---

## 4. Administrative Hierarchy Filtering Strategy

India's administrative healthcare geography requires a 4-tier drill-down hierarchy:
1. **State / Union Territory:** (e.g., Telangana, Maharashtra, Karnataka, Delhi, Tamil Nadu)
2. **District:** (e.g., Hyderabad, Rangareddy, Medchal-Malkajgiri, Bengaluru Urban)
3. **City / Town / Sub-District:** (e.g., Hyderabad, Secunderabad, Bengaluru, Electronic City)
4. **Postal Pincode:** 6-digit postal division (e.g., `500081`, `560038`, `110001`)

### Search Interaction Modes:
- **Mode A (GPS Proximity):** User enables browser GPS $\rightarrow$ System fetches GPS coordinates $\rightarrow$ Calculates Bounding Box & Haversine distance $\rightarrow$ Returns nearest facilities sorted by distance.
- **Mode B (Hierarchical Drill-Down):** User selects State $\rightarrow$ District dropdown auto-populates $\rightarrow$ City dropdown auto-populates $\rightarrow$ Returns matched facilities.
- **Mode C (Pincode Search):** User inputs 6-digit Pincode $\rightarrow$ System matches direct pincode, expanding to first 3-digits (postal sorting district) if exact matches are zero.

---

## 5. Leaflet.js Client-Side Map Architecture

### 5.1 Marker Performance & Clustering
Displaying over 100 markers simultaneously causes severe browser DOM lag. The client-side map architecture incorporates:
1. **Leaflet MarkerCluster Plugin:** Automatically clusters adjacent markers into numbered clusters at lower zoom levels, expanding into individual pins upon zoom-in.
2. **Distinct Marker Icon Taxonomy:**
   - **User Location:** Teal pulsing dot marker with person icon.
   - **Approved Active Pharmacy:** Green medical cross pin (`#16A34A`).
   - **Government Hospital:** Red cross hospital pin (`#DC2626`).
   - **Private Hospital:** Blue cross hospital pin (`#2563EB`).
   - **Community Health Centre (CHC/PHC):** Amber clinic pin (`#D97706`).
3. **Popup Mini-Card:**
   - Name and facility category badge.
   - Distance in kilometers (if user location active).
   - Address and telephone click-to-call link.
   - Action link: "View Inventory & Details" (for pharmacies) or "Directions & Emergency Contact" (for hospitals).

---

## 6. Service Layer Architecture

The existing `pharmacies/services.py` will be extended into two specialized service components:
1. `pharmacies.services.discovery`:
   - `discover_nearby_pharmacies(...)` — Handles retail pharmacy discovery, radius bounds, stock availability joins, and distance calculation.
2. `pharmacies.services.hospital_discovery`:
   - `discover_nearby_hospitals(...)` — Handles hospital discovery, facility type filtering (Govt/Private), bed capacity filtering, and emergency contact retrieval.
3. `pharmacies.services.spatial_utils`:
   - `compute_bounding_box(lat, lng, radius_km) -> (lat_min, lat_max, lng_min, lng_max)`
   - `calculate_haversine_distance(lat1, lon1, lat2, lon2) -> float`
   - `is_valid_coordinate(lat, lng) -> bool`

---

## 7. Zero-Impact Monolith Compatibility

- All new features reuse Django's template engine, existing `base.html`, Bootstrap 5 styling tokens, and Leaflet CDN scripts.
- No changes to existing authentication sessions, customer requests, or inventory management routes.
- The existing [db.sqlite3](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/db.sqlite3) and all 6 demo records remain untouched.

---
*Next Deliverable: See [`PROVIDER_DATA_MODEL_REVIEW.md`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/docs/PROVIDER_DATA_MODEL_REVIEW.md) for data model evaluations.*
