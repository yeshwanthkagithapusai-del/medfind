# MediFind – Database Architecture Document

## 1. Overview
The database layer for MediFind utilizes a normalized relational architecture managed via the Django 5.2 ORM. It guarantees referential integrity, eliminates redundant storage, prevents anomalous inventory operations, and optimizes lookup performance with strategic database indexing.

## 2. Entity Relationship Specifications

### 2.1 Custom User (`accounts_user`)
Inherits from Django's `AbstractUser`, configured as `AUTH_USER_MODEL` before initial migration.
- `id`: AutoField (Primary Key)
- `username`: CharField(150, unique=True)
- `email`: EmailField(unique=True)
- `password`: CharField(128) - PBKDF2 with SHA256 hashed
- `role`: CharField(20, choices=[('CUSTOMER', 'Customer'), ('PHARMACY', 'Pharmacy Owner'), ('ADMIN', 'Administrator')])
- `phone_number`: CharField(15, blank=True)
- `date_joined`: DateTimeField(auto_now_add=True)
- `is_active`: BooleanField(default=True)
- `is_staff`: BooleanField(default=False)
- `is_superuser`: BooleanField(default=False)

### 2.2 Pharmacy (`pharmacies_pharmacy`)
Represents registered pharmacy units operated by pharmacy owners.
- `id`: AutoField (Primary Key)
- `owner`: OneToOneField/ForeignKey to `User` (on_delete=models.CASCADE, related_name='pharmacy')
- `pharmacy_name`: CharField(200)
- `registration_number`: CharField(100, unique=True, db_index=True)
- `address`: TextField()
- `city`: CharField(100, db_index=True)
- `state`: CharField(100)
- `pincode`: CharField(20, db_index=True)
- `phone_number`: CharField(15)
- `latitude`: DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
- `longitude`: DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
- `is_approved`: BooleanField(default=False, db_index=True)
- `created_at`: DateTimeField(auto_now_add=True)

### 2.3 Medicine (`medicines_medicine`)
Master catalog of verified medicines.
- `id`: AutoField (Primary Key)
- `medicine_name`: CharField(200, db_index=True)
- `generic_name`: CharField(200, db_index=True)
- `strength`: CharField(100) (e.g., "500 mg", "10 ml", "250 mcg")
- `dosage_form`: CharField(100) (e.g., "Tablet", "Capsule", "Syrup", "Injection", "Ointment")
- `category`: CharField(100, db_index=True) (e.g., "Antibiotics", "Analgesics", "Antidiabetic", etc.)
- `description`: TextField(blank=True)
- `created_at`: DateTimeField(auto_now_add=True)

### 2.4 Inventory (`inventory_inventory`)
Bridge relation associating specific pharmacies with stock levels of medicine catalog items.
- `id`: AutoField (Primary Key)
- `pharmacy`: ForeignKey to `Pharmacy` (on_delete=models.CASCADE, related_name='inventories')
- `medicine`: ForeignKey to `Medicine` (on_delete=models.CASCADE, related_name='pharmacy_inventories')
- `quantity`: PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
- `availability_status`: CharField(20, choices=[('IN_STOCK', 'In Stock'), ('LOW_STOCK', 'Low Stock'), ('OUT_OF_STOCK', 'Out of Stock')], default='OUT_OF_STOCK', db_index=True)
- `updated_at`: DateTimeField(auto_now=True)
- **Constraints**:
  - `unique_together = ('pharmacy', 'medicine')`
  - Automatic status derivation in `save()`:
    - `quantity == 0` -> `OUT_OF_STOCK`
    - `1 <= quantity <= 10` -> `LOW_STOCK`
    - `quantity > 10` -> `IN_STOCK`

### 2.5 AvailabilityRequest (`requests_app_availabilityrequest`)
Customer-initiated inquiry lifecycle entity.
- `id`: AutoField (Primary Key)
- `customer`: ForeignKey to `User` (on_delete=models.CASCADE, related_name='customer_requests')
- `pharmacy`: ForeignKey to `Pharmacy` (on_delete=models.CASCADE, related_name='pharmacy_requests')
- `medicine`: ForeignKey to `Medicine` (on_delete=models.CASCADE, related_name='availability_requests')
- `quantity_requested`: PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
- `request_message`: TextField(blank=True)
- `status`: CharField(20, choices=[('PENDING', 'Pending'), ('CONFIRMED', 'Confirmed Available'), ('UNAVAILABLE', 'Unavailable'), ('CANCELLED', 'Cancelled')], default='PENDING', db_index=True)
- `pharmacy_response`: TextField(blank=True)
- `created_at`: DateTimeField(auto_now_add=True)
- `updated_at`: DateTimeField(auto_now=True)

### 2.6 Notification (`requests_app_notification`)
User notification messaging queue.
- `id`: AutoField (Primary Key)
- `user`: ForeignKey to `User` (on_delete=models.CASCADE, related_name='notifications')
- `message`: TextField()
- `is_read`: BooleanField(default=False)
- `created_at`: DateTimeField(auto_now_add=True)

## 3. Database Indexes & Query Optimizations
- `medicines_medicine(medicine_name, generic_name, category)` indexed for fast multi-field ILIKE searching.
- `pharmacies_pharmacy(city, pincode, is_approved)` indexed to filter public stock queries quickly.
- `inventory_inventory(availability_status, updated_at)` indexed for dashboard aggregation metrics.
- `unique_together` on `Inventory(pharmacy, medicine)` prevents accidental duplicate inventory rows.
