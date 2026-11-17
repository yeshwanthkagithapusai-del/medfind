"""
MediFind Stage 3 Test Suite: Frontend Geospatial Discovery & Healthcare Provider Integration
Verifies hospital search, pharmacy search, combined discovery, state/district/city/pincode filtering,
distance calculations, invalid coordinate handling, verification badges, and map data payloads.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from pharmacies.services import calculate_haversine_distance, discover_healthcare_providers

User = get_user_model()


class GeospatialDiscoveryFrontendTests(TestCase):
    """Exhaustive tests for Stage 3 Healthcare Provider Discovery."""

    def setUp(self):
        self.client = Client()

        # Customer User
        self.customer = User.objects.create_user(
            username='geo_cust',
            email='geo_cust@medifind.test',
            password='password123',
            role='CUSTOMER'
        )

        # Pharmacy Owner
        self.owner = User.objects.create_user(
            username='geo_owner',
            email='geo_owner@medifind.test',
            password='password123',
            role='PHARMACY'
        )

        # 1. Approved Pharmacy (Hyderabad)
        self.pharm_approved = Pharmacy.objects.create(
            owner=self.owner,
            pharmacy_name="Apollo Jubilee Care",
            provider_type=Pharmacy.ProviderType.PHARMACY,
            source_name=Pharmacy.DataSource.MANUAL,
            registration_number="REG-HYD-AP-01",
            address="Road No 36, Jubilee Hills",
            city="Hyderabad",
            district="Hyderabad",
            state="Telangana",
            pincode="500033",
            phone_number="040-23550000",
            latitude=Decimal("17.430000"),
            longitude=Decimal("78.408000"),
            is_approved=True,
            is_active=True,
            is_demo=False,
        )

        # 2. Approved Hospital (Hyderabad - NIMS)
        self.hosp_approved = Pharmacy.objects.create(
            pharmacy_name="NIMS Super Specialty Hospital",
            provider_type=Pharmacy.ProviderType.HOSPITAL,
            source_name=Pharmacy.DataSource.DATA_GOV_IN,
            source_id="NIN-TEST-NIMS-01",
            registration_number="NIN-TEST-NIMS-01",
            address="Punjagutta Road, Erramanzil",
            city="Hyderabad",
            district="Hyderabad",
            state="Telangana",
            pincode="500082",
            phone_number="040-23489000",
            latitude=Decimal("17.422700"),
            longitude=Decimal("78.452600"),
            is_approved=True,
            is_active=True,
            is_demo=False,
        )

        # 3. Directory / Unverified Hospital (Delhi - AIIMS)
        self.hosp_unapproved = Pharmacy.objects.create(
            pharmacy_name="AIIMS New Delhi Central",
            provider_type=Pharmacy.ProviderType.HOSPITAL,
            source_name=Pharmacy.DataSource.DATA_GOV_IN,
            source_id="NIN-TEST-AIIMS-02",
            registration_number="NIN-TEST-AIIMS-02",
            address="Ansari Nagar, Ring Road",
            city="New Delhi",
            district="New Delhi",
            state="Delhi",
            pincode="110029",
            phone_number="011-26588500",
            latitude=Decimal("28.567200"),
            longitude=Decimal("77.210000"),
            is_approved=False,
            is_active=True,
            is_demo=False,
        )

        # 4. Directory / Unverified Pharmacy (Bengaluru)
        self.pharm_unapproved = Pharmacy.objects.create(
            pharmacy_name="Unverified Corner Chemist",
            provider_type=Pharmacy.ProviderType.PHARMACY,
            source_name=Pharmacy.DataSource.OSM,
            source_id="OSM-TEST-BLR-03",
            registration_number="OSM-TEST-BLR-03",
            address="CMH Road, Indiranagar",
            city="Bengaluru",
            district="Bengaluru Urban",
            state="Karnataka",
            pincode="560038",
            phone_number="080-25200000",
            latitude=Decimal("12.978500"),
            longitude=Decimal("77.641200"),
            is_approved=False,
            is_active=True,
            is_demo=False,
        )

        # Medicine & Inventory for pharmacy stock test
        self.medicine = Medicine.objects.create(
            medicine_name="Paracetamol 650mg",
            generic_name="Paracetamol",
            category="Analgesics & Pain Relief",
            dosage_form="Tablet",
            strength="650mg",
        )
        self.inventory = Inventory.objects.create(
            pharmacy=self.pharm_approved,
            medicine=self.medicine,
            quantity=50,
        )

    # 1. Hospital Search
    def test_hospital_search_filtering(self):
        """Verify filtering by provider_type='HOSPITAL' returns only hospitals."""
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'type': 'HOSPITAL',
            'verification': 'all'
        })
        self.assertEqual(resp.status_code, 200)
        results = list(resp.context['page_obj'])
        self.assertEqual(len(results), 2)
        names = [p.pharmacy_name for p in results]
        self.assertIn("NIMS Super Specialty Hospital", names)
        self.assertIn("AIIMS New Delhi Central", names)
        self.assertNotIn("Apollo Jubilee Care", names)

    # 2. Pharmacy Search
    def test_pharmacy_search_filtering(self):
        """Verify filtering by provider_type='PHARMACY' returns only pharmacies."""
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'type': 'PHARMACY',
            'verification': 'all'
        })
        self.assertEqual(resp.status_code, 200)
        results = list(resp.context['page_obj'])
        self.assertEqual(len(results), 2)
        names = [p.pharmacy_name for p in results]
        self.assertIn("Apollo Jubilee Care", names)
        self.assertIn("Unverified Corner Chemist", names)
        self.assertNotIn("NIMS Super Specialty Hospital", names)

    # 3. Combined Search
    def test_combined_search(self):
        """Verify combined search returns both hospitals and pharmacies."""
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'type': 'ALL',
            'verification': 'all'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['page_obj']), 4)

    # 4. State Filtering
    def test_state_filtering(self):
        """Verify state filter narrows down facilities to that state."""
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'state': 'Telangana',
            'verification': 'all'
        })
        self.assertEqual(resp.status_code, 200)
        results = list(resp.context['page_obj'])
        self.assertEqual(len(results), 2)
        for p in results:
            self.assertEqual(p.state, "Telangana")

    # 5. District Filtering
    def test_district_filtering(self):
        """Verify district filter isolates facilities in the specified district."""
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'district': 'Bengaluru Urban',
            'verification': 'all'
        })
        self.assertEqual(resp.status_code, 200)
        results = list(resp.context['page_obj'])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].pharmacy_name, "Unverified Corner Chemist")

    # 6. City Filtering
    def test_city_filtering(self):
        """Verify city filter matches exact or substring city names."""
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'city': 'New Delhi',
            'verification': 'all'
        })
        self.assertEqual(resp.status_code, 200)
        results = list(resp.context['page_obj'])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].pharmacy_name, "AIIMS New Delhi Central")

    # 7. Pincode Filtering
    def test_pincode_filtering(self):
        """Verify pincode filter isolates facility by postal code."""
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'pincode': '500033',
            'verification': 'all'
        })
        self.assertEqual(resp.status_code, 200)
        results = list(resp.context['page_obj'])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].pharmacy_name, "Apollo Jubilee Care")

    # 8. Nearby Search & Haversine Distance Calculation
    def test_nearby_search_and_distance_calculation(self):
        """Verify Haversine distance calculation and radius threshold."""
        # User located near Jubilee Hills Checkpost: Lat 17.432000, Lng 78.410000
        # Apollo Jubilee Care is ~0.3 km away; NIMS is ~4.6 km away; AIIMS is >1200 km away
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'lat': '17.432000',
            'lng': '78.410000',
            'radius': '5',
            'verification': 'all',
            'sort': 'distance'
        })
        self.assertEqual(resp.status_code, 200)
        results = list(resp.context['page_obj'])
        # Only Apollo (~0.3 km) and NIMS (~4.6 km) are within 5 km
        self.assertEqual(len(results), 2)
        self.assertLess(results[0].distance_km, results[1].distance_km)
        self.assertEqual(results[0].pharmacy_name, "Apollo Jubilee Care")

    # 9. Invalid Coordinates Handling
    def test_invalid_coordinates_fallback(self):
        """Verify non-numeric or out-of-bounds coordinates do not crash the search."""
        resp = self.client.get(reverse('pharmacy_discovery'), {
            'lat': 'not_a_number',
            'lng': '999.999',
            'verification': 'all'
        })
        self.assertEqual(resp.status_code, 200)
        # Gracefully treats has_user_coords as False and returns records without distances
        self.assertFalse(resp.context['has_user_coords'])
        self.assertEqual(len(resp.context['page_obj']), 4)

    # 10. Unverified Provider Visibility & Badge Integrity
    def test_unverified_provider_badges_and_exclusion(self):
        """
        Verify strict rule:
        - When verification='approved' (default), unapproved facilities are excluded.
        - When verification='all', unapproved facilities appear with directory badge and are NEVER marked as verified.
        """
        # Default query (verification='approved')
        resp_approved = self.client.get(reverse('pharmacy_discovery'))
        self.assertEqual(resp_approved.status_code, 200)
        approved_results = list(resp_approved.context['page_obj'])
        for p in approved_results:
            self.assertTrue(p.is_approved)
        self.assertNotContains(resp_approved, "Unverified Corner Chemist")

        # Explicit directory query (verification='all')
        resp_all = self.client.get(reverse('pharmacy_discovery'), {'verification': 'all'})
        self.assertEqual(resp_all.status_code, 200)
        self.assertContains(resp_all, "Directory Listing")
        self.assertContains(resp_all, "Verified")

    # 11. Map Data Payloads & Marker Taxonomy
    def test_map_data_pins_payload(self):
        """Verify map_pins contains correct metadata, lat, lng, and distinct provider types."""
        resp = self.client.get(reverse('pharmacy_discovery'), {'verification': 'all'})
        self.assertEqual(resp.status_code, 200)
        pins = resp.context['map_pins']
        self.assertEqual(len(pins), 4)

        hospital_pins = [p for p in pins if p['provider_type'] == 'HOSPITAL']
        pharmacy_pins = [p for p in pins if p['provider_type'] == 'PHARMACY']
        self.assertEqual(len(hospital_pins), 2)
        self.assertEqual(len(pharmacy_pins), 2)

        for hp in hospital_pins:
            self.assertEqual(hp['icon_type'], 'hospital')
            self.assertIn('lat', hp)
            self.assertIn('lng', hp)

        for pp in pharmacy_pins:
            self.assertEqual(pp['icon_type'], 'pharmacy')

    # 12. Hospital Detail Public Access
    def test_hospital_detail_view(self):
        """Verify public access to hospital profile with emergency notices and NIN."""
        resp = self.client.get(reverse('pharmacy_detail', args=[self.hosp_approved.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Hospital &amp; Medical Center")
        self.assertContains(resp, "Emergency &amp; Critical Care Guidance")
        self.assertContains(resp, "NIN-TEST-NIMS-01")

    # 13. Existing Medicine Search Regression
    def test_medicine_search_regression(self):
        """Verify medicine search still associates stock with approved pharmacies."""
        resp = self.client.get(reverse('search_medicines'), {'q': 'Paracetamol'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paracetamol 650mg")
        self.assertContains(resp, "Apollo Jubilee Care")
