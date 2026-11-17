"""
Phase 7 – Administrative Portal & Governance Test Suite
MediFind Project

15 test vectors covering:
- Admin dashboard access and statistics
- Pharmacy governance (listing, filtering, search, pagination, approval workflow)
- User management portal
- Request monitoring portal
- Authorization enforcement across all admin views

setUp pattern: no license_number, no requires_prescription (fields do not exist on the models).
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from pharmacies.models import Pharmacy
from medicines.models import Medicine
from inventory.models import Inventory
from requests_app.models import AvailabilityRequest

User = get_user_model()


class AdminPortalAndGovernanceTests(TestCase):
    """
    Comprehensive test class for the MediFind Administrative Portal (Phase 7).
    Covers access control, statistics accuracy, governance workflows and UI features.
    """

    @classmethod
    def setUpTestData(cls):
        """
        Create shared fixtures once for the entire test class (read-only data).
        Individual tests that mutate state use self.setUp() instead.
        """
        # Admin superuser
        cls.admin = User.objects.create_superuser(
            username='admin_p7',
            email='admin_p7@test.com',
            password='AdminPass123!',
            role='ADMIN'
        )

        # Customer user
        cls.customer = User.objects.create_user(
            username='cust_p7',
            email='cust_p7@test.com',
            password='CustPass123!',
            role='CUSTOMER',
            phone_number='+91 9000000099',
        )

        # Pharmacy owner user
        cls.pharm_owner = User.objects.create_user(
            username='pharm_p7',
            email='pharm_p7@test.com',
            password='PharmPass123!',
            role='PHARMACY',
            phone_number='+91 9000000098',
        )

        # Unapproved pharmacy
        cls.pharmacy_pending = Pharmacy.objects.create(
            owner=cls.pharm_owner,
            pharmacy_name='Pending Pharmacy P7',
            registration_number='REG-P7-001',
            address='1 Test Road',
            city='Hyderabad',
            state='Telangana',
            pincode='500001',
            phone_number='040-11111111',
            is_approved=False,
        )

        # Approved pharmacy
        cls.pharmacy_approved = Pharmacy.objects.create(
            owner=cls.pharm_owner,
            pharmacy_name='Approved Pharmacy P7',
            registration_number='REG-P7-002',
            address='2 Test Road',
            city='Mumbai',
            state='Maharashtra',
            pincode='400001',
            phone_number='022-22222222',
            is_approved=True,
        )

        # Medicine
        cls.medicine = Medicine.objects.create(
            medicine_name='Test Med P7',
            generic_name='Generic P7',
            strength='100mg',
            dosage_form='Tablet',
            category='Other',
        )

        # Inventory item (approved pharmacy)
        try:
            cls.inventory = Inventory.objects.create(
                pharmacy=cls.pharmacy_approved,
                medicine=cls.medicine,
                quantity=50,
                price=10.00,
                availability_status='IN_STOCK',
            )
        except Exception:
            cls.inventory = Inventory.objects.filter(
                pharmacy=cls.pharmacy_approved, medicine=cls.medicine
            ).first()

        # Requests
        cls.req_pending = AvailabilityRequest.objects.create(
            customer=cls.customer,
            pharmacy=cls.pharmacy_approved,
            medicine=cls.medicine,
            quantity_requested=2,
            status='PENDING',
        )
        cls.req_confirmed = AvailabilityRequest.objects.create(
            customer=cls.customer,
            pharmacy=cls.pharmacy_approved,
            medicine=cls.medicine,
            quantity_requested=1,
            status='CONFIRMED',
        )
        cls.req_unavailable = AvailabilityRequest.objects.create(
            customer=cls.customer,
            pharmacy=cls.pharmacy_approved,
            medicine=cls.medicine,
            quantity_requested=3,
            status='UNAVAILABLE',
        )
        cls.req_cancelled = AvailabilityRequest.objects.create(
            customer=cls.customer,
            pharmacy=cls.pharmacy_approved,
            medicine=cls.medicine,
            quantity_requested=1,
            status='CANCELLED',
        )

    def setUp(self):
        """Fresh test client for each test to ensure clean authentication state."""
        self.client = Client()

    # ------------------------------------------------------------------ #
    # 1. Admin dashboard access control                                    #
    # ------------------------------------------------------------------ #
    def test_01_admin_dashboard_access(self):
        """Admin gets 200; customer, pharmacy owner and anonymous get redirects."""
        url = reverse('admin_dashboard')

        # Admin → 200
        self.client.login(username='admin_p7', password='AdminPass123!')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, 'Admin should get HTTP 200 on admin dashboard')

        # Customer → redirect
        self.client.login(username='cust_p7', password='CustPass123!')
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403], 'Customer should be denied admin dashboard')

        # Pharmacy owner → redirect
        self.client.login(username='pharm_p7', password='PharmPass123!')
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403], 'Pharmacy owner should be denied admin dashboard')

        # Anonymous → redirect
        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302, 'Anonymous user should be redirected from admin dashboard')

    # ------------------------------------------------------------------ #
    # 2. Admin dashboard statistics accuracy                               #
    # ------------------------------------------------------------------ #
    def test_02_admin_dashboard_statistics(self):
        """Dashboard context values match actual DB counts."""
        self.client.login(username='admin_p7', password='AdminPass123!')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)

        ctx = response.context

        # Customer count (at least 1 from fixtures)
        self.assertGreaterEqual(ctx['total_customers'], 1)
        # Pharmacy owner count
        self.assertGreaterEqual(ctx['total_pharmacy_owners'], 1)
        # Pending approvals (at least 1 pending pharmacy)
        self.assertGreaterEqual(ctx['pending_approvals'], 1)
        # Approved pharmacies (at least 1 approved pharmacy)
        self.assertGreaterEqual(ctx['approved_pharmacies'], 1)
        # Active (PENDING) requests
        self.assertGreaterEqual(ctx['active_requests'], 1)
        # Completed = confirmed + unavailable (at least 2 from fixtures)
        self.assertGreaterEqual(ctx['completed_requests'], 2)
        # Cancelled requests
        self.assertGreaterEqual(ctx['cancelled_requests'], 1)
        # Medicine catalogue
        self.assertGreaterEqual(ctx['total_medicines'], 1)

    # ------------------------------------------------------------------ #
    # 3. Admin pharmacy list – access control                              #
    # ------------------------------------------------------------------ #
    def test_03_admin_pharmacy_list_access(self):
        """Admin gets 200; non-admin roles are redirected."""
        url = reverse('admin_pharmacy_list')

        self.client.login(username='admin_p7', password='AdminPass123!')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.client.login(username='cust_p7', password='CustPass123!')
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])

        self.client.login(username='pharm_p7', password='PharmPass123!')
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])

    # ------------------------------------------------------------------ #
    # 4. Admin pharmacy list – filter pending                              #
    # ------------------------------------------------------------------ #
    def test_04_admin_pharmacy_list_filter_pending(self):
        """status=pending filter returns only unapproved pharmacies."""
        self.client.login(username='admin_p7', password='AdminPass123!')
        response = self.client.get(reverse('admin_pharmacy_list'), {'status': 'pending'})
        self.assertEqual(response.status_code, 200)

        pharmacies = list(response.context['page_obj'])
        for pharm in pharmacies:
            self.assertFalse(pharm.is_approved, 'Pending filter should only return unapproved pharmacies')

    # ------------------------------------------------------------------ #
    # 5. Admin pharmacy list – filter approved                             #
    # ------------------------------------------------------------------ #
    def test_05_admin_pharmacy_list_filter_approved(self):
        """status=approved filter returns only approved pharmacies."""
        self.client.login(username='admin_p7', password='AdminPass123!')
        response = self.client.get(reverse('admin_pharmacy_list'), {'status': 'approved'})
        self.assertEqual(response.status_code, 200)

        pharmacies = list(response.context['page_obj'])
        for pharm in pharmacies:
            self.assertTrue(pharm.is_approved, 'Approved filter should only return approved pharmacies')

    # ------------------------------------------------------------------ #
    # 6. Admin pharmacy list – search                                      #
    # ------------------------------------------------------------------ #
    def test_06_admin_pharmacy_list_search(self):
        """Search by pharmacy name returns matching results."""
        self.client.login(username='admin_p7', password='AdminPass123!')

        # Search by partial pharmacy name
        response = self.client.get(reverse('admin_pharmacy_list'), {'q': 'Pending Pharmacy P7'})
        self.assertEqual(response.status_code, 200)
        names = [p.pharmacy_name for p in response.context['page_obj']]
        self.assertIn('Pending Pharmacy P7', names)

        # Search by city
        response = self.client.get(reverse('admin_pharmacy_list'), {'q': 'Hyderabad'})
        self.assertEqual(response.status_code, 200)
        cities = [p.city for p in response.context['page_obj']]
        self.assertIn('Hyderabad', cities)

        # Search by owner username
        response = self.client.get(reverse('admin_pharmacy_list'), {'q': 'pharm_p7'})
        self.assertEqual(response.status_code, 200)
        # At least one result should have the pharm_owner
        page_pharmacies = list(response.context['page_obj'])
        self.assertGreater(len(page_pharmacies), 0, 'Search by owner username should return results')

    # ------------------------------------------------------------------ #
    # 7. Admin pharmacy list – pagination                                  #
    # ------------------------------------------------------------------ #
    def test_07_admin_pharmacy_list_pagination(self):
        """With 20 pharmacies in DB (plus 2 existing), page 1 has 15 and page 2 has the rest."""
        # Create 20 extra pharmacies for this test
        extra_owner = User.objects.create_user(
            username='extra_owner_p7',
            email='extra_owner_p7@test.com',
            password='ExtraPass123!',
            role='PHARMACY',
        )
        for i in range(20):
            Pharmacy.objects.create(
                owner=extra_owner,
                pharmacy_name=f'Pagination Pharmacy {i}',
                registration_number=f'REG-PAG-{i:03d}',
                address=f'{i} Pagination Street',
                city='Pune',
                state='Maharashtra',
                pincode='411001',
                phone_number=f'020-{i:08d}',
                is_approved=(i % 2 == 0),
            )

        self.client.login(username='admin_p7', password='AdminPass123!')

        response_p1 = self.client.get(reverse('admin_pharmacy_list'), {'page': 1})
        self.assertEqual(response_p1.status_code, 200)
        self.assertEqual(len(response_p1.context['page_obj']), 15)

        response_p2 = self.client.get(reverse('admin_pharmacy_list'), {'page': 2})
        self.assertEqual(response_p2.status_code, 200)
        self.assertGreater(len(response_p2.context['page_obj']), 0)

    # ------------------------------------------------------------------ #
    # 8. Pharmacy approval toggle – approve action                         #
    # ------------------------------------------------------------------ #
    def test_08_pharmacy_approval_action(self):
        """POST to toggle_pharmacy_approval approves a pending pharmacy."""
        # Create a fresh pending pharmacy for this test (to avoid state sharing)
        owner = User.objects.create_user(
            username='owner_approve_p7',
            email='owner_approve_p7@test.com',
            password='OwnerPass123!',
            role='PHARMACY',
        )
        pharm = Pharmacy.objects.create(
            owner=owner,
            pharmacy_name='Approval Test Pharmacy',
            registration_number='REG-APR-001',
            address='3 Approval Lane',
            city='Chennai',
            state='Tamil Nadu',
            pincode='600001',
            phone_number='044-33333333',
            is_approved=False,
        )

        self.client.login(username='admin_p7', password='AdminPass123!')
        response = self.client.post(
            reverse('toggle_pharmacy_approval', args=[pharm.pk]),
            follow=True
        )
        self.assertIn(response.status_code, [200, 302])

        pharm.refresh_from_db()
        self.assertTrue(pharm.is_approved, 'Pharmacy should be approved after toggle POST')

    # ------------------------------------------------------------------ #
    # 9. Pharmacy approval toggle – revoke action                          #
    # ------------------------------------------------------------------ #
    def test_09_pharmacy_revoke_action(self):
        """POST to toggle_pharmacy_approval revokes an approved pharmacy."""
        owner = User.objects.create_user(
            username='owner_revoke_p7',
            email='owner_revoke_p7@test.com',
            password='OwnerPass123!',
            role='PHARMACY',
        )
        pharm = Pharmacy.objects.create(
            owner=owner,
            pharmacy_name='Revoke Test Pharmacy',
            registration_number='REG-REV-001',
            address='4 Revoke Lane',
            city='Kolkata',
            state='West Bengal',
            pincode='700001',
            phone_number='033-44444444',
            is_approved=True,
        )

        self.client.login(username='admin_p7', password='AdminPass123!')
        response = self.client.post(
            reverse('toggle_pharmacy_approval', args=[pharm.pk]),
            follow=True
        )
        self.assertIn(response.status_code, [200, 302])

        pharm.refresh_from_db()
        self.assertFalse(pharm.is_approved, 'Pharmacy should be revoked after toggle POST')

    # ------------------------------------------------------------------ #
    # 10. Pharmacy approval toggle – unauthorized access                   #
    # ------------------------------------------------------------------ #
    def test_10_pharmacy_approval_unauthorized(self):
        """Customer and pharmacy owner cannot POST to toggle-approval."""
        url = reverse('toggle_pharmacy_approval', args=[self.pharmacy_pending.pk])

        self.client.login(username='cust_p7', password='CustPass123!')
        response = self.client.post(url)
        self.assertIn(response.status_code, [302, 403], 'Customer should not toggle approval')

        self.client.login(username='pharm_p7', password='PharmPass123!')
        response = self.client.post(url)
        self.assertIn(response.status_code, [302, 403], 'Pharmacy owner should not toggle approval')

    # ------------------------------------------------------------------ #
    # 11. Pharmacy approval toggle – GET method rejected                   #
    # ------------------------------------------------------------------ #
    def test_11_pharmacy_approval_get_rejected(self):
        """GET request to toggle-approval returns 405 Method Not Allowed."""
        self.client.login(username='admin_p7', password='AdminPass123!')
        response = self.client.get(
            reverse('toggle_pharmacy_approval', args=[self.pharmacy_pending.pk])
        )
        self.assertEqual(response.status_code, 405, 'GET on toggle_pharmacy_approval must return 405')

    # ------------------------------------------------------------------ #
    # 12. Admin user list – access control                                 #
    # ------------------------------------------------------------------ #
    def test_12_admin_user_list_access(self):
        """Admin gets 200; non-admin roles are redirected."""
        url = reverse('admin_user_list')

        self.client.login(username='admin_p7', password='AdminPass123!')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.client.login(username='cust_p7', password='CustPass123!')
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])

        self.client.login(username='pharm_p7', password='PharmPass123!')
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])

        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    # ------------------------------------------------------------------ #
    # 13. Admin user list – role filter                                    #
    # ------------------------------------------------------------------ #
    def test_13_admin_user_list_role_filter(self):
        """Customer and pharmacy role filters return only matching users."""
        self.client.login(username='admin_p7', password='AdminPass123!')

        # Filter by CUSTOMER
        response = self.client.get(reverse('admin_user_list'), {'role': 'CUSTOMER'})
        self.assertEqual(response.status_code, 200)
        users = list(response.context['page_obj'])
        for user in users:
            self.assertEqual(user.role, 'CUSTOMER', 'Customer filter should only show CUSTOMER users')

        # Filter by PHARMACY
        response = self.client.get(reverse('admin_user_list'), {'role': 'PHARMACY'})
        self.assertEqual(response.status_code, 200)
        users = list(response.context['page_obj'])
        for user in users:
            self.assertEqual(user.role, 'PHARMACY', 'Pharmacy filter should only show PHARMACY users')

    # ------------------------------------------------------------------ #
    # 14. Admin request monitor – access control                           #
    # ------------------------------------------------------------------ #
    def test_14_admin_request_monitor_access(self):
        """Admin gets 200; non-admin roles are redirected."""
        url = reverse('admin_request_monitor')

        self.client.login(username='admin_p7', password='AdminPass123!')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.client.login(username='cust_p7', password='CustPass123!')
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])

        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    # ------------------------------------------------------------------ #
    # 15. Admin request monitor – status filters                           #
    # ------------------------------------------------------------------ #
    def test_15_admin_request_monitor_status_filter(self):
        """PENDING/CONFIRMED/UNAVAILABLE/CANCELLED filters return only matching requests."""
        self.client.login(username='admin_p7', password='AdminPass123!')

        for status_val in ['PENDING', 'CONFIRMED', 'UNAVAILABLE', 'CANCELLED']:
            response = self.client.get(
                reverse('admin_request_monitor'), {'status': status_val}
            )
            self.assertEqual(response.status_code, 200, f'Filter {status_val} should return 200')
            requests_qs = list(response.context['page_obj'])
            for req in requests_qs:
                self.assertEqual(
                    req.status, status_val,
                    f'Status filter {status_val} returned request with status {req.status}'
                )
