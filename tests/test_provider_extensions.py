"""
MediFind Stage 2 Test Suite: Provider Model Extensions & Pilot Ingestion
Verifies provider creation, validation, deduplication, coordinate bounds,
and full regression preservation across existing pharmacy, inventory, and customer workflows.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.importers import (
    clean_indian_pincode,
    import_provider_records,
    validate_indian_coordinates,
    validate_provider_payload,
)
from pharmacies.models import Pharmacy
from requests_app.models import AvailabilityRequest

User = get_user_model()


class ProviderModelExtensionTests(TestCase):
    """Tests for extended Pharmacy / Provider fields and constraints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='dr_test_owner',
            email='dr_test@medifind.test',
            password='password123',
            role='PHARMACY'
        )

    def test_provider_creation_hospital(self):
        """Test creating a hospital provider with valid fields and source tracking."""
        hospital = Pharmacy.objects.create(
            pharmacy_name="City Multi-Specialty Hospital",
            provider_type=Pharmacy.ProviderType.HOSPITAL,
            source_name=Pharmacy.DataSource.DATA_GOV_IN,
            source_id="NIN-TEST-99001",
            registration_number="NIN-TEST-99001",
            address="100 Rajaji Salai",
            city="Chennai",
            district="Chennai",
            state="Tamil Nadu",
            pincode="600001",
            phone_number="044-25000000",
            latitude=Decimal("13.082700"),
            longitude=Decimal("80.270700"),
            is_approved=False,
            is_active=True,
            is_demo=False,
        )
        self.assertEqual(hospital.provider_type, Pharmacy.ProviderType.HOSPITAL)
        self.assertEqual(hospital.source_name, Pharmacy.DataSource.DATA_GOV_IN)
        self.assertEqual(hospital.source_id, "NIN-TEST-99001")
        self.assertFalse(hospital.is_approved)
        self.assertTrue(hospital.is_active)
        self.assertFalse(hospital.is_demo)
        self.assertIn("Hospital", str(hospital))
        self.assertEqual(hospital.provider_name, "City Multi-Specialty Hospital")

    def test_provider_creation_pharmacy_with_owner(self):
        """Test creating a pharmacy provider associated with an authenticated owner user."""
        pharmacy = Pharmacy.objects.create(
            owner=self.user,
            pharmacy_name="Dr Test Care Pharmacy",
            provider_type=Pharmacy.ProviderType.PHARMACY,
            source_name=Pharmacy.DataSource.MANUAL,
            registration_number="REG-TN-2026-99002",
            address="45 Anna Nagar West",
            city="Chennai",
            district="Chennai",
            state="Tamil Nadu",
            pincode="600040",
            phone_number="044-26000000",
            latitude=Decimal("13.085000"),
            longitude=Decimal("80.210000"),
            is_approved=True,
            is_demo=False,
        )
        self.assertEqual(pharmacy.owner, self.user)
        self.assertEqual(pharmacy.provider_type, Pharmacy.ProviderType.PHARMACY)
        self.assertTrue(pharmacy.is_approved)
        self.assertIn("Pharmacy", str(pharmacy))

    def test_provider_creation_unclaimed_public_facility(self):
        """Test that imported public facilities can exist with owner=None."""
        pub_store = Pharmacy.objects.create(
            owner=None,
            pharmacy_name="Public Community Dispensary",
            provider_type=Pharmacy.ProviderType.PHARMACY,
            source_name=Pharmacy.DataSource.OSM,
            source_id="OSM-TEST-12345",
            registration_number="OSM-TEST-12345",
            address="Near Bus Stand, Station Road",
            city="Secunderabad",
            district="Hyderabad",
            state="Telangana",
            pincode="500003",
            latitude=Decimal("17.439000"),
            longitude=Decimal("78.498000"),
            is_approved=False,
        )
        self.assertIsNone(pub_store.owner)
        self.assertFalse(pub_store.is_approved)

    def test_source_identifier_uniqueness(self):
        """Test that identical source_name and source_id cannot be duplicated in database."""
        Pharmacy.objects.create(
            pharmacy_name="First Facility",
            registration_number="UNIQUE-REG-001",
            source_name=Pharmacy.DataSource.DATA_GOV_IN,
            source_id="STABLE-SOURCE-001",
            address="Road 1",
            city="Hyderabad",
            state="Telangana",
            pincode="500001",
        )
        with self.assertRaises(IntegrityError):
            Pharmacy.objects.create(
                pharmacy_name="Second Facility With Same Source ID",
                registration_number="UNIQUE-REG-002",
                source_name=Pharmacy.DataSource.DATA_GOV_IN,
                source_id="STABLE-SOURCE-001",  # Same source_name and source_id
                address="Road 2",
                city="Hyderabad",
                state="Telangana",
                pincode="500001",
            )


