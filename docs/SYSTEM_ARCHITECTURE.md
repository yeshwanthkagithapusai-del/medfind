# MediFind – System Architecture Document

## 1. Executive Summary
**MediFind** is a location-based medicine availability and pharmacy inventory management platform designed to solve the critical problem of physical search exhaustion during medical emergencies and routine prescription fulfillment. By connecting patients with local registered pharmacies in real time, MediFind provides transparent stock visibility, location-filtered searches, and digital availability inquiries.

## 2. High-Level Architectural Pattern
MediFind adheres strictly to an industry-standard **Three-Tier Modular Monolithic Architecture** powered by Django 5.2 LTS, Bootstrap 5, and SQLite (with seamless production upgradability to PostgreSQL).

```
+-----------------------------------------------------------------------+
|                       TIER 1: PRESENTATION LAYER                      |
|  - HTML5, CSS3, Modern Healthcare Design System                      |
|  - Bootstrap 5 + Bootstrap Icons                                      |
|  - Leaflet.js & OpenStreetMap (Interactive Geo-Visualization)         |
|  - Chart.js (Operational & Inventory Analytics)                       |
|  - Asynchronous AJAX search & Modal Inquiries                         |
+-----------------------------------------------------------------------+
                                   ▲
                                   │ HTTPS / Django Templates / JSON
                                   ▼
+-----------------------------------------------------------------------+
|                       TIER 2: APPLICATION LAYER                       |
|                      (Django 5.2 LTS Web Framework)                   |
|                                                                       |
|  [accounts]       Authentication, Custom User Roles, Profile Mgmt    |
|  [medicines]      Catalogue, Generic Names, Categorization, Indexing |
|  [pharmacies]     Pharmacy Registration, Geo-Coordinates, Approval   |
|  [inventory]      Stock Management, In/Low/Out-of-Stock Logic        |
|  [requests_app]   Customer Inquiries, Pharmacy Dispatch, Alerts      |
|  [dashboard]      Customer, Pharmacy, & Admin Role-Based Portals     |
|                                                                       |
|  Services & Decorators: Role-based RBAC, Haversine Distance Helper    |
+-----------------------------------------------------------------------+
                                   ▲
                                   │ Django ORM (Object-Relational Mapping)
                                   ▼
+-----------------------------------------------------------------------+
|                          TIER 3: DATA LAYER                           |
|                      (Relational Database - SQLite)                   |
|                                                                       |
|  - Custom User Model (Customer, Pharmacy Owner, Admin)                |
|  - Pharmacy Entity (Location, Verification Status, Ownership)        |
|  - Medicine Entity (Standardized Drug Catalogue)                     |
|  - Inventory Entity (Composite Key: Pharmacy + Medicine, Strict Min) |
|  - AvailabilityRequest Entity (Lifecycle State Machine)              |
|  - Notification Entity (Internal Dispatch System)                    |
+-----------------------------------------------------------------------+
```

## 3. Tier Breakdown & Component Design

### 3.1 Presentation Layer (Frontend)
- **Design Philosophy**: Deep Navy (`#0f2b48`), Clinical Teal (`#0ea5e9`), Fresh Emerald (`#059669`), and Crisp Slate (`#f8fafc`).
- **Responsive Layout**: Fluid 12-column grid system fully tested across mobile, tablet, and widescreen viewports.
- **Dynamic Elements**:
  - OpenStreetMap integration via Leaflet for instant pharmacy pinouts.
  - Chart.js dynamic canvases for inventory balance and request trends.
  - Real-time stock status badges (`In Stock`, `Low Stock`, `Out of Stock`).

### 3.2 Application Layer (Django Monolith)
Composed of 6 cohesive Django applications:
1. `accounts`: Handles Django custom user model (`AUTH_USER_MODEL`), multi-role authentication (Customer, Pharmacy Owner, Admin), and secure session handling.
2. `medicines`: Manages master medicine catalog, generic chemical names, therapeutic classes, dosage formats, and fast search indexing.
3. `pharmacies`: Manages pharmacy onboarding, license verification, geocoding (`latitude`, `longitude`), and administrative approval gating.
4. `inventory`: Implements CRUD operations for pharmacy stock, real-time threshold calculations, and ownership validation guards.
5. `requests_app`: Provides stateful communication channel between seekers and pharmacies for medicine availability confirmation.
6. `dashboard`: Renders distinct analytical and workflow consoles tailored to each role's distinct operational priorities.

### 3.3 Data Layer (Relational Storage)
- Normalized relational schema enforcing integrity via Foreign Keys, Unique Constraints (`unique_together = ('pharmacy', 'medicine')`), and Positive Integer Validators.
- No reliance on untyped, unstructured JSON columns for relational business data.

## 4. Security & Access Control Architecture
- **Role-Based Access Control (RBAC)**: Enforced via custom view decorators (`@customer_required`, `@pharmacy_required`, `@admin_required`).
- **Tenant Isolation**: Pharmacy owners can only access, query, and modify inventory and inquiries associated with their verified pharmacy foreign key.
- **Public Visibility Filter**: Unapproved pharmacies are strictly excluded from public medicine search queries.
- **CSRF & Injection Defense**: Standard Django CSRF tokens on all state-altering forms; ORM parameterized queries eliminating SQL injection.
- **Safe Stock Disclaimers**: UI explicitly flags reported stock as "Pharmacy-reported last at [Timestamp]" to prevent medical misrepresentation.
