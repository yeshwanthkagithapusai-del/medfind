# MediFind – Technical Debt, Code Quality & Security Audit

**Author**: Senior Python Full-Stack Developer & Django Software Architect  
**Project**: MediFind  
**Audit Date**: November 17, 2026  
**Standards Evaluated**: OWASP Top 10, Django Security Guidelines, Clean Code & Database Normalization

---

## 1. Executive Summary

This report catalogues all technical debt, code anomalies, security vulnerabilities, missing validations, and query inefficiencies discovered during the complete codebase inspection. Each item is classified by severity with exact file references and remediation blueprints.

---

## 2. Findings by Severity Classification

```
  ┌─────────────────────────────────────────────────────────┐
  │                   SEVERITY BREAKDOWN                    │
  │                                                         │
  │  CRITICAL : 2 issues  (Security / State Mutation / Auth)│
  │  HIGH     : 4 issues  (Model Integrity / Geo / Queries) │
  │  MEDIUM   : 6 issues  (Performance / Caching / Bounds)  │
  │  LOW      : 4 issues  (UX / Formatting / Test Gaps)     │
  └─────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Audit Findings

### 3.1 CRITICAL SEVERITY

#### [SEC-01] State-Altering Database Mutations Accessible via HTTP GET
- **Affected Files**:
  - `pharmacies/views.py`: Lines 78–92 (`toggle_pharmacy_approval_view`)
  - `requests_app/views.py`: Lines 126–136 (`cancel_request_view`)
  - `accounts/views.py`: Lines 138–144 (`mark_notification_read`)
- **Category**: Security / CSRF Vulnerability / REST Violation
- **Why It Needs Attention**:
  These views mutate database state (`is_approved` toggled, request status set to `CANCELLED`, notification marked read) without enforcing `request.method == 'POST'`. A simple HTTP GET request triggers database alteration.
- **Potential Impact**:
  1. Web crawlers, link prefetchers, or malicious embedded images (`<img src="/pharmacies/manage/5/toggle-approval/">`) can silently revoke licenses or cancel customer inquiries.
  2. Complete bypass of CSRF token protection, which Django only validates on unsafe HTTP verbs (POST/PUT/DELETE).
- **Remediation**:
  Wrap all state-altering views with `@require_POST` from `django.views.decorators.http` and update frontend templates to submit via `<form method="POST">{% csrf_token %}`.

---

#### [SEC-02] Registration Forms Bypass Django's Configured Password Validators
- **Affected File**: `accounts/forms.py`: Lines 8–40 (`CustomerRegistrationForm`), Lines 43–110 (`PharmacyRegistrationForm`)
- **Category**: Authentication Security / Credential Weakness
- **Why It Needs Attention**:
  Both registration forms define `password = forms.CharField(min_length=6, widget=forms.PasswordInput)`. Neither form invokes `django.contrib.auth.password_validation.validate_password()`.
- **Potential Impact**:
  Users and pharmacy owners can register with trivial, insecure passwords such as `123456`, `password`, or `qwerty`, completely bypassing the four standard validators defined in `config/settings.py` (`AUTH_PASSWORD_VALIDATORS`).
- **Remediation**:
  In `clean()`, call `password_validation.validate_password(password, user=self.instance)` and catch `ValidationError` to populate `self.add_error('password', ...)`.

---

### 3.2 HIGH SEVERITY

#### [ARCH-01] Relationship Discrepancy: `Pharmacy.owner` Model vs. View Logic (1:N vs. 1:1)
- **Affected Files**:
  - `pharmacies/models.py`: Line 5 (`owner = models.ForeignKey(User, related_name='pharmacies')`)
  - `pharmacies/views.py`: Line 41 (`Pharmacy.objects.filter(owner=request.user).first()`)
  - `inventory/views.py`: Lines 11, 54, 92, 117 (`Pharmacy.objects.filter(owner=request.user).first()`)
  - `requests_app/views.py`: Lines 69, 98 (`Pharmacy.objects.filter(owner=request.user).first()`)
  - `dashboard/views.py`: Line 71 (`Pharmacy.objects.filter(owner=request.user).first()`)
- **Category**: Database Architecture / Domain Modeling
- **Why It Needs Attention**:
  The schema declares a 1-to-many relationship (`ForeignKey`), suggesting that an owner user could manage multiple pharmacy branches. However, every single view in the codebase hardcodes `.first()`, assuming a 1-to-1 relationship.
- **Potential Impact**:
  If a pharmacy owner creates or registers a second store location, the entire management interface will permanently bind to the first store, rendering subsequent branches orphaned and unmanageable.
- **Remediation**:
  Either:
  - *Option A (Preserve 1:1)*: Change `ForeignKey` to `OneToOneField(settings.AUTH_USER_MODEL, related_name='pharmacy')`.
  - *Option B (Enable Multi-Branch)*: Implement an active store selector session context so multi-location owners can switch branches.

---

#### [DATA-01] Missing Range Validation on Geographic Coordinates
- **Affected Files**:
  - `pharmacies/models.py`: Lines 22–35 (`latitude`, `longitude`)
  - `accounts/forms.py`: Lines 77–78, 88–89
  - `pharmacies/forms.py`: Lines 14–15, 24–25
- **Category**: Data Integrity / Spatial Validation
- **Why It Needs Attention**:
  `latitude` and `longitude` are defined as `DecimalField(max_digits=9, decimal_places=6)` without `MinValueValidator` or `MaxValueValidator`.
- **Potential Impact**:
  Users can input mathematically invalid coordinates (e.g. Latitude 450.0, Longitude -360.0). This will break Leaflet map pin calculations and trigger math errors in Haversine trigonometry.
- **Remediation**:
  Add `validators=[MinValueValidator(Decimal('-90.0')), MaxValueValidator(Decimal('90.0'))]` for latitude, and `-180.0` to `180.0` for longitude.

---

#### [PERF-01] Missing Query Pagination and In-Memory Queryset Evaluation
- **Affected Files**:
  - `medicines/views.py`: Lines 42–47 (`inventory_results = list(inventory_qs...)`)
  - `inventory/views.py`: Line 19 (`items = Inventory.objects.filter(...)`)
  - `medicines/views.py`: Line 116 (`medicines = Medicine.objects.all()`)
- **Category**: Scalability / Memory Consumption
- **Why It Needs Attention**:
  Calling `list(inventory_qs)` forces immediate evaluation of all matching rows into Python heap memory. If the master inventory reaches 10,000+ items, this will exhaust server memory and cause high response latency.
- **Potential Impact**:
  Denial of service under moderate data volume; high TTFB (Time to First Byte); slow page rendering.
- **Remediation**:
  Integrate Django's `Paginator` (`from django.core.paginator import Paginator`) to cap results to 20 items per page with standard bootstrap pagination controls.

---

#### [PERF-02] Sequential Redundant Aggregation Queries (N+1 Counts)
- **Affected Files**:
  - `inventory/views.py`: Lines 34–37 (4 separate `COUNT(*)` queries)
  - `dashboard/views.py`: Lines 47–50 (4 separate `COUNT(*)` queries on requests)
  - `dashboard/views.py`: Lines 76–80 (4 separate `COUNT(*)` queries on inventory)
  - `dashboard/views.py`: Lines 108–116 (8 separate `COUNT(*)` queries on admin dashboard)
- **Category**: Database Performance / Query Optimization
- **Why It Needs Attention**:
  Instead of aggregating metrics in a single SQL query, the codebase executes 4 to 8 sequential database queries on every dashboard and list load.
- **Potential Impact**:
  Unnecessary database connection overhead and high query execution time.
- **Remediation**:
  Refactor multiple `.count()` calls into a single `.aggregate()` call using conditional filters:
  ```python
  metrics = Inventory.objects.filter(pharmacy=pharmacy).aggregate(
      total=Count('id'),
      in_stock=Count('id', filter=Q(availability_status='IN_STOCK')),
      low_stock=Count('id', filter=Q(availability_status='LOW_STOCK')),
      out_stock=Count('id', filter=Q(availability_status='OUT_OF_STOCK')),
  )
  ```

---

### 3.3 MEDIUM SEVERITY

#### [PERF-03] Global Context Processor Query on Every Authenticated Request
- **Affected File**: `accounts/context_processors.py`: Lines 1–10
- **Category**: Middleware / Context Processor Performance
- **Why It Needs Attention**:
  Every single HTTP request dispatched by an authenticated user executes a database query `Notification.objects.filter(user=request.user, is_read=False).count()`.
- **Potential Impact**:
  Significant query multiplier across static asset requests or rapid page navigations.
- **Remediation**:
  Implement lightweight cache caching (e.g. `cache.get(f"unread_notif_{user.id}")`) with cache invalidation when a notification is created or marked read.

---

#### [DATA-02] Missing Uniqueness Constraint on Master Medicine Formulations
- **Affected File**: `medicines/models.py`: Lines 29–63
- **Category**: Data Integrity / Catalogue Deduplication
- **Why It Needs Attention**:
  The `Medicine` model lacks a `unique_together` constraint on `('medicine_name', 'strength', 'dosage_form')`.
- **Potential Impact**:
  Administrators can accidentally create duplicate catalog records for the same drug, fracturing store inventory across duplicate catalog IDs.
- **Remediation**:
  Add `unique_together = ('medicine_name', 'strength', 'dosage_form')` to `Medicine.Meta`.

---

#### [FEAT-01] Incomplete Medicine Master Catalogue CRUD (Missing Deletion in UI)
- **Affected Files**: `medicines/views.py`, `templates/medicines/manage_list.html`
- **Category**: Feature Completeness
- **Why It Needs Attention**:
  Admins can create and edit catalog items in the custom UI, but cannot delete or soft-delete/deactivate obsolete drugs from the custom portal.
- **Remediation**:
  Add `delete_medicine_view` with dependency checking (blocking deletion if active inventory or requests reference the medicine).

---

#### [MATH-01] Haversine Floating-Point Domain Clamping Boundary
- **Affected File**: `pharmacies/services.py`: Lines 25–29
- **Category**: Edge-Case Mathematical Robustness
- **Why It Needs Attention**:
  `c = 2 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))` can raise `ValueError: math domain error` if floating-point inaccuracy produces `a > 1.0` for near-antipodal coordinates.
- **Remediation**:
  Clamp `a` using `a = min(1.0, max(0.0, a))`.

---

#### [UX-01] Missing Distance Calculation on Medicine Detail View
- **Affected File**: `medicines/views.py`: Lines 110–125 (`medicine_detail_view`)
- **Category**: Feature Consistency / UX
- **Why It Needs Attention**:
  `search_medicines_view` calculates distance in kilometers for pharmacies, but `medicine_detail_view` does not compute distances even if `lat` and `lng` query params are passed.
- **Remediation**:
  Mirror the distance calculation logic from `search_medicines_view` in `medicine_detail_view`.

---

#### [SEC-03] Missing Cooldown / Rate Limiting on Availability Inquiries
- **Affected File**: `requests_app/views.py`: Lines 10–49 (`create_request_view`)
- **Category**: Abuse Prevention / Rate Limiting
- **Why It Needs Attention**:
  A customer can submit hundreds of availability requests in seconds, flooding the pharmacy inbox and notification tables.
- **Remediation**:
  Add a rate-limit check (e.g. maximum 5 inquiries per 10 minutes per customer, or blocking duplicate pending requests for the same medicine and store).

---

### 3.4 LOW SEVERITY

#### [SEC-04] Demonstration Credentials Exposed in Public Footer
- **Affected File**: `templates/base.html`: Lines 191–197
- **Category**: Information Disclosure
- **Why It Needs Attention**:
  The public footer contains credentials: `customer1 / password123`, `apollo_owner / password123`, `admin / admin123`.
- **Remediation**:
  Wrap the demonstration credential block in `{% if debug %}` or an environment-driven `DEMO_MODE` flag.

---

#### [DATA-03] Unvalidated Phone Number Strings
- **Affected Files**: `accounts/models.py`, `pharmacies/models.py`
- **Category**: Data Sanitization
- **Why It Needs Attention**:
  `phone_number = models.CharField(max_length=15)` accepts arbitrary text (e.g. `abc-call-me`).
- **Remediation**:
  Add `RegexValidator(regex=r'^\+?1?\d{9,15}$')`.

---

#### [CODE-01] Redundant Single-Notification Read Action
- **Affected File**: `accounts/views.py`: Lines 130–144
- **Category**: Dead / Redundant Code
- **Why It Needs Attention**:
  Visiting `/accounts/notifications/` automatically executes `user_notifications.filter(is_read=False).update(is_read=True)`, rendering individual `mark_notification_read` calls redundant.
- **Remediation**:
  Align UI so visiting the page does not automatically clear unread status, or provide explicit "Mark All as Read" and "Mark Read" actions.

---

#### [TEST-01] Missing Automated Test Cases for Profile Edits and Form Validations
- **Affected File**: `tests/test_features.py`
- **Category**: Quality Assurance / Regression Coverage
- **Why It Needs Attention**:
  While all 17 integration tests pass, edge cases such as invalid coordinate submission, profile editing, and password mismatch handling lack dedicated tests.
- **Remediation**:
  Expand test suite to 25+ tests covering form validation failures and 404 security boundaries.
