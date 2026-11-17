# MediFind Service Layer Documentation

**Document Version:** 1.0  
**Phase:** Backend Architecture Enhancement and Code Quality Improvement  
**Date:** November 2026  
**System:** MediFind (Three-Tier Modular Monolith)  
**Author:** Senior Python Developer & Django Software Architect  

---

## 1. Architectural Philosophy

The MediFind service layer establishes a clean boundary between presentation (HTTP views) and domain logic (business operations). Prior to this enhancement, Django views acted as "fat controllers", directly executing database transactions, dispatching notifications, parsing search algorithms, and computing analytics.

With the introduction of the service layer:
* **Views** are responsible solely for:
  1. Receiving HTTP requests and validating incoming parameters / forms.
  2. Enforcing authentication, role authorization, and HTTP verb restrictions.
  3. Calling the appropriate domain service function.
  4. Setting user-facing flash messages (`django.contrib.messages`).
  5. Returning HTTP redirects or rendering templates.
* **Services** are responsible for:
  1. Orchestrating multi-model atomic transactions.
  2. Enforcing core business rules and multi-tenant scoping.
  3. Dispatching internal domain notifications.
  4. Emitting structured security and operational log events.
  5. Returning clean Python objects, tuples, or querysets.

---

## 2. Detailed Service Catalog by Application

### 2.1 Accounts Services (`accounts/services.py`)

#### `register_customer(cleaned_data: Dict[str, Any]) -> User`
* **Purpose:** Registers a standard customer account and dispatches a welcome notification.
* **Parameters:** `cleaned_data` (validated form dictionary containing username, email, password, phone_number, first_name, last_name).
* **Behavior:**
  - Instantiates `User` with `role='CUSTOMER'`.
  - Hashes password via `set_password()`.
  - Creates a welcome `Notification` record.
  - Logs registration via `logger.info()`.
* **Returns:** The newly persisted `User` instance.

#### `register_pharmacy(cleaned_data: Dict[str, Any]) -> Pharmacy`
* **Purpose:** Atomically registers a pharmacy owner user account and their linked pharmacy profile.
* **Parameters:** `cleaned_data` (validated form dictionary containing user credentials and pharmacy metadata).
* **Behavior:**
  - Wraps operations in `transaction.atomic()`.
  - Creates `User` with `role='PHARMACY'`.
  - Creates `Pharmacy` record linked to owner with `is_approved=False`.
  - Dispatches verification pending `Notification`.
  - Logs pharmacy registration.
* **Returns:** The newly persisted `Pharmacy` instance.

#### `authenticate_user(request, username: str, password: str) -> Tuple[Optional[User], Optional[str]]`
* **Purpose:** Authenticates user credentials while emitting audit logs and neutralizing enumeration attacks.
* **Parameters:** `request`, `username`, `password`.
* **Behavior:**
  - Calls `django.contrib.auth.authenticate()`.
  - Checks `user.is_active`.
  - Logs warnings on failed attempts or inactive user access.
* **Returns:** `(user, None)` on success, or `(None, error_message)` on failure.

#### `mark_notification_as_read(notification_id: int, user: User) -> Notification`
* **Purpose:** Marks a single notification as read with tenant-scoping.
* **Parameters:** `notification_id`, `user`.
* **Returns:** Updated `Notification` instance.

#### `mark_all_notifications_as_read(user: User) -> int`
* **Purpose:** Bulk-acknowledges all unread notifications for a user in a single SQL UPDATE query.
* **Returns:** Number of updated rows.

---

### 2.2 Medicines Services (`medicines/services.py`)

#### `search_medicine_inventory(...) -> Tuple[List[Inventory], bool, List[Dict[str, Any]]]`
* **Purpose:** Executes multi-parameter search across approved pharmacy inventories with optional geolocation sorting.
* **Parameters:** `query`, `category`, `city`, `pincode`, `stock_status`, `user_lat`, `user_lng`, `sort_by`.
* **Behavior:**
  - Queries `Inventory.objects.filter(pharmacy__is_approved=True).select_related('medicine', 'pharmacy')`.
  - Applies `Q` filters across medicine name, generic name, strength, category, and pharmacy name.
  - Computes Haversine distance if coordinates are supplied.
  - Sorts by distance if `sort_by == 'distance'`.
  - Extracts unique map pins for Leaflet.js.
  - Logs search execution details.
* **Returns:** `(inventory_results, has_user_coords, map_pins)`.

#### `get_search_filter_options() -> Tuple[List[str], List[str]]`
* **Purpose:** Retrieves distinct medicine categories and active pharmacy cities for dropdown filters.
* **Returns:** `(categories, sorted_distinct_cities)`.

#### `get_medicine_detail_data(medicine_id: int) -> Tuple[Medicine, QuerySet, List[Dict[str, Any]]]`
* **Purpose:** Retrieves medicine catalog item, all approved stocking pharmacies, and map pin coordinates.
* **Returns:** `(medicine, stock_records, map_pins)`.

---

### 2.3 Pharmacies Services (`pharmacies/services.py`)

