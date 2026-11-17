# India Location Data Source Audit
**MediFind Healthcare Platform — Stage 1: Geospatial Data Engineering Audit**
**Date:** November 2026 | **Author:** Senior GIS & Data Integration Specialist

---

## 1. Executive Summary

This audit assesses authentic, authoritative geospatial healthcare data sources across India to transition MediFind from a localized demonstration application into a comprehensive, nation-wide platform. MediFind requires real-world data across two primary facility categories:
1. **Hospitals and Health Facilities:** Government and private tertiary centers, district hospitals, sub-divisional hospitals, Community Health Centres (CHCs), and Primary Health Centres (PHCs).
2. **Retail Pharmacies and Chemists:** Independent medical shops, retail chains (e.g., Apollo Pharmacy, MedPlus, Wellness Forever), and hospital-attached dispensing units.

Three primary sources were evaluated in depth:
1. **National Hospital Directory (data.gov.in / National Health Portal)**
2. **Ayushman Bharat Digital Mission (ABDM) Health Facility Registry (facility.abdm.gov.in)**
3. **OpenStreetMap (OSM - Overpass API & Geofabrik Extracts)**

Additionally, state-level regulatory bodies (State Drug Control Administrations and State Pharmacy Councils) were reviewed for legal pharmacy licensing verification.

---

## 2. In-Depth Source Evaluation Matrix

| Evaluation Criteria | National Hospital Directory (data.gov.in) | ABDM Health Facility Registry (`facility.abdm.gov.in`) | OpenStreetMap (OSM / Geofabrik) | State Drug Control Administrations (DCA) |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Domain** | Hospitals & Health Centers | Integrated National Healthcare Registry | Global Crowd-sourced Geospatial Map | State Drug Licensing & Inspection |
| **Provider Categories** | Govt Hospitals, Private Hospitals, CHCs, PHCs, Ayush Hospitals | Hospitals, Clinics, Diagnostic Labs, Pharmacies, Nursing Homes | Pharmacies, Chemists, Hospitals, Clinics, Dispensaries | Licensed Retail / Wholesale Chemists |
| **Coordinate Availability** | **High (~75–85%)** surveyed GPS coordinates | **High (~85%)** internally; masked/map pins on public UI | **100%** (by definition of spatial nodes/ways) | **Extremely Low (<5%)** (Text addresses only) |
| **Geographic Coverage** | Pan-India (All 28 States & 8 UTs) | Pan-India (Tier 1–3 & registered rural facilities) | Pan-India (Dense in Metros/Tier 2; Moderate in Rural) | State-by-State isolated silos |
| **Data Freshness** | Monthly/Quarterly snapshots | Live dynamic registry | Continuous real-time edits | Static PDFs or outdated portals |
| **Access Method** | Direct CSV/JSON download & OGD REST API | ABDM Developer Portal (API Keys/Gateway Token) | Overpass API (JSON) & Geofabrik (`.osm.pbf`) | Scraped HTML / Form searches / PDF lists |
| **License & Attribution** | **GODL-India** (Government Open Data License) | **NHA HDMP** (Health Data Management Policy) | **ODbL 1.0** (Open Database License) | Varies by State Government |
| **Access Gate / Barrier** | **None** for CSV download; API requires free key | **High** (Requires NHA Partner/Developer approval) | **None** (Public Overpass endpoints & open downloads) | **High** (No standard API; disparate formats) |
| **Suitability for MediFind** | **Primary Source for Hospitals** | **Secondary Verification Registry** | **Primary Source for Pharmacies** | **Tertiary Validation Source** |

---

## 3. Source-by-Source Technical Breakdown

### 3.1 National Hospital Directory (`data.gov.in`)

* **Host Agency:** Ministry of Health and Family Welfare (MoHFW) / National Health Portal (NHP) / National Institute of Health and Family Welfare (NIHFW).
* **Dataset Identifier:** `National Hospital Directory with Geo Code and additional parameters`.
* **Resource URL:** `https://www.data.gov.in/resource/national-hospital-directory-geo-code-and-additional-parameters-updated-till-last-month`

