from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from pharmacies.services import calculate_haversine_distance
from requests_app.models import AvailabilityRequest, Notification

User = get_user_model()

class MediFindCompleteTestSuite(TestCase):
    def setUp(self):
        self.client = Client()
        
        # 1. Create test admin
        self.admin = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='testpassword123',
            role='ADMIN'
        )

        # 2. Create test customer
        self.customer = User.objects.create_user(
            username='customer_test',
            email='customer@test.com',
            password='testpassword123',
            role='CUSTOMER',
            phone_number='+91 9000000001'
        )

        # 3. Create test pharmacy owner
        self.pharmacy_owner = User.objects.create_user(
            username='owner_test',
            email='owner@test.com',
            password='testpassword123',
            role='PHARMACY',
            phone_number='+91 9000000002'
        )

        # 4. Create an approved pharmacy
        self.approved_pharmacy = Pharmacy.objects.create(
            owner=self.pharmacy_owner,
            pharmacy_name="Green Health Pharmacy",
            registration_number="REG-HYD-001",
            address="Banjara Hills",
            city="Hyderabad",
            state="Telangana",
            pincode="500034",
            phone_number="+91 9000000003",
            latitude=17.415582,
            longitude=78.435783,
            is_approved=True
        )

        # 5. Create an unapproved pharmacy
        self.unapproved_owner = User.objects.create_user(
            username='unapproved_owner',
            email='unapproved@test.com',
            password='testpassword123',
            role='PHARMACY'
        )
        self.unapproved_pharmacy = Pharmacy.objects.create(
            owner=self.unapproved_owner,
            pharmacy_name="Pending Health Chemist",
            registration_number="REG-HYD-999",
            address="Secunderabad",
            city="Hyderabad",
            state="Telangana",
            pincode="500003",
            phone_number="+91 9000000004",
            is_approved=False
        )

        # 6. Create sample medicines
        self.med_dolo = Medicine.objects.create(
            medicine_name="Dolo 650",
            generic_name="Paracetamol",
            strength="650mg",
            dosage_form="Tablet",
            category="Antipyretic",
            description="Fever and pain relief."
        )
        self.med_insulin = Medicine.objects.create(
            medicine_name="Lantus",
            generic_name="Insulin Glargine",
            strength="100 IU/ml",
            dosage_form="Injection",
            category="Antidiabetic"
        )

        # 7. Create inventory
        self.inv_dolo = Inventory.objects.create(
            pharmacy=self.approved_pharmacy,
            medicine=self.med_dolo,
            quantity=50  # Should be IN_STOCK automatically
        )

    # TEST: Customer Registration
    def test_customer_registration(self):
        resp = self.client.post(reverse('register_customer'), {
            'username': 'new_patient',
            'email': 'new_patient@test.com',
            'phone_number': '+91 9999988888',
            'password': 'patientpass123',
            'confirm_password': 'patientpass123',
        })
        self.assertEqual(resp.status_code, 302)
        new_user = User.objects.filter(username='new_patient').first()
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user.role, 'CUSTOMER')

    # TEST: Pharmacy Registration (creates User + Pharmacy)
    def test_pharmacy_registration(self):
        resp = self.client.post(reverse('register_pharmacy'), {
            'username': 'new_pharmacy_user',
            'email': 'pharmacy@store.com',
            'owner_phone': '+91 9999977777',
            'password': 'ownerpass123',
            'confirm_password': 'ownerpass123',
            'pharmacy_name': 'Metro Care Pharmacy',
            'registration_number': 'REG-BLR-888',
            'address': 'MG Road',
            'city': 'Bengaluru',
            'state': 'Karnataka',
            'pincode': '560001',
            'phone_number': '+91 9999977777',
        })
        self.assertEqual(resp.status_code, 302)
        owner_user = User.objects.filter(username='new_pharmacy_user').first()
        self.assertIsNotNone(owner_user)
        self.assertEqual(owner_user.role, 'PHARMACY')
        pharmacy = Pharmacy.objects.filter(registration_number='REG-BLR-888').first()
        self.assertIsNotNone(pharmacy)
        self.assertFalse(pharmacy.is_approved)  # Must start as unapproved!

    # TEST: Login and Logout
    def test_login_logout(self):
        login_resp = self.client.post(reverse('login'), {
            'username': 'customer_test',
            'password': 'testpassword123',
        })
        self.assertEqual(login_resp.status_code, 302)
        logout_resp = self.client.get(reverse('logout'))
        self.assertEqual(logout_resp.status_code, 302)

    # TEST: Inventory auto-status derivation and negative quantity rejection
    def test_inventory_status_and_negative_rejection(self):
        # Quantity > 10 -> IN_STOCK
        inv = Inventory.objects.create(
            pharmacy=self.approved_pharmacy,
            medicine=self.med_insulin,
            quantity=15
        )
        self.assertEqual(inv.availability_status, 'IN_STOCK')

        # Quantity 1..10 -> LOW_STOCK
        inv.quantity = 5
        inv.save()
        self.assertEqual(inv.availability_status, 'LOW_STOCK')

        # Quantity 0 -> OUT_OF_STOCK
        inv.quantity = 0
        inv.save()
        self.assertEqual(inv.availability_status, 'OUT_OF_STOCK')

        # Negative quantity should raise ValidationError
        inv.quantity = -5
        with self.assertRaises(ValidationError):
            inv.save()

    # TEST: Medicine Search and Approved Pharmacy Filter
    def test_medicine_search_only_shows_approved_pharmacies(self):
        # Stock Dolo in unapproved pharmacy
        Inventory.objects.create(
            pharmacy=self.unapproved_pharmacy,
            medicine=self.med_dolo,
            quantity=100
        )

        resp = self.client.get(reverse('search_medicines'), {'q': 'Dolo'})
        self.assertEqual(resp.status_code, 200)
        results = resp.context['results']
        
        # Verify that ONLY the approved pharmacy appears in public search!
        for item in results:
            self.assertTrue(item.pharmacy.is_approved)
            self.assertNotEqual(item.pharmacy.id, self.unapproved_pharmacy.id)

    # TEST: Location Filtering (City / Pincode)
    def test_search_location_filter(self):
        resp = self.client.get(reverse('search_medicines'), {'city': 'Hyderabad'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(all(item.pharmacy.city.lower() == 'hyderabad' for item in resp.context['results']))

        resp_none = self.client.get(reverse('search_medicines'), {'city': 'NonExistentCity'})
        self.assertEqual(resp_none.status_code, 200)
        self.assertEqual(len(resp_none.context['results']), 0)

    # TEST: Availability Request Lifecycle
    def test_availability_request_workflow(self):
        # 1. Customer sends inquiry
        self.client.force_login(self.customer)
        req_resp = self.client.post(
            reverse('create_request', args=[self.approved_pharmacy.id, self.med_dolo.id]),
            {'quantity_requested': 2, 'request_message': 'Need urgently'}
        )
        self.assertEqual(req_resp.status_code, 302)
        req = AvailabilityRequest.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, 'PENDING')

        # 2. Pharmacy owner responds to inquiry
        self.client.force_login(self.pharmacy_owner)
        resp_action = self.client.post(
            reverse('respond_request', args=[req.id]),
            {'status': 'CONFIRMED', 'pharmacy_response': 'Ready at front billing counter.'}
        )
        self.assertEqual(resp_action.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'CONFIRMED')
        self.assertEqual(req.pharmacy_response, 'Ready at front billing counter.')

        # 3. Notification created for customer
        notif = Notification.objects.filter(user=self.customer).last()
        self.assertIsNotNone(notif)
        self.assertIn("Confirmed Available", notif.message)

    # TEST: Multi-Tenant Unauthorized Access Protection
    def test_unauthorized_inventory_modification(self):
        # Unapproved owner tries to edit approved owner's inventory item
        self.client.force_login(self.unapproved_owner)
        resp = self.client.post(
            reverse('inventory_edit', args=[self.inv_dolo.id]),
            {'quantity': 999}
        )
        # Should return 404 because query filters by pharmacy=user's pharmacy!
        self.assertEqual(resp.status_code, 404)
        self.inv_dolo.refresh_from_db()
        self.assertEqual(self.inv_dolo.quantity, 50)  # Untouched!

    # TEST: Admin Pharmacy Approval Toggle
    def test_admin_pharmacy_approval(self):
        self.client.force_login(self.admin)
        self.assertFalse(self.unapproved_pharmacy.is_approved)
        resp = self.client.post(reverse('toggle_pharmacy_approval', args=[self.unapproved_pharmacy.id]))
        self.assertEqual(resp.status_code, 302)
        self.unapproved_pharmacy.refresh_from_db()
        self.assertTrue(self.unapproved_pharmacy.is_approved)

    # TEST: Haversine Distance Helper Function
    def test_haversine_calculation(self):
        # Hyderabad to Bengaluru: ~500 km
        dist = calculate_haversine_distance(17.3850, 78.4867, 12.9716, 77.5946)
        self.assertIsNotNone(dist)
        self.assertTrue(490.0 <= dist <= 515.0)

        # None or invalid coordinates return None
        self.assertIsNone(calculate_haversine_distance(None, 78.0, 12.0, 77.0))
        self.assertIsNone(calculate_haversine_distance("invalid", 78.0, 12.0, 77.0))

    # TEST: Search with GPS Coordinates and Haversine Sorting
    def test_search_with_distance_and_sort(self):
        # User is located near Banjara Hills (17.4150, 78.4350)
        resp = self.client.get(reverse('search_medicines'), {
            'lat': '17.4150',
            'lng': '78.4350',
            'sort': 'distance'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['has_user_coords'])
        results = resp.context['results']
        self.assertGreater(len(results), 0)
        self.assertIsNotNone(results[0].distance_km)
        # Verify distance is under 1 km since coordinates are right next to the pharmacy
        self.assertLess(results[0].distance_km, 1.0)

    # TEST: Admin Master Catalogue Curation (Add & Edit Medicine)
    def test_admin_medicine_management(self):
        self.client.force_login(self.admin)
        
        # Add new medicine
        add_resp = self.client.post(reverse('add_medicine'), {
            'medicine_name': 'Azithral 500',
            'generic_name': 'Azithromycin',
            'strength': '500mg',
            'dosage_form': 'Tablet',
            'category': 'Antibiotics',
            'description': 'Bacterial infections'
        })
        self.assertEqual(add_resp.status_code, 302)
        new_med = Medicine.objects.filter(medicine_name='Azithral 500').first()
        self.assertIsNotNone(new_med)
        self.assertEqual(new_med.generic_name, 'Azithromycin')

        # Edit medicine
        edit_resp = self.client.post(reverse('edit_medicine', args=[new_med.id]), {
            'medicine_name': 'Azithral 500 Forte',
            'generic_name': 'Azithromycin Dihydrate',
            'strength': '500mg',
            'dosage_form': 'Tablet',
            'category': 'Antibiotics',
            'description': 'Updated description'
        })
        self.assertEqual(edit_resp.status_code, 302)
        new_med.refresh_from_db()
        self.assertEqual(new_med.medicine_name, 'Azithral 500 Forte')

    # TEST: Inventory Deletion & Multi-Tenant Protection
    def test_inventory_delete(self):
        # Unauthorized owner cannot delete
        self.client.force_login(self.unapproved_owner)
        unauth_resp = self.client.post(reverse('inventory_delete', args=[self.inv_dolo.id]))
        self.assertEqual(unauth_resp.status_code, 404)
        self.assertTrue(Inventory.objects.filter(id=self.inv_dolo.id).exists())

        # Legitimate owner can delete
        self.client.force_login(self.pharmacy_owner)
        auth_resp = self.client.post(reverse('inventory_delete', args=[self.inv_dolo.id]))
        self.assertEqual(auth_resp.status_code, 302)
        self.assertFalse(Inventory.objects.filter(id=self.inv_dolo.id).exists())

    # TEST: Customer Inquiry Cancellation
    def test_customer_cancel_request(self):
        # Customer creates request
        req = AvailabilityRequest.objects.create(
            customer=self.customer,
            pharmacy=self.approved_pharmacy,
            medicine=self.med_dolo,
            quantity_requested=1,
            status='PENDING'
        )
        self.client.force_login(self.customer)
        cancel_resp = self.client.post(reverse('cancel_request', args=[req.id]))
        self.assertEqual(cancel_resp.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'CANCELLED')

    # TEST: Role-Based Dashboard Dispatcher
    def test_dashboard_dispatcher(self):
        # Anonymous user -> login
        resp_anon = self.client.get(reverse('dashboard'))
        self.assertEqual(resp_anon.status_code, 302)
        self.assertIn('/accounts/login/', resp_anon.url)

        # Customer -> customer dashboard
        self.client.force_login(self.customer)
        resp_cust = self.client.get(reverse('dashboard'))
        self.assertEqual(resp_cust.status_code, 302)
        self.assertIn(reverse('customer_dashboard'), resp_cust.url)

        # Pharmacy Owner -> pharmacy dashboard
        self.client.force_login(self.pharmacy_owner)
        resp_pharm = self.client.get(reverse('dashboard'))
        self.assertEqual(resp_pharm.status_code, 302)
        self.assertIn(reverse('pharmacy_dashboard'), resp_pharm.url)

        # Admin -> admin dashboard
        self.client.force_login(self.admin)
        resp_adm = self.client.get(reverse('dashboard'))
        self.assertEqual(resp_adm.status_code, 302)
        self.assertIn(reverse('admin_dashboard'), resp_adm.url)

    # TEST: Access Control Role Guards
    def test_role_access_guards(self):
        # Customer blocked from inventory management
        self.client.force_login(self.customer)
        inv_resp = self.client.get(reverse('inventory_list'))
        self.assertEqual(inv_resp.status_code, 302)
        self.assertIn(reverse('dashboard'), inv_resp.url)

        # Customer blocked from admin dashboard
        adm_resp = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(adm_resp.status_code, 302)
        self.assertIn(reverse('dashboard'), adm_resp.url)

    # TEST: Notification Read Flow
    def test_notification_flow(self):
        notif = Notification.objects.create(
            user=self.customer,
            message="Test notification alert",
            is_read=False
        )
        self.client.force_login(self.customer)
        mark_resp = self.client.post(reverse('mark_notification_read', args=[notif.id]))
        self.assertEqual(mark_resp.status_code, 302)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
