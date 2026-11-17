import datetime
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from inventory.forms import InventoryAddForm, InventoryEditForm
from inventory.models import Inventory
from inventory.services import add_or_update_inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from requests_app.models import AvailabilityRequest
from requests_app.services import (
    create_availability_inquiry,
    respond_to_availability_inquiry,
)

User = get_user_model()


class PharmacyDashboardAndInventoryTests(TestCase):
    """
    Automated test suite verifying the 15 vectors required for Phase 6:
    1. Pharmacy dashboard access (role-based access control).
    2. Pharmacy analytics accuracy (KPI counts and chart metrics).
    3. Inventory creation with automatic status determination.
    4. Inventory update and dynamic status re-classification.
    5. Inventory deletion and removal.
    6. Duplicate inventory prevention via unique constraint.
    7. Negative stock validation (model and form layers).
    8. Low-stock classification (1-10 units).
    9. Out-of-stock classification (0 units).
    10. Customer request management (pharmacy inbox visibility).
    11. Invalid request state transitions (cancelled requests guarded).
    12. Strict multi-tenant pharmacy isolation (no cross-tenant leakage).
    13. Unapproved pharmacy restrictions (warning banner, exclusion from public search).
    14. Inventory freshness tier tracking (FRESH, MODERATE, STALE).
    15. Inventory pagination and filter preservation.
    """

    def setUp(self):
        self.client = Client()

        # Pharmacy A User & Pharmacy (Approved)
        self.owner_a = User.objects.create_user(
            username='apothecary_a',
            email='owner_a@apothecary.com',
            password='SecurePass123!',
            first_name='Arthur',
            last_name='Doyle',
            phone_number='9876543210',
            role='PHARMACY'
        )
        self.pharmacy_a = Pharmacy.objects.create(
            owner=self.owner_a,
            pharmacy_name="Apothecary Alpha",
            registration_number="REG-ALPHA-001",
            address="100 Baker Street",
            city="Hyderabad",
            state="Telangana",
            pincode="500001",
            phone_number="040-11223344",
            latitude=17.3850,
            longitude=78.4867,
            is_approved=True
        )

        # Pharmacy B User & Pharmacy (Approved, for isolation testing)
        self.owner_b = User.objects.create_user(
            username='apothecary_b',
            email='owner_b@apothecary.com',
            password='SecurePass123!',
            first_name='Beatrice',
            last_name='Potter',
            phone_number='9876543211',
            role='PHARMACY'
        )
        self.pharmacy_b = Pharmacy.objects.create(
            owner=self.owner_b,
            pharmacy_name="Beta Chemist",
            registration_number="REG-BETA-002",
            address="200 Elm Street",
            city="Hyderabad",
            state="Telangana",
            pincode="500002",
            phone_number="040-55667788",
            latitude=17.3900,
            longitude=78.4900,
            is_approved=True
        )

        # Customer User
        self.customer = User.objects.create_user(
            username='charlie_patient',
            email='charlie@patient.com',
            password='PatientPass123!',
            first_name='Charlie',
            last_name='Brown',
            phone_number='9876543212',
            role='CUSTOMER'
        )

        # Master Catalog Medicines
        self.med_paracetamol = Medicine.objects.create(
            medicine_name="Paracetamol 650",
            generic_name="Paracetamol",
            category="Analgesics & Pain Relief",
            dosage_form="Tablet",
            strength="650mg"
        )
        self.med_amoxicillin = Medicine.objects.create(
            medicine_name="Amoxicillin 500",
            generic_name="Amoxicillin Trihydrate",
            category="Antibiotics",
            dosage_form="Capsule",
            strength="500mg"
        )
        self.med_metformin = Medicine.objects.create(
            medicine_name="Metformin 500 SR",
            generic_name="Metformin Hydrochloride",
            category="Antidiabetic",
            dosage_form="Tablet",
            strength="500mg"
        )

    def test_pharmacy_dashboard_access(self):
        """Vector 1: Authenticated pharmacy owner gets 200; customers and anon users are restricted."""
        # Anon user redirected to login
        response = self.client.get(reverse('pharmacy_dashboard'))
        self.assertEqual(response.status_code, 302)

        # Customer user denied access / redirected
        self.client.login(username='charlie_patient', password='PatientPass123!')
        response = self.client.get(reverse('pharmacy_dashboard'))
        self.assertEqual(response.status_code, 302)

        # Pharmacy owner gets 200
        self.client.login(username='apothecary_a', password='SecurePass123!')
        response = self.client.get(reverse('pharmacy_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/pharmacy_dashboard.html')
        self.assertContains(response, "Apothecary Alpha")
        self.assertContains(response, "REG-ALPHA-001")

    def test_pharmacy_analytics(self):
        """Vector 2: Dashboard metrics accurately aggregate inventory status and inquiries."""
        # Setup Pharmacy A inventory: 1 in-stock (20), 1 low-stock (5), 1 out-of-stock (0)
        Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=self.med_paracetamol, quantity=20)
        Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=self.med_amoxicillin, quantity=5)
        Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=self.med_metformin, quantity=0)

        # Requests: 1 PENDING, 1 CONFIRMED
        AvailabilityRequest.objects.create(
            customer=self.customer,
            pharmacy=self.pharmacy_a,
            medicine=self.med_paracetamol,
            quantity_requested=2,
            status='PENDING'
        )
        AvailabilityRequest.objects.create(
            customer=self.customer,
            pharmacy=self.pharmacy_a,
            medicine=self.med_amoxicillin,
            quantity_requested=1,
            status='CONFIRMED',
            pharmacy_response='Ready for pickup'
        )

        self.client.login(username='apothecary_a', password='SecurePass123!')
        response = self.client.get(reverse('pharmacy_dashboard'))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['total_items'], 3)
        self.assertEqual(response.context['in_stock_count'], 1)
        self.assertEqual(response.context['low_stock_count'], 1)
        self.assertEqual(response.context['out_stock_count'], 1)
        self.assertEqual(response.context['pending_requests_count'], 1)
        self.assertGreaterEqual(response.context['total_catalog_medicines'], 3)

    def test_inventory_creation(self):
        """Vector 3: Adding stock creates an inventory record with auto-computed status."""
        self.client.login(username='apothecary_a', password='SecurePass123!')
        response = self.client.post(reverse('inventory_add'), {
            'medicine': self.med_paracetamol.id,
            'quantity': 35
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('inventory_list'))

        inv = Inventory.objects.get(pharmacy=self.pharmacy_a, medicine=self.med_paracetamol)
        self.assertEqual(inv.quantity, 35)
        self.assertEqual(inv.availability_status, 'IN_STOCK')

    def test_inventory_update(self):
        """Vector 4: Updating stock quantity recomputes availability status."""
        inv = Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=self.med_paracetamol, quantity=40)
        self.assertEqual(inv.availability_status, 'IN_STOCK')

        self.client.login(username='apothecary_a', password='SecurePass123!')

        # Update to low stock (7 units)
        response = self.client.post(reverse('inventory_edit', kwargs={'pk': inv.pk}), {
            'quantity': 7
        })
        self.assertEqual(response.status_code, 302)
        inv.refresh_from_db()
        self.assertEqual(inv.quantity, 7)
        self.assertEqual(inv.availability_status, 'LOW_STOCK')

        # Update to out of stock (0 units)
        self.client.post(reverse('inventory_edit', kwargs={'pk': inv.pk}), {
            'quantity': 0
        })
        inv.refresh_from_db()
        self.assertEqual(inv.quantity, 0)
        self.assertEqual(inv.availability_status, 'OUT_OF_STOCK')

    def test_inventory_deletion(self):
        """Vector 5: Pharmacy owner can delete inventory record."""
        inv = Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=self.med_paracetamol, quantity=15)
        self.client.login(username='apothecary_a', password='SecurePass123!')

        response = self.client.post(reverse('inventory_delete', kwargs={'pk': inv.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('inventory_list'))
        self.assertFalse(Inventory.objects.filter(pk=inv.pk).exists())

    def test_duplicate_inventory_prevention(self):
        """Vector 6: Duplicate (pharmacy, medicine) entry raises ValidationError/IntegrityError and add_or_update updates."""
        Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=self.med_paracetamol, quantity=10)

        # Direct duplicate creation raises ValidationError (via full_clean) or IntegrityError
        with self.assertRaises((ValidationError, IntegrityError)):
            Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=self.med_paracetamol, quantity=20)

        # Service add_or_update_inventory updates quantity without creating duplicate
        item, created = add_or_update_inventory(self.pharmacy_a, self.med_paracetamol, 55)
        self.assertFalse(created)
        self.assertEqual(item.quantity, 55)
        self.assertEqual(Inventory.objects.filter(pharmacy=self.pharmacy_a, medicine=self.med_paracetamol).count(), 1)

    def test_negative_stock_validation(self):
        """Vector 7: Negative stock quantity rejected by model validation and form clean."""
        # Model level validation
        inv = Inventory(pharmacy=self.pharmacy_a, medicine=self.med_paracetamol, quantity=-5)
        with self.assertRaises(ValidationError):
            inv.full_clean()

        # Form level validation
        form_add = InventoryAddForm(data={'medicine': self.med_paracetamol.id, 'quantity': -10})
        self.assertFalse(form_add.is_valid())
        self.assertIn('quantity', form_add.errors)

        form_edit = InventoryEditForm(data={'quantity': -1})
        self.assertFalse(form_edit.is_valid())
        self.assertIn('quantity', form_edit.errors)

    def test_low_stock_classification(self):
        """Vector 8: Quantities 1 to 10 automatically classified as LOW_STOCK."""
        inv1 = Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=self.med_paracetamol, quantity=1)
        self.assertEqual(inv1.availability_status, 'LOW_STOCK')

        inv10 = Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=self.med_amoxicillin, quantity=10)
        self.assertEqual(inv10.availability_status, 'LOW_STOCK')

    def test_out_of_stock_classification(self):
        """Vector 9: Quantity 0 automatically classified as OUT_OF_STOCK."""
        inv0 = Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=self.med_metformin, quantity=0)
        self.assertEqual(inv0.availability_status, 'OUT_OF_STOCK')

    def test_customer_request_management(self):
        """Vector 10: Pharmacy can view incoming requests in inbox and respond."""
        req = create_availability_inquiry(
            customer=self.customer,
            pharmacy=self.pharmacy_a,
            medicine=self.med_paracetamol,
            quantity_requested=3,
            request_message="Need for high fever"
        )

        self.client.login(username='apothecary_a', password='SecurePass123!')
        response = self.client.get(reverse('pharmacy_inbox'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "charlie_patient")
        self.assertContains(response, "Paracetamol 650")

        # Pharmacy responds CONFIRMED
        resp_post = self.client.post(reverse('respond_request', kwargs={'pk': req.pk}), {
            'status': 'CONFIRMED',
            'pharmacy_response': 'Held at counter 2 for 4 hours.'
        })
        self.assertEqual(resp_post.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'CONFIRMED')
        self.assertEqual(req.pharmacy_response, 'Held at counter 2 for 4 hours.')

    def test_invalid_request_transitions(self):
        """Vector 11: Responding to CANCELLED request blocked; invalid transition statuses rejected."""
        req = create_availability_inquiry(
            customer=self.customer,
            pharmacy=self.pharmacy_a,
            medicine=self.med_paracetamol,
            quantity_requested=1
        )
        req.status = 'CANCELLED'
        req.save()

        # Responding via view redirects with warning
        self.client.login(username='apothecary_a', password='SecurePass123!')
        response = self.client.get(reverse('respond_request', kwargs={'pk': req.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('pharmacy_inbox'))

        # Direct service call raises ValidationError
        with self.assertRaises(ValidationError):
            respond_to_availability_inquiry(req.pk, self.pharmacy_a, 'CONFIRMED', 'Attempted note')

        # Setting invalid status raises ValidationError
        req.status = 'PENDING'
        req.save()
        with self.assertRaises(ValidationError):
            respond_to_availability_inquiry(req.pk, self.pharmacy_a, 'PENDING', 'Invalid loop')

    def test_pharmacy_ownership_protection(self):
        """Vector 12: Multi-tenant protection: Pharmacy A cannot access or mutate Pharmacy B's data."""
        # Pharmacy B inventory item
        inv_b = Inventory.objects.create(pharmacy=self.pharmacy_b, medicine=self.med_paracetamol, quantity=25)
        # Pharmacy B customer request
        req_b = AvailabilityRequest.objects.create(
            customer=self.customer,
            pharmacy=self.pharmacy_b,
            medicine=self.med_paracetamol,
            quantity_requested=2
        )

        # Login as Pharmacy A
        self.client.login(username='apothecary_a', password='SecurePass123!')

        # Cannot edit Pharmacy B inventory (404)
        response = self.client.get(reverse('inventory_edit', kwargs={'pk': inv_b.pk}))
        self.assertEqual(response.status_code, 404)
        post_resp = self.client.post(reverse('inventory_edit', kwargs={'pk': inv_b.pk}), {'quantity': 99})
        self.assertEqual(post_resp.status_code, 404)

        # Cannot delete Pharmacy B inventory (404)
        del_resp = self.client.post(reverse('inventory_delete', kwargs={'pk': inv_b.pk}))
        self.assertEqual(del_resp.status_code, 404)
        self.assertTrue(Inventory.objects.filter(pk=inv_b.pk).exists())

        # Cannot view or respond to Pharmacy B request (404)
        req_resp = self.client.get(reverse('respond_request', kwargs={'pk': req_b.pk}))
        self.assertEqual(req_resp.status_code, 404)

        # Pharmacy B's inventory is not in Pharmacy A's inventory list
        list_resp = self.client.get(reverse('inventory_list'))
        self.assertEqual(list_resp.status_code, 200)
        self.assertNotIn(inv_b, list_resp.context['items'])

    def test_unapproved_pharmacy_restrictions(self):
        """Vector 13: Unapproved pharmacy displays review banner and is excluded from public search."""
        unapproved_owner = User.objects.create_user(
            username='unverified_user',
            password='Password123!',
            role='PHARMACY'
        )
        unapproved_pharmacy = Pharmacy.objects.create(
            owner=unapproved_owner,
            pharmacy_name="Unapproved Drugs",
            registration_number="REG-UNAPP-999",
            address="99 Ghost Road",
            city="Hyderabad",
            state="Telangana",
            pincode="500003",
            phone_number="040-99999999",
            latitude=17.3850,
            longitude=78.4867,
            is_approved=False
        )
        Inventory.objects.create(pharmacy=unapproved_pharmacy, medicine=self.med_paracetamol, quantity=50)

        # Owner sees banner in inventory list
        self.client.login(username='unverified_user', password='Password123!')
        response = self.client.get(reverse('inventory_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account Pending Administrator Verification")

        # Public medicine discovery search excludes unapproved pharmacy
        self.client.logout()
        search_resp = self.client.get(reverse('search_medicines'), {'q': 'Paracetamol'})
        self.assertEqual(search_resp.status_code, 200)
        self.assertNotContains(search_resp, "Unapproved Drugs")

    def test_inventory_freshness(self):
        """Vector 14: Freshness tier dynamically reports FRESH, MODERATE, or STALE."""
        inv = Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=self.med_paracetamol, quantity=20)
        self.assertEqual(inv.freshness_tier, 'FRESH')
        self.assertFalse(inv.is_stale)

        # Simulate 30 hours ago (MODERATE)
        moderate_time = timezone.now() - datetime.timedelta(hours=30)
        Inventory.objects.filter(pk=inv.pk).update(updated_at=moderate_time)
        inv.refresh_from_db()
        self.assertEqual(inv.freshness_tier, 'MODERATE')
        self.assertTrue(inv.is_stale)

        # Simulate 60 hours ago (STALE)
        stale_time = timezone.now() - datetime.timedelta(hours=60)
        Inventory.objects.filter(pk=inv.pk).update(updated_at=stale_time)
        inv.refresh_from_db()
        self.assertEqual(inv.freshness_tier, 'STALE')
        self.assertTrue(inv.is_stale)

    def test_inventory_pagination(self):
        """Vector 15: Inventory pagination operates across multiple pages and preserves filters."""
        # Create 14 additional medicines and inventory items (total 14 items)
        for i in range(14):
            med = Medicine.objects.create(
                medicine_name=f"Medication {i:02d}",
                generic_name=f"Generic {i:02d}",
                dosage_form="Tablet",
                strength="100mg"
            )
            Inventory.objects.create(pharmacy=self.pharmacy_a, medicine=med, quantity=15)

        self.client.login(username='apothecary_a', password='SecurePass123!')

        # Page 1 has 10 items and has_next=True
        page1_resp = self.client.get(reverse('inventory_list'))
        self.assertEqual(page1_resp.status_code, 200)
        self.assertEqual(len(page1_resp.context['items']), 10)
        self.assertTrue(page1_resp.context['page_obj'].has_next())

        # Page 2 has 4 items
        page2_resp = self.client.get(reverse('inventory_list'), {'page': 2})
        self.assertEqual(page2_resp.status_code, 200)
        self.assertEqual(len(page2_resp.context['items']), 4)

        # Filtered request with status=IN_STOCK and sort=name
        filtered_resp = self.client.get(reverse('inventory_list'), {
            'status': 'IN_STOCK',
            'sort': 'name',
            'page': 1
        })
        self.assertEqual(filtered_resp.status_code, 200)
        self.assertIn('status=IN_STOCK', filtered_resp.context['query_string'])
        self.assertIn('sort=name', filtered_resp.context['query_string'])
