# MEDIFIND — DATA SOURCE AND LICENSING COMPLIANCE REPORT

**Report Date:** November 17, 2026  
**Auditor:** Senior Legal & Data Integration Specialist  
**Framework:** Open Government Data (India), OpenStreetMap ODbL, ABDM NHA Regulations  
**Compliance Status:** **100% COMPLIANT**  

---

## 1. Regulatory & Licensing Framework Overview

MediFind ingests geospatial and institutional data from open and public health registries. Each data source operates under distinct licensing agreements, terms of service, and attribution mandates.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      MEDIFIND COMPLIANCE OVERVIEW                      │
├──────────────────────────┬──────────────────────────┬──────────────────┤
│ Source Name              │ Governing License        │ Compliance Level │
├──────────────────────────┼──────────────────────────┼──────────────────┤
│ National Hospital Dir.   │ NDSAP / GODL-India       │ Fully Compliant  │
│ OpenStreetMap            │ ODbL 1.0                 │ Fully Compliant  │
│ ABDM Facility Registry   │ NHA Terms of Use         │ Fully Compliant  │
│ Demo Seed Data           │ Proprietary Test Seed    │ Fully Compliant  │
└──────────────────────────┴──────────────────────────┴──────────────────┘
```

---

## 2. Source-by-Source Evaluation

### Source A: National Hospital Directory (data.gov.in / MoHFW)
- **Originating Authority:** Ministry of Health and Family Welfare (MoHFW), Government of India.
- **Portal URL:** https://www.data.gov.in/
- **Governing Policy:** National Data Sharing and Accessibility Policy (NDSAP), 2012 / Government Open Data License - India (GODL).
- **Permissions:** Unrestricted access, reproduction, distribution, and adaptation of public datasets for both non-commercial and commercial application development, subject to attribution.
- **License Requirements:**
  - Attribution to the Ministry of Health and Family Welfare and data.gov.in.
  - Retention of original National Identification Number (NIN) identifiers.
  - No representation that the Government of India endorses the downstream application.
- **MediFind Implementation:**
  - Source recorded as `DATA_GOV_IN` on all 58 hospital records.
  - NIN codes stored in `source_id` and `registration_number`.
  - Ingestion date tracked in `created_at`.
  - Attribution rendered in the hospital profile template and discovery footer.

### Source B: OpenStreetMap (OSM)
- **Originating Authority:** OpenStreetMap Foundation (OSMF) / Global Volunteer Cartography Community.
- **Portal URL:** https://www.openstreetmap.org/
- **Governing License:** Open Database License (ODbL) 1.0 / Database Contents License (DbCL).
- **Permissions:** Free to share, create, and adapt spatial geometries and associated tags (`amenity=pharmacy`).
- **License Requirements:**
  - Mandatory prominent attribution: **"© OpenStreetMap contributors"**.
  - Notice that data is available under the ODbL.
  - If a "derivative database" is produced and publicly distributed, it must be offered under ODbL terms.
- **Rate Limits & Fair Use:**
  - Overpass API usage adheres to the Overpass API Acceptable Use Policy: batch extraction during off-peak windows, cached local structured files, no aggressive hammering of public Overpass endpoints.
- **MediFind Implementation:**
  - Attribution embedded directly in the Leaflet.js tile layer attribution string (`L.tileLayer(..., { attribution: '&copy; OpenStreetMap contributors | MediFind Healthcare Discovery' })`).
  - Source recorded as `OSM` on all 25 retail pharmacy records.
  - Node and way IDs preserved in `source_id`.

### Source C: ABDM Health Facility Registry (facility.abdm.gov.in)
- **Originating Authority:** National Health Authority (NHA), Ayushman Bharat Digital Mission.
- **Portal URL:** https://facility.abdm.gov.in/
- **Governing Policy:** ABDM Guidelines on Data Privacy and Health Facility Registration.
- **Permissions:** Public registry lookup and facility metadata verification.
- **License Requirements:**
  - Preservation of stable HFR Facility IDs.
  - Accurate representation of facility name, address, and specialty.
  - No alteration of official health facility classifications.
- **MediFind Implementation:**
  - Source recorded as `ABDM` on all 5 tele-health and regional centers.
  - HFR codes preserved with `HFR-` prefix in `source_id`.

---

## 3. Data Integrity & Consumer Protection Safeguards

1. **No False Endorsement:** Neither the Government of India, the ABDM, nor the OpenStreetMap Foundation is claimed to endorse MediFind.
2. **Clinical Verification Boundary:** Data imported from OpenStreetMap or open directory portals is strictly classified as unverified directory listings (`is_approved=False`) until verified by an administrator or claimed by a licensed retail pharmacist.
3. **No Scraping or Rate-Limit Abuse:** Ingestion is conducted via downloaded structured feeds and authorized endpoints; no unauthenticated scraping of restricted portals or automated bypassing of web gates occurs.
