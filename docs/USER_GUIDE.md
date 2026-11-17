# MediFind – User Guide & College Demonstration Runbook

## 1. Introduction
**MediFind** is a location-based medicine availability finder and pharmacy inventory management platform. This guide provides step-by-step instructions for running, testing, and demonstrating the complete application during final-year CSE project examinations.

---

## 2. Project Quickstart Guide

### 2.1 Starting the Application
Open a terminal in the project directory (`medi finder project.1` or `medifind`) and execute:

```bash
# 1. Verify Django System Checks
python manage.py check

# 2. Run Database Migrations
python manage.py migrate

# 3. Populate Pre-Seeded Demonstration Dataset (If not already loaded)
python manage.py seed_data

# 4. Launch Development Server
python manage.py runserver
```

Open your web browser and navigate to: `http://127.0.0.1:8000/`

---

## 3. Demonstration Accounts & Credentials

The pre-seeded database contains realistic demonstration accounts ready for evaluation:

| Role | Username | Password | Operational Purpose |
| :--- | :--- | :--- | :--- |
| **Platform Administrator** | `admin` | `admin123` | Pharmacy approval, Master catalogue curation, System metrics |
| **Pharmacy Owner (Approved)** | `apollo_owner` | `password123` | Manages stock at *[DEMO] Apollo Healthcare Store*, handles inquiries |
| **Pharmacy Owner (Approved)** | `medplus_owner` | `password123` | Manages stock at *[DEMO] MedPlus Pharma Hub* |
| **Pharmacy Owner (Pending)** | `pending_owner` | `password123` | Demonstrates pending verification state and admin approval |
| **Patient / Customer 1** | `customer1` | `password123` | Search medicines, check availability, send requests |
| **Patient / Customer 2** | `customer2` | `password123` | Send requests and receive notifications |

---

## 4. End-to-End Examiner Demonstration Walkthrough

### Step 1: Public Discovery & Location Search
1. Open `http://127.0.0.1:8000/`.
2. Observe the **Healthcare Landing Page**, real-time metric counters, and the medical disclaimer banner.
3. In the search box, search for **"Dolo"** or **"Insulin"**.
4. Filter by City: **"Hyderabad"** or **"Bengaluru"**.
5. Click **"Interactive Map"** toggle to view OpenStreetMap pins showing participating pharmacy retail locations with real-time stock popups.

### Step 2: Patient Availability Inquiry
1. Log in as `customer1` (password: `password123`).
2. Search for **"Dolo 650"** and click **"Request Availability"** for *[DEMO] Apollo Healthcare Store*.
3. Enter requested quantity (e.g., 2 units) and an urgency message: *"Prescription in hand, can you hold for 1 hour?"*
4. Click **"Send Request"**.
5. You are redirected to your **My Requests** dashboard where the status is displayed as **Pending**.

### Step 3: Pharmacist Inventory & Inquiry Response
1. Log out, then log in as `apollo_owner` (password: `password123`).
2. Notice the **Pharmacy Dashboard** featuring:
   - Doughnut Chart of stock distribution (In Stock, Low Stock, Out of Stock).
   - Pending inquiries notification counter.
3. Click **"Customer Inquiries"** in the top navigation.
4. Click **"Respond"** on Customer 1's request.
5. Select **"Confirm Medicine Available for Pickup"**, enter note: *"Reserved at front counter 2 until 9 PM"*, and submit.
6. Click **"Stock Inventory"** to inspect CRUD operations. Click **"Update"** on any item to adjust quantity (notice auto-recalculation of status).

### Step 4: Patient Notification Verification
1. Log out, then log back in as `customer1`.
2. Notice the **Notification Bell** badge count in the top right.
3. Navigate to **"My Requests"**: the status has updated to **Confirmed Available** with the pharmacist's note.

### Step 5: Admin Approval Workflow
1. Log in as `admin` (password: `admin123`).
2. Visit **Admin Dashboard**: view system-wide stats and the **Drug Indications Bar Chart**.
3. In the **"Pending Pharmacy Approvals"** table, notice *[DEMO] Metro Life Pharmacy*.
4. Click **"Approve"**. The pharmacy is instantly verified and will now appear in public medicine searches.
5. Click **"Medicine Catalogue"** to demonstrate adding a new pharmaceutical formulation.
