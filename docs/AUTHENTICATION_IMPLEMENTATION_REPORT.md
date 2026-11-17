# MediFind Authentication & Identity Implementation Report

**Project:** MediFind – Location-Based Medicine Availability and Pharmacy Inventory Management Platform  
**Document:** Technical Implementation Specification & Architecture Audit  
**Phase:** Phase 3 – Authentication & User Profile Enhancement  
**Status:** Completed & 100% Verified (58/58 Tests Passing)  
**Date:** November 2026  
**Engineering Discipline:** Senior Django Authentication Engineering & Backend Architecture  

---

## 1. Executive Summary

As part of **Phase 3: Authentication and User Profile Enhancement**, the authentication, registration, session management, and access perimeter of MediFind were thoroughly hardened and modernized. The implementation strictly preserves the existing Three-Tier Modular Monolith without introducing external dependencies or altering the established data model relationships.

### Key Deliverables Completed:
1. **Enhanced Customer Registration:** Integrated full name capture (`first_name`, `last_name`), strict email validation, case-insensitive duplicate prevention, and Django-governed password complexity validation.
2. **Pharmacy Facility Onboarding:** Refined atomic pharmacy owner and facility registration (`register_pharmacy`) enforcing default unapproved status (`is_approved=False`) to prevent unvetted retail visibility.
3. **Open Redirect Remediation & Safe Sessions:** Hardened `login_view` against open redirect attacks using `url_has_allowed_host_and_scheme`, integrated password visibility toggles, and enforced session flushing upon logout.
4. **Unified Role-Based Dispatching:** Cleanly orchestrated role redirects from `/dashboard/` to role-specific interfaces (`/dashboard/customer/`, `/dashboard/pharmacy/`, `/dashboard/admin/`).
5. **Modernized Password Management:** Implemented the complete 6-stage tokenized password reset and password change suite utilizing Django's built-in cryptographic token infrastructure.

---

## 2. Architecture & Application Boundaries

All authentication logic remains encapsulated within the `accounts` application, interacting through explicit service boundaries:

```mermaid
flowchart TD
    subgraph Client Tier [Presentation Layer]
        LoginForm[templates/accounts/login.html]
        CustRegForm[templates/accounts/register_customer.html]
        PharmRegForm[templates/accounts/register_pharmacy.html]
        ProfileView[templates/accounts/profile.html]
        PwdChangeForm[templates/accounts/password_change.html]
        PwdResetForm[templates/accounts/password_reset.html]
    end

    subgraph Service Tier [accounts/services.py]
        AuthService[authenticate_user]
        CustRegService[register_customer]
        PharmRegService[register_pharmacy]
        ProfileService[UserProfileForm & PharmacyProfileForm]
    end

    subgraph Data Tier [ORM & Database]
        UserModel[(accounts_user)]
        PharmModel[(pharmacies_pharmacy)]
        NotifModel[(requests_app_notification)]
    end

    LoginForm -->|POST /accounts/login/| AuthService
    CustRegForm -->|POST /accounts/register/customer/| CustRegService
    PharmRegForm -->|POST /accounts/register/pharmacy/| PharmRegService
    ProfileView -->|POST /accounts/profile/| ProfileService

    AuthService --> UserModel
    CustRegService --> UserModel
    CustRegService --> NotifModel
    PharmRegService --> UserModel
    PharmRegService --> PharmModel
    PharmRegService --> NotifModel
```

---

## 3. Customer Registration Architecture

### 3.1 Field Hierarchy & Data Mapping
The customer registration form (`CustomerRegistrationForm`) maps directly to the custom `User` model (`AbstractUser` subclass):
- **Full Name:** Captures `first_name` and `last_name`. Optional on the form to maintain 100% backward compatibility with automated integration tests, but surfaced prominently in the user interface.
- **Account Identifiers:** Captures unique `username` and unique `email`.
- **Contact:** Captures mobile `phone_number`.
- **Credentials:** Captures `password` and `confirm_password` with client-side interactive visibility toggles.

### 3.2 Duplicate Prevention & Sanitization
Registration incorporates case-insensitive duplicate checks to prevent username/email squatting:
```python
def clean_email(self):
    email = self.cleaned_data.get('email', '').strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise forms.ValidationError("A user with this email address already exists.")
    return email

def clean_username(self):
    username = self.cleaned_data.get('username', '').strip()
    if User.objects.filter(username__iexact=username).exists():
        raise forms.ValidationError("This username is already taken.")
    return username
```

### 3.3 Password Complexity Validation
Passwords are systematically audited against Django's `AUTH_PASSWORD_VALIDATORS`:
1. `UserAttributeSimilarityValidator` (prevents passwords matching username or email).
2. `MinimumLengthValidator` (enforces 8 characters minimum).
3. `CommonPasswordValidator` (rejects top 20,000 common passwords).
4. `NumericPasswordValidator` (rejects entirely numeric strings).

Passwords are encrypted using Django's default PBKDF2 with SHA-256 hash algorithm (600,000 iterations).

---

## 4. Pharmacy Registration & Vetting Perimeter

### 4.1 Atomic Two-Entity Creation
When a pharmacy self-registers, the backend wraps user creation and physical pharmacy record generation in a single database transaction (`transaction.atomic()`):

1. **Owner User Account:** Created with role `PHARMACY`.
2. **Pharmacy Facility Profile:** Created with `is_approved=False`, storing store trade name, drug license registration number, address, city, state, pincode, phone, and optional GPS coordinates.
3. **Audit Notification:** Generates an initial pending-verification notification for the pharmacy owner.

### 4.2 Security Isolation Guarantee
A freshly registered pharmacy is strictly isolated from public search:
- Excluded from `medicines/services.py:search_medicine_inventory` (`pharmacy__is_approved=True`).
- Excluded from landing page metrics and featured pharmacy carousels.
- Excluded from public pharmacy inventory listings.
- Only platform administrators can toggle `is_approved` via the protected admin console.

---

## 5. Login, Session Management & Safe Redirects

### 5.1 Open Redirect Remediation
Previous versions accepted raw `?next=` URL parameters, which could allow external phishing redirects. The enhanced `login_view` validates redirect targets:
```python
next_url = request.GET.get('next') or request.POST.get('next')
if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
    return redirect(next_url)
return redirect('dashboard')
```
If an attacker attempts `?next=https://malicious-phishing.com`, the URL fails validation and the user is redirected safely to their role-based internal dashboard.

### 5.2 Session Invalidation on Logout
The `logout_view` invokes Django's `django.contrib.auth.logout(request)`:
- Flushes session keys completely from the database backend.
- Deletes session cookies.
- Prevents session fixation attacks and session replay.

---

## 6. User Experience & Design System Standards

1. **Password Visibility Toggles:** Integrated accessible eye icon buttons (`togglePasswordVisibility`) on all authentication forms allowing users to review typed input.
2. **Evaluation Demonstration Credentials:** Maintained clear, distinct testing credentials on `/accounts/login/` for seamless academic and grading reviews.
3. **Validation Feedback:** Styled form error alerts using the MediFind color palette (`#102A43` Primary, `#0EA5A4` Secondary, `#DC2626` Danger).
