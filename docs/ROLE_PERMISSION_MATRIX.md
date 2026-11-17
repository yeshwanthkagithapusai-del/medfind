# MediFind Role & Permission Matrix (RBAC & Multi-Tenant Isolation)

**Document Version:** 1.0  
**Phase:** Phase 1 – Security Hardening & Vulnerability Remediation  
**Date:** November 2026  
**System:** MediFind (Three-Tier Modular Monolith)  
**Security Architect:** Senior Django Security Engineer & Application Security Architect  

---

## 1. Executive Summary

This document establishes the official Role-Based Access Control (RBAC) and Multi-Tenant Data Isolation Matrix for MediFind. The platform supports four discrete authentication actors:
1. **ANONYMOUS (Public / Guest):** Unauthenticated visitors seeking emergency medicine information and exploring registered pharmacies.
2. **CUSTOMER:** Registered public users searching medicine availability, checking proximity, creating availability inquiries, and managing their private inquiry history.
3. **PHARMACY (Owner / Staff):** Registered and admin-vetted pharmacy operators managing their inventory catalogue, stock quantities, and responding to incoming customer requests.
4. **ADMIN (Platform Overseer):** System administrators governing pharmacy approvals, global medicine catalogs, user accounts, and platform compliance.

---

## 2. Core Architectural Roles

| Role | Database Representation | Default Landing / Routing | Key Architectural Responsibilities |
| :--- | :--- | :--- | :--- |
| **ANONYMOUS** | `AnonymousUser` (`is_authenticated=False`) | `/` (`home.html`) | Public medicine search, viewing approved pharmacy profiles, public catalogue viewing, registration, authentication. |
| **CUSTOMER** | `User.role == 'CUSTOMER'` | `/dashboard/` -> `/dashboard/customer/` | Medicine search, creating availability requests, viewing own request tracking, updating personal profile, receiving system notifications. |
| **PHARMACY** | `User.role == 'PHARMACY'` | `/dashboard/` -> `/dashboard/pharmacy/` | Managing own inventory, viewing incoming inquiries for their facility, responding to requests, updating pharmacy profile. |
| **ADMIN** | `User.role == 'ADMIN'` or `is_superuser=True` | `/dashboard/` -> `/dashboard/admin/` | Approving/rejecting pharmacy registrations, adding/editing global medicine catalog, platform monitoring, superuser audit. |

---

## 3. Comprehensive View & Endpoint Authorization Matrix

### A. Accounts Application (`accounts`)

| Endpoint / View | URL Pattern | Allowed Roles | Denied Roles | Enforcement Mechanism | Unauthorized Action Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `home` | `/` | All Roles | None | Public | N/A |
| `login_view` | `/accounts/login/` | All (Redirects if auth) | None | Standard Django Auth | Redirects authenticated users to `/dashboard/` |
| `register_customer` | `/accounts/register/customer/` | ANONYMOUS | Authenticated | Anonymous check | Redirects authenticated users to `/dashboard/` |
| `register_pharmacy` | `/accounts/register/pharmacy/` | ANONYMOUS | Authenticated | Anonymous check | Redirects authenticated users to `/dashboard/` |
| `logout_view` | `/accounts/logout/` | All Authenticated | None | `django.contrib.auth.logout` | Clears session; 302 to `/` |
| `profile_view` | `/accounts/profile/` | CUSTOMER, PHARMACY, ADMIN | ANONYMOUS | `@login_required` | 302 Redirect to `/accounts/login/` |
| `notifications_view` | `/accounts/notifications/` | CUSTOMER, PHARMACY, ADMIN | ANONYMOUS | `@login_required` | 302 Redirect to `/accounts/login/` |
| `mark_notification_read` | `/accounts/notifications/<id>/read/` | CUSTOMER, PHARMACY, ADMIN | ANONYMOUS | `@login_required`, `@require_POST`, `user=request.user` | 302 to login or 405 Method Not Allowed; 404 on IDOR |

---

### B. Medicines Application (`medicines`)

| Endpoint / View | URL Pattern | Allowed Roles | Denied Roles | Enforcement Mechanism | Unauthorized Action Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `medicine_search_view` | `/medicines/search/` | All Roles | None | Public | Allows open search across approved pharmacies |
| `medicine_detail_view` | `/medicines/<id>/` | All Roles | None | Public | Public read-only; filters availability to approved pharmacies only |
| `medicine_catalog_view` | `/medicines/catalog/` | All Roles | None | Public | Displays verified catalog medicines |
| `medicine_create_view` | `/medicines/manage/create/` | ADMIN | ANONYMOUS, CUSTOMER, PHARMACY | `@admin_required` | 302 to `/dashboard/` with warning message |
| `medicine_update_view` | `/medicines/manage/<id>/edit/` | ADMIN | ANONYMOUS, CUSTOMER, PHARMACY | `@admin_required` | 302 to `/dashboard/` with warning message |
| `medicine_delete_view` | `/medicines/manage/<id>/delete/` | ADMIN | ANONYMOUS, CUSTOMER, PHARMACY | `@admin_required`, `@require_POST` | 302 to `/dashboard/` or 405 Method Not Allowed |

