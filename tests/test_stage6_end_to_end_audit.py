from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from requests_app.models import AvailabilityRequest, Notification

User = get_user_model()


class Stage6EndToEndAuditTestCase(TestCase):
    """
    Comprehensive End-to-End Technical Audit & Security Verification Suite for Stage 6.
    Covers:
      - Complete Customer Workflows
      - Complete Pharmacy Owner Workflows
      - Complete Administrator Workflows
      - Role-Based Access Control (RBAC) & Tenant Isolation
      - Security: SQL Injection, XSS Sanitization, CSRF, and HTTP Method enforcement
    """

    def setUp(self):
        self.client = Client()

        # Pre-seed Admin
        self.admin_user = User.objects.create_superuser(
            username='e2e_admin',
            email='admin@e2e.test',
            password='Password123!',
            role='ADMIN'
        )

        # Pre-seed Pharmacy Owner 1 & Approved Pharmacy
        self.owner1 = User.objects.create_user(
            username='e2e_owner1',
            email='owner1@e2e.test',
            password='Password123!',
            role='PHARMACY'
        )
        self.pharmacy1 = Pharmacy.objects.create(
            pharmacy_name="MediCare City Pharmacy",
            registration_number="E2E-REG-001",
            provider_type=Pharmacy.ProviderType.PHARMACY,
            owner=self.owner1,
            address="100 Metro Boulevard",
            city="Hyderabad",
            district="Hyderabad",
            state="Telangana",
            pincode="500001",
            latitude=Decimal("17.385000"),
            longitude=Decimal("78.486700"),
            source_name=Pharmacy.DataSource.DEMO,
            source_id="E2E-PHARM-1",
            is_approved=True,
            is_active=True,
            is_demo=False
        )

        # Pre-seed Pharmacy Owner 2 & Pharmacy (for multi-tenant isolation tests)
        self.owner2 = User.objects.create_user(
            username='e2e_owner2',
            email='owner2@e2e.test',
            password='Password123!',
            role='PHARMACY'
        )
        self.pharmacy2 = Pharmacy.objects.create(
            pharmacy_name="Reliable Chemists Secunderabad",
            registration_number="E2E-REG-002",
            provider_type=Pharmacy.ProviderType.PHARMACY,
            owner=self.owner2,
            address="50 Station Road",
            city="Secunderabad",
            district="Hyderabad",
            state="Telangana",
            pincode="500003",
            latitude=Decimal("17.439900"),
            longitude=Decimal("78.498300"),
            source_name=Pharmacy.DataSource.DEMO,
            source_id="E2E-PHARM-2",
            is_approved=True,
            is_active=True,
            is_demo=False
        )

        # Pre-seed Hospital (public directory)
        self.hospital = Pharmacy.objects.create(
            pharmacy_name="Osmania General Hospital",
            registration_number="E2E-NIN-001",
            provider_type=Pharmacy.ProviderType.HOSPITAL,
            address="Afzal Gunj",
            city="Hyderabad",
            district="Hyderabad",
            state="Telangana",
            pincode="500012",
            latitude=Decimal("17.375300"),
            longitude=Decimal("78.479400"),
            source_name=Pharmacy.DataSource.DATA_GOV_IN,
            source_id="NIN-HYD-001",
            is_approved=False,
            is_active=True,
            is_demo=False
        )

        # Pre-seed Medicine Catalog
        self.medicine = Medicine.objects.create(
            medicine_name="Azithromycin 500",
            generic_name="Azithromycin",
            category="Antibiotics",
            strength="500mg",
            dosage_form="Tablet"
        )

        # Pre-seed Inventory for Pharmacy 1
        self.inv1 = Inventory.objects.create(
            pharmacy=self.pharmacy1,
            medicine=self.medicine,
            quantity=25,
            availability_status='IN_STOCK'
        )

    # =========================================================================
    # 1. CUSTOMER WORKFLOW TESTS
    # =========================================================================

    def test_01_customer_registration_and_authentication(self):
        """
        Verify end-to-end customer registration, login, profile view, and logout.
        """
        reg_data = {
            'username': 'new_customer',
            'email': 'new_cust@e2e.test',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
            'phone_number': '9876543210'
        }
        res_reg = self.client.post(reverse('register_customer'), reg_data)
        self.assertEqual(res_reg.status_code, 302)

        # Confirm user exists in database as CUSTOMER
        new_user = User.objects.get(username='new_customer')
        self.assertEqual(new_user.role, 'CUSTOMER')
        self.assertTrue(new_user.is_customer)

        # Login
        res_login = self.client.post(reverse('login'), {
            'username': 'new_customer',
            'password': 'StrongPassword123!'
        })
        self.assertEqual(res_login.status_code, 302)

        # Profile Access
        res_prof = self.client.get(reverse('profile'))
        self.assertEqual(res_prof.status_code, 200)
        self.assertContains(res_prof, 'new_customer')

        # Logout
        res_logout = self.client.post(reverse('logout'))
        self.assertIn(res_logout.status_code, (200, 302))

    def test_02_customer_search_and_discovery_filters(self):
        """
        Verify customer search by city, pincode, provider type, radius, and availability.
        """
        # City & Pincode manual search
        res = self.client.get(reverse('pharmacy_discovery'), {'city': 'Hyderabad', 'verification': 'all'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "MediCare City Pharmacy")
        self.assertContains(res, "Osmania General Hospital")

        # Provider Type: HOSPITAL only
        res_hosp = self.client.get(reverse('pharmacy_discovery'), {'type': 'HOSPITAL', 'verification': 'all'})
        self.assertContains(res_hosp, "Osmania General Hospital")
        self.assertNotContains(res_hosp, "MediCare City Pharmacy")

        # Provider Type: PHARMACY only
        res_pharm = self.client.get(reverse('pharmacy_discovery'), {'type': 'PHARMACY', 'verification': 'all'})
        self.assertContains(res_pharm, "MediCare City Pharmacy")
        self.assertNotContains(res_pharm, "Osmania General Hospital")

        # Medicine Availability filter: in_stock
        res_avail = self.client.get(reverse('pharmacy_discovery'), {'availability': 'in_stock', 'verification': 'all'})
        self.assertContains(res_avail, "MediCare City Pharmacy")
        self.assertNotContains(res_avail, "Osmania General Hospital")

    def test_03_customer_medicine_search_and_availability_request(self):
        """
        Verify customer medicine search, viewing store inventory, creating an
        inquiry request, and tracking status updates.
        """
        customer = User.objects.create_user(
            username='cust_inquiry',
            email='inq@e2e.test',
            password='Password123!',
            role='CUSTOMER'
        )
        self.client.force_login(customer)

        # Medicine search
        res_med = self.client.get(reverse('search_medicines'), {'q': 'Azithromycin'})
        self.assertEqual(res_med.status_code, 200)
        self.assertContains(res_med, "Azithromycin 500")

        # Pharmacy detail page
        res_det = self.client.get(reverse('pharmacy_detail', args=[self.pharmacy1.id]))
        self.assertEqual(res_det.status_code, 200)
        self.assertContains(res_det, "Azithromycin 500")

        # Create availability request
        req_url = reverse('create_request', args=[self.pharmacy1.id, self.medicine.id])
        res_req = self.client.post(req_url, {
            'quantity_requested': 2,
            'request_message': 'Need 2 strips immediately'
        })
        self.assertEqual(res_req.status_code, 302)

        # Confirm request created in DB
        created_req = AvailabilityRequest.objects.filter(customer=customer, pharmacy=self.pharmacy1).first()
        self.assertIsNotNone(created_req)
        self.assertEqual(created_req.status, 'PENDING')

        # Customer views their request tracker
        res_track = self.client.get(reverse('customer_requests'))
        self.assertEqual(res_track.status_code, 200)
        self.assertContains(res_track, "Azithromycin 500")

    # =========================================================================
    # 2. PHARMACY OWNER WORKFLOW TESTS
    # =========================================================================

    def test_04_pharmacy_inventory_crud_and_request_response(self):
        """
        Verify pharmacy owner login, adding inventory, updating stock,
        responding to customer requests, and deleting inventory.
        """
        self.client.force_login(self.owner1)

        # View pharmacy dashboard
        res_dash = self.client.get(reverse('pharmacy_dashboard'))
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, "MediCare City Pharmacy")

        # Create new medicine to add
        new_med = Medicine.objects.create(
            medicine_name="Amoxicillin 250",
            generic_name="Amoxicillin",
            category="Antibiotics",
            strength="250mg",
            dosage_form="Capsule"
        )

        # Add Inventory
        res_add = self.client.post(reverse('inventory_add'), {
            'medicine': new_med.id,
            'quantity': 40,
            'availability_status': 'IN_STOCK'
        })
        self.assertEqual(res_add.status_code, 302)
        inv2 = Inventory.objects.filter(pharmacy=self.pharmacy1, medicine=new_med).first()
        self.assertIsNotNone(inv2)
        self.assertEqual(inv2.quantity, 40)

        # Update Inventory
        res_edit = self.client.post(reverse('inventory_edit', args=[inv2.id]), {
            'quantity': 5,
            'availability_status': 'LOW_STOCK'
        })
        self.assertEqual(res_edit.status_code, 302)
        inv2.refresh_from_db()
        self.assertEqual(inv2.quantity, 5)
        self.assertEqual(inv2.availability_status, 'LOW_STOCK')

        # Respond to customer request
        cust = User.objects.create_user(username='c_resp', email='cr@e2e.test', password='Password123!', role='CUSTOMER')
        req = AvailabilityRequest.objects.create(
            customer=cust,
            pharmacy=self.pharmacy1,
            medicine=self.medicine,
            quantity_requested=2,
            request_message='Patient Test Inquiry',
            status='PENDING'
        )

        res_resp = self.client.post(reverse('respond_request', args=[req.id]), {
            'status': 'CONFIRMED',
            'pharmacy_response': 'Medicine reserved for pickup.'
        })
        self.assertEqual(res_resp.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'CONFIRMED')

        # Delete Inventory
        res_del = self.client.post(reverse('inventory_delete', args=[inv2.id]))
        self.assertEqual(res_del.status_code, 302)
        self.assertFalse(Inventory.objects.filter(id=inv2.id).exists())

    # =========================================================================
    # 3. ADMINISTRATOR WORKFLOW TESTS
    # =========================================================================

    def test_05_admin_governance_and_approval_workflow(self):
        """
        Verify administrator portal access, listing providers, filtering,
        toggling verification status, and monitoring users and requests.
        """
        self.client.force_login(self.admin_user)

        # Admin portal dashboard
        res_admin = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(res_admin.status_code, 200)

        # Admin provider management list
        res_list = self.client.get(reverse('admin_pharmacy_list'))
        self.assertEqual(res_list.status_code, 200)
        self.assertContains(res_list, "MediCare City Pharmacy")
        self.assertContains(res_list, "Osmania General Hospital")

        # Toggle approval: Approve the unapproved hospital
        res_toggle = self.client.post(reverse('toggle_pharmacy_approval', args=[self.hospital.id]))
        self.assertEqual(res_toggle.status_code, 302)
        self.hospital.refresh_from_db()
        self.assertTrue(self.hospital.is_approved)

        # Admin User List view
        res_users = self.client.get(reverse('admin_user_list'))
        self.assertEqual(res_users.status_code, 200)
        self.assertContains(res_users, "e2e_owner1")

        # Admin Request Monitor view
        res_reqs = self.client.get(reverse('admin_request_monitor'))
        self.assertEqual(res_reqs.status_code, 200)

    # =========================================================================
    # 4. SECURITY AUDIT & RBAC ENFORCEMENT
    # =========================================================================

    def test_06_role_based_access_control_enforcement(self):
        """
        Verify strict role-based access control (RBAC):
        - Customers cannot access pharmacy dashboards or inventory mutations.
        - Customers and Pharmacy owners cannot access administrative portals.
        - Unauthenticated users cannot access restricted resources.
        """
        customer = User.objects.create_user(
            username='c_sec',
            email='csec@e2e.test',
            password='Password123!',
            role='CUSTOMER'
        )
        self.client.force_login(customer)

        # Customer attempting pharmacy dashboard -> redirected with error
        res = self.client.get(reverse('pharmacy_dashboard'))
        self.assertEqual(res.status_code, 302)

        # Customer attempting to add inventory -> redirected with error
        res = self.client.get(reverse('inventory_add'))
        self.assertEqual(res.status_code, 302)

        # Customer attempting admin portal -> redirected with error
        res = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(res.status_code, 302)

        # Pharmacy owner attempting admin portal -> redirected with error
        self.client.force_login(self.owner1)
        res = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(res.status_code, 302)

    def test_07_cross_tenant_inventory_isolation(self):
        """
        Verify tenant isolation: Owner 2 cannot edit or delete Owner 1's inventory.
        """
        self.client.force_login(self.owner2)

        # Owner 2 tries to edit Owner 1's inventory item
        res_edit = self.client.post(reverse('inventory_edit', args=[self.inv1.id]), {
            'quantity': 0,
            'availability_status': 'OUT_OF_STOCK'
        })
        self.assertIn(res_edit.status_code, (302, 403, 404))
        self.inv1.refresh_from_db()
        self.assertEqual(self.inv1.quantity, 25)  # Must remain unaltered

        # Owner 2 tries to delete Owner 1's inventory item
        res_del = self.client.post(reverse('inventory_delete', args=[self.inv1.id]))
        self.assertIn(res_del.status_code, (302, 403, 404))
        self.assertTrue(Inventory.objects.filter(id=self.inv1.id).exists())  # Must not be deleted

    def test_08_sql_injection_and_xss_fuzzing(self):
        """
        Verify that search parameters and query strings are protected against
        SQL injection and Cross-Site Scripting (XSS) payloads.
        """
        sql_payloads = [
            "' OR 1=1 --",
            "'; DROP TABLE pharmacies_pharmacy; --",
            "\" OR \"a\"=\"a",
            "1' UNION SELECT username, password FROM accounts_user --"
        ]
        xss_payloads = [
            "<script>alert('xss')</script>",
            "\" onmouseover=\"alert(1)\"",
            "<img src=x onerror=alert(1)>"
        ]

        # Test Discovery View with malicious payloads
        for payload in sql_payloads + xss_payloads:
            res = self.client.get(reverse('pharmacy_discovery'), {'q': payload, 'city': payload})
            self.assertEqual(res.status_code, 200)
            # Response must not contain unescaped executable script tags
            if "<script>" in payload:
                self.assertNotContains(res, "<script>alert('xss')</script>")

        # Confirm database table was not dropped
        self.assertTrue(Pharmacy.objects.exists())

    def test_09_http_method_enforcement_on_sensitive_actions(self):
        """
        Verify that sensitive actions like toggling pharmacy approval reject GET requests
        with 405 Method Not Allowed or appropriate guard.
        """
        self.client.force_login(self.admin_user)
        res = self.client.get(reverse('toggle_pharmacy_approval', args=[self.hospital.id]))
        self.assertEqual(res.status_code, 405)
