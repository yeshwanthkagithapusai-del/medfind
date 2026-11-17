# Admin Security Review
**MediFind – Phase 7: Administrative Portal & Governance**

---

## 1. Executive Summary

All admin portal views are protected by role-based access control, CSRF validation, and HTTP method enforcement. No sensitive data (passwords, payment info, PII beyond contact details) is exposed through admin portal views. The admin portal follows Django security best practices throughout.

---

## 2. Access Control Architecture

### `@admin_required` Decorator

**Location**: `accounts/decorators.py`

```python
def admin_required(view_func):
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL)
        if not (request.user.role == 'ADMIN' or
                request.user.is_superuser or
                request.user.is_staff):
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped
```

**Enforcement**:
- Unauthenticated users → redirected to login page
- Authenticated non-admin users (CUSTOMER, PHARMACY) → redirected to `dashboard`
- Admin users (`role='ADMIN'`, `is_superuser`, or `is_staff`) → allowed through

### Applied to All Admin Views

| View | Decorator(s) |
|------|-------------|
| `admin_dashboard_view` | `@login_required`, `@admin_required` |
| `admin_pharmacy_list_view` | `@login_required`, `@admin_required` |
| `toggle_pharmacy_approval_view` | `@login_required`, `@admin_required`, `@require_POST` |
| `admin_user_list_view` | `@login_required`, `@admin_required` |
| `admin_request_monitor_view` | `@login_required`, `@admin_required` |
| `manage_medicines_view` | `@login_required`, `@admin_required` |

---

## 3. CSRF Protection

All state-mutating POST actions use Django's built-in CSRF middleware:

- `toggle_pharmacy_approval_view`: requires valid CSRF token via `{% csrf_token %}` in template form
- Django's `CsrfViewMiddleware` is enabled in `settings.py` (default)
- No CSRF exemptions (`@csrf_exempt`) used on any admin view

---

## 4. HTTP Method Enforcement

The pharmacy approval toggle uses `@require_POST` to prevent accidental mutations via GET:

```python
@admin_required
@require_POST
def toggle_pharmacy_approval_view(request, pk):
    pharmacy = get_object_or_404(Pharmacy, pk=pk)
    toggle_pharmacy_approval(pharmacy, request.user)
    ...
```

GET requests return **HTTP 405 Method Not Allowed** (verified in test #11).

---

## 5. Object-Level Authorization

Pharmacy approval lookups use `get_object_or_404`:

```python
pharmacy = get_object_or_404(Pharmacy, pk=pk)
```

This prevents:
- Object enumeration returning 200 for non-existent PKs (returns 404 instead of 500)
- Unauthorized approval of non-existent pharmacies

---

## 6. Data Exposure Analysis

### Admin Pharmacy List
- Columns exposed: pharmacy_name, registration_number, city, owner username, is_approved, created_at, phone_number
- ❌ No passwords, financial data, or geolocation coordinates exposed in list view

### Admin User List
- Columns exposed: username, role badge, email, phone_number, date_joined
- ❌ No password hashes, session tokens, or sensitive auth data exposed
- Admin users excluded from listing (only CUSTOMER + PHARMACY roles shown)

### Admin Request Monitor
- Columns exposed: request ID, customer username, medicine name, pharmacy name, quantity, status, created_at
- ❌ No personal health data beyond medicine names and quantities exposed
- ❌ No financial transaction data exposed

### Admin Dashboard
- All statistics are aggregate counts (integers) — no PII exposed in tiles
- Recent requests table: same exposure as request monitor
- Pending pharmacy list: same as pharmacy list view

---

## 7. Query Injection Prevention

All search and filter inputs use Django ORM's parameterised queries:

```python
# Example from admin_pharmacy_list_view
queryset = queryset.filter(
    Q(pharmacy_name__icontains=q) |
    Q(registration_number__icontains=q) |
    Q(city__icontains=q) |
    Q(owner__username__icontains=q) |
    Q(owner__email__icontains=q)
)
```

`__icontains` lookups are translated to parameterised SQL — not raw string interpolation. Django's ORM prevents SQL injection by design.

---

## 8. Template XSS Prevention

All template output uses Django's auto-escaping:
- Django templates escape `{{ variable }}` by default
- No `{{ variable|safe }}` or `{% autoescape off %}` used in admin templates
- `json_script` filter used for Chart.js data to safely embed JSON without XSS risk:
  ```django
  {{ cat_labels|json_script:"admin-cat-labels" }}
  ```

---

## 9. Session & Authentication

- Django's session-based authentication is used (no JWT or custom tokens)
- `@login_required` redirects unauthenticated users to `settings.LOGIN_URL`
- Session expiry governed by `SESSION_COOKIE_AGE` in settings

---

## 10. Identified Risk Items (Low Severity)

| Risk | Severity | Note |
|------|----------|------|
| Binary approval toggle (no audit trail stored in DB) | Low | Actions are logged to `medfind` logger; no DB audit log table |
| No "rejected with reason" capability | Informational | Business decision — binary toggle only; can be added as a future enhancement |
| Admin Django panel (`/admin/`) open | Low | Protected by `is_staff`/`is_superuser`; not accessible to `role='ADMIN'` only users unless also `is_staff` |

---

## 11. Security Checklist

- [x] All admin views require authentication
- [x] All admin views require `role='ADMIN'` or superuser/staff
- [x] CSRF tokens on all POST forms
- [x] `@require_POST` on state-mutating endpoints
- [x] `get_object_or_404` on object lookups
- [x] ORM parameterised queries (no raw SQL)
- [x] Django auto-escaping on all template output
- [x] `json_script` for safe JSON embedding
- [x] No sensitive data (passwords, payment) exposed in views
- [x] No `@csrf_exempt` decorators on admin views