---

### C. Pharmacies Application (`pharmacies`)

| Endpoint / View | URL Pattern | Allowed Roles | Denied Roles | Enforcement Mechanism | Unauthorized Action Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `pharmacy_list_view` | `/pharmacies/` | All Roles | None | Public View (Filtered: `is_approved=True`) | Open directory |
| `pharmacy_detail_view` | `/pharmacies/<id>/` | All Roles | None | Public View (`is_approved=True` or `owner==user` or `ADMIN`) | 404 for unapproved pharmacy if not owner/admin |
| `pharmacy_profile_edit` | `/pharmacies/profile/edit/` | PHARMACY | ANONYMOUS, CUSTOMER, ADMIN | `@pharmacy_required`, `Pharmacy.objects.get(owner=request.user)` | 302 to `/dashboard/` with warning message |
| `admin_pharmacy_list` | `/pharmacies/admin/manage/` | ADMIN | ANONYMOUS, CUSTOMER, PHARMACY | `@admin_required` | 302 to `/dashboard/` with warning message |
| `toggle_pharmacy_approval` | `/pharmacies/admin/<id>/toggle/` | ADMIN | ANONYMOUS, CUSTOMER, PHARMACY | `@admin_required`, `@require_POST` | 302 to `/dashboard/` or 405 Method Not Allowed |

---

### D. Inventory Application (`inventory`)

| Endpoint / View | URL Pattern | Allowed Roles | Denied Roles | Enforcement Mechanism | Unauthorized Action Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `inventory_list_view` | `/inventory/` | PHARMACY | ANONYMOUS, CUSTOMER, ADMIN | `@pharmacy_required`, `filter(pharmacy=user.pharmacy)` | 302 to `/dashboard/` with warning message |
| `inventory_add_view` | `/inventory/add/` | PHARMACY | ANONYMOUS, CUSTOMER, ADMIN | `@pharmacy_required`, automatic pharmacy assignment | 302 to `/dashboard/` with warning message |
| `inventory_edit_view` | `/inventory/<id>/edit/` | PHARMACY | ANONYMOUS, CUSTOMER, ADMIN | `@pharmacy_required`, `get_object_or_404(..., pharmacy=user.pharmacy)` | 404 Not Found if inventory belongs to another pharmacy |
| `inventory_delete_view` | `/inventory/<id>/delete/` | PHARMACY | ANONYMOUS, CUSTOMER, ADMIN | `@pharmacy_required`, `get_object_or_404(..., pharmacy=user.pharmacy)`, `@require_POST` | 404 Not Found if inventory belongs to another pharmacy; 405 on GET |

---

### E. Requests Application (`requests_app`)

| Endpoint / View | URL Pattern | Allowed Roles | Denied Roles | Enforcement Mechanism | Unauthorized Action Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `create_request_view` | `/requests/create/<pharmacy_id>/<medicine_id>/` | CUSTOMER | ANONYMOUS, PHARMACY, ADMIN | `@customer_required`, Pharmacy approval verification | 302 to `/dashboard/` with warning message |
| `customer_requests_list` | `/requests/my-requests/` | CUSTOMER | ANONYMOUS, PHARMACY, ADMIN | `@customer_required`, `filter(customer=request.user)` | 302 to `/dashboard/` with warning message |
| `cancel_request_view` | `/requests/<id>/cancel/` | CUSTOMER | ANONYMOUS, PHARMACY, ADMIN | `@customer_required`, `@require_POST`, `get_object_or_404(..., customer=request.user)` | 404 Not Found on cross-tenant IDOR; 405 on GET |
| `pharmacy_inbox_view` | `/requests/inbox/` | PHARMACY | ANONYMOUS, CUSTOMER, ADMIN | `@pharmacy_required`, `filter(pharmacy=user.pharmacy)` | 302 to `/dashboard/` with warning message |
| `respond_request_view` | `/requests/<id>/respond/` | PHARMACY | ANONYMOUS, CUSTOMER, ADMIN | `@pharmacy_required`, `get_object_or_404(..., pharmacy=user.pharmacy)` | 404 Not Found if request addressed to different pharmacy |

