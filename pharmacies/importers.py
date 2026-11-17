"""
MediFind Healthcare Provider Data Ingestion & Validation Module
Stage 2: Real Healthcare Data Integration (Pilot Pipeline)
"""

import logging
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import Pharmacy

logger = logging.getLogger('medfind')

# Sovereign Geographic Boundaries of India (WGS84 Bounding Box)
INDIA_LAT_MIN = 6.500000
INDIA_LAT_MAX = 37.500000
INDIA_LNG_MIN = 68.000000
INDIA_LNG_MAX = 97.500000


def validate_indian_coordinates(lat: Any, lng: Any) -> Tuple[bool, Optional[Decimal], Optional[Decimal], str]:
    """
    Validates that latitude and longitude are valid numeric coordinates located
    strictly within the sovereign geographic boundaries of India.
    Detects and corrects transposed latitude/longitude pairs.

    Returns:
        (is_valid, validated_lat, validated_lng, message)
    """
    if lat is None or lng is None:
        return False, None, None, "Coordinates missing or None"

    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (ValueError, TypeError):
        return False, None, None, f"Non-numeric coordinates: lat='{lat}', lng='{lng}'"

    if math.isnan(lat_f) or math.isnan(lng_f) or math.isinf(lat_f) or math.isinf(lng_f):
        return False, None, None, "Coordinates are NaN or infinite"

    # Transposition check: if Lng is in India Lat range and Lat is in India Lng range
    if (INDIA_LAT_MIN <= lng_f <= INDIA_LAT_MAX) and (INDIA_LNG_MIN <= lat_f <= INDIA_LNG_MAX):
        logger.warning("Detected transposed coordinates: lat=%f, lng=%f. Swapping to correct.", lat_f, lng_f)
        lat_f, lng_f = lng_f, lat_f

    # Strict territorial boundary check
    if not (INDIA_LAT_MIN <= lat_f <= INDIA_LAT_MAX):
        return False, None, None, f"Latitude {lat_f:.6f} outside India boundary [{INDIA_LAT_MIN}, {INDIA_LAT_MAX}]"

    if not (INDIA_LNG_MIN <= lng_f <= INDIA_LNG_MAX):
        return False, None, None, f"Longitude {lng_f:.6f} outside India boundary [{INDIA_LNG_MIN}, {INDIA_LNG_MAX}]"

    dec_lat = Decimal(str(round(lat_f, 6)))
    dec_lng = Decimal(str(round(lng_f, 6)))
    return True, dec_lat, dec_lng, "Coordinates valid within India"


def clean_indian_pincode(val: Any) -> str:
    """
    Normalizes Indian postal pincodes to exactly 6 digits.
    Indian pincodes cannot start with 0.
    """
    digits = re.sub(r'\D', '', str(val or ''))
    if len(digits) == 6 and digits[0] != '0':
        return digits
    return ''


