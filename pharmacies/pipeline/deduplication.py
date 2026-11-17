"""
MediFind Healthcare Ingestion Pipeline - Duplicate Detection Engine
Implements multi-tier matching: exact source-ID, registration number,
normalized name matching, and geospatial proximity checks.
"""

import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from pharmacies.models import Pharmacy
from pharmacies.services import calculate_haversine_distance

logger = logging.getLogger('medfind')


@dataclass
class DuplicateMatchResult:
    is_duplicate: bool
    match_type: str  # 'EXACT_SOURCE_ID', 'EXACT_REG_NUM', 'GEOSPATIAL_PROXIMITY', 'EXACT_NAME_CITY', 'NONE'
    existing_provider: Optional[Pharmacy] = None
    similarity_score: float = 0.0
    distance_meters: Optional[float] = None
    explanation: str = ""


def _normalize_name_tokens(name: str) -> set:
    """Helper to extract clean alphanumeric tokens for name comparison."""
    cleaned = re.sub(r'[^\w\s]', ' ', name.lower())
    tokens = set(cleaned.split())
    # Remove common stopwords in healthcare names
    stopwords = {'hospital', 'pharmacy', 'chemist', 'druggist', 'medical', 'store', 'center', 'centre', 'clinic', 'ltd', 'pvt'}
    informative_tokens = tokens - stopwords
    return informative_tokens if informative_tokens else tokens


def compute_token_similarity(name1: str, name2: str) -> float:
    """Computes Jaccard token similarity between two provider names."""
    tokens1 = _normalize_name_tokens(name1)
    tokens2 = _normalize_name_tokens(name2)
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)


def find_duplicate(payload: Dict[str, Any], proximity_radius_meters: float = 100.0) -> DuplicateMatchResult:
    """
    Evaluates a candidate provider payload against the database.
    Checks:
      Tier 1: Exact Source Identifier (source_name + source_id)
      Tier 2: Exact Registration Number (registration_number)
      Tier 3: Geospatial Proximity (< 100m) + Significant Name Similarity (> 75%)
      Tier 4: Exact Normalized Name + Same City & State

    Returns DuplicateMatchResult with explanation.
    """
    source_name = payload.get('source_name', '')
    source_id = payload.get('source_id', '')
    reg_number = payload.get('registration_number', '')
    name = payload.get('pharmacy_name', '')
    city = payload.get('city', '')
    state = payload.get('state', '')
    lat = payload.get('latitude')
    lng = payload.get('longitude')

    # Tier 1: Exact Source Identifier
    if source_id and source_name:
        existing = Pharmacy.objects.filter(source_name=source_name, source_id=source_id).first()
        if existing:
            return DuplicateMatchResult(
                is_duplicate=True,
                match_type='EXACT_SOURCE_ID',
                existing_provider=existing,
                similarity_score=1.0,
                explanation=f"Exact match on source identifier: source={source_name}, id={source_id} (existing ID #{existing.id})"
            )

    # Tier 2: Exact Registration Number
    if reg_number:
        existing = Pharmacy.objects.filter(registration_number=reg_number).first()
        if existing:
            return DuplicateMatchResult(
                is_duplicate=True,
                match_type='EXACT_REG_NUM',
                existing_provider=existing,
                similarity_score=1.0,
                explanation=f"Exact match on registration number: '{reg_number}' (existing ID #{existing.id})"
            )

    # Tier 3: Geospatial Proximity + Name Similarity
    if lat is not None and lng is not None:
        try:
            lat_f = float(lat)
            lng_f = float(lng)
            # Rough bounding box window (~0.002 degrees ~ 220 meters)
            window = 0.0025
            nearby_candidates = Pharmacy.objects.filter(
                latitude__range=(Decimal(str(lat_f - window)), Decimal(str(lat_f + window))),
                longitude__range=(Decimal(str(lng_f - window)), Decimal(str(lng_f + window))),
            )

            for cand in nearby_candidates:
                dist_km = calculate_haversine_distance(lat_f, lng_f, float(cand.latitude), float(cand.longitude))
                dist_m = dist_km * 1000.0

                if dist_m <= proximity_radius_meters:
                    sim = compute_token_similarity(name, cand.pharmacy_name)
                    # High similarity within 100 meters
                    if sim >= 0.70 or name.lower() == cand.pharmacy_name.lower():
                        return DuplicateMatchResult(
                            is_duplicate=True,
                            match_type='GEOSPATIAL_PROXIMITY',
                            existing_provider=cand,
                            similarity_score=round(sim, 2),
                            distance_meters=round(dist_m, 1),
                            explanation=(
                                f"Geospatial duplicate candidate within {round(dist_m, 1)}m of existing ID #{cand.id} "
                                f"('{cand.pharmacy_name}') with name similarity {round(sim * 100, 1)}%"
                            )
                        )
        except Exception as e:
            logger.debug("Proximity check failed: %s", e)

    # Tier 4: Exact Name + City + State Match
    if name and city and state:
        existing = Pharmacy.objects.filter(
            pharmacy_name__iexact=name,
            city__iexact=city,
            state__iexact=state
        ).first()
        if existing:
            return DuplicateMatchResult(
                is_duplicate=True,
                match_type='EXACT_NAME_CITY',
                existing_provider=existing,
                similarity_score=1.0,
                explanation=f"Exact name, city, and state match with existing ID #{existing.id} ('{existing.pharmacy_name}', {existing.city})"
            )

    return DuplicateMatchResult(
        is_duplicate=False,
        match_type='NONE',
        existing_provider=None,
        similarity_score=0.0,
        explanation="Unique record; no duplicates detected"
    )
