"""
MediFind Healthcare Ingestion Pipeline Package
"""

from .adapters import (
    ABDMRegistryAdapter,
    BaseProviderAdapter,
    DataGovInHospitalAdapter,
    OSMPharmacyAdapter,
)
from .deduplication import DuplicateMatchResult, find_duplicate
from .engine import BulkIngestionEngine, BulkIngestionSummary
from .normalization import (
    clean_indian_pincode,
    normalize_indian_state,
    normalize_phone_number,
    sanitize_text,
)
from .validation import (
    INDIA_LAT_MAX,
    INDIA_LAT_MIN,
    INDIA_LNG_MAX,
    INDIA_LNG_MIN,
    validate_indian_coordinates,
    validate_provider_record,
)

__all__ = [
    'BaseProviderAdapter',
    'DataGovInHospitalAdapter',
    'OSMPharmacyAdapter',
    'ABDMRegistryAdapter',
    'BulkIngestionEngine',
    'BulkIngestionSummary',
    'find_duplicate',
    'DuplicateMatchResult',
    'normalize_indian_state',
    'clean_indian_pincode',
    'normalize_phone_number',
    'sanitize_text',
    'validate_indian_coordinates',
    'validate_provider_record',
    'INDIA_LAT_MIN',
    'INDIA_LAT_MAX',
    'INDIA_LNG_MIN',
    'INDIA_LNG_MAX',
]