#### `calculate_haversine_distance(lat1, lon1, lat2, lon2) -> Optional[float]`
* **Purpose:** Computes great-circle distance between two GPS coordinates in kilometers.
* **Returns:** Distance rounded to 2 decimal places, or `None` if coordinates are invalid.

#### `get_pharmacy_for_user(user) -> Optional[Pharmacy]`
* **Purpose:** Safely retrieves the pharmacy entity owned by an authenticated user.
* **Returns:** `Pharmacy` instance or `None`.

#### `toggle_pharmacy_approval(pharmacy_id: int, admin_user) -> Tuple[Pharmacy, bool, str]`
* **Purpose:** Inverts the approval status of a pharmacy, sends an alert to the pharmacy owner, and records an admin audit log.
* **Returns:** `(pharmacy, new_status_bool, status_display_string)`.

#### `get_pharmacy_detail_data(pharmacy_id: int, user) -> Tuple[Optional[Pharmacy], Optional[QuerySet], Optional[Dict[str, Any]], bool]`
* **Purpose:** Fetches pharmacy profile and stock items, enforcing that unapproved pharmacies cannot be viewed by the public.
* **Returns:** `(pharmacy, inventory_items, map_pin, is_authorized)`.

---

### 2.4 Inventory Services (`inventory/services.py`)

#### `get_inventory_counts(pharmacy: Pharmacy) -> Dict[str, int]`
* **Purpose:** Computes stock summary badges using a single SQL query with conditional aggregation.
* **SQL Optimization:** Combines 4 `COUNT(*)` queries into 1 `SELECT COUNT(id), COUNT(CASE WHEN ...) FROM inventory...`.
* **Returns:** Dictionary with keys: `total_count`, `in_stock_count`, `low_stock_count`, `out_stock_count`.

#### `get_filtered_inventory(pharmacy: Pharmacy, query: str = '', status_filter: str = '') -> QuerySet`
* **Purpose:** Retrieves pharmacy stock items with keyword and status filtering, applying `select_related('medicine')`.
* **Returns:** Ordered `Inventory` QuerySet.

#### `add_or_update_inventory(pharmacy: Pharmacy, medicine: Medicine, quantity: int) -> Tuple[Inventory, bool]`
* **Purpose:** Safely increments existing stock or adds a new inventory item.
* **Returns:** `(inventory_item, created_bool)`.

#### `delete_inventory_item(pharmacy: Pharmacy, pk: int) -> Tuple[bool, str]`
* **Purpose:** Deletes an inventory record ensuring multi-tenant ownership scoping (`pharmacy=pharmacy`).
* **Returns:** `(True, deleted_medicine_name)`.

---

### 2.5 Requests Services (`requests_app/services.py`)

#### `create_availability_inquiry(customer, pharmacy: Pharmacy, medicine: Medicine, quantity_requested: int, request_message: str = '') -> AvailabilityRequest`
* **Purpose:** Creates a medicine inquiry record with status `PENDING` and alerts the pharmacy owner.
* **Returns:** Persisted `AvailabilityRequest` instance.

#### `get_pharmacy_inbox_counts(pharmacy: Pharmacy) -> Dict[str, int]`
* **Purpose:** Computes request status badges using a single consolidated aggregate query.
* **Returns:** Dictionary with keys: `pending_count`, `confirmed_count`, `unavailable_count`.

#### `respond_to_availability_inquiry(request_id: int, pharmacy: Pharmacy, status: str, pharmacy_response: str) -> AvailabilityRequest`
* **Purpose:** Records pharmacy response notes and status update, alerting the customer.
* **Returns:** Updated `AvailabilityRequest` instance.

#### `cancel_availability_inquiry(request_id: int, customer) -> Tuple[bool, str]`
* **Purpose:** Cancels a pending request with customer ownership verification.
* **Returns:** `(success_bool, message_str)`.

---

### 2.6 Dashboard Services (`dashboard/services.py`)

#### `get_home_page_metrics() -> Dict[str, Any]`
* **Purpose:** Aggregates public statistics for approved pharmacies, catalog medicines, and in-stock listings.

#### `get_customer_dashboard_metrics(user) -> Dict[str, Any]`
* **Purpose:** Computes customer inquiry statistics via conditional aggregation, recent requests, and notifications.

#### `get_pharmacy_dashboard_metrics(pharmacy: Pharmacy) -> Dict[str, Any]`
* **Purpose:** Assembles stock metrics, pending inquiries, recent inventory updates, and Chart.js distribution datasets.

#### `get_admin_dashboard_metrics() -> Dict[str, Any]`
* **Purpose:** Aggregates platform user counts, verification queues, recent requests, and medicine category distribution.

---

## 3. Benefits Realized

1. **Testability:** Domain logic can be unit-tested directly without constructing mock HTTP requests or handling template rendering.
2. **Reusability:** Services can be invoked by CLI management commands, asynchronous Celery tasks, or REST APIs without code duplication.
3. **Maintainability:** Views average fewer than 30 lines of clean code, strictly focused on request handling.
4. **Security:** Multi-tenant scoping and IDOR protections are centralized inside service boundaries.
