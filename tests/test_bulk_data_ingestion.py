"""
Automated Test Suite for MediFind Stage 4: India-Wide Bulk Data Ingestion Pipeline
Verifies adapter parsing, canonical normalization, territorial coordinate validation,
multi-tier deduplication, idempotency, batch transactions, demo preservation, and CLI execution.
"""

import io
import json
import os
from decimal import Decimal
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from accounts.models import User
from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from pharmacies.pipeline import (
    ABDMRegistryAdapter,
    BulkIngestionEngine,
    DataGovInHospitalAdapter,
    OSMPharmacyAdapter,
    clean_indian_pincode,
    find_duplicate,
    normalize_indian_state,
    normalize_phone_number,
    validate_indian_coordinates,
    validate_provider_record,
)


class BulkDataIngestionPipelineTests(TestCase):

    def setUp(self):
        # Create an existing verified demo pharmacy with user and inventory to test preservation
        self.demo_user = User.objects.create_user(
            username='preserved_owner',
            email='preserved@medfind.test',
            password='TestPassword123!',
            role='PHARMACY'
        )
        self.demo_pharmacy = Pharmacy.objects.create(
            pharmacy_name="Preserved Demo Chemist",
            registration_number="REG-DEMO-PRESERVED-001",
            owner=self.demo_user,
            address="Road 1, Banjara Hills",
            city="Hyderabad",
            district="Hyderabad",
            state="Telangana",
            pincode="500034",
            phone_number="040-23351111",
            latitude=Decimal("17.415600"),
            longitude=Decimal("78.435600"),
            source_name="DEMO",
            source_id="DEMO-001",
            is_approved=True,
            is_demo=True,
            is_active=True
        )
        self.test_medicine = Medicine.objects.create(
            medicine_name="Preserved Paracetamol",
            generic_name="Paracetamol",
            strength="650mg",
            dosage_form="Tablet",
            category="Analgesics & Pain Relief"
        )
        self.test_inventory = Inventory.objects.create(
            pharmacy=self.demo_pharmacy,
            medicine=self.test_medicine,
            quantity=100,
            availability_status='IN_STOCK'
        )

    def test_01_coordinate_validation_and_transposition(self):
        """Verifies strict territorial coordinate validation and transposition auto-correction."""
        # 1. Valid coordinates across India
        valid_coords = [
            (28.5672, 77.2100),  # New Delhi
            (19.0028, 72.8424),  # Mumbai
            (17.4227, 78.4526),  # Hyderabad
            (12.9644, 77.5756),  # Bengaluru
            (22.5735, 88.3639),  # Kolkata
        ]
        for lat, lng in valid_coords:
            is_valid, v_lat, v_lng, msg = validate_indian_coordinates(lat, lng)
            self.assertTrue(is_valid, f"Expected {lat}, {lng} to be valid: {msg}")
            self.assertEqual(float(v_lat), round(lat, 6))

        # 2. Foreign coordinates outside India (rejected)
        invalid_coords = [
            (48.8566, 2.3522),    # Paris, France
            (51.5074, -0.1278),   # London, UK
            (1.3521, 103.8198),   # Singapore (Lat < 6.5)
            (40.7128, -74.0060),  # New York, USA
            (0.0, 0.0),           # Null Island
        ]
        for lat, lng in invalid_coords:
            is_valid, _, _, msg = validate_indian_coordinates(lat, lng)
            self.assertFalse(is_valid, f"Expected {lat}, {lng} to be rejected, but got valid: {msg}")

        # 3. Transposed coordinates (Lat in lng range, Lng in lat range) -> Auto-swap
        transposed_lat, transposed_lng = 78.452600, 17.422700  # Hyderabad inverted
        is_valid, corrected_lat, corrected_lng, msg = validate_indian_coordinates(transposed_lat, transposed_lng)
        self.assertTrue(is_valid)
        self.assertEqual(float(corrected_lat), 17.422700)
        self.assertEqual(float(corrected_lng), 78.452600)

    def test_02_indian_pincode_and_state_normalization(self):
        """Verifies 6-digit Indian postal code validation and official state canonicalization."""
        # Pincodes
        self.assertEqual(clean_indian_pincode("500082"), "500082")
        self.assertEqual(clean_indian_pincode(" 110029 "), "110029")
        self.assertEqual(clean_indian_pincode("PIN: 400012"), "400012")
        self.assertEqual(clean_indian_pincode("12345"), "")   # 5 digits invalid
        self.assertEqual(clean_indian_pincode("012345"), "")  # Leading 0 invalid
        self.assertEqual(clean_indian_pincode("ABCDEF"), "")

        # States / UTs
        self.assertEqual(normalize_indian_state("DL"), "Delhi")
        self.assertEqual(normalize_indian_state("NCT of Delhi"), "Delhi")
        self.assertEqual(normalize_indian_state("TG"), "Telangana")
        self.assertEqual(normalize_indian_state("Telengana"), "Telangana")
        self.assertEqual(normalize_indian_state("Telangana State"), "Telangana")
        self.assertEqual(normalize_indian_state("MH"), "Maharashtra")
        self.assertEqual(normalize_indian_state("Orissa"), "Odisha")
        self.assertEqual(normalize_indian_state("Pondicherry"), "Puducherry")
        self.assertEqual(normalize_indian_state("Jammu & Kashmir"), "Jammu and Kashmir")
        self.assertEqual(normalize_indian_state("Bengaluru"), "Bengaluru")

    def test_03_data_gov_in_hospital_adapter(self):
        """Verifies parsing of National Hospital Directory CSV structured feeds."""
        sample_csv = os.path.join(settings.BASE_DIR, 'data', 'national_hospital_directory.csv')
        self.assertTrue(os.path.exists(sample_csv))

        adapter = DataGovInHospitalAdapter()
        records = list(adapter.parse(sample_csv))
        self.assertGreaterEqual(len(records), 50)

        first = records[0]
        self.assertEqual(first['provider_type'], 'HOSPITAL')
        self.assertEqual(first['source_name'], 'DATA_GOV_IN')
        self.assertTrue(first['name'])
        self.assertTrue(first['pincode'])
        self.assertIsNotNone(first['lat'])
        self.assertIsNotNone(first['lng'])

    def test_04_osm_pharmacy_adapter(self):
        """Verifies parsing of OpenStreetMap Overpass JSON structured feeds."""
        sample_json = os.path.join(settings.BASE_DIR, 'data', 'osm_pharmacies_india.json')
        self.assertTrue(os.path.exists(sample_json))

        adapter = OSMPharmacyAdapter()
        records = list(adapter.parse(sample_json))
        self.assertGreaterEqual(len(records), 20)

        first = records[0]
        self.assertEqual(first['provider_type'], 'PHARMACY')
        self.assertEqual(first['source_name'], 'OSM')
        self.assertTrue(first['name'])
        self.assertTrue(first['source_id'].startswith('OSM-'))

    def test_05_abdm_registry_adapter(self):
        """Verifies parsing of ABDM Health Facility Registry JSON feeds."""
        sample_json = os.path.join(settings.BASE_DIR, 'data', 'abdm_health_facilities.json')
        self.assertTrue(os.path.exists(sample_json))

        adapter = ABDMRegistryAdapter()
        records = list(adapter.parse(sample_json))
        self.assertEqual(len(records), 5)
        self.assertEqual(records[0]['source_name'], 'ABDM')
        self.assertTrue(records[0]['source_id'].startswith('HFR-'))

    def test_06_multi_tier_duplicate_detection(self):
        """Verifies exact source-ID, reg number, geospatial proximity, and name duplicate checks."""
        # 1. Exact Source ID match
        dup1 = find_duplicate({
            'source_name': 'DEMO',
            'source_id': 'DEMO-001',
            'pharmacy_name': 'Preserved Demo Chemist'
        })
        self.assertTrue(dup1.is_duplicate)
        self.assertEqual(dup1.match_type, 'EXACT_SOURCE_ID')

        # 2. Exact Registration Number match
        dup2 = find_duplicate({
            'registration_number': 'REG-DEMO-PRESERVED-001',
            'pharmacy_name': 'Some Other Name'
        })
        self.assertTrue(dup2.is_duplicate)
        self.assertEqual(dup2.match_type, 'EXACT_REG_NUM')

        # 3. Geospatial proximity (< 100m) + Name similarity (> 75%)
        # Existing demo is at 17.415600, 78.435600. Move by ~0.0002 deg (~22 meters)
        dup3 = find_duplicate({
            'pharmacy_name': 'Preserved Demo Chemist & Druggist',
            'latitude': Decimal('17.415750'),
            'longitude': Decimal('78.435650'),
            'city': 'Hyderabad',
            'state': 'Telangana'
        })
        self.assertTrue(dup3.is_duplicate)
        self.assertEqual(dup3.match_type, 'GEOSPATIAL_PROXIMITY')
        self.assertLess(dup3.distance_meters, 50.0)

        # 4. Completely distinct facility far away -> No duplicate
        distinct = find_duplicate({
            'source_name': 'DATA_GOV_IN',
            'source_id': 'NIN-NEW-9999',
            'registration_number': 'NIN-NEW-9999',
            'pharmacy_name': 'Totally Unique Rural Clinic',
            'latitude': Decimal('26.123400'),
            'longitude': Decimal('85.123400'),
            'city': 'Muzaffarpur',
            'state': 'Bihar'
        })
        self.assertFalse(distinct.is_duplicate)
        self.assertEqual(distinct.match_type, 'NONE')

    def test_07_dry_run_leaves_database_unmodified(self):
        """Verifies that dry-run mode previews would-be imports without creating records in DB."""
        initial_count = Pharmacy.objects.count()

        sample_records = [
            {
                'name': 'Dry Run Test Hospital 1',
                'provider_type': 'HOSPITAL',
                'source_name': 'DATA_GOV_IN',
                'source_id': 'DRY-TEST-001',
                'registration_number': 'NIN-DRY-001',
                'address': 'MG Road 1',
                'city': 'Bengaluru',
                'state': 'Karnataka',
                'pincode': '560001',
                'lat': 12.971600,
                'lng': 77.594600
            },
            {
                'name': 'Dry Run Test Hospital 2',
                'provider_type': 'HOSPITAL',
                'source_name': 'DATA_GOV_IN',
                'source_id': 'DRY-TEST-002',
                'registration_number': 'NIN-DRY-002',
                'address': 'MG Road 2',
                'city': 'Bengaluru',
                'state': 'Karnataka',
                'pincode': '560001',
                'lat': 12.972000,
                'lng': 77.595000
            }
        ]

        engine = BulkIngestionEngine(batch_size=10, dry_run=True)
        summary = engine.execute(sample_records)

        self.assertEqual(summary.total_scanned, 2)
        self.assertEqual(summary.valid_records, 2)
        self.assertEqual(summary.imported, 2)  # Eligible count

        # Crucial check: Database count must remain unchanged in dry run
        self.assertEqual(Pharmacy.objects.count(), initial_count)

    def test_08_idempotent_reimport(self):
        """Verifies that re-running the pipeline does not create duplicate entries."""
        initial_count = Pharmacy.objects.count()

        batch = [
            {
                'name': 'Idempotent Testing Hospital',
                'provider_type': 'HOSPITAL',
                'source_name': 'DATA_GOV_IN',
                'source_id': 'IDEM-TEST-001',
                'registration_number': 'NIN-IDEM-001',
                'address': 'Medical Road, Sector 5',
                'city': 'Jaipur',
                'state': 'Rajasthan',
                'pincode': '302001',
                'lat': 26.912400,
                'lng': 75.787300
            }
        ]

        engine = BulkIngestionEngine(batch_size=10, dry_run=False)

        # Run 1: Should import 1 record
        s1 = engine.execute(batch)
        self.assertEqual(s1.imported, 1)
        self.assertEqual(s1.skipped_duplicate, 0)
        self.assertEqual(Pharmacy.objects.count(), initial_count + 1)

        # Run 2: Exact same record should be skipped
        s2 = engine.execute(batch)
        self.assertEqual(s2.imported, 0)
        self.assertEqual(s2.skipped_duplicate, 1)
        # Database count must not increase
        self.assertEqual(Pharmacy.objects.count(), initial_count + 1)

    def test_09_demo_data_and_existing_pharmacy_accounts_preserved(self):
        """Verifies that existing demo records, pharmacy user accounts, and inventory are untouched."""
        initial_demo_count = Pharmacy.objects.filter(is_demo=True).count()
        initial_inventory_count = Inventory.objects.count()

        # Run a real import of fresh records
        fresh_records = [
            {
                'name': 'Fresh Genuine Medical Center',
                'provider_type': 'HOSPITAL',
                'source_name': 'DATA_GOV_IN',
                'source_id': 'FRESH-001',
                'registration_number': 'NIN-FRESH-001',
                'address': 'Ring Road, Civil Lines',
                'city': 'Nagpur',
                'state': 'Maharashtra',
                'pincode': '440001',
                'lat': 21.145800,
                'lng': 79.088200
            }
        ]
        engine = BulkIngestionEngine(batch_size=10, dry_run=False)
        engine.execute(fresh_records)

        # Verify demo pharmacy remains unchanged
        self.demo_pharmacy.refresh_from_db()
        self.assertEqual(self.demo_pharmacy.pharmacy_name, "Preserved Demo Chemist")
        self.assertEqual(self.demo_pharmacy.owner, self.demo_user)
        self.assertTrue(self.demo_pharmacy.is_demo)
        self.assertTrue(self.demo_pharmacy.is_approved)
        self.assertEqual(Pharmacy.objects.filter(is_demo=True).count(), initial_demo_count)

        # Verify linked inventory remains intact
        self.test_inventory.refresh_from_db()
        self.assertEqual(self.test_inventory.quantity, 100)
        self.assertEqual(Inventory.objects.count(), initial_inventory_count)

    def test_10_imported_records_never_auto_approved(self):
        """Enforces clinical invariant: All imported records must have is_approved=False."""
        batch = [
            {
                'name': 'Safety Check Hospital',
                'provider_type': 'HOSPITAL',
                'source_name': 'DATA_GOV_IN',
                'source_id': 'SAFETY-001',
                'registration_number': 'NIN-SAFETY-001',
                'address': 'Hospital Road',
                'city': 'Kochi',
                'state': 'Kerala',
                'pincode': '682001',
                'lat': 9.931200,
                'lng': 76.267300,
                'is_approved': True  # Injected malicious attempt to auto-verify!
            }
        ]

        engine = BulkIngestionEngine(batch_size=10, dry_run=False)
        engine.execute(batch)

        saved = Pharmacy.objects.get(registration_number='NIN-SAFETY-001')
        self.assertFalse(saved.is_approved, "Clinical violation: Ingested record was auto-verified!")
        self.assertFalse(saved.is_demo)

    def test_11_management_command_execution(self):
        """Verifies Django management command 'import_india_data' with --dry-run flag."""
        out = io.StringIO()
        call_command('import_india_data', '--dry-run', '--source', 'all', stdout=out)
        output_str = out.getvalue()

        self.assertIn("MEDIFIND NATIONWIDE HEALTHCARE DATA INGESTION PIPELINE", output_str)
        self.assertIn("Mode: [DRY-RUN PREVIEW]", output_str)
        self.assertIn("Total Source Records Scanned", output_str)
        self.assertIn("Breakdown by State / Union Territory", output_str)
        self.assertIn("DATABASE STATUS POST-PIPELINE", output_str)
