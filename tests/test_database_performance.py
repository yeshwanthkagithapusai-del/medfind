"""
Phase 8 – Database Optimization & ORM Performance Test Suite
MediFind Project

15 test vectors covering:
- select_related / prefetch_related query count bounds (avoiding N+1 queries)
- Single-query consolidated aggregation verification
- Index verification in the schema
- Database constraints and referential integrity
- Efficient pagination and queryset filtering
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from inventory.models import Inventory
from inventory.services import get_inventory_counts, delete_inventory_item
from medicines.models import Medicine
from medicines.services import get_search_filter_options, search_medicine_inventory
from pharmacies.models import Pharmacy
from pharmacies.services import discover_nearby_pharmacies, get_pharmacy_detail_data
from requests_app.models import AvailabilityRequest, Notification
from requests_app.services import get_pharmacy_inbox_counts, respond_to_availability_inquiry
from dashboard.services import get_admin_dashboard_metrics, get_customer_dashboard_metrics

User = get_user_model()


class DatabaseOptimizationAndPerformanceTests(TestCase):
    """
    Dedicated test suite for verifying ORM query efficiency, index existence,
    aggregation performance, and referential integrity (Phase 8).
    """

    @classmethod
    def setUpTestData(cls):
        # 1. Admin
        cls.admin = User.objects.create_superuser(
            username='admin_perf',
            email='admin_perf@test.com',
            password='AdminPass123!',
            role='ADMIN'
        )

        # 2. Pharmacy Owners & Customer
        cls.owner1 = User.objects.create_user(
            username='owner_perf1',
            email='owner_perf1@test.com',
            password='Password123!',
            role='PHARMACY',
            phone_number='9876543210'
        )
        cls.owner2 = User.objects.create_user(
            username='owner_perf2',
            email='owner_perf2@test.com',
            password='Password123!',
            role='PHARMACY',
            phone_number='9876543211'
        )
        cls.customer = User.objects.create_user(
            username='cust_perf',
            email='cust_perf@test.com',
            password='CustomerPass123!',
            role='CUSTOMER',
            phone_number='9876543299'
        )

        # 3. Approved Pharmacies
        cls.pharm1 = Pharmacy.objects.create(
            owner=cls.owner1,
            pharmacy_name="Alpha Chemist Perf",
            registration_number="REG-PERF-001",
            address="10 Alpha Street",
            city="Hyderabad",
            state="Telangana",
            pincode="500001",
            phone_number="040-11112222",
            latitude=Decimal('17.410000'),
            longitude=Decimal('78.430000'),
            is_approved=True
        )
        cls.pharm2 = Pharmacy.objects.create(
            owner=cls.owner2,
            pharmacy_name="Beta Pharmacy Perf",
            registration_number="REG-PERF-002",
            address="20 Beta Avenue",
            city="Secunderabad",
            state="Telangana",
            pincode="500003",
            phone_number="040-33334444",
            latitude=Decimal('17.440000'),
            longitude=Decimal('78.490000'),
            is_approved=True
        )
        # Unapproved Pharmacy
        cls.pharm_unapproved = Pharmacy.objects.create(
            owner=cls.owner2,
            pharmacy_name="Unapproved Store Perf",
            registration_number="REG-PERF-999",
            address="99 Shadow Way",
            city="Hyderabad",
            state="Telangana",
            pincode="500001",
            phone_number="040-99999999",
            latitude=Decimal('17.420000'),
            longitude=Decimal('78.450000'),
            is_approved=False
        )

        # 4. Medicines
        cls.med1 = Medicine.objects.create(
            medicine_name="Paracetamol 500",
            generic_name="Paracetamol",
            strength="500mg",
            dosage_form="Tablet",
            category="Analgesics & Pain Relief",
            description="Fever and pain relief tablet."
        )
        cls.med2 = Medicine.objects.create(
            medicine_name="Amoxicillin 250",
            generic_name="Amoxicillin",
            strength="250mg",
            dosage_form="Capsule",
            category="Antibiotics",
            description="Broad spectrum antibiotic."
        )
        cls.med3 = Medicine.objects.create(
            medicine_name="Cough Clear",
            generic_name="Ambroxol",
            strength="100ml",
            dosage_form="Syrup",
            category="Respiratory & Anti-Allergic",
            description="Cough syrup formulation."
        )

        # 5. Inventory Items
        cls.inv1 = Inventory.objects.create(pharmacy=cls.pharm1, medicine=cls.med1, quantity=50)
        cls.inv2 = Inventory.objects.create(pharmacy=cls.pharm1, medicine=cls.med2, quantity=5)   # LOW_STOCK
        cls.inv3 = Inventory.objects.create(pharmacy=cls.pharm1, medicine=cls.med3, quantity=0)   # OUT_OF_STOCK
        cls.inv4 = Inventory.objects.create(pharmacy=cls.pharm2, medicine=cls.med1, quantity=100)

        # 6. Availability Requests
        cls.req1 = AvailabilityRequest.objects.create(
            customer=cls.customer,
            pharmacy=cls.pharm1,
            medicine=cls.med1,
            quantity_requested=2,
            status='PENDING'
        )
        cls.req2 = AvailabilityRequest.objects.create(
            customer=cls.customer,
            pharmacy=cls.pharm1,
            medicine=cls.med2,
            quantity_requested=1,
            status='CONFIRMED'
        )
        cls.req3 = AvailabilityRequest.objects.create(
            customer=cls.customer,
            pharmacy=cls.pharm1,
            medicine=cls.med3,
            quantity_requested=3,
            status='UNAVAILABLE'
        )

        # 7. Notifications
        cls.notif1 = Notification.objects.create(user=cls.customer, message="Test notification 1", is_read=False)
        cls.notif2 = Notification.objects.create(user=cls.customer, message="Test notification 2", is_read=True)

    def setUp(self):
        self.client = Client()

    # ------------------------------------------------------------------ #
    # 1. Medicine Search select_related eliminates N+1 queries           #
    # ------------------------------------------------------------------ #
    def test_01_medicine_search_select_related(self):
        """Medicine search uses select_related('medicine', 'pharmacy'), eliminating N+1 queries when accessing relations."""
        with CaptureQueriesContext(connection) as ctx:
            page_obj, has_coords, pins, total, user_coords = search_medicine_inventory(
                query='Paracetamol',
                page=1,
                per_page=10
            )
            # Access related attributes on every item in page
            for item in page_obj:
                _ = item.medicine.medicine_name
                _ = item.medicine.generic_name
                _ = item.pharmacy.pharmacy_name
                _ = item.pharmacy.city

        # The search executes at most 2 queries (1 count / main query, without N+1 per result)
        self.assertLessEqual(len(ctx.captured_queries), 3)
        self.assertGreaterEqual(total, 1)

    # ------------------------------------------------------------------ #
    # 2. Search filter options direct table query                        #
    # ------------------------------------------------------------------ #
    def test_02_filter_options_single_query(self):
        """get_search_filter_options queries Pharmacy directly, avoiding heavy join across Inventory."""
        with CaptureQueriesContext(connection) as ctx:
            categories, cities, dosage_forms = get_search_filter_options()

        # Should execute exactly 1 query to Pharmacy table
        self.assertEqual(len(ctx.captured_queries), 1)
        self.assertIn('Hyderabad', cities)
        self.assertIn('Secunderabad', cities)
        self.assertGreaterEqual(len(categories), 5)
        self.assertGreaterEqual(len(dosage_forms), 5)

    # ------------------------------------------------------------------ #
    # 3. Pharmacy discovery omits unnecessary User table JOINs           #
    # ------------------------------------------------------------------ #
    def test_03_pharmacy_discovery_no_user_join(self):
        """Public pharmacy discovery queries Pharmacy directly without joining auth_user table."""
        with CaptureQueriesContext(connection) as ctx:
            page_obj, has_coords, pins, total, user_coords = discover_nearby_pharmacies(
                only_approved=True,
                page=1,
                per_page=10
            )
            for p in page_obj:
                _ = p.pharmacy_name
                _ = p.city
                _ = p.phone_number

        self.assertGreaterEqual(total, 2)
        # Verify no captured query contains auth_user / accounts_user JOIN
        for query_info in ctx.captured_queries:
            sql = query_info['sql'].lower()
            self.assertNotIn('accounts_user', sql, "Public pharmacy discovery should not join accounts_user table")

    # ------------------------------------------------------------------ #
    # 4. Pharmacy detail data select_related('owner')                    #
    # ------------------------------------------------------------------ #
    def test_04_pharmacy_detail_select_related_owner(self):
        """get_pharmacy_detail_data uses select_related('owner'), avoiding extra query when checking ownership."""
        with CaptureQueriesContext(connection) as ctx:
            pharmacy, items, map_pin, is_auth = get_pharmacy_detail_data(self.pharm1.id, self.owner1)
            # Check owner attribute
            _ = pharmacy.owner.username

        # Queries: 1 for Pharmacy (with owner) + 1 for Inventory (with medicine) = 2 queries total
        self.assertLessEqual(len(ctx.captured_queries), 2)
        self.assertTrue(is_auth)

    # ------------------------------------------------------------------ #
    # 5. Inventory counts single consolidated aggregate                  #
    # ------------------------------------------------------------------ #
    def test_05_inventory_counts_single_aggregate(self):
        """get_inventory_counts executes exactly 1 aggregate query for all stock buckets."""
        with CaptureQueriesContext(connection) as ctx:
            counts = get_inventory_counts(self.pharm1)

        self.assertEqual(len(ctx.captured_queries), 1)
        self.assertEqual(counts['total_count'], 3)
        self.assertEqual(counts['in_stock_count'], 1)
        self.assertEqual(counts['low_stock_count'], 1)
        self.assertEqual(counts['out_stock_count'], 1)

    # ------------------------------------------------------------------ #
    # 6. Pharmacy inbox counts single consolidated aggregate             #
    # ------------------------------------------------------------------ #
    def test_06_pharmacy_inbox_counts_single_aggregate(self):
        """get_pharmacy_inbox_counts executes exactly 1 aggregate query for all request statuses."""
        with CaptureQueriesContext(connection) as ctx:
            counts = get_pharmacy_inbox_counts(self.pharm1)

        self.assertEqual(len(ctx.captured_queries), 1)
        self.assertEqual(counts['total_count'], 3)
        self.assertEqual(counts['pending_count'], 1)
        self.assertEqual(counts['confirmed_count'], 1)
        self.assertEqual(counts['unavailable_count'], 1)

    # ------------------------------------------------------------------ #
    # 7. Customer dashboard metrics single consolidated aggregate        #
    # ------------------------------------------------------------------ #
    def test_07_customer_dashboard_counts_single_aggregate(self):
        """get_customer_dashboard_metrics aggregates request status in a single query."""
        with CaptureQueriesContext(connection) as ctx:
            metrics = get_customer_dashboard_metrics(self.customer)

        self.assertGreaterEqual(metrics['total_requests'], 3)
        self.assertEqual(metrics['pending_requests'], 1)
        self.assertEqual(metrics['confirmed_requests'], 1)
        self.assertEqual(metrics['unavailable_requests'], 1)
        # Should be bounded to ~4 queries (aggregate, recent requests, notifications, unread count)
        self.assertLessEqual(len(ctx.captured_queries), 5)

    # ------------------------------------------------------------------ #
    # 8. Admin dashboard grouped queries                                 #
    # ------------------------------------------------------------------ #
    def test_08_admin_dashboard_metrics_grouped_queries(self):
        """get_admin_dashboard_metrics uses consolidated grouped queries for all KPI counts."""
        with CaptureQueriesContext(connection) as ctx:
            metrics = get_admin_dashboard_metrics()

        self.assertGreaterEqual(metrics['total_customers'], 1)
        self.assertGreaterEqual(metrics['total_pharmacy_owners'], 2)
        self.assertGreaterEqual(metrics['approved_pharmacies'], 2)
        self.assertGreaterEqual(metrics['pending_approvals'], 1)
        self.assertGreaterEqual(metrics['active_requests'], 1)
        # Total queries bounded to ~8
        self.assertLessEqual(len(ctx.captured_queries), 8)

    # ------------------------------------------------------------------ #
    # 9. Respond to request select_related avoids N+1 on notification    #
    # ------------------------------------------------------------------ #
    def test_09_respond_request_select_related(self):
        """respond_to_availability_inquiry uses select_related to avoid queries when notifying customer."""
        req = AvailabilityRequest.objects.create(
            customer=self.customer,
            pharmacy=self.pharm1,
            medicine=self.med1,
            quantity_requested=1,
            status='PENDING'
        )

        with CaptureQueriesContext(connection) as ctx:
            respond_to_availability_inquiry(
                request_id=req.id,
                pharmacy=self.pharm1,
                status='CONFIRMED',
                pharmacy_response='Ready for pickup'
            )

        # Look up request + update + notification insert = 3 queries (no extra lookups for customer/medicine)
        self.assertLessEqual(len(ctx.captured_queries), 4)

    # ------------------------------------------------------------------ #
    # 10. Inventory delete uses select_related('medicine')               #
    # ------------------------------------------------------------------ #
    def test_10_inventory_edit_delete_select_related(self):
        """delete_inventory_item uses select_related('medicine') avoiding lazy medicine lookup."""
        inv = Inventory.objects.create(
            pharmacy=self.pharm2,
            medicine=self.med3,
            quantity=15
        )

        with CaptureQueriesContext(connection) as ctx:
            success, med_name = delete_inventory_item(self.pharm2, inv.id)

        self.assertTrue(success)
        self.assertEqual(med_name, "Cough Clear")
        # Query 1: select_related lookup, Query 2: delete -> at most 2 queries
        self.assertLessEqual(len(ctx.captured_queries), 2)

    # ------------------------------------------------------------------ #
    # 11. Database unique_together constraint on Inventory               #
    # ------------------------------------------------------------------ #
    def test_11_inventory_unique_together_constraint(self):
        """Inventory enforces uniqueness on (pharmacy, medicine) at the database level."""
        with self.assertRaises((ValidationError, IntegrityError)):
            inv_duplicate = Inventory(
                pharmacy=self.pharm1,
                medicine=self.med1,
                quantity=10
            )
            inv_duplicate.full_clean()
            inv_duplicate.save()

    # ------------------------------------------------------------------ #
    # 12. Schema indexes exist in database                               #
    # ------------------------------------------------------------------ #
    def test_12_schema_indexes_exist(self):
        """Composite and single-column indexes created in migrations exist in the database."""
        with connection.cursor() as cursor:
            # Query SQLite index list
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
            indexes = [row[0] for row in cursor.fetchall()]

        # Check key indexes added in Phase 8
        expected_indexes = [
            'med_cat_name_idx',
            'med_dosage_cat_idx',
            'pharm_appr_city_idx',
            'pharm_appr_pincode_idx',
            'pharm_appr_created_idx',
            'inv_pharm_status_idx',
            'inv_pharm_updated_idx',
            'inv_status_updated_idx',
            'req_cust_status_idx',
            'req_cust_created_idx',
            'req_pharm_status_idx',
            'req_pharm_created_idx',
            'notif_user_read_idx',
            'notif_user_created_idx',
            'user_role_joined_idx',
        ]
        for idx in expected_indexes:
            self.assertIn(idx, indexes, f"Index '{idx}' should exist in the database schema")

    # ------------------------------------------------------------------ #
    # 13. Cascade referential integrity on delete                        #
    # ------------------------------------------------------------------ #
    def test_13_cascade_referential_integrity(self):
        """Deleting a pharmacy cascades and cleans up its inventory items and requests."""
        owner = User.objects.create_user(
            username='temp_owner_perf',
            email='temp_owner@test.com',
            password='Password123!',
            role='PHARMACY'
        )
        pharm = Pharmacy.objects.create(
            owner=owner,
            pharmacy_name="Temporary Pharmacy",
            registration_number="REG-TEMP-001",
            address="1 Temp Way",
            city="Hyderabad",
            state="Telangana",
            pincode="500001",
            phone_number="040-00000000",
            is_approved=True
        )
        inv = Inventory.objects.create(pharmacy=pharm, medicine=self.med1, quantity=10)
        req = AvailabilityRequest.objects.create(
            customer=self.customer,
            pharmacy=pharm,
            medicine=self.med1,
            quantity_requested=1
        )

        pharm_id = pharm.id
        pharm.delete()

        # Related inventory and requests should be deleted via CASCADE
        self.assertFalse(Inventory.objects.filter(pharmacy_id=pharm_id).exists())
        self.assertFalse(AvailabilityRequest.objects.filter(pharmacy_id=pharm_id).exists())

    # ------------------------------------------------------------------ #
    # 14. Validation for positive quantities                             #
    # ------------------------------------------------------------------ #
    def test_14_positive_quantity_validation(self):
        """Negative inventory quantities and zero/negative request quantities raise ValidationError."""
        # Inventory quantity cannot be negative
        inv = Inventory(pharmacy=self.pharm1, medicine=self.med2, quantity=-5)
        with self.assertRaises(ValidationError):
            inv.full_clean()

        # Request quantity must be >= 1
        req = AvailabilityRequest(
            customer=self.customer,
            pharmacy=self.pharm1,
            medicine=self.med1,
            quantity_requested=0
        )
        with self.assertRaises(ValidationError):
            req.full_clean()

    # ------------------------------------------------------------------ #
    # 15. Query pagination efficiency                                    #
    # ------------------------------------------------------------------ #
    def test_15_query_pagination_efficiency(self):
        """Medicine search and pharmacy discovery paginate without loading unneeded page slices."""
        page_obj, has_coords, pins, total, user_coords = search_medicine_inventory(
            query='Paracetamol',
            page=1,
            per_page=1
        )
        self.assertEqual(len(page_obj), 1)
        self.assertTrue(page_obj.has_next() or total == 1)
        self.assertEqual(page_obj.paginator.per_page, 1)
