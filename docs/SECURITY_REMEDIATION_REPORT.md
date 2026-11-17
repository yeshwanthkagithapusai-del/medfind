# MediFind – Security Remediation & Code Modification Report

**Author**: Senior Django Security Engineer & Application Security Architect  
**Project**: MediFind  
**Phase**: Phase 1 – Security Hardening & Vulnerability Remediation  
**Date**: November 17, 2026  
**Status**: All Critical & High Vulnerabilities Remediated and Verified  

---

## 1. Executive Summary

This report documents the exact source code, configuration, and template modifications executed during Phase 1. Every change was performed with zero disruption to existing business logic, zero destructive database alterations, and full backward compatibility.

---

## 2. Inventory of Modified Files

| File Modified | Component | Category | Purpose of Remediation |
| :--- | :--- | :--- | :--- |
| `pharmacies/views.py` | Backend View | Security / HTTP Method | Enforced `@require_POST` on `toggle_pharmacy_approval_view`. |
| `requests_app/views.py` | Backend View | Security & RBAC | Enforced `@require_POST` on `cancel_request_view`; applied `@customer_required`. |
| `accounts/views.py` | Backend View | Security / HTTP Method | Enforced `@require_POST` on `mark_notification_read`. |
| `accounts/forms.py` | Forms Validation | Auth / Validation | Wired `password_validation.validate_password()`; added email uniqueness in profile. |
| `config/settings.py` | Configuration | Security Headers | Configured `SECURE_CONTENT_TYPE_NOSNIFF`, `SESSION_COOKIE_HTTPONLY`, and conditional SSL/HSTS. |
| `templates/requests/customer_list.html` | Presentation | CSRF & Form Security | Refactored cancellation `<a>` link into secure `<form method="POST">` with `{% csrf_token %}`. |
| `tests/test_features.py` | Automated Tests | Test Harness | Updated notification read test call to `POST`. |
| `tests/test_security.py` | Automated Tests | Security Test Suite | Authored 12 comprehensive security unit and integration tests (new file). |

---

## 3. Granular Code Changes & Diffs

### 3.1 `pharmacies/views.py`
- **Location**: Lines 77–81
- **Modification**: Imported `require_POST` from `django.views.decorators.http` and applied it to `toggle_pharmacy_approval_view`:
  ```python
  from django.views.decorators.http import require_POST

  @admin_required
  @require_POST
  def toggle_pharmacy_approval_view(request, pk):
      pharmacy = get_object_or_404(Pharmacy, pk=pk)
      pharmacy.is_approved = not pharmacy.is_approved
      pharmacy.save()
  ```
- **Security Impact**: Rejects HTTP GET with `405 Method Not Allowed`, preventing CSRF and prefetch state toggles.

---

### 3.2 `requests_app/views.py`
- **Location**: Lines 10, 51, 126
- **Modification**:
  - Replaced `@login_required` with `@customer_required` on `create_request_view` and `customer_requests_list_view`.
  - Decorated `cancel_request_view` with `@customer_required` and `@require_POST`:
  ```python
  from django.views.decorators.http import require_POST
  from accounts.decorators import customer_required, pharmacy_required

  @customer_required
  @require_POST
  def cancel_request_view(request, pk):
      req_obj = get_object_or_404(AvailabilityRequest, pk=pk, customer=request.user)
      if req_obj.status == 'PENDING':
          req_obj.status = 'CANCELLED'
          req_obj.save()
          messages.success(request, f"Request #{req_obj.id} has been cancelled.")
      else:
          messages.error(request, "Only pending requests can be cancelled.")
      return redirect('customer_requests')
  ```
- **Security Impact**: Enforces strict RBAC and eliminates GET-based inquiry cancellations.

---

### 3.3 `accounts/views.py`
- **Location**: Lines 138–144
- **Modification**: Applied `@require_POST` to `mark_notification_read`:
  ```python
  from django.views.decorators.http import require_POST

  @login_required
  @require_POST
  def mark_notification_read(request, pk):
      notif = get_object_or_404(Notification, pk=pk, user=request.user)
      notif.is_read = True
      notif.save()
      messages.success(request, "Notification marked as read.")
      return redirect('notifications')
  ```
- **Security Impact**: Eliminates GET-based alert mutation.

---

### 3.4 `accounts/forms.py`
- **Location**: `CustomerRegistrationForm`, `PharmacyRegistrationForm`, `UserProfileForm`
- **Modification**:
  - Imported `password_validation` and `ValidationError`.
  - Added password strength validation invoking all configured `AUTH_PASSWORD_VALIDATORS`.
  - Added profile email uniqueness check in `UserProfileForm`:
  ```python
  def clean_email(self):
      email = self.cleaned_data.get('email')
      if email and User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
          raise forms.ValidationError("A user with this email address already exists.")
      return email
  ```
- **Security Impact**: Blocks trivial passwords (`123456`, dictionary words) during registration and prevents account hijacking via duplicate email updating.

---

### 3.5 `config/settings.py`
- **Location**: Lines 117–134
- **Modification**: Added security header configuration:
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
- **Security Impact**: Protects against MIME-sniffing, XSS cookie exfiltration, and framing attacks, with full HTTPS readiness for cloud staging/production.

---

### 3.6 `templates/requests/customer_list.html`
- **Location**: Lines 70–78
- **Modification**: Refactored cancellation hyperlink into an inline POST form:
  ```html
  <td class="text-end">
    {% if req.status == 'PENDING' %}
      <form method="POST" action="{% url 'cancel_request' req.id %}" class="d-inline" onsubmit="return confirm('Cancel this pending request?');">
        {% csrf_token %}
        <button type="submit" class="btn btn-sm btn-outline-danger">
          Cancel
        </button>
      </form>
    {% endif %}
  </td>
  ```
- **Security Impact**: Aligns frontend template with backend `@require_POST` security guard.
