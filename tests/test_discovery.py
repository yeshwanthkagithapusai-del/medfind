import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy

User = get_user_model()


class MedicineDiscoveryTests(TestCase):
    """
    Dedicated Discovery and Search Test Suite verifying:
    1. Keyword discovery (Brand name, Partial name, Generic active compound).
    2. Multi-faceted filters (Category, Dosage form, Strength, City, Pincode, Stock status).
    3. Multi-parameter compound queries.
    4. Pagination engine and query parameter state preservation.
    5. User feedback on empty search results.
    6. Strict exclusion of unapproved pharmacies from search and detail views.
    7. Inventory data freshness (>24h stale detection).
    8. Medicine detail monograph and medical disclaimer presentation.
    9. Geolocation proximity calculations and distance-based sorting.
    """

    def setUp(self):
        self.client = Client()

        # 1. Create Users
        self.owner_approved = User.objects.create_user(
            username='pharmacy_owner_1',
            email='owner1@test.com',
            password='Password123!',
            role='PHARMACY'
        )
        self.owner_unapproved = User.objects.create_user(
            username='pharmacy_owner_2',
            email='owner2@test.com',
            password='Password123!',
            role='PHARMACY'
        )
        self.owner_secondary = User.objects.create_user(
            username='pharmacy_owner_3',
            email='owner3@test.com',
            password='Password123!',
            role='PHARMACY'
        )
        self.customer = User.objects.create_user(
            username='customer_jane',
            email='jane@test.com',
            password='Password123!',
            role='CUSTOMER'
        )

        # 2. Create Pharmacies
        # Approved Pharmacy 1: Central Hyderabad (17.415582, 78.435783)
        self.pharmacy_approved = Pharmacy.objects.create(
            owner=self.owner_approved,
            pharmacy_name="Central Care Pharmacy",
            registration_number="REG-HYD-001",
            address="Road No 1, Banjara Hills",
            city="Hyderabad",
            state="Telangana",
            pincode="500034",
            phone_number="9876543210",
            latitude=Decimal('17.415582'),
            longitude=Decimal('78.435783'),
            is_approved=True
        )

        # Approved Pharmacy 2: Secunderabad (~8 km away: 17.4399, 78.4983)
        self.pharmacy_distant = Pharmacy.objects.create(
            owner=self.owner_secondary,
            pharmacy_name="Secunderabad Health Mart",
            registration_number="REG-SEC-002",
            address="Station Road",
            city="Secunderabad",
            state="Telangana",
            pincode="500003",
            phone_number="9123456780",
            latitude=Decimal('17.439928'),
            longitude=Decimal('78.498274'),
            is_approved=True
        )

        # Unapproved Pharmacy (Must never appear in public search)
        self.pharmacy_unapproved = Pharmacy.objects.create(
            owner=self.owner_unapproved,
            pharmacy_name="Unapproved Underground Drugstore",
            registration_number="REG-FAKE-999",
            address="Shadow Alley",
            city="Hyderabad",
            state="Telangana",
            pincode="500034",
            phone_number="9000000000",
            latitude=Decimal('17.415000'),
            longitude=Decimal('78.435000'),
            is_approved=False
        )

        # 3. Create Sample Master Medicines
        self.med_dolo = Medicine.objects.create(
            medicine_name="Dolo 650",
            generic_name="Paracetamol",
            strength="650mg",
            dosage_form="Tablet",
            category="Analgesics & Pain Relief",
            description="Antipyretic and analgesic tablet for fever and pain relief."
        )
        self.med_augmentin = Medicine.objects.create(
            medicine_name="Augmentin 625 Duo",
            generic_name="Amoxicillin and Potassium Clavulanate",
            strength="625mg",
            dosage_form="Tablet",
            category="Antibiotics",
            description="Broad-spectrum antibiotic formulation."
        )
        self.med_cough_syrup = Medicine.objects.create(
            medicine_name="Ascoril LS",
            generic_name="Levosalbutamol, Ambroxol, Guaiphenesin",
            strength="100ml",
            dosage_form="Syrup",
            category="Respiratory & Anti-Allergic",
            description="Expectorant syrup for productive cough."
        )
        self.med_insulin = Medicine.objects.create(
            medicine_name="Lantus Solostar",
            generic_name="Insulin Glargine",
            strength="100 IU/ml",
            dosage_form="Injection",
            category="Antidiabetic",
            description="Long-acting basal insulin analog."
        )

        # 4. Create Initial Inventory Records
        self.inv_dolo = Inventory.objects.create(
            pharmacy=self.pharmacy_approved,
            medicine=self.med_dolo,
            quantity=50
        )
        self.inv_augmentin = Inventory.objects.create(
            pharmacy=self.pharmacy_approved,
            medicine=self.med_augmentin,
            quantity=8  # LOW_STOCK (<10)
        )
        self.inv_syrup = Inventory.objects.create(
            pharmacy=self.pharmacy_distant,
            medicine=self.med_cough_syrup,
            quantity=25
        )
        self.inv_unapproved = Inventory.objects.create(
            pharmacy=self.pharmacy_unapproved,
            medicine=self.med_dolo,
            quantity=100
        )

    # 1. Test Search by Exact Medicine Brand Name
    def test_medicine_name_search(self):
        resp = self.client.get(reverse('search_medicines'), {'q': 'Dolo 650'})
        self.assertEqual(resp.status_code, 200)
        results = resp.context['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].medicine.medicine_name, "Dolo 650")
        self.assertContains(resp, "Dolo 650")

    # 2. Test Substring / Partial Name Search
    def test_partial_medicine_search(self):
        resp = self.client.get(reverse('search_medicines'), {'q': 'aug'})
        self.assertEqual(resp.status_code, 200)
        results = resp.context['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].medicine.medicine_name, "Augmentin 625 Duo")

    # 3. Test Search by Generic Active Compound
    def test_generic_name_search(self):
        resp = self.client.get(reverse('search_medicines'), {'q': 'Paracetamol'})
        self.assertEqual(resp.status_code, 200)
        results = resp.context['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].medicine.generic_name, "Paracetamol")

    # 4. Test Filtering by Therapeutic Category
    def test_category_filtering(self):
        resp = self.client.get(reverse('search_medicines'), {'category': 'Antibiotics'})
        self.assertEqual(resp.status_code, 200)
        results = resp.context['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].medicine.category, "Antibiotics")

    # 5. Test Filtering by Strength and Dosage Form
    def test_strength_and_dosage_filtering(self):
        resp = self.client.get(reverse('search_medicines'), {
            'dosage_form': 'Tablet',
            'strength': '650mg'
        })
        self.assertEqual(resp.status_code, 200)
        results = resp.context['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].medicine.medicine_name, "Dolo 650")
        self.assertEqual(results[0].medicine.dosage_form, "Tablet")
        self.assertEqual(results[0].medicine.strength, "650mg")

    # 6. Test Multi-Parameter Filter Combinations
    def test_multiple_filter_combinations(self):
        resp = self.client.get(reverse('search_medicines'), {
            'q': 'Dolo',
            'category': 'Analgesics & Pain Relief',
            'dosage_form': 'Tablet',
            'city': 'Hyderabad',
            'status': 'IN_STOCK'
        })
        self.assertEqual(resp.status_code, 200)
        results = resp.context['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].medicine.medicine_name, "Dolo 650")
        self.assertEqual(results[0].pharmacy.city, "Hyderabad")
        self.assertEqual(results[0].availability_status, "IN_STOCK")

    # 7. Test Pagination Engine (10 items per page limit)
    def test_search_pagination(self):
        # Create 12 additional medicines and inventory items in pharmacy_approved
        for i in range(12):
            med = Medicine.objects.create(
                medicine_name=f"TestAntibioticBatch {i+1:02d}",
                generic_name=f"GenericCompound {i+1:02d}",
                strength="500mg",
                dosage_form="Tablet",
                category="Antibiotics"
            )
            Inventory.objects.create(
                pharmacy=self.pharmacy_approved,
                medicine=med,
                quantity=20
            )

        # Page 1 request
        resp_p1 = self.client.get(reverse('search_medicines'), {'category': 'Antibiotics', 'page': 1})
        self.assertEqual(resp_p1.status_code, 200)
        page1_obj = resp_p1.context['page_obj']
        self.assertEqual(len(page1_obj), 10)  # Exactly 10 on page 1
        self.assertEqual(resp_p1.context['total_results'], 13)  # 1 initial + 12 created = 13
        self.assertTrue(page1_obj.has_next())
        self.assertFalse(page1_obj.has_previous())

        # Page 2 request
        resp_p2 = self.client.get(reverse('search_medicines'), {'category': 'Antibiotics', 'page': 2})
        self.assertEqual(resp_p2.status_code, 200)
        page2_obj = resp_p2.context['page_obj']
        self.assertEqual(len(page2_obj), 3)  # Remaining 3 on page 2
        self.assertFalse(page2_obj.has_next())
        self.assertTrue(page2_obj.has_previous())

    # 8. Test Preservation of Query Parameters in Pagination Context
    def test_pagination_preserves_query_params(self):
        resp = self.client.get(reverse('search_medicines'), {
            'q': 'Dolo',
            'city': 'Hyderabad',
            'category': 'Analgesics & Pain Relief',
            'page': 1
        })
        self.assertEqual(resp.status_code, 200)
        query_string = resp.context['query_string']
        # query_string must contain filters but NOT page parameter
        self.assertIn('q=Dolo', query_string)
        self.assertIn('city=Hyderabad', query_string)
        self.assertNotIn('page=1', query_string)

    # 9. Test Empty Search Feedback and Suggestions
    def test_empty_search_results_feedback(self):
        resp = self.client.get(reverse('search_medicines'), {'q': 'NONEXISTENT_FORMULATION_XYZ'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_results'], 0)
        self.assertContains(resp, "No Matching Medicine Stock Found")
        self.assertContains(resp, "Search Suggestions")
        self.assertContains(resp, "Reset All Filters")

    # 10. Test Approved Pharmacy Visibility
    def test_approved_pharmacy_visibility(self):
        resp = self.client.get(reverse('search_medicines'), {'q': 'Dolo'})
        self.assertEqual(resp.status_code, 200)
        results = resp.context['results']
        pharmacy_names = [item.pharmacy.pharmacy_name for item in results]
        self.assertIn("Central Care Pharmacy", pharmacy_names)

    # 11. Test Unapproved Pharmacy Exclusion
    def test_unapproved_pharmacy_excluded_from_search(self):
        resp = self.client.get(reverse('search_medicines'), {'q': 'Dolo'})
        self.assertEqual(resp.status_code, 200)
        for item in resp.context['results']:
            self.assertTrue(item.pharmacy.is_approved)
            self.assertNotEqual(item.pharmacy.id, self.pharmacy_unapproved.id)
            self.assertNotIn("Unapproved Underground", item.pharmacy.pharmacy_name)

    # 12. Test Inventory Freshness and Stale Stock Detection
    def test_inventory_freshness_stale_detection(self):
        # Create a stale inventory item (updated 26 hours ago)
        med_stale = Medicine.objects.create(
            medicine_name="StaleMed 100",
            generic_name="OldCompound",
            strength="100mg",
            dosage_form="Capsule",
            category="Vitamins & Supplements"
        )
        inv_stale = Inventory.objects.create(
            pharmacy=self.pharmacy_approved,
            medicine=med_stale,
            quantity=15
        )
        # Manually alter updated_at to simulate >24h elapsed
        stale_time = timezone.now() - datetime.timedelta(hours=26)
        Inventory.objects.filter(pk=inv_stale.pk).update(updated_at=stale_time)
        inv_stale.refresh_from_db()

        self.assertTrue(inv_stale.is_stale)

        # Verify search results render stale warning badge
        resp = self.client.get(reverse('search_medicines'), {'q': 'StaleMed'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Reported &gt;24h ago &bull; Inquire to confirm")

        # Verify fresh item renders fresh update badge
        resp_fresh = self.client.get(reverse('search_medicines'), {'q': 'Dolo'})
        self.assertEqual(resp_fresh.status_code, 200)
        self.assertContains(resp_fresh, "Fresh update")

    # 13. Test Medicine Detail Page and Medical Disclaimer
    def test_medicine_detail_page_and_disclaimer(self):
        resp = self.client.get(reverse('medicine_detail', args=[self.med_dolo.id]))
        self.assertEqual(resp.status_code, 200)

        # 1. Monograph details rendered
        self.assertContains(resp, "Dolo 650")
        self.assertContains(resp, "Paracetamol")
        self.assertContains(resp, "650mg")
        self.assertContains(resp, "Analgesics &amp; Pain Relief")

        # 2. Medical advice disclaimer rendered
        self.assertContains(resp, "Medical Advice &amp; Prescriptions Disclaimer")
        self.assertContains(resp, "MediFind provides reported pharmacy inventory listings for informational purposes only")
        self.assertContains(resp, "Do not self-medicate or alter dosage without certified physician consultation")

        # 3. Approved pharmacy stock rendered
        self.assertContains(resp, "Central Care Pharmacy")
        self.assertNotContains(resp, "Unapproved Underground")

    # 14. Test Geolocation Haversine Proximity Sorting
    def test_location_distance_sorting(self):
        # Coordinates located right next to Banjara Hills (Central Care Pharmacy): 17.4150, 78.4350
        # Central Care is <0.1 km away; Secunderabad Health Mart is ~8 km away
        resp = self.client.get(reverse('search_medicines'), {
            'lat': '17.4150',
            'lng': '78.4350',
            'sort': 'distance'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['has_user_coords'])
        results = resp.context['results']
        self.assertGreaterEqual(len(results), 2)

        # First item must be closest (Central Care Pharmacy)
        first_item = results[0]
        second_item = results[1]
        self.assertIsNotNone(first_item.distance_km)
        self.assertIsNotNone(second_item.distance_km)
        self.assertLessEqual(first_item.distance_km, second_item.distance_km)
        self.assertEqual(first_item.pharmacy.pharmacy_name, "Central Care Pharmacy")