#### Data Fields & Schema:
- `nin_to_facility_code`: National Identification Number (NIN) – unique identifier.
- `state_name` / `district_name` / `sub_district_name`: Standardized administrative hierarchy.
- `hospital_name`: Full facility legal title.
- `facility_type`: Categorical breakdown (District Hospital, Sub-District Hospital, Community Health Centre, Primary Health Centre, Medical College Hospital, Ayush).
- `ownership`: Government (State/Central/Municipal) or Private.
- `address_line1`, `address_line2`, `pincode`: Postal street delivery data.
- `latitude` / `longitude`: Decimal degree coordinates surveyed via GPS.
- `number_of_beds`: Total authorized bed capacity.
- `specialties_available`: Departmental listing (e.g., General Medicine, Pediatrics, Surgery, OB-GYN).
- `telephone` / `mobile_number` / `emergency_contact`: Public inquiry lines.
- `website` / `email`: Institutional contacts.

#### Legal & Licensing Terms:
- Governed by **Government Open Data License - India (GODL-India)**.
- **Permissions:** Unrestricted commercial and non-commercial reuse, transformation, publication, and distribution.
- **Requirements:** Explicit attribution to the Ministry of Health and Family Welfare, Government of India, and `data.gov.in`.
- **Restrictions:** Cannot be misrepresented as official government endorsement.

#### Access & Rate Limits:
- **Bulk Download:** Direct CSV/JSON download directly accessible via HTTP GET.
- **OGD API:** Requires a registered developer API token (`api-key`). Rate limit is 10,000 calls per 24 hours per key.
- **Import Feasibility:** **Highest for Hospitals.** The schema maps cleanly to Django relational models with minimal data transformation.

---

### 3.2 ABDM Health Facility Registry (`facility.abdm.gov.in`)

* **Host Agency:** National Health Authority (NHA), Government of India.
* **Objective:** Comprehensive digital master registry of all verified health facilities in India.
* **Portal URL:** `https://facility.abdm.gov.in/` | **Developer Portal:** `https://docs.abdm.gov.in/`

#### Data Fields & Schema:
- `facility_id`: 10-digit standardized ABDM HFR identifier (e.g., `IN0110000001`).
- `facility_name`: Registered facility name.
- `system_of_medicine`: Allopathy, Ayurveda, Homeopathy, Unani, Siddha, Dental.
- `facility_type`: Clinic, Day Care, Hospital, Diagnostic Lab, Pharmacy/Chemist, Blood Bank.
- `ownership`: Public, Private, NGO, Trust.
- `verification_status`: Fully Verified, Self-Registered, Verification Pending.
- `state`, `district`, `sub_district`, `pincode`, `village_city`: Spatial hierarchy.
- `latitude`, `longitude`: Maintained in internal registry.

#### Legal & Licensing Terms:
- Governed by the **ABDM Health Data Management Policy (HDMP)** and Digital Personal Data Protection (DPDP) Act compliance.
- Data access is restricted to verified ecosystem partners, software solutions (HMIS/LMIS/EMR), and healthcare providers.

#### Access & Rate Limits:
- **No Unrestricted Public Bulk Download:** The NHA does not publish complete live database dumps on the open web.
- **Programmatic API:** Requires developer registration on `sandbox.abdm.gov.in`, client credentials (Client ID and Client Secret), and adherence to ABDM Milestone 1 (M1) and Milestone 2 (M2) integration protocols.
- **Public Search Interface:** Gated by CAPTCHA, session tokens, and strict client-side rate limits to prevent programmatic web scraping.
- **Import Feasibility:** **Low for initial bulk data ingestion.** High value as an **Authoritative Verification Provider** for verifying facilities during individual pharmacy or hospital claims.

---

### 3.3 OpenStreetMap (OSM) India Healthcare Dataset

* **Host Agency:** OpenStreetMap Foundation / OpenStreetMap India Community.
* **Primary Query Interfaces:** Overpass API (`https://overpass-api.de/api/interpreter`), Geofabrik Regional Extract Server (`https://download.geofabrik.de/asia/india.html`).
* **Tags of Interest:**
  - Pharmacies: `amenity=pharmacy`, `healthcare=pharmacy`, `shop=chemist`.
  - Hospitals: `amenity=hospital`, `healthcare=hospital`.
  - Clinics & Dispensaries: `amenity=clinic`, `healthcare=clinic`.

