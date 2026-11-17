from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from requests_app.models import AvailabilityRequest, Notification

User = get_user_model()


class MediFindSecurityTestSuite(TestCase):
    """
    Automated Security Test Suite verifying:
    - Authentication & Session Invalidation
    - Role-Based Access Control (RBAC)
    - Multi-Tenant Isolation & IDOR Defense
    - HTTP Method Enforcement (@require_POST)
    - Password Strength & Form Validation
    """

    def setUp(self):
        self.client = Client()

        # Admin User
        self.admin = User.objects.create_superuser(
            username='sec_admin',
            email='admin@sec.test',
            password='ComplexAdminPass123!',
            role='ADMIN'
        )

        # Customer A
        self.customer_a = User.objects.create_user(
            username='sec_customer_a',
            email='customer_a@sec.test',
            password='ComplexUserPass123!',
            role='CUSTOMER',
            phone_number='+91 9111111111'
        )

        # Customer B
        self.customer_b = User.objects.create_user(
            username='sec_customer_b',
            email='customer_b@sec.test',
            password='ComplexUserPass123!',
            role='CUSTOMER',
            phone_number='+91 9222222222'
        )

        # Pharmacy Owner A
        self.owner_a = User.objects.create_user(
            username='sec_owner_a',
            email='owner_a@sec.test',
            password='ComplexOwnerPass123!',
            role='PHARMACY'
        )
        self.pharmacy_a = Pharmacy.objects.create(
            owner=self.owner_a,
            pharmacy_name="Sec Pharmacy Alpha",
            registration_number="REG-SEC-001",
            address="Road 1, Jubilee Hills",
            city="Hyderabad",
            state="Telangana",
            pincode="500033",
            phone_number="+91 9333333331",
            is_approved=True
        )

        # Pharmacy Owner B
        self.owner_b = User.objects.create_user(
            username='sec_owner_b',
            email='owner_b@sec.test',
            password='ComplexOwnerPass123!',
            role='PHARMACY'
        )
        self.pharmacy_b = Pharmacy.objects.create(
            owner=self.owner_b,
            pharmacy_name="Sec Pharmacy Beta",
            registration_number="REG-SEC-002",
            address="Road 2, Banjara Hills",
            city="Hyderabad",
            state="Telangana",
            pincode="500034",
            phone_number="+91 9333333332",
            is_approved=True
        )

        # Medicine Catalog Item
        self.med = Medicine.objects.create(
            medicine_name="Securillin 500",
            generic_name="Amoxicillin",
            strength="500mg",
            dosage_form="Capsule",
            category="Antibiotics"
        )

        # Inventory in Pharmacy A
        self.inv_a = Inventory.objects.create(
            pharmacy=self.pharmacy_a,
            medicine=self.med,
            quantity=20
        )

        # Availability Request from Customer A to Pharmacy A
        self.request_a = AvailabilityRequest.objects.create(
            customer=self.customer_a,
            pharmacy=self.pharmacy_a,
            medicine=self.med,
            quantity_requested=2,
            status='PENDING'
        )

    # 1. Anonymous User Access Control
    def test_anonymous_access_redirects_to_login(self):
        protected_urls = [
            reverse('customer_dashboard'),
            reverse('pharmacy_dashboard'),
            reverse('admin_dashboard'),
            reverse('inventory_list'),
            reverse('customer_requests'),
            reverse('pharmacy_inbox'),
            reverse('notifications'),
            reverse('profile'),
        ]
        for url in protected_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, f"URL {url} should redirect anonymous users")
            self.assertIn('/accounts/login/', resp.url)

    # 2. Customer Role Restrictions
    def test_customer_cannot_access_pharmacy_or_admin_routes(self):
        self.client.force_login(self.customer_a)
        # Blocked from pharmacy inventory
        resp_inv = self.client.get(reverse('inventory_list'))
        self.assertEqual(resp_inv.status_code, 302)
        self.assertIn(reverse('dashboard'), resp_inv.url)

        # Blocked from admin portal
        resp_admin = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(resp_admin.status_code, 302)
        self.assertIn(reverse('dashboard'), resp_admin.url)

        # Blocked from approving pharmacies
        resp_toggle = self.client.post(reverse('toggle_pharmacy_approval', args=[self.pharmacy_a.id]))
        self.assertEqual(resp_toggle.status_code, 302)
        self.assertIn(reverse('dashboard'), resp_toggle.url)

    # 3. Pharmacy Role Restrictions
    def test_pharmacy_owner_cannot_access_admin_or_customer_inbox(self):
        self.client.force_login(self.owner_a)
        # Blocked from admin dashboard
        resp_admin = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(resp_admin.status_code, 302)
        self.assertIn(reverse('dashboard'), resp_admin.url)

        # Blocked from customer request history
        resp_cust = self.client.get(reverse('customer_requests'))
        self.assertEqual(resp_cust.status_code, 302)
        self.assertIn(reverse('dashboard'), resp_cust.url)

    # 4. Admin Role Restrictions & Authorization
    def test_admin_can_access_management_and_toggle_approvals(self):
        self.client.force_login(self.admin)
        resp_admin = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(resp_admin.status_code, 200)

        resp_list = self.client.get(reverse('admin_pharmacy_list'))
        self.assertEqual(resp_list.status_code, 200)

        # Non-admin user cannot access admin pharmacy list
        self.client.force_login(self.customer_a)
        resp_unauth = self.client.get(reverse('admin_pharmacy_list'))
        self.assertEqual(resp_unauth.status_code, 302)

    # 5. Customer Data Isolation (IDOR Defense)
    def test_customer_data_isolation(self):
        # Customer B attempts to view customer requests
        self.client.force_login(self.customer_b)
        resp = self.client.get(reverse('customer_requests'))
        self.assertEqual(resp.status_code, 200)
        # Customer B should NOT see Customer A's request
        self.assertNotIn(self.request_a, resp.context['requests'])

        # Customer B attempts to cancel Customer A's request
        resp_cancel = self.client.post(reverse('cancel_request', args=[self.request_a.id]))
        self.assertEqual(resp_cancel.status_code, 404)
        self.request_a.refresh_from_db()
        self.assertEqual(self.request_a.status, 'PENDING')  # Untouched

    # 6. Pharmacy Inventory Multi-Tenant Isolation
    def test_pharmacy_inventory_isolation(self):
        # Owner B attempts to view or edit Pharmacy A's inventory
        self.client.force_login(self.owner_b)
        resp_edit = self.client.post(reverse('inventory_edit', args=[self.inv_a.id]), {'quantity': 999})
        self.assertEqual(resp_edit.status_code, 404)
        self.inv_a.refresh_from_db()
        self.assertEqual(self.inv_a.quantity, 20)  # Untouched

        # Owner B attempts to delete Pharmacy A's inventory
        resp_del = self.client.post(reverse('inventory_delete', args=[self.inv_a.id]))
        self.assertEqual(resp_del.status_code, 404)
        self.assertTrue(Inventory.objects.filter(id=self.inv_a.id).exists())

    # 7. Unauthorized Response to Pharmacy Inquiry (IDOR Defense)
    def test_unauthorized_pharmacy_inquiry_response(self):
        # Owner B attempts to respond to request addressed to Pharmacy A
        self.client.force_login(self.owner_b)
        resp = self.client.post(
            reverse('respond_request', args=[self.request_a.id]),
            {'status': 'CONFIRMED', 'pharmacy_response': 'Hijacked response'}
        )
        self.assertEqual(resp.status_code, 404)
        self.request_a.refresh_from_db()
        self.assertEqual(self.request_a.status, 'PENDING')

    # 8. HTTP Method Enforcement (@require_POST)
    def test_http_method_enforcement_rejects_get(self):
        # 1. toggle_pharmacy_approval GET must return 405 Method Not Allowed
        self.client.force_login(self.admin)
        get_toggle = self.client.get(reverse('toggle_pharmacy_approval', args=[self.pharmacy_a.id]))
        self.assertEqual(get_toggle.status_code, 405)

        # 2. cancel_request GET must return 405 Method Not Allowed
        self.client.force_login(self.customer_a)
        get_cancel = self.client.get(reverse('cancel_request', args=[self.request_a.id]))
        self.assertEqual(get_cancel.status_code, 405)

        # 3. mark_notification_read GET must return 405 Method Not Allowed
        notif = Notification.objects.create(user=self.customer_a, message="Sec alert")
        get_read = self.client.get(reverse('mark_notification_read', args=[notif.id]))
        self.assertEqual(get_read.status_code, 405)

    # 9. Password Strength Validation during Registration
    def test_weak_passwords_rejected_during_registration(self):
        # Trivial password (< 8 chars, common)
        resp = self.client.post(reverse('register_customer'), {
            'username': 'weak_user',
            'email': 'weak@test.com',
            'password': '123',
            'confirm_password': '123',
        })
        self.assertEqual(resp.status_code, 200)  # Form redisplayed with errors
        form = resp.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

        # Password matching username
        resp_similar = self.client.post(reverse('register_customer'), {
            'username': 'userpass123',
            'email': 'similar@test.com',
            'password': 'userpass123',
            'confirm_password': 'userpass123',
        })
        self.assertEqual(resp_similar.status_code, 200)
        self.assertFalse(resp_similar.context['form'].is_valid())

    # 10. Invalid Input Validation (Negative Stock & Zero Quantity)
    def test_invalid_input_rejection(self):
        # Negative stock rejected by model clean
        inv_neg = Inventory(pharmacy=self.pharmacy_a, medicine=self.med, quantity=-5)
        with self.assertRaises(ValidationError):
            inv_neg.save()

        # Zero quantity requested rejected by form
        self.client.force_login(self.customer_a)
        resp = self.client.post(
            reverse('create_request', args=[self.pharmacy_a.id, self.med.id]),
            {'quantity_requested': 0, 'request_message': 'Invalid qty'}
        )
        self.assertEqual(resp.status_code, 200)  # Redisplay form
        self.assertIn('quantity_requested', resp.context['form'].errors)

    # 11. Session Logout Invalidation
    def test_logout_invalidates_session(self):
        self.client.force_login(self.customer_a)
        session_id = self.client.session.session_key
        self.assertTrue(bool(session_id))

        logout_resp = self.client.get(reverse('logout'))
        self.assertEqual(logout_resp.status_code, 302)
        # Session user id cleared
        self.assertIsNone(self.client.session.get('_auth_user_id'))

    # 12. Profile Email Collision Protection
    def test_user_profile_prevents_duplicate_email(self):
        self.client.force_login(self.customer_a)
        # Attempt to steal Customer B's email
        resp = self.client.post(reverse('profile'), {
            'first_name': 'Hacker',
            'last_name': 'User',
            'email': 'customer_b@sec.test',
            'phone_number': '+91 9999999999'
        })
        self.assertEqual(resp.status_code, 200)
        form = resp.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
