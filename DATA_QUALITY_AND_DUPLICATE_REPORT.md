# MEDIFIND — DATA QUALITY AND DUPLICATE DETECTION REPORT

**Report Date:** November 17, 2026  
**Auditor:** Senior Data Quality Specialist & GIS Engineer  
**Pipeline Engine:** `pharmacies.pipeline.deduplication` & `validation`  
**Quality Enforcement:** Multi-Tier Matching, Bounding Box Constraints, Zero Auto-Merge  

---

## 1. Quality Control Philosophy

In healthcare location datasets, false duplicates or careless merges can erase a genuine trauma center, while duplicate proliferation degrades search relevance and distance sorting.

MediFind implements a **defensive, multi-tier data quality framework**:
- Strict validation runs *before* any database query or write.
- Defective, foreign, or coordinate-deficient records are rejected outright and logged with actionable explanations.
- Transposed coordinates are detected via geographical bounds and automatically swapped.
- Duplicate identification is tiered: exact matches are safely skipped; uncertain or geospatial matches are flagged as duplicate candidates for administrative audit and **never automatically merged**.

---

## 2. Multi-Tier Deduplication Hierarchy

The deduplication engine in `pharmacies/pipeline/deduplication.py` evaluates candidate records through four sequential tiers:

```
[Candidate Provider Payload]
           │
           ▼
[Tier 1: Exact Source-ID Match]
(source_name + source_id)
           ├── Found ──> [Result: EXACT_SOURCE_ID -> Skip Duplicate]
           ▼
[Tier 2: Exact Registration Number Match]
(registration_number)
           ├── Found ──> [Result: EXACT_REG_NUM -> Skip Duplicate]
           ▼
[Tier 3: Geospatial Proximity + Name Similarity]
(Haversine Distance < 100m AND Jaccard Name Similarity > 70%)
           ├── Found ──> [Result: GEOSPATIAL_PROXIMITY -> Flag Duplicate Candidate]
           ▼
[Tier 4: Exact Name + City + State Match]
(Case-insensitive, normalized whitespace)
           ├── Found ──> [Result: EXACT_NAME_CITY -> Flag Duplicate Candidate]
           ▼
[Result: NONE -> Unique Eligible Record]
```

---

## 3. Duplicate Candidate Audit & Invariant Enforcement

During live execution, the pipeline detected **10 duplicate candidates** between the new incoming feeds and existing pilot records. In accordance with clinical safety guidelines, **none were automatically merged or overwritten**.

### Detailed Audit of Flagged Candidates:

| # | Facility Name | Existing Record ID | Conflict Type | Proximity / Similarity | Action Taken |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **01** | Rajiv Gandhi Government General Hospital | ID #17 | Geospatial Proximity | 90.0 meters away; 100% name match | Flagged; candidate preserved |
| **02** | AIIMS Jodhpur | ID #21 | Exact Name + City | Identical name in Jodhpur, Rajasthan | Flagged; candidate preserved |
| **03** | AIIMS Bhopal | ID #19 | Exact Name + City | Identical name in Bhopal, Madhya Pradesh | Flagged; candidate preserved |
| **04** | AIIMS Rishikesh | ID #20 | Geospatial Proximity | 50.0 meters away; 100% name match | Flagged; candidate preserved |
| **05** | Tulsi Chemist & Druggist - Camp | ID #33 | Geospatial Proximity | 0.0 meters; 100% name match | Flagged; candidate preserved |
| **06** | Guardian Pharmacy - South Extension | ID #29 | Geospatial Proximity | 0.0 meters; 100% name match | Flagged; candidate preserved |
| **07** | Apollo Pharmacy - Connaught Place | ID #28 | Geospatial Proximity | 0.0 meters; 100% name match | Flagged; candidate preserved |
| **08** | Apollo Pharmacy - Shanthi Colony | ID #32 | Geospatial Proximity | 0.0 meters; 100% name match | Flagged; candidate preserved |
| **09** | MedPlus Pharmacy - Anna Nagar | ID #31 | Geospatial Proximity | 0.0 meters; 100% name match | Flagged; candidate preserved |
| **10** | Frank Ross Pharmacy - Park Street | ID #30 | Geospatial Proximity | 0.0 meters; 100% name match | Flagged; candidate preserved |

**Audit Outcome:** All 10 candidates correspond to genuine pilot facilities that were seeded in Stage 2. Because they carried slight variations in source ID or registration formatting, the Tier 3 proximity check successfully intercepted them before any database collision occurred, preventing redundant duplicate entries.

---

## 4. Coordinate Range & Territorial Validation

All coordinates are validated against the sovereign terrestrial bounding box of the Republic of India:
- **Latitude Range:** $6.500000^\circ\text{N} \le \text{Latitude} \le 37.500000^\circ\text{N}$
- **Longitude Range:** $68.000000^\circ\text{E} \le \text{Longitude} \le 97.500000^\circ\text{E}$

### Rejection and Recovery Audit:

1. **Foreign Coordinates Rejection:**
   - Record `Invalid Foreign Facility (Paris France)` (`lat=48.856600, lng=2.352200`): Correctly rejected.
   - Record `Invalid Coordinates Facility (London UK)` (`lat=51.507400, lng=-0.127800`): Correctly rejected.
2. **Missing Coordinates Rejection:**
   - Record `Missing Coordinates Hospital`: Latitude/Longitude missing; rejected with explicit diagnostic.
3. **Null Island Zero Coordinate Rejection:**
   - Record `Null Island Facility` (`lat=0.000000, lng=0.000000`): Detected and rejected.
4. **Transposed Coordinate Auto-Correction:**
   - Record `Bannerghatta Road Hospital` had transposed coordinates: `lat=77.596300` (fits India Longitude) and `lng=12.891200` (fits India Latitude).
   - The engine detected the inversion, logged a warning (`Detected transposed coordinates: lat=77.596300, lng=12.891200. Swapping to correct`), and restored them to `lat=12.891200, lng=77.596300` in Bengaluru, Karnataka.
5. **Postal Code Validation:**
   - Pincodes with 5 digits (e.g. `50001`) or leading zeros are rejected.
   - Valid 6-digit Indian PIN codes are normalized and whitespace-trimmed.
