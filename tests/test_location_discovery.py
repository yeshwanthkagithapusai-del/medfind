import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from pharmacies.services import (
    calculate_haversine_distance,
    discover_nearby_pharmacies,
    is_valid_coordinate,
)

User = get_user_model()


class LocationDiscoveryAndDistanceTests(TestCase):
    """
    Automated test suite verifying the 15 vectors required for Phase 4:
    1. Haversine distance calculation.
    2. Invalid latitude.
    3. Invalid longitude.
    4. Missing coordinates.
    5. Nearby pharmacy search.
    6. Distance sorting.
    7. Search radius.
    8. Manual city search.
    9. Pincode filtering.
    10. Approved pharmacy filtering.
    11. Unapproved pharmacy exclusion.
    12. Medicine-specific availability.
    13. Stale inventory handling.
    14. Missing inventory.
    15. Location permission failure handling.
    """

    def setUp(self):
        self.client = Client()

        # Customer User
        self.customer = User.objects.create_user(
            username='loc_customer',
            email='loc_customer@example.com',
            password='CustomerPass123!',
            role='CUSTOMER'
        )

        # Pharmacy Owners
        self.owner_near = User.objects.create_user(
            username='owner_near',
            email='owner_near@example.com',
            password='Password123!',
            role='PHARMACY'
        )
        self.owner_far = User.objects.create_user(
            username='owner_far',
            email='owner_far@example.com',
            password='Password123!',
            role='PHARMACY'
        )
        self.owner_unapproved = User.objects.create_user(
            username='owner_unapproved',
            email='owner_unapproved@example.com',
            password='Password123!',
            role='PHARMACY'
        )

        # 1. Near Approved Pharmacy in Jubilee Hills (~2.0 km from test user at 17.4350, 78.4100)
        self.pharm_near = Pharmacy.objects.create(
            owner=self.owner_near,
            pharmacy_name="Jubilee Care Chemist",
            registration_number="REG-LOC-001",
            address="Road No 36, Jubilee Hills",
            city="Hyderabad",
            state="Telangana",
            pincode="500033",
            phone_number="040-23551122",
            latitude=Decimal('17.425000'),
            longitude=Decimal('78.410000'),
            is_approved=True
        )

        # 2. Far Approved Pharmacy in Secunderabad (~16.0 km from test user)
        self.pharm_far = Pharmacy.objects.create(
            owner=self.owner_far,
            pharmacy_name="Secunderabad Health Hub",
            registration_number="REG-LOC-002",
            address="MG Road, Clock Tower",
            city="Secunderabad",
            state="Telangana",
            pincode="500003",
            phone_number="040-27801122",
            latitude=Decimal('17.440000'),
            longitude=Decimal('78.500000'),
            is_approved=True
        )

        # 3. Unapproved Pharmacy in Jubilee Hills (Nearby, but NOT approved)
        self.pharm_unapproved = Pharmacy.objects.create(
            owner=self.owner_unapproved,
            pharmacy_name="Unapproved Counter Pharmacy",
            registration_number="REG-LOC-999",
            address="Road No 10, Jubilee Hills",
            city="Hyderabad",
            state="Telangana",
            pincode="500033",
            phone_number="040-99998888",
            latitude=Decimal('17.428000'),
            longitude=Decimal('78.412000'),
            is_approved=False
        )

        # Medicines
        self.med_paracetamol = Medicine.objects.create(
            medicine_name="Paracetamol 650mg",
            generic_name="Paracetamol",
            category="Analgesics & Pain Relief",
            dosage_form="Tablet",
            strength="650mg",
            description="Antipyretic and analgesic tablet."
        )
        self.med_amoxicillin = Medicine.objects.create(
            medicine_name="Amoxicillin 500mg",
            generic_name="Amoxicillin Trihydrate",
            category="Antibiotics",
            dosage_form="Capsule",
            strength="500mg",
            description="Broad-spectrum antibiotic."
        )
        self.med_rare = Medicine.objects.create(
            medicine_name="Rare Orphan Drug 100mg",
            generic_name="Orphan Salt",
            category="Specialty",
            dosage_form="Injection",
            strength="100mg",
            description="Rarely stocked hospital injection."
        )

        # Fresh Inventory at Near Pharmacy (updated now)
        self.inv_near = Inventory.objects.create(
            pharmacy=self.pharm_near,
            medicine=self.med_paracetamol,
            quantity=25
        )

        # Stale Inventory at Far Pharmacy (>48 hours ago)
        self.inv_far_stale = Inventory.objects.create(
            pharmacy=self.pharm_far,
            medicine=self.med_paracetamol,
            quantity=15
        )
        stale_time = timezone.now() - datetime.timedelta(hours=50)
        Inventory.objects.filter(pk=self.inv_far_stale.pk).update(updated_at=stale_time)
        self.inv_far_stale.refresh_from_db()

        # Out of Stock Inventory at Near Pharmacy
        self.inv_near_out = Inventory.objects.create(
            pharmacy=self.pharm_near,
            medicine=self.med_amoxicillin,
            quantity=0
        )

    # 1. Haversine distance calculation
    def test_haversine_distance_calculation(self):
        # Coordinates: Jubilee Hills (17.4250, 78.4100) to Gachibowli (17.4400, 78.3489)
        # Expected great-circle distance is ~6.7 km
        dist = calculate_haversine_distance(17.4250, 78.4100, 17.4400, 78.3489)
        self.assertIsNotNone(dist)
        self.assertAlmostEqual(dist, 6.71, delta=0.5)

        # Identical coordinates must yield 0.0 km
        dist_same = calculate_haversine_distance(17.4250, 78.4100, 17.4250, 78.4100)
        self.assertEqual(dist_same, 0.0)

    # 2. Invalid latitude rejection
    def test_invalid_latitude(self):
        self.assertFalse(is_valid_coordinate(95.0, 78.0))
        self.assertFalse(is_valid_coordinate(-91.0, 78.0))
        self.assertIsNone(calculate_haversine_distance(95.0, 78.0, 17.0, 78.0))
        self.assertIsNone(calculate_haversine_distance(17.0, 78.0, -100.0, 78.0))

    # 3. Invalid longitude rejection
    def test_invalid_longitude(self):
        self.assertFalse(is_valid_coordinate(17.0, 185.0))
        self.assertFalse(is_valid_coordinate(17.0, -195.0))
        self.assertIsNone(calculate_haversine_distance(17.0, 185.0, 17.0, 78.0))
        self.assertIsNone(calculate_haversine_distance(17.0, 78.0, 17.0, -200.0))

    # 4. Missing coordinates handling
    def test_missing_coordinates(self):
        self.assertFalse(is_valid_coordinate(None, 78.0))
        self.assertFalse(is_valid_coordinate(17.0, None))
        self.assertFalse(is_valid_coordinate("", 78.0))
        self.assertFalse(is_valid_coordinate("not_a_coord", 78.0))
        self.assertIsNone(calculate_haversine_distance(None, 78.0, 17.0, 78.0))
        self.assertIsNone(calculate_haversine_distance("abc", "def", 17.0, 78.0))

    # 5. Nearby pharmacy search
    def test_nearby_pharmacy_search(self):
        # User located near Jubilee Hills (17.4350, 78.4100)
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'lat': '17.435000',
            'lng': '78.410000'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Jubilee Care Chemist")
        self.assertContains(resp, "Secunderabad Health Hub")
        # Verify distance is computed and rendered
        self.assertContains(resp, "km")

    # 6. Distance sorting (nearest first)
    def test_distance_sorting(self):
        # User at Jubilee Hills (17.4350, 78.4100)
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'lat': '17.435000',
            'lng': '78.410000',
            'sort': 'distance'
        })
        self.assertEqual(resp.status_code, 200)
        pharmacies = list(resp.context['page_obj'])
        self.assertGreaterEqual(len(pharmacies), 2)
        # First pharmacy must be the nearest one (Jubilee Care Chemist ~1.1 km vs Secunderabad ~9.5 km)
        self.assertEqual(pharmacies[0].id, self.pharm_near.id)
        self.assertLess(pharmacies[0].distance_km, pharmacies[1].distance_km)

    # 7. Search radius filtering
    def test_search_radius(self):
        # User at Jubilee Hills (17.4350, 78.4100) with radius=5 km
        resp_5km = self.client.get(reverse('pharmacy_discovery'), {
            'lat': '17.435000',
            'lng': '78.410000',
            'radius': '5'
        })
        self.assertEqual(resp_5km.status_code, 200)
        pharmacies_5km = list(resp_5km.context['page_obj'])
        # Only near pharmacy (~1.1 km) should be returned; far pharmacy (>9 km) excluded
        self.assertEqual(len(pharmacies_5km), 1)
        self.assertEqual(pharmacies_5km[0].id, self.pharm_near.id)

        # Widen radius to 25 km: both pharmacies included
        resp_25km = self.client.get(reverse('pharmacy_discovery'), {
            'lat': '17.435000',
            'lng': '78.410000',
            'radius': '25'
        })
        self.assertEqual(resp_25km.status_code, 200)
        self.assertEqual(len(resp_25km.context['page_obj']), 2)

    # 8. Manual city search
    def test_manual_city_search(self):
        # Filter by Secunderabad without any GPS coordinates
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'city': 'Secunderabad'
        })
        self.assertEqual(resp.status_code, 200)
        pharmacies = list(resp.context['page_obj'])
        self.assertEqual(len(pharmacies), 1)
        self.assertEqual(pharmacies[0].id, self.pharm_far.id)
        self.assertContains(resp, "Secunderabad Health Hub")
        self.assertNotContains(resp, "Jubilee Care Chemist")

    # 9. Pincode filtering
    def test_pincode_filtering(self):
        # Filter by pincode 500033 (Jubilee Hills)
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'pincode': '500033'
        })
        self.assertEqual(resp.status_code, 200)
        pharmacies = list(resp.context['page_obj'])
        self.assertEqual(len(pharmacies), 1)
        self.assertEqual(pharmacies[0].id, self.pharm_near.id)
        self.assertContains(resp, "Jubilee Care Chemist")
        self.assertNotContains(resp, "Secunderabad Health Hub")

    # 10. Approved pharmacy filtering
    def test_approved_pharmacy_filtering(self):
        # Both approved pharmacies must be present in general discovery
        resp = self.client.get(reverse('pharmacy_discovery'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Jubilee Care Chemist")
        self.assertContains(resp, "Secunderabad Health Hub")

    # 11. Unapproved pharmacy exclusion
    def test_unapproved_pharmacy_exclusion(self):
        # Verify unapproved pharmacy NEVER appears in public discovery
        resp = self.client.get(reverse('pharmacy_discovery'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Unapproved Counter Pharmacy")
        self.assertNotContains(resp, "REG-LOC-999")

        # Verify unapproved pharmacy does not appear in medicine search
        resp_med = self.client.get(reverse('search_medicines'), {'q': 'Paracetamol'})
        self.assertEqual(resp_med.status_code, 200)
        self.assertNotContains(resp_med, "Unapproved Counter Pharmacy")

    # 12. Medicine-specific availability
    def test_medicine_specific_availability(self):
        # Search for Paracetamol with coordinates
        resp = self.client.get(reverse('search_medicines'), {
            'q': 'Paracetamol',
            'lat': '17.435000',
            'lng': '78.410000',
            'sort': 'distance'
        })
        self.assertEqual(resp.status_code, 200)
        results = list(resp.context['results'])
        self.assertGreaterEqual(len(results), 2)
        # Nearest pharmacy stock first
        self.assertEqual(results[0].pharmacy.id, self.pharm_near.id)
        self.assertEqual(results[0].availability_status, 'IN_STOCK')
        self.assertEqual(results[0].quantity, 25)

    # 13. Stale inventory handling
    def test_stale_inventory_handling(self):
        # Fresh item updated now
        self.assertFalse(self.inv_near.is_stale)
        self.assertEqual(self.inv_near.freshness_tier, 'FRESH')

        # Stale item updated > 48h ago
        self.assertTrue(self.inv_far_stale.is_stale)
        self.assertEqual(self.inv_far_stale.freshness_tier, 'STALE')

        resp = self.client.get(reverse('search_medicines'), {'q': 'Paracetamol'})
        self.assertEqual(resp.status_code, 200)
        # Search results must identify stale stock with warning
        self.assertContains(resp, "Reported &gt;24h ago &bull; Inquire to confirm")

    # 14. Missing inventory handling
    def test_missing_inventory(self):
        # Search for a drug with no inventory anywhere in system
        resp = self.client.get(reverse('search_medicines'), {'q': 'Rare Orphan Drug'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['results']), 0)
        self.assertContains(resp, "No Matching Medicine Stock Found")

        # Drug out of stock (quantity 0)
        resp_out = self.client.get(reverse('search_medicines'), {'q': 'Amoxicillin'})
        self.assertEqual(resp_out.status_code, 200)
        self.assertContains(resp_out, "Reported Out of Stock")

    # 15. Location permission failure handling
    def test_location_permission_failure_handling(self):
        # Client coordinates omitted or invalid (e.g. user denied permission in browser)
        resp_no_geo = self.client.get(reverse('pharmacy_discovery'))
        self.assertEqual(resp_no_geo.status_code, 200)
        self.assertFalse(resp_no_geo.context['has_user_coords'])
        # Gracefully renders pharmacies ordered by recency or name
        self.assertGreaterEqual(resp_no_geo.context['total_results'], 2)

        # Invalid coordinates (e.g. malformed query string) handled gracefully
        resp_bad_coords = self.client.get(reverse('pharmacy_discovery'), {
            'lat': 'invalid_latitude',
            'lng': 'invalid_longitude'
        })
        self.assertEqual(resp_bad_coords.status_code, 200)
        self.assertFalse(resp_bad_coords.context['has_user_coords'])
