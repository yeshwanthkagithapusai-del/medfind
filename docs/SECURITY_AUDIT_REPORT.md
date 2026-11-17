# MediFind – Comprehensive Application Security Audit Report

**Author**: Senior Django Security Engineer & Application Security Architect  
**Project**: MediFind (Location-Based Medicine Availability and Pharmacy Inventory Management Platform)  
**Phase**: Phase 1 – Security Hardening & Vulnerability Remediation  
**Audit Date**: November 17, 2026  
**Target Architecture**: Three-Tier Modular Monolith (Django 5.2.16 LTS)  
**Security Posture**: **HARDENED & VERIFIED**  

---

## 1. Executive Summary

A comprehensive application security audit and vulnerability assessment was conducted on the MediFind web application. The audit focused on the OWASP Top 10 vulnerabilities, authentication strength, Role-Based Access Control (RBAC), multi-tenant inventory isolation (IDOR defense), HTTP method safety, CSRF protection, and session security.

All critical vulnerabilities identified in the initial architecture baseline have been analyzed, classified, and remediated without altering the underlying monolithic architecture or introducing breaking schema changes.

---

## 2. Vulnerability Classification Matrix

| Vulnerability ID | Vulnerability Title | Affected Components / Files | Severity | Initial Status | Remediated Status |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **VULN-01** | **State Mutation via HTTP GET (CSRF Bypass)** | `pharmacies/views.py`<br>`requests_app/views.py`<br>`accounts/views.py` | **CRITICAL** | Vulnerable | **REMEDIATED** |
| **VULN-02** | **Weak Password Acceptance on Registration** | `accounts/forms.py` | **CRITICAL** | Vulnerable | **REMEDIATED** |
| **VULN-03** | **Missing RBAC Protection on Customer Routes** | `requests_app/views.py` | **HIGH** | Vulnerable | **REMEDIATED** |
| **VULN-04** | **Unprotected User Profile Email Collisions** | `accounts/forms.py` | **HIGH** | Vulnerable | **REMEDIATED** |
| **VULN-05** | **Missing HTTP Security & Cookie Flags** | `config/settings.py` | **MEDIUM** | Incomplete | **REMEDIATED** |
| **VULN-06** | **Insecure Direct Object Reference (IDOR)** | `inventory/views.py`<br>`requests_app/views.py` | **HIGH** | Verified Safe | **VERIFIED SAFE** |
| **VULN-07** | **Public Isolation of Unapproved Pharmacies** | `medicines/views.py` | **HIGH** | Verified Safe | **VERIFIED SAFE** |
| **VULN-08** | **Negative Quantity Stock Injection** | `inventory/models.py` | **MEDIUM** | Verified Safe | **VERIFIED SAFE** |

---

## 3. Deep-Dive Vulnerability Analysis & Findings

### 3.1 Authentication & Credential Security (VULN-02)
- **Vulnerability**: `CustomerRegistrationForm` and `PharmacyRegistrationForm` in `accounts/forms.py` defined `password = forms.CharField(min_length=6)` without invoking Django's configured password validators (`AUTH_PASSWORD_VALIDATORS`).
- **Risk**: Users could register with trivially crackable passwords (e.g. `123456`, `password`), bypassing the `UserAttributeSimilarityValidator`, `MinimumLengthValidator`, `CommonPasswordValidator`, and `NumericPasswordValidator`.
- **Remediation Applied**:
  - Implemented explicit password complexity validation in `clean()` for both registration forms:
    ```python
    if password:
        temp_user = User(username=cleaned_data.get('username', ''), email=cleaned_data.get('email', ''))
        try:
            password_validation.validate_password(password, user=temp_user)
        except ValidationError as e:
            self.add_error('password', e)
    ```
  - Added unique username validation to prevent silent form rejections.

---

### 3.2 State Alteration via HTTP GET & CSRF Bypass (VULN-01)
- **Vulnerability**:
  - `toggle_pharmacy_approval_view` (`pharmacies/views.py`): Approved or revoked pharmacy operating licenses upon GET request.
  - `cancel_request_view` (`requests_app/views.py`): Transitioned availability requests to `CANCELLED` upon GET request.
  - `mark_notification_read` (`accounts/views.py`): Updated alert status to read upon GET request.
- **Risk**:
  1. Attackers could execute CSRF attacks via cross-origin embedded tags (`<img src="/requests/10/cancel/">`) because Django only enforces CSRF checks on unsafe methods (POST/PUT/DELETE).
  2. Search crawlers or browser link prefetchers could inadvertently cancel active medicine orders or revoke store verification.
- **Remediation Applied**:
  - Enforced `@require_POST` from `django.views.decorators.http` across all three views.
  - Refactored `templates/requests/customer_list.html` to execute cancellations through a CSRF-protected form:
    ```html
    <form method="POST" action="{% url 'cancel_request' req.id %}" class="d-inline" onsubmit="return confirm('Cancel this pending request?');">
      {% csrf_token %}
      <button type="submit" class="btn btn-sm btn-outline-danger">Cancel</button>
    </form>
    ```
  - Refactored `templates/pharmacies/admin_list.html` to confirm that approval toggles execute strictly via POST forms with CSRF tokens.

---

### 3.3 Role-Based Access Control (RBAC) Hardening (VULN-03)
- **Vulnerability**: `customer_requests_list_view` and `create_request_view` previously used standard `@login_required` instead of role-enforcing `@customer_required`.
- **Risk**: Authenticated pharmacy owners and internal non-customer sessions could wander into customer request queues and trigger state mismatches.
- **Remediation Applied**:
  - Applied `@customer_required` to `create_request_view`, `customer_requests_list_view`, and `cancel_request_view`.
  - Non-customer authenticated roles attempting access are safely redirected to `/dashboard/` with flash error alerts.

---

### 3.4 Multi-Tenant Inventory Isolation & IDOR Defense (VULN-06)
- **Audit Finding**: Verified that all mutation endpoints in `inventory/views.py` (`inventory_edit`, `inventory_delete`) explicitly bind lookups to `pharmacy=request.user.pharmacies.first()`.
- **Validation**:
  - Direct object reference manipulation in URL routes (`/inventory/<id>/edit/` or `/inventory/<id>/delete/`) for an item belonging to Pharmacy A by Pharmacy B strictly yields HTTP 404 Not Found.
  - In `requests_app/views.py`, `respond_request_view` strictly filters by `pharmacy=pharmacy`. Foreign pharmacy response attempts return HTTP 404.

---

### 3.5 Django HTTP Security Configuration (VULN-05)
- **Audit Finding**: Configured security headers in `config/settings.py` were enhanced to separate development and production security policies:
  ```python
  # Security Hardening Settings
  SECURE_CONTENT_TYPE_NOSNIFF = True
  SESSION_COOKIE_HTTPONLY = True

  if not DEBUG:
      X_FRAME_OPTIONS = 'DENY'
      SESSION_COOKIE_SECURE = True
      CSRF_COOKIE_SECURE = True
      SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 'yes')
      SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
      SECURE_HSTS_INCLUDE_SUBDOMAINS = True
      SECURE_HSTS_PRELOAD = True
  else:
      X_FRAME_OPTIONS = 'SAMEORIGIN'
      SESSION_COOKIE_SECURE = False
      CSRF_COOKIE_SECURE = False
      SECURE_SSL_REDIRECT = False
  ```
- **Result**: Protects against session hijacking, XSS cookie theft, and clickjacking while preserving zero-friction local HTTP development.