#### Data Fields & Schema:
- `id`: OSM node/way/relation ID.
- `lat` / `lon`: Exact WGS84 geographic coordinates.
- `tags.name`: Common / commercial business name.
- `tags.brand` / `tags.operator`: Chain identification (e.g., "Apollo Pharmacy", "MedPlus").
- `tags.addr:street`, `tags.addr:city`, `tags.addr:postcode`, `tags.addr:state`: Address attributes.
- `tags.phone` / `tags.contact:phone`: Contact telephone numbers.
- `tags.opening_hours`: Operational schedule (e.g., `24/7`, `Mo-Su 08:00-22:00`).
- `tags.dispensing`: Boolean tag indicating prescription dispensing capability.

#### Legal & Licensing Terms:
- Governed by the **Open Database License (ODbL) 1.0**.
- **Permissions:** Free to share, create, and adapt the database.
- **Requirements:**
  - Attribution: Must credit "© OpenStreetMap contributors" prominently on all maps and search result pages.
  - Share-Alike: If you publicize a derivative database incorporating OSM data, you must make that derived database available under ODbL terms.

#### Access & Rate Limits:
- **Overpass API:** Free, no API keys required. Rate limits are concurrency-based (maximum 2 concurrent queries per IP, with a server execution timeout of 25–180 seconds). Bulk nationwide queries must be sharded state-by-state or bounding-box by bounding-box to avoid `429 Too Many Requests` or `504 Gateway Timeout`.
- **Geofabrik Extracts:** Precompiled binary dumps (`india-latest.osm.pbf`, ~1.4 GB compressed) updated daily. Filterable offline using `osmium-tool` or `osmosis` with zero rate limit restrictions.
- **Import Feasibility:** **Highest for Pharmacies.** Thousands of geotagged pharmacies across major Indian metropolitan areas and tier-2 cities can be cleanly extracted.

---

### 3.4 State Drug Control Administrations (DCA)

* **Scope:** State-level statutory regulatory bodies (e.g., Telangana DCA, Karnataka Drugs Control Dept, Maharashtra FDA).
* **Data Nature:** Legal retail and wholesale drug license registries (Form 20, 21, 20-B, 21-B).
* **Limitations:**
  - No unified national portal; each of India's 28 states operates an independent, non-standardized portal.
  - Almost entirely lack geographic coordinates (only text street addresses and pincodes).
  - Many states publish data only inside locked PDFs or behind dynamic ASPX forms.
* **Role in MediFind:** Useful for regulatory validation of registration/license numbers, but impractical as an automated geospatial ingestion pipeline.

---

## 4. Hospital vs. Pharmacy Separation Strategy

| Characteristic | Hospitals (Healthcare Landmark) | Pharmacies (Inventory & Dispensing Node) |
| :--- | :--- | :--- |
| **Primary Role on MediFind** | Emergency triage navigation, inpatient beds, clinical services | Real-time medicine stock search, availability requests, order tracking |
| **Inventory Requirement** | Optional (only for hospital internal pharmacy) | **Mandatory** (linked to `inventory.Inventory` model) |
| **User Account Dependency** | None (institutional public discovery) | Required for order fulfillment and stock updates (`owner = ForeignKey(User)`) |
| **Data Source Recommendation**| **National Hospital Directory (data.gov.in)** | **OpenStreetMap (OSM) + Geofabrik Extracts** |
| **Verification Mechanism** | Government NIN / ABDM Facility ID verification | Admin approval + Drug Retail License (DCA) verification |

---

## 5. Summary Recommendations for MediFind Stage 1

1. **Hospital Data Pipeline:**
   Adopt the **National Hospital Directory from data.gov.in** as the definitive source. It provides verified government and private hospitals with official NIN codes, administrative classifications, bed capacities, and surveyed coordinates under the permissive GODL-India license.
2. **Pharmacy Data Pipeline:**
   Adopt **OpenStreetMap (OSM)** via Geofabrik / Overpass API as the definitive source for retail pharmacies. It provides immediate, high-density coordinate data for chains (Apollo, MedPlus, etc.) and neighborhood chemists with standard ODbL attribution.
3. **ABDM Alignment:**
   Integrate ABDM Health Facility Registry as an **external verification reference** where facility IDs can be validated on a per-facility basis rather than attempting bulk scraping.
4. **License Compliance:**
   - Display "Data sourced from National Hospital Directory (data.gov.in) & © OpenStreetMap contributors" in the application footer and map modal.

---
*Next Phase Reference: See [`MEDIFIND_GIS_ARCHITECTURE_PLAN.md`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/docs/MEDIFIND_GIS_ARCHITECTURE_PLAN.md) for architectural integration specifications.*
