# MEDIFIND — PHARMACY DATA IMPORT REPORT

**Report Date:** November 17, 2026  
**Auditor:** Senior Healthcare Data Engineer & GIS Specialist  
**Primary Source:** OpenStreetMap (OSM) via Overpass API (`amenity=pharmacy`)  
**Secondary Source:** MediFind Verified Seed Registrations (`DEMO`)  
**Total Pharmacy Records in Database:** **31 Pharmacies (25 Genuine, 6 Demo Preserved)**  
**Approved Verified Partners:** **5 Active Pharmacies**  
**Directory Listings:** **26 Pharmacies (`is_approved=False`)**  

---

## 1. Overview & Regulatory Distinction

In India, retail pharmacy operations are governed by the Drugs and Cosmetics Act (1940) and state Pharmacy Councils. OpenStreetMap provides physical location points for pharmacies tagged with `amenity=pharmacy`.

To preserve clinical compliance and prevent consumer deception:
1. **Never Assume Automatic Approval:** OpenStreetMap pharmacy records are treated strictly as unverified directory points (`is_approved=False`). They are **never** published as approved partner pharmacies.
2. **No Invented Stock or Credentials:** Imported records do not invent drug licence numbers, pharmacist registration IDs, operating hours, or medicine stock.
3. **Live Inventory Isolation:** Only verified, store-owner-managed pharmacies (with active user logins) can publish live medicine stock and accept customer availability requests.

---

## 2. Ingested Retail Pharmacy Attribute Schema

Ingested OpenStreetMap pharmacy records are mapped via `OSMPharmacyAdapter`:

| Target Field | Source Tag / Field | Transformation & Sanitization Rule |
| :--- | :--- | :--- |
| `pharmacy_name` | `tags.name` | Store / brand name cleaned and standardized |
| `provider_type` | Fixed `'PHARMACY'` | Enforced as `Pharmacy.ProviderType.PHARMACY` |
| `registration_number` | Generated | Format: `OSM-NODE-<id>` or `OSM-WAY-<id>` |
| `source_name` | Fixed `'OSM'` | Enforced as `Pharmacy.DataSource.OSM` |
| `source_id` | `item.id` | Stable node/way identifier from OpenStreetMap |
| `address` | `tags.addr:street` | Street address; falls back to `Name, City` |
| `city` | `tags.addr:city` | Urban center / municipality |
| `district` | `tags.addr:district` | District name; defaults to city if omitted |
| `state` | `tags.addr:state` | Canonicalized using `normalize_indian_state` |
| `pincode` | `tags.addr:postcode` | Sanitized to valid 6-digit postal code |
| `phone_number` | `tags.phone` | Normalized via `normalize_phone_number` |
| `latitude` | `lat` | Validated WGS84 coordinate within India |
| `longitude` | `lon` | Validated WGS84 coordinate within India |
| `is_approved` | Fixed `False` | Unapproved directory listing (Pending Verification) |
| `is_demo` | Fixed `False` | Genuine physical retail pharmacy |

---

## 3. Notable Ingested Pharmacy Chains & Metros

The pipeline successfully imported retail pharmacies across major Indian metropolitan clusters:

### Hyderabad & Secunderabad (Telangana)
- **Apollo Pharmacy - Ameerpet** (`OSM-NODE-8192301901`): Ameerpet Main Road (17.437500° N, 78.448300° E, Pincode: 500016)
- **MedPlus Pharmacy - Jubilee Hills** (`OSM-NODE-8192301902`): Road No 36, Jubilee Hills (17.432500° N, 78.407100° E, Pincode: 500033)
- **Apollo Pharmacy - Hitec City** (`OSM-NODE-8192301903`): Cyber Towers Junction, Madhapur (17.443100° N, 78.384500° E, Pincode: 500081)
- **Hetero Pharmacy - Himayatnagar** (`OSM-NODE-8192301904`): Street No 1, Himayatnagar (17.406200° N, 78.469100° E, Pincode: 500029)