def validate_provider_payload(data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates a provider record dictionary prior to database persistence.
    Checks name, address, pincode, coordinates, provider_type, and source_name.
    """
    name = str(data.get('name') or data.get('pharmacy_name') or '').strip()
    if not name or len(name) < 3:
        return False, "Provider name must be at least 3 characters long", {}

    address = str(data.get('address') or '').strip()
    if not address or len(address) < 5:
        return False, "Street address must be at least 5 characters long", {}

    city = str(data.get('city') or '').strip()
    if not city:
        return False, "City is mandatory", {}

    state = str(data.get('state') or '').strip()
    if not state:
        return False, "State is mandatory", {}

    district = str(data.get('district') or '').strip()
    if not district:
        district = city

    pincode = clean_indian_pincode(data.get('pincode'))
    if not pincode:
        return False, f"Invalid 6-digit Indian postal pincode: '{data.get('pincode')}'", {}

    lat = data.get('lat', data.get('latitude'))
    lng = data.get('lng', data.get('longitude'))
    is_valid_coords, dec_lat, dec_lng, coord_msg = validate_indian_coordinates(lat, lng)
    if not is_valid_coords:
        return False, f"Coordinate validation failed: {coord_msg}", {}

    raw_type = str(data.get('provider_type') or 'PHARMACY').upper()
    if raw_type not in (Pharmacy.ProviderType.PHARMACY, Pharmacy.ProviderType.HOSPITAL):
        return False, f"Invalid provider_type: '{raw_type}'", {}

    raw_source = str(data.get('source_name') or 'MANUAL').upper()
    valid_sources = {s.value for s in Pharmacy.DataSource}
    if raw_source not in valid_sources:
        return False, f"Invalid source_name: '{raw_source}'. Allowed: {valid_sources}", {}

    source_id = str(data.get('source_id') or '').strip()
    reg_number = str(data.get('registration_number') or '').strip()
    if not reg_number:
        if source_id:
            reg_number = f"{raw_source}-{source_id}"
        else:
            return False, "Either registration_number or source_id is required", {}

    phone = str(data.get('phone_number') or data.get('phone') or '').strip()

    cleaned_payload = {
        'pharmacy_name': name,
        'provider_type': raw_type,
        'registration_number': reg_number,
        'address': address,
        'city': city,
        'district': district,
        'state': state,
        'pincode': pincode,
        'phone_number': phone,
        'latitude': dec_lat,
        'longitude': dec_lng,
        'source_name': raw_source,
        'source_id': source_id,
        'is_approved': False,  # Strict: Unverified imported records are NOT published as verified automatically
        'is_active': True,
        'is_demo': False,
        'last_verified_at': None,
    }
    return True, "Valid", cleaned_payload


@dataclass
class ImportReport:
    total_scanned: int = 0
    imported: int = 0
    skipped_duplicate: int = 0
    rejected_invalid: int = 0
    details: List[str] = field(default_factory=list)


def import_provider_records(records: List[Dict[str, Any]], dry_run: bool = False) -> ImportReport:
    """
    Safely ingests a list of provider records with strict validation,
    idempotent deduplication against source_id and registration_number,
    and detailed audit logging.
    """
    report = ImportReport(total_scanned=len(records))

    for idx, item in enumerate(records, start=1):
        is_valid, msg, cleaned = validate_provider_payload(item)
        item_title = item.get('name') or item.get('pharmacy_name') or f"Record #{idx}"

        if not is_valid:
            report.rejected_invalid += 1
            report.details.append(f"REJECTED #{idx} '{item_title}': {msg}")
            logger.warning("Provider record rejected [%s]: %s", item_title, msg)
            continue

        # Check for existing duplicate by source identifier
        source_name = cleaned['source_name']
        source_id = cleaned['source_id']
        reg_number = cleaned['registration_number']

        existing = None
        if source_id:
            existing = Pharmacy.objects.filter(source_name=source_name, source_id=source_id).first()
        if not existing:
            existing = Pharmacy.objects.filter(registration_number=reg_number).first()

        if existing:
            report.skipped_duplicate += 1
            report.details.append(f"SKIPPED #{idx} '{item_title}': Duplicate of existing ID {existing.id} (source={source_name}, id={source_id or reg_number})")
            logger.info("Provider record skipped (duplicate) [%s]: existing ID %d", item_title, existing.id)
            continue

        if not dry_run:
            try:
                with transaction.atomic():
                    Pharmacy.objects.create(**cleaned)
                report.imported += 1
                report.details.append(f"IMPORTED #{idx} '{item_title}' ({cleaned['provider_type']}, {cleaned['city']}, {cleaned['state']})")
                logger.info("Provider record successfully imported: '%s' (type=%s, city=%s)", item_title, cleaned['provider_type'], cleaned['city'])
            except IntegrityError as e:
                report.rejected_invalid += 1
                report.details.append(f"REJECTED #{idx} '{item_title}': DB IntegrityError: {str(e)}")
                logger.error("IntegrityError importing provider [%s]: %s", item_title, e)
        else:
            report.imported += 1
            report.details.append(f"DRY-RUN WOULD IMPORT #{idx} '{item_title}' ({cleaned['provider_type']}, {cleaned['city']})")

    return report
