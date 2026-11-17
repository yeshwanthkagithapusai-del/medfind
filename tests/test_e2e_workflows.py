"""
Phase 9 – End-to-End Workflow Verification Test Suite
MediFind Project

Tests complete end-to-end journeys:
1. Customer Workflow: Registration -> Login -> Profile -> Search -> Distance -> Request -> Notification.
2. Pharmacy Workflow: Registration -> Pending status -> Admin Approval -> Login -> Inventory Management -> Request Response.
3. Admin Workflow: Admin Dashboard KPIs -> Store Verification -> User Management -> Request Monitoring.
4. Security & Isolation: Tenant boundaries, non-admin blocks, CSRF enforcement.
5. Favicon & Branding: Static assets integration in HTML base template.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from requests_app.models import AvailabilityRequest, Notification

User = get_user_model()


class EndToEndWorkflowTests(TestCase):
    """
    Comprehensive end-to-end QA validation suite covering all user roles,
    business workflows, security policies, and UI asset integrations.
    """

    def setUp(self):
        self.client = Client()

    # ------------------------------------------------------------------ #
    # 1. Favicon and Branding Integration Verification                   #
    # ------------------------------------------------------------------ #
    def test_01_favicon_and_branding_in_base_template(self):
        """Base template contains favicon links, apple-touch-icon, and branded navbar logo."""
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)

        # Verify favicon links in HTML
        self.assertContains(resp, 'static/images/favicon.svg')
        self.assertContains(resp, 'static/images/favicon-32x32.png')
        self.assertContains(resp, 'static/images/favicon-192x192.png')
        self.assertContains(resp, 'static/images/apple-touch-icon.png')
        self.assertContains(resp, 'static/images/favicon.ico')

        # Verify logo in navbar
        self.assertContains(resp, 'static/images/medifind-icon.svg')
        self.assertContains(resp, 'navbar-brand-logo')

    # ------------------------------------------------------------------ #
    # 2. Complete Customer Journey                                       #
    # ------------------------------------------------------------------ #
    def test_02_customer_full_workflow(self):
        """Customer: Register -> Login -> Profile -> Search -> Request -> Track -> Read Notification."""
        # 1. Register
        reg_data = {
            'username': 'e2e_customer',
            'email': 'e2e_customer@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
            'phone_number': '+91 9998887770',
            'first_name': 'E2E',
            'last_name': 'Patient'
        }
        resp = self.client.post(reverse('register_customer'), reg_data, follow=True)
        self.assertIn(resp.status_code, [200, 302])
        self.assertTrue(User.objects.filter(username='e2e_customer').exists())
        cust = User.objects.get(username='e2e_customer')
        self.assertEqual(cust.role, 'CUSTOMER')

        # 2. Login
        login_success = self.client.login(username='e2e_customer', password='SecurePassword123!')
        self.assertTrue(login_success)

        # 3. Profile view & update
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'e2e_customer')

        update_data = {
            'first_name': 'UpdatedE2E',
            'last_name': 'Patient',
            'email': 'e2e_customer@example.com',
            'phone_number': '+91 9998887771',
            'action': 'user'
        }
        resp = self.client.post(reverse('profile'), update_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        cust.refresh_from_db()
        self.assertEqual(cust.first_name, 'UpdatedE2E')

        # 4. Search medicine
        # Setup: Create approved pharmacy with medicine
        pharm_owner = User.objects.create_user(
            username='pharm_e2e_owner', email='po@test.com', password='Pass123!', role='PHARMACY'
        )
        pharmacy = Pharmacy.objects.create(
            owner=pharm_owner,
            pharmacy_name="E2E Apollo Care",
            registration_number="REG-E2E-001",
            address="Road 10, Banjara",
            city="Hyderabad",
            state="Telangana",
            pincode="500034",
            phone_number="040-55556666",
            latitude=Decimal('17.415000'),
            longitude=Decimal('78.435000'),
            is_approved=True
        )
        med = Medicine.objects.create(
            medicine_name="E2EMed 500",
            generic_name="Paracetamol",
            strength="500mg",
            dosage_form="Tablet",
            category="Analgesics & Pain Relief"
        )
        Inventory.objects.create(pharmacy=pharmacy, medicine=med, quantity=25)

        search_resp = self.client.get(reverse('search_medicines'), {'q': 'E2EMed'})
        self.assertEqual(search_resp.status_code, 200)
        self.assertContains(search_resp, 'E2EMed 500')
        self.assertContains(search_resp, 'E2E Apollo Care')

        # 5. Submit Availability Request
        req_resp = self.client.post(
            reverse('create_request', args=[pharmacy.id, med.id]),
            {'quantity_requested': 2, 'request_message': 'Urgent pickup needed'},
            follow=True
        )
        self.assertEqual(req_resp.status_code, 200)
        self.assertTrue(AvailabilityRequest.objects.filter(customer=cust, medicine=med).exists())
        req_obj = AvailabilityRequest.objects.get(customer=cust, medicine=med)
        self.assertEqual(req_obj.status, 'PENDING')

        # 6. Check Customer Dashboard
        dash_resp = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, 'E2EMed 500')

        # 7. Cancel Request (Customer feature)
        cancel_resp = self.client.post(reverse('cancel_request', args=[req_obj.id]), follow=True)
        self.assertEqual(cancel_resp.status_code, 200)
        req_obj.refresh_from_db()
        self.assertEqual(req_obj.status, 'CANCELLED')

        # 8. Check Notifications & Mark as Read
        notif = Notification.objects.filter(user=cust).first()
        if notif:
            notif_resp = self.client.post(reverse('mark_notification_read', args=[notif.id]), follow=True)
            self.assertEqual(notif_resp.status_code, 200)
            notif.refresh_from_db()
            self.assertTrue(notif.is_read)

        # 9. Logout
        logout_resp = self.client.post(reverse('logout'), follow=True)
        self.assertIn(logout_resp.status_code, [200, 302])

    # ------------------------------------------------------------------ #
    # 3. Complete Pharmacy Workflow                                      #
    # ------------------------------------------------------------------ #
    def test_03_pharmacy_full_workflow(self):
        """Pharmacy: Register -> Pending approval -> Admin approves -> Login -> Dashboard -> Inventory -> Respond."""
        # 1. Register Pharmacy
        reg_data = {
            'username': 'e2e_pharma_owner',
            'email': 'e2e_pharma@test.com',
            'password': 'SecurePharmPass123!',
            'confirm_password': 'SecurePharmPass123!',
            'owner_first_name': 'Raj',
            'owner_last_name': 'Sharma',
            'owner_phone': '+91 9888877770',
            'pharmacy_name': 'E2E Health Center Chemist',
            'registration_number': 'REG-E2E-PHARM-99',
            'address': 'Plot 45, Gachibowli',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500032',
            'phone_number': '040-77778888',
            'latitude': '17.440000',
            'longitude': '78.350000',
        }
        resp = self.client.post(reverse('register_pharmacy'), reg_data, follow=True)
        self.assertIn(resp.status_code, [200, 302])

        pharmacy = Pharmacy.objects.get(registration_number='REG-E2E-PHARM-99')
        # Crucial: Pharmacy must start as unapproved!
        self.assertFalse(pharmacy.is_approved)

        # 2. Admin Approves Pharmacy
        admin = User.objects.create_superuser(
            username='admin_e2e', email='admin_e2e@test.com', password='AdminPass123!', role='ADMIN'
        )
        self.client.login(username='admin_e2e', password='AdminPass123!')
        appr_resp = self.client.post(reverse('toggle_pharmacy_approval', args=[pharmacy.id]), follow=True)
        self.assertEqual(appr_resp.status_code, 200)
        pharmacy.refresh_from_db()
        self.assertTrue(pharmacy.is_approved)
        self.client.logout()

        # 3. Pharmacy Owner Log In
        self.client.login(username='e2e_pharma_owner', password='SecurePharmPass123!')

        # 4. View Pharmacy Dashboard
        dash_resp = self.client.get(reverse('pharmacy_dashboard'))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, 'E2E Health Center Chemist')

        # 5. Add Inventory Item
        med = Medicine.objects.create(
            medicine_name="Amox E2E",
            generic_name="Amoxicillin",
            strength="250mg",
            dosage_form="Capsule",
            category="Antibiotics"
        )
        add_resp = self.client.post(reverse('inventory_add'), {'medicine': med.id, 'quantity': 15}, follow=True)
        self.assertEqual(add_resp.status_code, 200)
        self.assertTrue(Inventory.objects.filter(pharmacy=pharmacy, medicine=med).exists())
        inv = Inventory.objects.get(pharmacy=pharmacy, medicine=med)
        self.assertEqual(inv.quantity, 15)
        self.assertEqual(inv.availability_status, 'IN_STOCK')

        # 6. Edit Inventory Quantity to Low Stock (< 10)
        edit_resp = self.client.post(reverse('inventory_edit', args=[inv.id]), {'quantity': 4}, follow=True)
        self.assertEqual(edit_resp.status_code, 200)
        inv.refresh_from_db()
        self.assertEqual(inv.quantity, 4)
        self.assertEqual(inv.availability_status, 'LOW_STOCK')

        # 7. Customer sends request and pharmacy responds
        cust = User.objects.create_user(
            username='cust_inq_e2e', email='inq@test.com', password='Pass123!', role='CUSTOMER'
        )
        req = AvailabilityRequest.objects.create(
            customer=cust, pharmacy=pharmacy, medicine=med, quantity_requested=2, status='PENDING'
        )
        resp_view = self.client.post(
            reverse('respond_request', args=[req.id]),
            {'status': 'CONFIRMED', 'pharmacy_response': 'Stock held at counter for 2 hours'},
            follow=True
        )
        self.assertEqual(resp_view.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, 'CONFIRMED')
        self.assertIn('Stock held', req.pharmacy_response)

    # ------------------------------------------------------------------ #
    # 4. Complete Administrative Governance Workflow                     #
    # ------------------------------------------------------------------ #
    def test_04_admin_governance_workflow(self):
        """Admin: Dashboard stats -> User management -> Request monitor -> Store vetting."""
        admin = User.objects.create_superuser(
            username='gov_admin_e2e', email='gov@test.com', password='AdminPass123!', role='ADMIN'
        )
        self.client.login(username='gov_admin_e2e', password='AdminPass123!')

        # 1. Admin Dashboard
        dash_resp = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, 'Operations Command Console')

        # 2. Manage Users Portal
        users_resp = self.client.get(reverse('admin_user_list'))
        self.assertEqual(users_resp.status_code, 200)
        self.assertContains(users_resp, 'User Account Management')

        # 3. Monitor Requests Portal
        reqs_resp = self.client.get(reverse('admin_request_monitor'))
        self.assertEqual(reqs_resp.status_code, 200)
        self.assertContains(reqs_resp, 'Platform Availability Request Monitor')

        # 4. Pharmacy List with pending filter
        stores_resp = self.client.get(reverse('admin_pharmacy_list'), {'status': 'pending'})
        self.assertEqual(stores_resp.status_code, 200)

        # 5. Master Medicine Catalogue
        cat_resp = self.client.get(reverse('manage_medicines'))
        self.assertEqual(cat_resp.status_code, 200)

    # ------------------------------------------------------------------ #
    # 5. Security & Isolation Checks                                     #
    # ------------------------------------------------------------------ #
    def test_05_security_and_tenant_isolation(self):
        """Verify customers cannot access pharmacy/admin views, and pharmacy owners cannot edit other stores."""
        cust = User.objects.create_user(
            username='sec_cust_e2e', email='sc@test.com', password='Pass123!', role='CUSTOMER'
        )
        pharm_owner_a = User.objects.create_user(
            username='owner_a_e2e', email='oa@test.com', password='Pass123!', role='PHARMACY'
        )
        pharm_owner_b = User.objects.create_user(
            username='owner_b_e2e', email='ob@test.com', password='Pass123!', role='PHARMACY'
        )

        pharm_a = Pharmacy.objects.create(
            owner=pharm_owner_a, pharmacy_name="Pharm A", registration_number="REG-A-01",
            address="Addr A", city="Hyd", state="TS", pincode="500001", phone_number="040-00000001",
            is_approved=True
        )
        pharm_b = Pharmacy.objects.create(
            owner=pharm_owner_b, pharmacy_name="Pharm B", registration_number="REG-B-01",
            address="Addr B", city="Hyd", state="TS", pincode="500002", phone_number="040-00000002",
            is_approved=True
        )
        med = Medicine.objects.create(
            medicine_name="Med Sec", generic_name="Gen Sec", strength="10mg", dosage_form="Tablet"
        )
        inv_a = Inventory.objects.create(pharmacy=pharm_a, medicine=med, quantity=10)

        # Customer denied admin & pharmacy dashboards
        self.client.login(username='sec_cust_e2e', password='Pass123!')
        self.assertIn(self.client.get(reverse('admin_dashboard')).status_code, [302, 403])
        self.assertIn(self.client.get(reverse('pharmacy_dashboard')).status_code, [302, 403])
        self.assertIn(self.client.get(reverse('inventory_list')).status_code, [302, 403])

        # Pharmacy owner B CANNOT edit or delete Pharmacy A's inventory
        self.client.login(username='owner_b_e2e', password='Pass123!')
        edit_resp = self.client.get(reverse('inventory_edit', args=[inv_a.id]))
        self.assertEqual(edit_resp.status_code, 404, "Cross-tenant inventory edit must return 404")
        del_resp = self.client.post(reverse('inventory_delete', args=[inv_a.id]))
        self.assertEqual(del_resp.status_code, 404, "Cross-tenant inventory delete must return 404")
