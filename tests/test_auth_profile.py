from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pharmacies.models import Pharmacy

User = get_user_model()


class AuthenticationAndProfileTests(TestCase):
    """
    Automated test suite verifying the 15 vectors required for Phase 3:
    1. Customer registration.
    2. Duplicate registration.
    3. Customer login.
    4. Invalid login.
    5. Customer logout.
    6. Pharmacy registration.
    7. Pharmacy approval status.
    8. Profile viewing.
    9. Profile editing.
    10. Unauthorized profile editing.
    11. Password change.
    12. Password reset.
    13. Role-based redirects.
    14. Protected dashboard access.
    15. Customer and pharmacy data isolation.
    """

    def setUp(self):
        self.client = Client()

        # Customer User
        self.customer = User.objects.create_user(
            username='jane_customer',
            email='jane@example.com',
            password='CustomerPass123!',
            first_name='Jane',
            last_name='Doe',
            phone_number='9876543210',
            role='CUSTOMER'
        )

        # Pharmacy Owner User & Pharmacy
        self.pharmacy_owner = User.objects.create_user(
            username='apollo_owner',
            email='apollo@example.com',
            password='PharmacyPass123!',
            first_name='Ramesh',
            last_name='Kumar',
            phone_number='9123456780',
            role='PHARMACY'
        )
        self.pharmacy = Pharmacy.objects.create(
            owner=self.pharmacy_owner,
            pharmacy_name="Apollo Healthcare Chemist",
            registration_number="REG-DL-2024-110",
            address="Plot 45, Jubilee Hills",
            city="Hyderabad",
            state="Telangana",
            pincode="500033",
            phone_number="040-23456789",
            latitude=Decimal('17.425000'),
            longitude=Decimal('78.410000'),
            is_approved=True
        )

        # Secondary Pharmacy Owner for isolation testing
        self.other_pharmacy_owner = User.objects.create_user(
            username='medplus_owner',
            email='medplus@example.com',
            password='PharmacyPass123!',
            first_name='Suresh',
            last_name='Reddy',
            phone_number='9988776655',
            role='PHARMACY'
        )
        self.other_pharmacy = Pharmacy.objects.create(
            owner=self.other_pharmacy_owner,
            pharmacy_name="MedPlus Pharmacy",
            registration_number="REG-DL-2024-220",
            address="Main Road, Madhapur",
            city="Hyderabad",
            state="Telangana",
            pincode="500081",
            phone_number="040-98765432",
            latitude=Decimal('17.448000'),
            longitude=Decimal('78.390000'),
            is_approved=True
        )

        # Administrator User
        self.admin = User.objects.create_superuser(
            username='system_admin',
            email='admin@medfind.com',
            password='AdminPass123!',
            role='ADMIN'
        )

    # 1. Customer registration
    def test_customer_registration(self):
        resp = self.client.post(reverse('register_customer'), {
            'first_name': 'Rahul',
            'last_name': 'Sharma',
            'username': 'rahul_s',
            'email': 'rahul@example.com',
            'phone_number': '9811223344',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
        })
        self.assertEqual(resp.status_code, 302)
        user = User.objects.filter(username='rahul_s').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'rahul@example.com')
        self.assertEqual(user.first_name, 'Rahul')
        self.assertEqual(user.last_name, 'Sharma')
        self.assertEqual(user.role, 'CUSTOMER')
        self.assertTrue(user.check_password('SecurePassword123!'))

    # 2. Duplicate registration prevention (Username and Email)
    def test_duplicate_registration(self):
        # Duplicate username
        resp_user = self.client.post(reverse('register_customer'), {
            'username': 'jane_customer',
            'email': 'different_email@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
        })
        self.assertEqual(resp_user.status_code, 200)
        self.assertIn('username', resp_user.context['form'].errors)
        self.assertEqual(resp_user.context['form'].errors['username'][0], 'This username is already taken.')

        # Duplicate email (case-insensitive)
        resp_email = self.client.post(reverse('register_customer'), {
            'username': 'unique_user_99',
            'email': 'JANE@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
        })
        self.assertEqual(resp_email.status_code, 200)
        self.assertIn('email', resp_email.context['form'].errors)
        self.assertEqual(resp_email.context['form'].errors['email'][0], 'A user with this email address already exists.')

    # 3. Customer login
    def test_customer_login(self):
        resp = self.client.post(reverse('login'), {
            'username': 'jane_customer',
            'password': 'CustomerPass123!',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.customer.id)

    # 4. Invalid login rejected
    def test_invalid_login(self):
        # Wrong password
        resp_bad_pass = self.client.post(reverse('login'), {
            'username': 'jane_customer',
            'password': 'WrongPassword999!',
        })
        self.assertEqual(resp_bad_pass.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(resp_bad_pass, "Invalid username or password")

        # Nonexistent username
        resp_bad_user = self.client.post(reverse('login'), {
            'username': 'ghost_user',
            'password': 'CustomerPass123!',
        })
        self.assertEqual(resp_bad_user.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    # 5. Customer logout
    def test_customer_logout(self):
        self.client.force_login(self.customer)
        self.assertIn('_auth_user_id', self.client.session)
        resp = self.client.get(reverse('logout'))
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    # 6. Pharmacy registration
    def test_pharmacy_registration(self):
        resp = self.client.post(reverse('register_pharmacy'), {
            'owner_first_name': 'Anil',
            'owner_last_name': 'Reddy',
            'username': 'anil_pharma',
            'email': 'anil@lifecare.com',
            'owner_phone': '9848012345',
            'password': 'PharmaOwnerPass123!',
            'confirm_password': 'PharmaOwnerPass123!',
            'pharmacy_name': 'LifeCare Meds',
            'registration_number': 'REG-TS-2024-555',
            'address': 'Plot 12, Gachibowli',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500032',
            'phone_number': '040-5551234',
            'latitude': '17.440080',
            'longitude': '78.348910',
        })
        self.assertEqual(resp.status_code, 302)
        owner = User.objects.filter(username='anil_pharma').first()
        self.assertIsNotNone(owner)
        self.assertEqual(owner.role, 'PHARMACY')
        pharm = Pharmacy.objects.filter(owner=owner).first()
        self.assertIsNotNone(pharm)
        self.assertEqual(pharm.pharmacy_name, 'LifeCare Meds')
        self.assertEqual(pharm.registration_number, 'REG-TS-2024-555')

    # 7. Pharmacy approval status starts as False
    def test_pharmacy_approval_status(self):
        resp = self.client.post(reverse('register_pharmacy'), {
            'username': 'pending_store_owner',
            'email': 'pending@store.com',
            'owner_phone': '9848099999',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!',
            'pharmacy_name': 'Pending Chemist Store',
            'registration_number': 'REG-PEND-001',
            'address': 'Kukatpally',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500072',
            'phone_number': '040-9999888',
        })
        self.assertEqual(resp.status_code, 302)
        pharm = Pharmacy.objects.filter(registration_number='REG-PEND-001').first()
        self.assertIsNotNone(pharm)
        self.assertFalse(pharm.is_approved)

    # 8. Profile viewing
    def test_profile_viewing(self):
        # Customer Profile
        self.client.force_login(self.customer)
        resp_cust = self.client.get(reverse('profile'))
        self.assertEqual(resp_cust.status_code, 200)
        self.assertContains(resp_cust, "Jane")
        self.assertContains(resp_cust, "Doe")
        self.assertContains(resp_cust, "jane@example.com")
        self.assertContains(resp_cust, "Customer")

        # Pharmacy Owner Profile
        self.client.force_login(self.pharmacy_owner)
        resp_pharm = self.client.get(reverse('profile'))
        self.assertEqual(resp_pharm.status_code, 200)
        self.assertContains(resp_pharm, "Apollo Healthcare Chemist")
        self.assertContains(resp_pharm, "REG-DL-2024-110")
        self.assertContains(resp_pharm, "Approved &amp; Publicly Visible")

    # 9. Profile editing
    def test_profile_editing(self):
        # Customer edits their own name and phone
        self.client.force_login(self.customer)
        resp = self.client.post(reverse('profile'), {
            'action': 'user',
            'first_name': 'Janet',
            'last_name': 'Doe-Smith',
            'email': 'jane@example.com',
            'phone_number': '9999900000',
        })
        self.assertEqual(resp.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, 'Janet')
        self.assertEqual(self.customer.last_name, 'Doe-Smith')
        self.assertEqual(self.customer.phone_number, '9999900000')

        # Pharmacy owner edits pharmacy contact details
        self.client.force_login(self.pharmacy_owner)
        resp_pharm = self.client.post(reverse('profile'), {
            'action': 'pharmacy',
            'pharmacy_name': 'Apollo Chemist Superstore',
            'phone_number': '040-99991111',
            'address': 'Plot 45, Jubilee Hills Road 36',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500033',
            'latitude': '17.425000',
            'longitude': '78.410000',
        })
        self.assertEqual(resp_pharm.status_code, 302)
        self.pharmacy.refresh_from_db()
        self.assertEqual(self.pharmacy.pharmacy_name, 'Apollo Chemist Superstore')
        self.assertEqual(self.pharmacy.phone_number, '040-99991111')

    # 10. Unauthorized profile editing (unauthenticated & role tampering prevention)
    def test_unauthorized_profile_editing(self):
        # Unauthenticated user redirected
        resp_anon = self.client.get(reverse('profile'))
        self.assertEqual(resp_anon.status_code, 302)
        self.assertIn('/accounts/login/', resp_anon.url)

        # Customer attempts to alter role to ADMIN via POST
        self.client.force_login(self.customer)
        resp_tamper = self.client.post(reverse('profile'), {
            'action': 'user',
            'first_name': 'Hacker',
            'last_name': 'Customer',
            'email': 'jane@example.com',
            'phone_number': '9999900000',
            'role': 'ADMIN',
            'is_staff': True,
            'is_superuser': True,
        })
        self.assertEqual(resp_tamper.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.role, 'CUSTOMER')
        self.assertFalse(self.customer.is_staff)
        self.assertFalse(self.customer.is_superuser)

    # 11. Password change
    def test_password_change(self):
        self.client.force_login(self.customer)
        resp = self.client.post(reverse('password_change'), {
            'old_password': 'CustomerPass123!',
            'new_password1': 'BrandNewPass999!',
            'new_password2': 'BrandNewPass999!',
        })
        self.assertEqual(resp.status_code, 302)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password('BrandNewPass999!'))
        self.assertFalse(self.customer.check_password('CustomerPass123!'))

    # 12. Password reset workflow (token-based)
    def test_password_reset(self):
        # 1. Initiate password reset
        mail.outbox = []
        resp_init = self.client.post(reverse('password_reset'), {
            'email': 'jane@example.com'
        })
        self.assertEqual(resp_init.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        email_content = mail.outbox[0].body
        self.assertIn('password-reset-confirm', email_content)

        # 2. Extract token & uidb64
        uidb64 = urlsafe_base64_encode(force_bytes(self.customer.pk))
        token = default_token_generator.make_token(self.customer)

        # 3. Simulate user following token link (sets session and redirects to set-password)
        resp_token_link = self.client.get(
            reverse('password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
        )
        self.assertEqual(resp_token_link.status_code, 302)

        # 4. Confirm new password submission on the set-password URL
        resp_confirm = self.client.post(
            resp_token_link.url,
            {
                'new_password1': 'ResetCompletePass777!',
                'new_password2': 'ResetCompletePass777!',
            }
        )
        self.assertEqual(resp_confirm.status_code, 302)
        self.assertRedirects(resp_confirm, reverse('password_reset_complete'))
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password('ResetCompletePass777!'))

        # Nonexistent email does not crash or leak user existence
        mail.outbox = []
        resp_nonexistent = self.client.post(reverse('password_reset'), {
            'email': 'nonexistent_account_xyz@example.com'
        })
        self.assertEqual(resp_nonexistent.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    # 13. Role-based redirects via dispatcher
    def test_role_based_redirects(self):
        # Customer redirected to customer dashboard
        self.client.force_login(self.customer)
        resp_c = self.client.get(reverse('dashboard'))
        self.assertRedirects(resp_c, reverse('customer_dashboard'))

        # Pharmacy owner redirected to pharmacy dashboard
        self.client.force_login(self.pharmacy_owner)
        resp_p = self.client.get(reverse('dashboard'))
        self.assertRedirects(resp_p, reverse('pharmacy_dashboard'))

        # Admin redirected to admin dashboard
        self.client.force_login(self.admin)
        resp_a = self.client.get(reverse('dashboard'))
        self.assertRedirects(resp_a, reverse('admin_dashboard'))

    # 14. Protected dashboard access
    def test_protected_dashboard_access(self):
        # Customer cannot access pharmacy dashboard
        self.client.force_login(self.customer)
        resp_cp = self.client.get(reverse('pharmacy_dashboard'))
        self.assertEqual(resp_cp.status_code, 302)
        self.assertEqual(resp_cp.url, reverse('dashboard'))

        # Customer cannot access admin dashboard
        resp_ca = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(resp_ca.status_code, 302)
        self.assertEqual(resp_ca.url, reverse('dashboard'))

        # Pharmacy owner cannot access admin dashboard
        self.client.force_login(self.pharmacy_owner)
        resp_pa = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(resp_pa.status_code, 302)
        self.assertEqual(resp_pa.url, reverse('dashboard'))

    # 15. Customer and pharmacy data isolation
    def test_customer_and_pharmacy_data_isolation(self):
        # Pharmacy owner A cannot update Pharmacy B's profile
        self.client.force_login(self.pharmacy_owner)
        # Attempt to tamper by sending action='pharmacy'
        # The view uses get_pharmacy_for_user(request.user) - it will only update self.pharmacy!
        resp = self.client.post(reverse('profile'), {
            'action': 'pharmacy',
            'pharmacy_name': 'Tampered Name',
            'phone_number': '040-11112222',
            'address': 'Hacked Address',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500081',
        })
        self.assertEqual(resp.status_code, 302)
        # self.pharmacy was updated, other_pharmacy remains untouched
        self.other_pharmacy.refresh_from_db()
        self.assertEqual(self.other_pharmacy.pharmacy_name, "MedPlus Pharmacy")
        self.assertEqual(self.other_pharmacy.phone_number, "040-98765432")