class CoordinateAndDataValidationTests(TestCase):
    """Tests for geospatial coordinate validation and payload cleansing."""

    def test_valid_indian_coordinates(self):
        """Test that coordinates within India's boundary return True and exact Decimals."""
        # Hyderabad
        valid, lat, lng, msg = validate_indian_coordinates(17.385044, 78.486671)
        self.assertTrue(valid)
        self.assertEqual(lat, Decimal('17.385044'))
        self.assertEqual(lng, Decimal('78.486671'))

        # Delhi
        valid, lat, lng, msg = validate_indian_coordinates('28.613939', '77.209021')
        self.assertTrue(valid)
        self.assertEqual(lat, Decimal('28.613939'))
        self.assertEqual(lng, Decimal('77.209021'))

    def test_coordinate_transposition_correction(self):
        """Test that inverted coordinates (Lat swapped with Lng) are detected and corrected."""
        # Intentionally transposed: Lat=78.486671 (Longitude of Hyd), Lng=17.385044 (Latitude of Hyd)
        valid, lat, lng, msg = validate_indian_coordinates(78.486671, 17.385044)
        self.assertTrue(valid)
        self.assertEqual(lat, Decimal('17.385044'))
        self.assertEqual(lng, Decimal('78.486671'))

    def test_out_of_bounds_coordinates_rejection(self):
        """Test rejection of coordinates outside India (e.g. Europe, USA, Ocean)."""
        # London (Lat: 51.5, Lng: -0.1)
        valid, lat, lng, msg = validate_indian_coordinates(51.5074, -0.1278)
        self.assertFalse(valid)
        self.assertIn("outside India boundary", msg)

        # Null or missing coordinates
        valid, lat, lng, msg = validate_indian_coordinates(None, 78.5)
        self.assertFalse(valid)

        # Non-numeric coordinates
        valid, lat, lng, msg = validate_indian_coordinates('invalid_lat', '78.5')
        self.assertFalse(valid)

    def test_clean_indian_pincode(self):
        """Test normalization of 6-digit Indian postal codes."""
        self.assertEqual(clean_indian_pincode('500081'), '500081')
        self.assertEqual(clean_indian_pincode(' 560038 '), '560038')
        self.assertEqual(clean_indian_pincode('500-034'), '500034')
        self.assertEqual(clean_indian_pincode('012345'), '')  # Cannot start with 0
        self.assertEqual(clean_indian_pincode('12345'), '')    # 5 digits invalid
        self.assertEqual(clean_indian_pincode('abcdef'), '')   # Non-numeric invalid

    def test_validate_provider_payload_rejections(self):
        """Test that missing mandatory fields are rejected by payload validator."""
        # Short name
        valid, msg, _ = validate_provider_payload({'name': 'AB', 'address': 'Long Street Address', 'city': 'Hyd', 'state': 'TG', 'pincode': '500001', 'lat': 17.4, 'lng': 78.4})
        self.assertFalse(valid)

        # Short address
        valid, msg, _ = validate_provider_payload({'name': 'Apollo', 'address': 'St', 'city': 'Hyd', 'state': 'TG', 'pincode': '500001', 'lat': 17.4, 'lng': 78.4})
        self.assertFalse(valid)

        # Invalid provider type
        valid, msg, _ = validate_provider_payload({'name': 'Apollo', 'address': 'Long Street Address', 'city': 'Hyd', 'state': 'TG', 'pincode': '500001', 'lat': 17.4, 'lng': 78.4, 'provider_type': 'INVALID_TYPE'})
        self.assertFalse(valid)