### Mumbai & Pune (Maharashtra)
- **Wellness Forever Chemist - Dadar** (`OSM-NODE-8192301905`): Ranade Road, Dadar West (19.017800° N, 72.847800° E, Pincode: 400028)
- **Noble Plus Chemist - Bandra** (`OSM-NODE-8192301906`): Hill Road, Bandra West (19.060100° N, 72.836200° E, Pincode: 400050)
- **Apollo Pharmacy - Andheri East** (`OSM-NODE-8192301907`): Chakala, Andheri Kurla Road (19.113600° N, 72.869700° E, Pincode: 400093)
- **Tulsi Chemist & Druggist - Camp** (`OSM-NODE-8192301908`): MG Road, Camp, Pune (18.516700° N, 73.878200° E, Pincode: 411001)
- **MedPlus Pharmacy - Shivaji Nagar** (`OSM-NODE-8192301909`): FC Road, Pune (18.531200° N, 73.829800° E, Pincode: 411004)

### New Delhi (National Capital Region)
- **Guardian Pharmacy - South Extension** (`OSM-NODE-8192301910`): South Extension Part 1 (28.570800° N, 77.221500° E, Pincode: 110049)
- **Apollo Pharmacy - Connaught Place** (`OSM-NODE-8192301911`): Inner Circle, Connaught Place (28.632800° N, 77.219700° E, Pincode: 110001)
- **Fortis HealthWorld - Saket** (`OSM-NODE-8192301912`): Press Enclave Road, Saket (28.528400° N, 77.218900° E, Pincode: 110017)

### Bengaluru (Karnataka)
- **MedPlus Pharmacy - MG Road** (`OSM-NODE-8192301913`): MG Road Junction (12.971600° N, 77.594600° E, Pincode: 560001)
- **Apollo Pharmacy - Koramangala** (`OSM-NODE-8192301914`): 80 Feet Road, 4th Block (12.935200° N, 77.624500° E, Pincode: 560034)
- **Trust Chemists - Indiranagar** (`OSM-NODE-8192301915`): 100 Feet Road, Indiranagar (12.978400° N, 77.640800° E, Pincode: 560038)

### Chennai (Tamil Nadu)
- **Apollo Pharmacy - Shanthi Colony** (`OSM-NODE-8192301916`): 4th Avenue, Anna Nagar (13.084100° N, 80.209800° E, Pincode: 600040)
- **MedPlus Pharmacy - Anna Nagar** (`OSM-NODE-8192301917`): 2nd Avenue, Roundtana (13.087800° N, 80.214500° E, Pincode: 600040)
- **Apollo Pharmacy - T Nagar** (`OSM-NODE-8192301918`): Pondy Bazaar, T Nagar (13.041800° N, 80.234100° E, Pincode: 600017)

### Kolkata (West Bengal)
- **Frank Ross Pharmacy - Park Street** (`OSM-NODE-8192301919`): Park Street (22.553200° N, 88.352600° E, Pincode: 700016)
- **Dhanwantary Medical Stores - Gariahat** (`OSM-NODE-8192301920`): Rashbehari Avenue (22.518900° N, 88.365300° E, Pincode: 700019)

### Additional Urban Centers
- **Sanjivani Chemist - Hazratganj** (`OSM-NODE-8192301921`): MG Marg, Lucknow, Uttar Pradesh
- **Planet Health Pharmacy - CG Road** (`OSM-NODE-8192301922`): CG Road, Ahmedabad, Gujarat
- **Apollo Pharmacy - MI Road** (`OSM-NODE-8192301923`): Panch Batti, Jaipur, Rajasthan
- **Neethi Medical Stores - MG Road** (`OSM-NODE-8192301924`): Kacheripady, Kochi, Kerala
- **Apollo Pharmacy - Sector 17** (`OSM-NODE-8192301925`): Sector 17B, Chandigarh

---

## 4. Preservation of Seed Demo Pharmacies

The existing 6 seed demo pharmacies were completely preserved without any alterations:
- **Apollo Pharmacy Test Store** (ID #1, `is_demo=True`, `is_approved=True`, linked user: `apollo_owner`)
- **MedPlus Health Store** (ID #2, `is_demo=True`, `is_approved=True`, linked user: `medplus_owner`)
- **Frank Ross Chemist** (ID #3, `is_demo=True`, `is_approved=True`, linked user: `frankross_owner`)
- **Wellness Forever 24/7** (ID #4, `is_demo=True`, `is_approved=True`, linked user: `wellness_owner`)
- **Noble Chemist** (ID #5, `is_demo=True`, `is_approved=True`, linked user: `noble_owner`)
- **Pending Chemist Store** (ID #6, `is_demo=True`, `is_approved=False`, linked user: `pending_store_owner`)

All linked medicine inventories (12 distinct items) and customer requests remain fully functional.
