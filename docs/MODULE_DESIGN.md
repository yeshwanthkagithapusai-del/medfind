# MediFind – Module Design Specification

## 1. Modular Architecture Overview
MediFind is organized into 6 specialized Django applications adhering strictly to the separation of concerns:

```
medifind/
├── accounts/        # User lifecycle, authentication, role assignment
├── medicines/       # Drug taxonomy, master catalog, search indexes
├── pharmacies/      # Pharmacy entities, geo-coordinates, verification
├── inventory/       # Stock tracking, threshold triggers, ownership guards
├── requests_app/    # Communication lifecycle between seekers & pharmacies
└── dashboard/       # Specialized role consoles (Customer, Pharmacy, Admin)
```

---

## 2. Module Details

### 2.1 `accounts` Module
- **Purpose**: Unified identity and access management.
- **Key Models**:
  - `User`: Custom user with role choice (`CUSTOMER`, `PHARMACY`, `ADMIN`) and phone number.
- **Key Views & URLs**:
  - `/accounts/register/customer/`: Registration for regular seekers.
  - `/accounts/register/pharmacy/`: Two-in-one registration creating the User and the associated Pharmacy profile in a single atomic transaction.
  - `/accounts/login/`: Role-aware login redirecting users to their designated dashboard.
  - `/accounts/logout/`: Session teardown.
  - `/accounts/profile/`: Profile update view.
- **Security Decorators**:
  - `@customer_required`: Blocks non-customers from posting requests.
  - `@pharmacy_required`: Blocks non-pharmacies from inventory views.
  - `@admin_required`: Protects platform approval and global moderation tools.

### 2.2 `medicines` Module
- **Purpose**: Master pharmaceutical catalog and search indexing.
- **Key Models**:
  - `Medicine`: Catalog record with generic name, strength, dosage form, category, and therapeutic description.
- **Key Views & URLs**:
  - `/medicines/search/`: Public search portal filtering medicines by name, generic, category, and pharmacy city/pincode.
  - `/medicines/<int:pk>/`: Detailed medicine monograph and participating pharmacy stock listing.
- **Search Capabilities**:
  - Case-insensitive `icontains` lookup on `medicine_name`, `generic_name`, `category`, and `strength`.
  - Filter by available stock (`IN_STOCK`, `LOW_STOCK`).
  - Spatial filtering by city and pincode.

### 2.3 `pharmacies` Module
- **Purpose**: Pharmacy registration, geographic profiling, and compliance vetting.
- **Key Models**:
  - `Pharmacy`: Physical retail or hospital pharmacy profile with address, coordinates (`latitude`, `longitude`), and verification flag `is_approved`.
- **Key Views & URLs**:
  - `/pharmacies/<int:pk>/`: Public pharmacy details card showing contact info and in-stock medicines.
  - `/pharmacies/profile/edit/`: Pharmacy owner view to update contact and location details.
  - `/pharmacies/manage/approval/<int:pk>/`: Admin action to toggle approval status.

### 2.4 `inventory` Module
- **Purpose**: Real-time stock maintenance, threshold state machine, and multi-tenant isolation.
- **Key Models**:
  - `Inventory`: Associative entity binding a pharmacy to a catalog medicine with quantity and status.
- **Key Views & URLs**:
  - `/inventory/`: List of medicines stocked by the logged-in pharmacy owner.
  - `/inventory/add/`: Form to stock an existing catalog medicine with quantity.
  - `/inventory/<int:pk>/edit/`: Form to adjust quantity with real-time status re-calculation.
  - `/inventory/<int:pk>/delete/`: Deletion of inventory entry with ownership check.
- **Validation**:
  - Strictly disallows negative values (`MinValueValidator(0)`).
  - Automatically updates `availability_status` (`IN_STOCK` if >10, `LOW_STOCK` if 1..10, `OUT_OF_STOCK` if 0).

### 2.5 `requests_app` Module
- **Purpose**: Direct availability inquiries, response management, and notifications.
- **Key Models**:
  - `AvailabilityRequest`: Inquiry record linking customer, pharmacy, medicine, quantity, status, and response note.
  - `Notification`: In-app alert queue for users.
- **Key Views & URLs**:
  - `/requests/create/<int:pharmacy_id>/<int:medicine_id>/`: Form to initiate an inquiry.
  - `/requests/my-requests/`: Customer dashboard viewing all inquiries and responses.
  - `/requests/pharmacy-inbox/`: Pharmacy owner console to accept (`CONFIRMED`) or reject (`UNAVAILABLE`) requests.
  - `/requests/<int:pk>/respond/`: Pharmacy response action updating status and writing message note.

### 2.6 `dashboard` Module
- **Purpose**: Analytics, high-level operational overview, and quick-action launcher for each user role.
- **Key Views & URLs**:
  - `/dashboard/`: Intelligent dispatcher redirecting user to their specific dashboard:
    - Customer -> `/dashboard/customer/`
    - Pharmacy -> `/dashboard/pharmacy/`
    - Admin -> `/dashboard/admin/`
  - `/dashboard/customer/`: Metrics: searches conducted, requests pending/confirmed, recent activity.
  - `/dashboard/pharmacy/`: Metrics: total medicines, in-stock count, low-stock count, pending requests.
  - `/dashboard/admin/`: Metrics: total users, approved/pending pharmacies, total catalog items, total inventory rows, total inquiries.