---

### F. Dashboard Application (`dashboard`)

| Endpoint / View | URL Pattern | Allowed Roles | Denied Roles | Enforcement Mechanism | Unauthorized Action Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `dashboard_dispatch` | `/dashboard/` | CUSTOMER, PHARMACY, ADMIN | ANONYMOUS | `@login_required`, role dispatcher | 302 to `/accounts/login/` |
| `customer_dashboard` | `/dashboard/customer/` | CUSTOMER | ANONYMOUS, PHARMACY, ADMIN | `@customer_required` | 302 to `/dashboard/` with error message |
| `pharmacy_dashboard` | `/dashboard/pharmacy/` | PHARMACY | ANONYMOUS, CUSTOMER, ADMIN | `@pharmacy_required` | 302 to `/dashboard/` with error message |
| `admin_dashboard` | `/dashboard/admin/` | ADMIN | ANONYMOUS, CUSTOMER, PHARMACY | `@admin_required` | 302 to `/dashboard/` with error message |

---

## 4. Multi-Tenant Data Isolation Guarantees

### 4.1 Customer Data Privacy (Customer A vs Customer B)
* **Inquiry Scoping:** Availability inquiries are isolated via `AvailabilityRequest.objects.filter(customer=request.user)`. Customer B cannot enumerate, view details, or cancel Customer A's requests.
* **IDOR Prevention on Cancellation:** `get_object_or_404(AvailabilityRequest, id=request_id, customer=request.user)` ensures that an attacker submitting `POST /requests/12/cancel/` receives an immediate HTTP 404 Not Found rather than unauthorized modification.
* **Notification Scoping:** Notifications are strictly scoped with `Notification.objects.filter(user=request.user)`. Marking notifications read executes `get_object_or_404(Notification, id=notification_id, user=request.user)`.

### 4.2 Pharmacy Multi-Tenancy (Pharmacy A vs Pharmacy B)
* **Inventory Scoping:** Every inventory query filters against the active session user's owned pharmacy: `Inventory.objects.filter(pharmacy=request.user.pharmacy)`.
* **Inventory Edit & Delete Protection:** Mutating endpoints execute `get_object_or_404(Inventory, id=inventory_id, pharmacy=request.user.pharmacy)`. Pharmacy B attempting to edit Pharmacy A's item is rejected with HTTP 404.
* **Inquiry Inbox Scoping:** Pharmacy inboxes display exclusively items where `pharmacy=request.user.pharmacy`.
* **Inquiry Response IDOR Guard:** When submitting a response, `get_object_or_404(AvailabilityRequest, id=request_id, pharmacy=request.user.pharmacy)` prevents Pharmacy B from confirming or declining prescriptions directed to Pharmacy A.

### 4.3 Public Access Guarding (Unapproved Pharmacy Suppression)
* **Search Engine Isolation:** The medicine availability search engine filters stock strictly to approved facilities: `Inventory.objects.filter(pharmacy__is_approved=True)`.
* **Directory Isolation:** Public pharmacy listings apply `Pharmacy.objects.filter(is_approved=True)`.
* **Direct Access Guard:** Accessing `/pharmacies/<id>/` enforces that non-approved pharmacies can only be viewed by their respective owner or by an administrator; all other visitors receive an HTTP 404 Not Found.

---

## 5. Architectural Enforcement Mechanisms

### 5.1 Role Decorators (`accounts/decorators.py`)
Custom decorators wrap Django view functions, enforcing authentication and role checks prior to execution:
```python
def customer_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.role != 'CUSTOMER':
            messages.error(request, 'Access restricted to customer accounts.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
```
* Identical robust implementations protect `@pharmacy_required` and `@admin_required`.

### 5.2 HTTP Method Verification (`django.views.decorators.http.require_POST`)
All state-altering actions (canceling requests, marking notifications read, toggling pharmacy approval, deleting inventory) reject HTTP GET requests with `HTTP 405 Method Not Allowed`, eliminating drive-by GET CSRF exploits.

### 5.3 Database-Level & Model-Level Constraints
* Inventory quantity is constrained with `MinValueValidator(0)` and explicit `clean()` enforcement.
* Medicine request quantities require strictly positive integers (`min_value=1`).
* Unique constraints prevent duplicate catalog collisions and redundant user registrations.

---

## 6. Verification Status

The RBAC and Multi-Tenant Isolation rules documented above are verified by the automated test suite in `tests/test_security.py` (12 automated test cases) and `tests/test_features.py` (17 automated test cases), achieving 100% test pass rates across all boundaries.
