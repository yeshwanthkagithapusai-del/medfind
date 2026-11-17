"""
MediFind Healthcare Ingestion Pipeline - Validation Module
Enforces territorial coordinate constraints, schema validity, and clinical invariants.
"""

import logging
import math
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple
from pharmacies.models import Pharmacy
from .normalization import (
    clean_indian_pincode,
    normalize_indian_state,
    normalize_phone_number,
    sanitize_text,
)

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

    # Reject null island / zero coordinates
    if abs(lat_f) < 0.0001 and abs(lng_f) < 0.0001:
        return False, None, None, "Coordinates are at zero (0, 0) - Null Island rejected"

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


def validate_provider_record(data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates and standardizes a healthcare provider payload before database entry.
    Enforces required fields, state canonicalization, 6-digit postal code,
    India boundary coordinates, and data hygiene invariants.
    """
    raw_name = data.get('name') or data.get('pharmacy_name') or ''
    name = sanitize_text(raw_name, max_length=200)
    if not name or len(name) < 3:
        return False, "Provider name must be at least 3 characters long", {}

    raw_addr = data.get('address') or ''
    address = sanitize_text(raw_addr)
    if not address or len(address) < 5:
        return False, "Street address must be at least 5 characters long", {}

    city = sanitize_text(data.get('city') or '', max_length=100)
    if not city:
        return False, "City is mandatory", {}

    raw_state = data.get('state') or ''
    state = normalize_indian_state(raw_state)
    if not state:
        return False, "State / Union Territory is mandatory", {}

    district = sanitize_text(data.get('district') or '', max_length=100)
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

    source_id = sanitize_text(data.get('source_id') or '', max_length=100)
    reg_number = sanitize_text(data.get('registration_number') or '', max_length=100)
    if not reg_number:
        if source_id:
            reg_number = f"{raw_source}-{source_id}"
        else:
            return False, "Either registration_number or source_id is required", {}

    phone = normalize_phone_number(data.get('phone_number') or data.get('phone') or '')

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
        'is_approved': False,  # Strict invariant: Unverified imported records are NEVER published as verified automatically
        'is_active': True,
        'is_demo': False,      # Genuine imported records are not demo records
        'last_verified_at': None,
    }
    return True, "Valid", cleaned_payload
