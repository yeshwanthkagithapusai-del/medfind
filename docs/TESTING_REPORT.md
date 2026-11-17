# MediFind – Comprehensive QA & Testing Report

## 1. Quality Assurance Summary
- **Test Framework**: Django Test Runner (`unittest` / `django.test.TestCase`)
- **Backend Environment**: Python 3.11.9, Django 5.2.16 LTS
- **Database Tested**: SQLite (In-Memory Isolation for Test Harness)
- **Total Test Cases Executed**: 17 automated test suites + manual validation
- **Pass Rate**: 100% (0 Failures, 0 Errors, 0 Silenced Warnings)

```
Ran 17 tests in 39.157s
OK
Destroying test database for alias 'default'...
System check identified no issues (0 silenced).
```

---

## 2. Test Execution Matrix

| Test ID | Module | Scenario / Feature Tested | Execution Method | Result | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | `accounts` | Customer Registration & Account Activation | `test_customer_registration` | **PASS** | Creates User with `role='CUSTOMER'` & emits welcome alert |
| **TC-02** | `accounts` & `pharmacies` | Pharmacy Onboarding (Atomic Transaction) | `test_pharmacy_registration` | **PASS** | Creates User (`role='PHARMACY'`) & unapproved Pharmacy profile |
| **TC-03** | `accounts` | Authentication, Login, and Session Teardown | `test_login_logout` | **PASS** | Correctly redirects to role dashboard and clears session |
| **TC-04** | `inventory` | Auto-status Computation & Negative Stock Guard | `test_inventory_status_and_negative_rejection` | **PASS** | `>10`=IN_STOCK, `1..10`=LOW_STOCK, `0`=OUT_OF_STOCK, `<0` rejected |
| **TC-05** | `medicines` & `pharmacies` | Public Search Isolation (Approved Stores Only) | `test_medicine_search_only_shows_approved_pharmacies` | **PASS** | Unapproved pharmacies are strictly filtered from public results |
| **TC-06** | `medicines` | Multi-field Location Filter (City / Pincode) | `test_search_location_filter` | **PASS** | Case-insensitive spatial queries filter correctly |
| **TC-07** | `requests_app` | End-to-end Availability Inquiry Lifecycle | `test_availability_request_workflow` | **PASS** | Customer inquiry -> Pharmacist confirmation -> Notification |
| **TC-08** | `inventory` | Multi-Tenant Security & Isolation (IDOR Defense) | `test_unauthorized_inventory_modification` | **PASS** | Pharmacy A cannot edit/delete Pharmacy B's inventory (404) |
| **TC-09** | `pharmacies` | Admin Pharmacy Approval Toggle Action | `test_admin_pharmacy_approval` | **PASS** | Admin toggles verification state; notifies store owner |
| **TC-10** | `pharmacies` (services) | Haversine Formula Distance Calculation | `test_haversine_calculation` | **PASS** | Accurately calculates km between coordinates (~500 km Hyd-Blr) |
| **TC-11** | `medicines` | Geolocation Search & Nearest-First Sort | `test_search_with_distance_and_sort` | **PASS** | Computes distance to pharmacies and sorts nearest first |
| **TC-12** | `medicines` (admin) | Master Catalogue Curation (Add & Edit Drug) | `test_admin_medicine_management` | **PASS** | Admin adds new drug and edits existing catalog record |
| **TC-13** | `inventory` | Inventory Deletion & Multi-Tenant IDOR Guard | `test_inventory_delete` | **PASS** | Owner can delete item; foreign pharmacy blocked with 404 |
| **TC-14** | `requests_app` | Customer Pending Inquiry Cancellation | `test_customer_cancel_request` | **PASS** | Customer cancels pending inquiry; status updates to CANCELLED |
| **TC-15** | `dashboard` | Role-Based Dispatcher Redirection | `test_dashboard_dispatcher` | **PASS** | Routes Customer, Pharmacy, Admin to appropriate dashboard |
| **TC-16** | `accounts` (security) | RBAC Role Access Protection Guards | `test_role_access_guards` | **PASS** | Blocks customer from inventory and admin views with redirect |
| **TC-17** | `requests_app` | In-App Notification Center Read Lifecycle | `test_notification_flow` | **PASS** | Reads and updates notification status from unread to read |

---

## 3. Security & Boundary Verification
1. **Multi-Tenant Isolation (IDOR Defense)**: Verified that an authenticated pharmacy owner cannot view, edit, or delete another pharmacy's stock by directly manipulating URL parameters (strictly returns 404).
2. **Access Control**: Unauthenticated visitors attempting to create an inquiry or manage inventory are redirected to login. Role decorators enforce that only pharmacy owners can manage inventory and only administrators can approve pharmacies or curate master catalogue drugs.
3. **Data Integrity**: Relational database constraints (`unique_together = ('pharmacy', 'medicine')` and `MinValueValidator(0)`) prevent duplicate and corrupt stock entries.
4. **XSS & CSRF Defense**: All state-altering forms employ Django CSRF tokens. All template variables are escaped.
5. **Safe Stock Disclaimers**: Public views flag reported stock as "Pharmacy-reported last at [Timestamp]" to prevent medical misrepresentation.
