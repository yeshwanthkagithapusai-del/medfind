"""
MediFind Healthcare Ingestion Pipeline - Core Execution Engine
Orchestrates batch ingestion, duplicate detection, atomic transactions,
dry-run preview, and clinical audit reporting.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Iterable, List, Optional
from django.db import IntegrityError, transaction
from pharmacies.models import Pharmacy
from .deduplication import find_duplicate
from .validation import validate_provider_record

logger = logging.getLogger('medfind')


@dataclass
class BulkIngestionSummary:
    total_scanned: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    missing_coordinates: int = 0
    skipped_duplicate: int = 0
    duplicate_candidates: int = 0
    imported: int = 0
    hospitals_imported: int = 0
    pharmacies_imported: int = 0
    records_by_state: Dict[str, int] = field(default_factory=dict)
    records_by_district: Dict[str, int] = field(default_factory=dict)
    records_by_source: Dict[str, int] = field(default_factory=dict)
    details: List[str] = field(default_factory=list)
    duplicate_details: List[str] = field(default_factory=list)
    rejection_details: List[str] = field(default_factory=list)
    dry_run: bool = False
    duration_seconds: float = 0.0


class BulkIngestionEngine:
    """
    Production-grade bulk ingestion engine for nationwide healthcare provider records.
    Guarantees idempotency, transaction safety, and clinical verification boundaries.
    """

    def __init__(self, batch_size: int = 50, dry_run: bool = False):
        self.batch_size = batch_size
        self.dry_run = dry_run

    def execute(
        self,
        records: Iterable[Dict[str, Any]],
        state_filter: Optional[str] = None,
        limit: Optional[int] = None
    ) -> BulkIngestionSummary:
        """
        Executes ingestion over a stream of raw records with atomic batching.
        """
        start_time = time.time()
        summary = BulkIngestionSummary(dry_run=self.dry_run)

        current_batch: List[Dict[str, Any]] = []

        for idx, raw_record in enumerate(records, start=1):
            if limit and summary.imported >= limit:
                break

            summary.total_scanned += 1
            raw_title = raw_record.get('name') or raw_record.get('pharmacy_name') or f"Record #{idx}"

            # Check for missing coordinates before full validation
            lat = raw_record.get('lat') or raw_record.get('latitude')
            lng = raw_record.get('lng') or raw_record.get('longitude')
            if lat is None or lng is None or str(lat).strip() == '' or str(lng).strip() == '':
                summary.missing_coordinates += 1
                summary.invalid_records += 1
                msg = f"REJECTED #{idx} '{raw_title}': Missing latitude or longitude coordinates"
                summary.rejection_details.append(msg)
                logger.warning(msg)
                continue

            # Validate schema and territorial constraints
            is_valid, val_msg, cleaned = validate_provider_record(raw_record)
            if not is_valid:
                summary.invalid_records += 1
                msg = f"REJECTED #{idx} '{raw_title}': {val_msg}"
                summary.rejection_details.append(msg)
                logger.warning(msg)
                continue

            summary.valid_records += 1

            # Optional State Filter
            if state_filter and cleaned['state'].lower() != state_filter.lower():
                continue

            # Multi-tier Duplicate Detection
            dup_result = find_duplicate(cleaned)
            if dup_result.is_duplicate:
                if dup_result.match_type in ('EXACT_SOURCE_ID', 'EXACT_REG_NUM'):
                    summary.skipped_duplicate += 1
                    msg = f"SKIPPED #{idx} '{raw_title}': {dup_result.explanation}"
                    summary.details.append(msg)
                    logger.info(msg)
                    continue
                else:
                    # Geospatial or Normalized Name Duplicate Candidate
                    summary.duplicate_candidates += 1
                    msg = f"DUPLICATE CANDIDATE #{idx} '{raw_title}': {dup_result.explanation}"
                    summary.duplicate_details.append(msg)
                    logger.warning(msg)
                    # Safe invariant: Never automatically merge or overwrite uncertain records
                    continue

            # Record is eligible for ingestion
            current_batch.append(cleaned)

            if len(current_batch) >= self.batch_size:
                self._commit_batch(current_batch, summary)
                current_batch = []

        # Flush remaining batch
        if current_batch:
            self._commit_batch(current_batch, summary)

        summary.duration_seconds = round(time.time() - start_time, 3)
        return summary

    def _commit_batch(self, batch: List[Dict[str, Any]], summary: BulkIngestionSummary):
        """Commits a validated batch within an atomic database transaction."""
        if not batch:
            return

        if self.dry_run:
            for item in batch:
                summary.imported += 1
                self._record_metrics(item, summary)
                summary.details.append(
                    f"DRY-RUN WOULD IMPORT '{item['pharmacy_name']}' ({item['provider_type']}, {item['city']}, {item['state']})"
                )
            return

        try:
            with transaction.atomic():
                for item in batch:
                    Pharmacy.objects.create(**item)
                    summary.imported += 1
                    self._record_metrics(item, summary)
                    summary.details.append(
                        f"IMPORTED '{item['pharmacy_name']}' ({item['provider_type']}, {item['city']}, {item['state']})"
                    )
            logger.info("Committed batch of %d provider records successfully", len(batch))
        except IntegrityError as e:
            logger.error("Batch insertion failed due to IntegrityError: %s. Rolling back batch.", e)
            summary.invalid_records += len(batch)
            summary.rejection_details.append(f"BATCH INTEGRITY ERROR: {str(e)}")

    def _record_metrics(self, item: Dict[str, Any], summary: BulkIngestionSummary):
        """Aggregates metrics by state, district, provider type, and source."""
        st = item.get('state', 'Unknown')
        dist = item.get('district') or item.get('city') or 'Unknown'
        src = item.get('source_name', 'Unknown')
        ptype = item.get('provider_type', 'PHARMACY')

        summary.records_by_state[st] = summary.records_by_state.get(st, 0) + 1
        summary.records_by_district[dist] = summary.records_by_district.get(dist, 0) + 1
        summary.records_by_source[src] = summary.records_by_source.get(src, 0) + 1

        if ptype == 'HOSPITAL':
            summary.hospitals_imported += 1
        else:
            summary.pharmacies_imported += 1