class ImporterPipelineAndDeduplicationTests(TestCase):
    """Tests for bulk/pilot importer execution, idempotency, and deduplication."""

    def test_import_provider_records_success_and_deduplication(self):
        """Test import of valid records, followed by idempotent skipping on re-import."""
        records = [
            {
                'name': 'AIIMS Delhi Test Unit',
                'provider_type': 'HOSPITAL',
                'source_name': 'DATA_GOV_IN',
                'source_id': 'TEST-NIN-100',
                'address': 'Ansari Nagar East',
                'city': 'New Delhi',
                'state': 'Delhi',
                'pincode': '110029',
                'lat': 28.567200,
                'lng': 77.210000,
            },
            {
                'name': 'Apollo Pharmacy Test Unit',
                'provider_type': 'PHARMACY',
                'source_name': 'OSM',
                'source_id': 'TEST-OSM-200',
                'address': 'Jubilee Hills Checkpost',
                'city': 'Hyderabad',
                'state': 'Telangana',
                'pincode': '500033',
                'lat': 17.430000,
                'lng': 78.410000,
            },
        ]

        # First run: both imported
        report1 = import_provider_records(records, dry_run=False)
        self.assertEqual(report1.imported, 2)
        self.assertEqual(report1.skipped_duplicate, 0)
        self.assertEqual(report1.rejected_invalid, 0)

        # Imported records must be unapproved by default
        hosp = Pharmacy.objects.get(source_id='TEST-NIN-100')
        self.assertFalse(hosp.is_approved)
        self.assertFalse(hosp.is_demo)

        # Second run: both detected as duplicates and skipped
        report2 = import_provider_records(records, dry_run=False)
        self.assertEqual(report2.imported, 0)
        self.assertEqual(report2.skipped_duplicate, 2)
        self.assertEqual(report2.rejected_invalid, 0)

    def test_import_provider_records_failure_handling(self):
        """Test that bad records are counted as rejected and do not stop processing."""
        mixed_records = [
            {
                'name': 'Valid Hospital',
                'provider_type': 'HOSPITAL',
                'source_name': 'DATA_GOV_IN',
                'source_id': 'TEST-GOOD-01',
                'address': 'Valid Address Line 1',
                'city': 'Hyderabad',
                'state': 'Telangana',
                'pincode': '500001',
                'lat': 17.400000,
                'lng': 78.450000,
            },
            {
                'name': 'Bad Coordinates Hospital (Paris)',
                'provider_type': 'HOSPITAL',
                'source_name': 'DATA_GOV_IN',
                'source_id': 'TEST-BAD-02',
                'address': 'Champs-Élysées',
                'city': 'Paris',
                'state': 'Europe',
                'pincode': '500001',
                'lat': 48.856600,
                'lng': 2.352200,
            },
        ]
        report = import_provider_records(mixed_records, dry_run=False)
        self.assertEqual(report.imported, 1)
        self.assertEqual(report.rejected_invalid, 1)
        self.assertTrue(Pharmacy.objects.filter(source_id='TEST-GOOD-01').exists())
        self.assertFalse(Pharmacy.objects.filter(source_id='TEST-BAD-02').exists())


class ExistingWorkflowPreservationRegressionTests(TestCase):
    """Verifies that existing pharmacy registration, inventory, and customer workflows remain 100% operational."""

    def setUp(self):
        self.customer = User.objects.create_user(
            username='regress_cust',
            email='cust@medifind.test',
            password='password123',
            role='CUSTOMER'
        )
        self.owner = User.objects.create_user(
            username='regress_owner',
            email='owner@medifind.test',
            password='password123',
            role='PHARMACY'
        )
        self.pharmacy = Pharmacy.objects.create(
            owner=self.owner,
            pharmacy_name="Regression Demo Pharmacy",
            provider_type=Pharmacy.ProviderType.PHARMACY,
            registration_number="REG-REGRESS-001",
            address="12 Banjara Hills",
            city="Hyderabad",
            district="Hyderabad",
            state="Telangana",
            pincode="500034",
            phone_number="040-12345678",
            latitude=Decimal("17.415000"),
            longitude=Decimal("78.435000"),
            is_approved=True,
            is_demo=True,
        )
        self.medicine = Medicine.objects.create(
            medicine_name="Paracetamol 650mg",
            generic_name="Paracetamol",
            category="Analgesics & Pain Relief",
            dosage_form="Tablet",
            strength="650mg",
            description="Used for mild to moderate pain and fever.",
        )

    def test_inventory_creation_and_workflow(self):
        """Verify that existing Inventory model still associates smoothly with Pharmacy."""
        item = Inventory.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            quantity=100,
        )
        self.assertEqual(item.pharmacy, self.pharmacy)
        self.assertEqual(item.medicine, self.medicine)
        self.assertEqual(self.pharmacy.inventories.count(), 1)

    def test_customer_availability_request_workflow(self):
        """Verify customer availability requests continue to work flawlessly with extended model."""
        req = AvailabilityRequest.objects.create(
            customer=self.customer,
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            quantity_requested=2,
            request_message="Need for mild fever",
        )
        self.assertEqual(req.customer, self.customer)
        self.assertEqual(req.pharmacy, self.pharmacy)
        self.assertEqual(req.status, 'PENDING')
        self.assertEqual(self.pharmacy.pharmacy_requests.count(), 1)
