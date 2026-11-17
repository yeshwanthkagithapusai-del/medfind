import json
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from pharmacies.services import (
    build_external_directions_url,
    calculate_haversine_distance,
    discover_healthcare_providers,
    is_valid_coordinate,
)

User = get_user_model()


class AdvancedMapAndDirectionsTestCase(TestCase):
    """
    Comprehensive verification suite for Stage 5:
    - Distinct hospital & pharmacy markers
    - Marker popup data
    - Haversine distance calculations
    - Provider-type filters (Hospital, Pharmacy, All)
    - Verification status filters (Approved, All, Pending)
    - Medicine availability filter based strictly on MediFind inventory
    - Search radius filtering
    - External directions URLs (Google Maps & OpenStreetMap)
    - Missing and invalid coordinates handling
    - Detail view directions and map rendering
    - Existing customer and pharmacy workflow integrity
    """

    @classmethod
    def setUpTestData(cls):
        # 1. Accounts
        cls.admin_user = User.objects.create_superuser(
            username='admin_stage5',
            email='admin5@medfind.test',
            password='testpassword123',
            role='ADMIN'
        )
        cls.pharmacy_owner = User.objects.create_user(
            username='owner_stage5',
            email='owner5@medfind.test',
            password='testpassword123',
            role='PHARMACY'
        )
        cls.customer_user = User.objects.create_user(
            username='customer_stage5',
            email='customer5@medfind.test',
            password='testpassword123',
            role='CUSTOMER'
        )

        # 2. Healthcare Providers
        # Genuine Hospital (data.gov.in)
        cls.hospital = Pharmacy.objects.create(
            pharmacy_name="Nizam's Institute of Medical Sciences",
            registration_number="REG-NIMS-001",
            provider_type=Pharmacy.ProviderType.HOSPITAL,
            address="Punjagutta Road",
            city="Hyderabad",
            district="Hyderabad",
            state="Telangana",
            pincode="500082",
            phone_number="040-23489000",
            latitude=Decimal("17.422700"),
            longitude=Decimal("78.452600"),
            source_name=Pharmacy.DataSource.DATA_GOV_IN,
            source_id="NIN-TEL-001",
            is_approved=False,
            is_active=True,
            is_demo=False
        )

        # Approved Pharmacy with Active Stock
        cls.pharmacy_with_stock = Pharmacy.objects.create(
            pharmacy_name="Apollo Pharmacy Jubilee Hills",
            registration_number="REG-APOLLO-001",
            provider_type=Pharmacy.ProviderType.PHARMACY,
            owner=cls.pharmacy_owner,
            address="Road No 36, Jubilee Hills",
            city="Hyderabad",
            district="Hyderabad",
            state="Telangana",
            pincode="500033",
            phone_number="040-23550001",
            latitude=Decimal("17.431900"),
            longitude=Decimal("78.407300"),
            source_name=Pharmacy.DataSource.DEMO,
            source_id="APOLLO-JH-01",
            is_approved=True,
            is_active=True,
            is_demo=True
        )

        # Directory Pharmacy from OSM without MediFind Inventory
        cls.pharmacy_no_stock = Pharmacy.objects.create(
            pharmacy_name="MedPlus Chemist Banjara Hills",
            registration_number="REG-MEDPLUS-001",
            provider_type=Pharmacy.ProviderType.PHARMACY,
            address="Road No 12, Banjara Hills",
            city="Hyderabad",
            district="Hyderabad",
            state="Telangana",
            pincode="500034",
            phone_number="040-23300002",
            latitude=Decimal("17.415000"),
            longitude=Decimal("78.435000"),
            source_name=Pharmacy.DataSource.OSM,
            source_id="osm-node-998877",
            is_approved=False,
            is_active=True,
            is_demo=False
        )

        # Remote Hospital in New Delhi (for radius cutoff testing)
        cls.delhi_hospital = Pharmacy.objects.create(
            pharmacy_name="AIIMS New Delhi",
            registration_number="REG-AIIMS-001",
            provider_type=Pharmacy.ProviderType.HOSPITAL,
            address="Ansari Nagar",
            city="New Delhi",
            district="New Delhi",
            state="Delhi",
            pincode="110029",
            phone_number="011-26588500",
            latitude=Decimal("28.567200"),
            longitude=Decimal("77.210000"),
            source_name=Pharmacy.DataSource.DATA_GOV_IN,
            source_id="NIN-DEL-001",
            is_approved=True,
            is_active=True,
            is_demo=False
        )

        # Provider with Missing Coordinates
        cls.unmapped_provider = Pharmacy.objects.create(
            pharmacy_name="Rural Health Center Unmapped",
            registration_number="REG-UNM-001",
            provider_type=Pharmacy.ProviderType.HOSPITAL,
            address="Village Square",
            city="Nalgonda",
            district="Nalgonda",
            state="Telangana",
            pincode="508001",
            latitude=None,
            longitude=None,
            source_name=Pharmacy.DataSource.DATA_GOV_IN,
            source_id="NIN-TEL-999",
            is_approved=False,
            is_active=True,
            is_demo=False
        )

        # 3. Medicine & Inventory
        cls.medicine = Medicine.objects.create(
            medicine_name="Paracetamol 650",
            generic_name="Paracetamol",
            category="Analgesics & Pain Relief",
            strength="650mg",
            dosage_form="Tablet"
        )
        cls.inventory = Inventory.objects.create(
            pharmacy=cls.pharmacy_with_stock,
            medicine=cls.medicine,
            quantity=50,
            availability_status='IN_STOCK'
        )

    def setUp(self):
        self.client = Client()

    def test_01_distinct_marker_data_and_icons(self):
        """
        Verify that hospital and pharmacy map pins contain distinct icon types,
        correct coordinates, and structured metadata.
        """
        page_obj, has_user, map_pins, total, _ = discover_healthcare_providers(
            verification_status='all',
            provider_type='ALL'
        )
        pins_by_id = {p['id']: p for p in map_pins}

        # Hospital pin checks
        self.assertIn(self.hospital.id, pins_by_id)
        hospital_pin = pins_by_id[self.hospital.id]
        self.assertEqual(hospital_pin['icon_type'], 'hospital')
        self.assertEqual(hospital_pin['provider_type'], 'HOSPITAL')
        self.assertAlmostEqual(hospital_pin['lat'], 17.422700, places=4)
        self.assertAlmostEqual(hospital_pin['lng'], 78.452600, places=4)
        self.assertFalse(hospital_pin['is_approved'])
        self.assertEqual(hospital_pin['verification_label'], 'Directory Listing')

        # Pharmacy pin checks
        self.assertIn(self.pharmacy_with_stock.id, pins_by_id)
        pharmacy_pin = pins_by_id[self.pharmacy_with_stock.id]
        self.assertEqual(pharmacy_pin['icon_type'], 'pharmacy')
        self.assertEqual(pharmacy_pin['provider_type'], 'PHARMACY')
        self.assertTrue(pharmacy_pin['is_approved'])
        self.assertEqual(pharmacy_pin['verification_label'], 'Verified Partner')
        self.assertTrue(pharmacy_pin['has_active_inventory'])

    def test_02_haversine_distance_calculations(self):
        """
        Test Haversine distance formula with known geographic baselines.
        Punjagutta (17.4227, 78.4526) to Jubilee Hills (17.4319, 78.4073) is ~4.9 km.
        """
        user_lat, user_lng = 17.4227, 78.4526
        dest_lat, dest_lng = 17.4319, 78.4073

        distance = calculate_haversine_distance(user_lat, user_lng, dest_lat, dest_lng)
        self.assertIsNotNone(distance)
        self.assertGreater(distance, 4.0)
        self.assertLess(distance, 6.0)

        # Identity test (same coordinate -> 0.0 km)
        zero_dist = calculate_haversine_distance(user_lat, user_lng, user_lat, user_lng)
        self.assertEqual(zero_dist, 0.0)

        # Invalid coordinate rejection
        self.assertIsNone(calculate_haversine_distance(999, 78.4, 17.4, 78.4))
        self.assertIsNone(calculate_haversine_distance(None, 78.4, 17.4, 78.4))

    def test_03_provider_type_filters(self):
        """
        Test server-side filtering by provider type (HOSPITAL, PHARMACY, ALL).
        """
        # Hospitals only
        page_obj, _, _, total_hosp, _ = discover_healthcare_providers(
            provider_type='HOSPITAL',
            verification_status='all'
        )
        for p in page_obj:
            self.assertEqual(p.provider_type, Pharmacy.ProviderType.HOSPITAL)

        # Pharmacies only
        page_obj, _, _, total_pharm, _ = discover_healthcare_providers(
            provider_type='PHARMACY',
            verification_status='all'
        )
        for p in page_obj:
            self.assertEqual(p.provider_type, Pharmacy.ProviderType.PHARMACY)

    def test_04_verification_status_filters(self):
        """
        Test filtering by 'approved', 'all', and 'pending'.
        """
        # Approved only
        page_obj, _, _, total_app, _ = discover_healthcare_providers(
            verification_status='approved',
            provider_type='ALL'
        )
        for p in page_obj:
            self.assertTrue(p.is_approved)

        # Pending (unapproved) only
        page_obj, _, _, total_pend, _ = discover_healthcare_providers(
            verification_status='pending',
            provider_type='ALL'
        )
        for p in page_obj:
            self.assertFalse(p.is_approved)

    def test_05_medicine_availability_filter_strictly_inventory_based(self):
        """
        Test that filtering by availability='in_stock' returns ONLY pharmacies
        that have verified active stock in the Inventory table.
        Pharmacies without inventory and hospitals must NOT be returned.
        """
        page_obj, _, map_pins, total, _ = discover_healthcare_providers(
            availability='in_stock',
            verification_status='all',
            provider_type='ALL'
        )
        result_ids = [p.id for p in page_obj]

        # Pharmacy with active stock must be present
        self.assertIn(self.pharmacy_with_stock.id, result_ids)
        # Pharmacy without stock must NOT be present
        self.assertNotIn(self.pharmacy_no_stock.id, result_ids)
        # Hospital must NOT be present under available pharmacy stock filter
        self.assertNotIn(self.hospital.id, result_ids)

    def test_06_search_radius_filtering(self):
        """
        Test proximity radius cutoff around user location (Hyderabad: 17.4227, 78.4526).
        At radius=10km: Hyderabad facilities must be included, Delhi AIIMS excluded.
        """
        user_lat, user_lng = 17.4227, 78.4526
        page_obj, has_user, map_pins, total, coords = discover_healthcare_providers(
            user_lat=user_lat,
            user_lng=user_lng,
            radius_km='10',
            verification_status='all',
            provider_type='ALL'
        )
        self.assertTrue(has_user)
        result_ids = [p.id for p in page_obj]

        self.assertIn(self.hospital.id, result_ids)
        self.assertIn(self.pharmacy_with_stock.id, result_ids)
        # Delhi AIIMS (~1250 km away) must be excluded
        self.assertNotIn(self.delhi_hospital.id, result_ids)

    def test_07_external_directions_url_builder(self):
        """
        Test directions URL generation for Google Maps and OpenStreetMap.
        Verifies both origin-present and origin-absent formats without simulated routes.
        """
        dest_lat, dest_lng = 17.4227, 78.4526
        user_lat, user_lng = 17.4319, 78.4073

        # Google Maps with origin
        g_url_with_origin = build_external_directions_url(dest_lat, dest_lng, user_lat, user_lng, 'google')
        self.assertIn("https://www.google.com/maps/dir/?api=1", g_url_with_origin)
        self.assertIn("origin=17.4319,78.4073", g_url_with_origin)
        self.assertIn("destination=17.4227,78.4526", g_url_with_origin)

        # Google Maps without origin
        g_url_no_origin = build_external_directions_url(dest_lat, dest_lng, None, None, 'google')
        self.assertIn("https://www.google.com/maps/search/?api=1&query=17.4227,78.4526", g_url_no_origin)

        # OpenStreetMap with origin
        osm_url_with_origin = build_external_directions_url(dest_lat, dest_lng, user_lat, user_lng, 'osm')
        self.assertIn("https://www.openstreetmap.org/directions?", osm_url_with_origin)
        self.assertIn("engine=fossgis_osrm_car", osm_url_with_origin)

        # OpenStreetMap without origin
        osm_url_no_origin = build_external_directions_url(dest_lat, dest_lng, None, None, 'osm')
        self.assertIn("https://www.openstreetmap.org/?mlat=17.4227&mlon=78.4526", osm_url_no_origin)

        # Invalid coordinates return empty string
        self.assertEqual(build_external_directions_url(None, None), '')
        self.assertEqual(build_external_directions_url(999, 999), '')

    def test_08_missing_and_invalid_coordinates_handled_gracefully(self):
        """
        Test that facilities without coordinates are omitted from map pins
        and have distance_km=None, without triggering errors.
        """
        page_obj, _, map_pins, _, _ = discover_healthcare_providers(
            verification_status='all',
            provider_type='ALL'
        )
        pin_ids = [p['id'] for p in map_pins]
        self.assertNotIn(self.unmapped_provider.id, pin_ids)

        # Check list object has distance_km = None
        for p in page_obj:
            if p.id == self.unmapped_provider.id:
                self.assertIsNone(p.distance_km)

    def test_09_discovery_view_http_response_and_map_pins(self):
        """
        Test GET /pharmacies/ response contains interactive map markers,
        clustering assets, directions URLs, and filter options in HTML context.
        """
        response = self.client.get(reverse('pharmacy_discovery') + '?verification=all')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pharmacies/discovery.html')

        # Check filter options in context
        self.assertIn('availability_options', response.context)
        self.assertIn('radius_options', response.context)
        self.assertIn('map_pins', response.context)

        # Check HTML contains Leaflet MarkerCluster CDN references
        self.assertContains(response, 'leaflet.markercluster')
        self.assertContains(response, 'Map Legend')
        self.assertContains(response, 'straight-line')

    def test_10_provider_detail_view_directions(self):
        """
        Test provider detail page for both Hospital and Pharmacy
        renders valid directions links and map information.
        """
        # Hospital detail
        hosp_res = self.client.get(reverse('pharmacy_detail', args=[self.hospital.id]))
        self.assertEqual(hosp_res.status_code, 200)
        self.assertContains(hosp_res, "Google Directions")
        self.assertContains(hosp_res, "OSM Route")
        self.assertContains(hosp_res, "Nizam's Institute of Medical Sciences")

        # Pharmacy detail
        pharm_res = self.client.get(reverse('pharmacy_detail', args=[self.pharmacy_with_stock.id]))
        self.assertEqual(pharm_res.status_code, 200)
        self.assertContains(pharm_res, "Google Directions")
        self.assertContains(pharm_res, "Apollo Pharmacy Jubilee Hills")
        self.assertContains(pharm_res, "Reported Medicine Inventory")

    def test_11_customer_request_workflow_integrity(self):
        """
        Verify that existing customer inquiry workflows remain intact.
        Customer can view medicine, view pharmacy, and access request forms.
        """
        self.client.force_login(self.customer_user)
        res = self.client.get(reverse('create_request', args=[self.pharmacy_with_stock.id, self.medicine.id]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Paracetamol 650")
