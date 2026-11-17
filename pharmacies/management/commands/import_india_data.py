"""
Django Management Command: import_india_data
Production nationwide data ingestion command for hospitals, pharmacies, and ABDM facilities.
Supports atomic batching, multi-tier deduplication, dry-run previews, and detailed state breakdowns.
"""

import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from pharmacies.models import Pharmacy
from pharmacies.pipeline import (
    ABDMRegistryAdapter,
    BulkIngestionEngine,
    BulkIngestionSummary,
    DataGovInHospitalAdapter,
    OSMPharmacyAdapter,
)

DEFAULT_HOSPITALS_CSV = os.path.join(settings.BASE_DIR, 'data', 'national_hospital_directory.csv')
DEFAULT_PHARMACIES_JSON = os.path.join(settings.BASE_DIR, 'data', 'osm_pharmacies_india.json')
DEFAULT_ABDM_JSON = os.path.join(settings.BASE_DIR, 'data', 'abdm_health_facilities.json')


class Command(BaseCommand):
    help = "Imports nationwide genuine hospital and pharmacy data into MediFind with strict validation and deduplication."

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            default='all',
            choices=['all', 'hospitals', 'pharmacies', 'abdm', 'data_gov_in', 'osm'],
            help="Data source to ingest ('all', 'hospitals', 'pharmacies', 'abdm', 'data_gov_in', 'osm'). Default: 'all'",
        )
        parser.add_argument(
            '--file',
            type=str,
            default='',
            help="Custom path to CSV or JSON data file. If omitted, uses default curated datasets in data/.",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Simulates ingestion, runs validation and deduplication, and reports expected changes without committing to DB.",
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help="Number of records to process per atomic database transaction. Default: 50",
        )
        parser.add_argument(
            '--state',
            type=str,
            default='',
            help="Optional state filter (e.g. 'Telangana', 'Delhi', 'Maharashtra') to selectively import.",
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help="Optional maximum number of records to import.",
        )

    def handle(self, *args, **options):
        source_opt = options['source'].lower()
        file_path = options['file']
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        state_filter = options['state'].strip()
        limit = options['limit']

        mode_banner = "[DRY-RUN PREVIEW]" if dry_run else "[LIVE INGESTION EXECUTION]"
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(self.style.WARNING(f"  MEDIFIND NATIONWIDE HEALTHCARE DATA INGESTION PIPELINE"))
        self.stdout.write(self.style.WARNING(f"  Mode: {mode_banner} | Source: {source_opt.upper()} | Batch Size: {batch_size}"))
        if state_filter:
            self.stdout.write(self.style.NOTICE(f"  Target State Filter: {state_filter}"))
        self.stdout.write(self.style.WARNING("=" * 80 + "\n"))

        engine = BulkIngestionEngine(batch_size=batch_size, dry_run=dry_run)
        grand_summary = BulkIngestionSummary(dry_run=dry_run)

        # Plan operations based on source flag
        tasks = []
        if file_path:
            # Custom file provided
            if not os.path.exists(file_path):
                raise CommandError(f"Specified file does not exist: {file_path}")
            if source_opt in ('hospitals', 'data_gov_in'):
                adapter = DataGovInHospitalAdapter()
            elif source_opt in ('pharmacies', 'osm'):
                adapter = OSMPharmacyAdapter()
            elif source_opt == 'abdm':
                adapter = ABDMRegistryAdapter()
            else:
                adapter = DataGovInHospitalAdapter() if file_path.endswith('.csv') else OSMPharmacyAdapter()
            tasks.append((adapter, file_path, "Custom Feed"))
        else:
            # Use default curated datasets
            if source_opt in ('all', 'hospitals', 'data_gov_in'):
                if os.path.exists(DEFAULT_HOSPITALS_CSV):
                    tasks.append((DataGovInHospitalAdapter(), DEFAULT_HOSPITALS_CSV, "National Hospital Directory (data.gov.in / MoHFW)"))
                else:
                    self.stdout.write(self.style.ERROR(f"Warning: Default hospitals file not found at {DEFAULT_HOSPITALS_CSV}"))

            if source_opt in ('all', 'pharmacies', 'osm'):
                if os.path.exists(DEFAULT_PHARMACIES_JSON):
                    tasks.append((OSMPharmacyAdapter(), DEFAULT_PHARMACIES_JSON, "OpenStreetMap Retail Pharmacies (OSM / ODbL)"))
                else:
                    self.stdout.write(self.style.ERROR(f"Warning: Default pharmacies file not found at {DEFAULT_PHARMACIES_JSON}"))

            if source_opt in ('all', 'abdm'):
                if os.path.exists(DEFAULT_ABDM_JSON):
                    tasks.append((ABDMRegistryAdapter(), DEFAULT_ABDM_JSON, "ABDM Health Facility Registry (HFR)"))
                else:
                    self.stdout.write(self.style.ERROR(f"Warning: Default ABDM file not found at {DEFAULT_ABDM_JSON}"))

        if not tasks:
            raise CommandError("No valid data files or sources scheduled for ingestion.")

        for adapter, path, desc in tasks:
            self.stdout.write(self.style.HTTP_INFO(f"\n--> Ingesting from: {desc}"))
            self.stdout.write(f"    File: {path}")

            parsed_stream = adapter.parse(path)
            summary = engine.execute(parsed_stream, state_filter=state_filter, limit=limit)

            # Aggregate to grand summary
            grand_summary.total_scanned += summary.total_scanned
            grand_summary.valid_records += summary.valid_records
            grand_summary.invalid_records += summary.invalid_records
            grand_summary.missing_coordinates += summary.missing_coordinates
            grand_summary.skipped_duplicate += summary.skipped_duplicate
            grand_summary.duplicate_candidates += summary.duplicate_candidates
            grand_summary.imported += summary.imported
            grand_summary.hospitals_imported += summary.hospitals_imported
            grand_summary.pharmacies_imported += summary.pharmacies_imported
            grand_summary.duration_seconds += summary.duration_seconds

            for st, cnt in summary.records_by_state.items():
                grand_summary.records_by_state[st] = grand_summary.records_by_state.get(st, 0) + cnt
            for dist, cnt in summary.records_by_district.items():
                grand_summary.records_by_district[dist] = grand_summary.records_by_district.get(dist, 0) + cnt
            for src, cnt in summary.records_by_source.items():
                grand_summary.records_by_source[src] = grand_summary.records_by_source.get(src, 0) + cnt

            grand_summary.details.extend(summary.details)
            grand_summary.duplicate_details.extend(summary.duplicate_details)
            grand_summary.rejection_details.extend(summary.rejection_details)

            self.stdout.write(f"    Batch results: Scanned={summary.total_scanned}, Valid={summary.valid_records}, "
                              f"Imported/Eligible={summary.imported}, Duplicates Skipped={summary.skipped_duplicate}, "
                              f"Duplicate Candidates={summary.duplicate_candidates}, Invalid={summary.invalid_records}")

        # Final Report Output
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(f"  INGESTION PIPELINE EXECUTION SUMMARY {mode_banner}"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"  Total Source Records Scanned     : {grand_summary.total_scanned}")
        self.stdout.write(f"  Valid Records Checked            : {grand_summary.valid_records}")
        self.stdout.write(self.style.SUCCESS(f"  Records Eligible / Imported      : {grand_summary.imported}"))
        self.stdout.write(f"    - Hospitals                    : {grand_summary.hospitals_imported}")
        self.stdout.write(f"    - Pharmacies                   : {grand_summary.pharmacies_imported}")
        self.stdout.write(self.style.WARNING(f"  Exact Duplicates Skipped         : {grand_summary.skipped_duplicate}"))
        self.stdout.write(self.style.WARNING(f"  Geospatial Duplicate Candidates  : {grand_summary.duplicate_candidates}"))
        self.stdout.write(self.style.ERROR(f"  Invalid / Rejected Records       : {grand_summary.invalid_records}"))
        self.stdout.write(f"  Missing Coordinates              : {grand_summary.missing_coordinates}")
        self.stdout.write(f"  Execution Time                   : {round(grand_summary.duration_seconds, 3)} seconds\n")

        if grand_summary.records_by_state:
            self.stdout.write(self.style.HTTP_INFO("  Breakdown by State / Union Territory:"))
            for st, cnt in sorted(grand_summary.records_by_state.items(), key=lambda x: -x[1]):
                self.stdout.write(f"    - {st:<32}: {cnt} records")

        if grand_summary.duplicate_details:
            self.stdout.write(self.style.WARNING("\n  Duplicate Candidate Audit Warnings (Uncertain Matches Not Auto-Merged):"))
            for dup_msg in grand_summary.duplicate_details[:10]:
                self.stdout.write(self.style.WARNING(f"    [!] {dup_msg}"))
            if len(grand_summary.duplicate_details) > 10:
                self.stdout.write(f"    ... and {len(grand_summary.duplicate_details) - 10} more duplicate candidates")

        if grand_summary.rejection_details:
            self.stdout.write(self.style.ERROR("\n  Rejection / Error Details:"))
            for err_msg in grand_summary.rejection_details[:10]:
                self.stdout.write(self.style.ERROR(f"    [x] {err_msg}"))

        total_db = Pharmacy.objects.count()
        hosp_db = Pharmacy.objects.filter(provider_type=Pharmacy.ProviderType.HOSPITAL).count()
        pharm_db = Pharmacy.objects.filter(provider_type=Pharmacy.ProviderType.PHARMACY).count()
        approved_db = Pharmacy.objects.filter(is_approved=True).count()
        unapproved_db = Pharmacy.objects.filter(is_approved=False).count()
        demo_db = Pharmacy.objects.filter(is_demo=True).count()
        genuine_db = Pharmacy.objects.filter(is_demo=False).count()

        self.stdout.write("\n" + "-" * 80)
        self.stdout.write(self.style.SUCCESS("  DATABASE STATUS POST-PIPELINE:"))
        self.stdout.write(f"    Total Providers in DB          : {total_db}")
        self.stdout.write(f"    - Hospitals                    : {hosp_db}")
        self.stdout.write(f"    - Pharmacies                   : {pharm_db}")
        self.stdout.write(f"    - Genuine Records              : {genuine_db}")
        self.stdout.write(f"    - Demo Records (Preserved)     : {demo_db}")
        self.stdout.write(f"    - Verified / Approved          : {approved_db}")
        self.stdout.write(f"    - Directory / Pending Review   : {unapproved_db}")
        self.stdout.write("-" * 80 + "\n")
