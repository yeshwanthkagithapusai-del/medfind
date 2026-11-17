"""
MediFind Healthcare Ingestion Pipeline - Source-Specific Adapters
Provides adapters for National Hospital Directory (data.gov.in), OpenStreetMap (OSM),
ABDM Health Facility Registry, and generic tabular feeds.
"""

import csv
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, List, Union

logger = logging.getLogger('medfind')


class BaseProviderAdapter(ABC):
    """Abstract base class for all provider data source adapters."""

    @abstractmethod
    def parse(self, source_data: Union[str, List[Dict[str, Any]]]) -> Generator[Dict[str, Any], None, None]:
        """
        Parses source data (file path, raw JSON string, or record list)
        and yields standardized candidate record dictionaries.
        """
        pass


class DataGovInHospitalAdapter(BaseProviderAdapter):
    """
    Adapter for India National Hospital Directory feeds from data.gov.in / MoHFW.
    Supports CSV and JSON formats containing National Identification Numbers (NIN).
    """

    def parse(self, source_data: Union[str, List[Dict[str, Any]]]) -> Generator[Dict[str, Any], None, None]:
        records = []
        if isinstance(source_data, list):
            records = source_data
        elif isinstance(source_data, str):
            if source_data.endswith('.csv'):
                with open(source_data, mode='r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    records = list(reader)
            elif source_data.endswith('.json'):
                with open(source_data, mode='r', encoding='utf-8') as f:
                    data = json.load(f)
                    records = data if isinstance(data, list) else data.get('records', [])
            else:
                # Raw JSON string
                try:
                    data = json.loads(source_data)
                    records = data if isinstance(data, list) else data.get('records', [])
                except Exception:
                    records = []

        for row in records:
            # Flexible field extraction supporting official data.gov.in column names
            name = (
                row.get('Hospital_Name') or row.get('name') or
                row.get('Facility_Name') or row.get('facility_name') or ''
            )
            state = (
                row.get('State_Name') or row.get('state') or
                row.get('State') or ''
            )
            district = (
                row.get('District_Name') or row.get('district') or
                row.get('District') or ''
            )
            city = (
                row.get('City') or row.get('city') or
                row.get('Town') or district or ''
            )
            address = (
                row.get('Address') or row.get('address') or
                row.get('Full_Address') or f"{name}, {city}, {state}"
            )
            pincode = (
                row.get('Pincode') or row.get('pincode') or
                row.get('Pin_Code') or row.get('Postal_Code') or ''
            )
            lat = row.get('Latitude') or row.get('lat') or row.get('latitude')
            lng = row.get('Longitude') or row.get('long') or row.get('lng') or row.get('longitude')

            source_id = (
                row.get('NIN_Code') or row.get('source_id') or
                row.get('Hospital_ID') or row.get('id') or ''
            )
            phone = (
                row.get('Contact_Number') or row.get('phone') or
                row.get('Telephone') or row.get('phone_number') or ''
            )

            yield {
                'name': name,
                'provider_type': 'HOSPITAL',
                'source_name': 'DATA_GOV_IN',
                'source_id': str(source_id).strip(),
                'registration_number': f"NIN-{source_id}" if source_id else "",
                'address': address,
                'city': city,
                'district': district,
                'state': state,
                'pincode': str(pincode).strip(),
                'phone': phone,
                'lat': lat,
                'lng': lng,
            }


class OSMPharmacyAdapter(BaseProviderAdapter):
    """
    Adapter for OpenStreetMap (OSM) Overpass API JSON / GeoJSON / CSV exports
    with amenity=pharmacy tags.
    """

    def parse(self, source_data: Union[str, List[Dict[str, Any]]]) -> Generator[Dict[str, Any], None, None]:
        elements = []
        if isinstance(source_data, list):
            elements = source_data
        elif isinstance(source_data, str):
            if source_data.endswith('.json'):
                with open(source_data, mode='r', encoding='utf-8') as f:
                    data = json.load(f)
                    elements = data.get('elements', data if isinstance(data, list) else [])
            elif source_data.endswith('.csv'):
                with open(source_data, mode='r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    elements = list(reader)
            else:
                try:
                    data = json.loads(source_data)
                    elements = data.get('elements', data if isinstance(data, list) else [])
                except Exception:
                    elements = []

        for item in elements:
            # Overpass elements format has 'tags' nested dictionary
            tags = item.get('tags', {}) if isinstance(item, dict) else {}
            if not tags and isinstance(item, dict):
                # Fallback if flat dictionary
                tags = item

            name = tags.get('name') or item.get('name') or ''
            osm_id = item.get('id') or tags.get('osm_id') or ''
            osm_type = str(item.get('type') or 'node').upper()
            source_id = f"OSM-{osm_type}-{osm_id}" if osm_id else ""

            lat = item.get('lat') or tags.get('lat') or tags.get('latitude')
            lng = item.get('lon') or item.get('lng') or tags.get('lon') or tags.get('longitude')

            street = tags.get('addr:street') or tags.get('street') or ''
            city = tags.get('addr:city') or tags.get('city') or ''
            district = tags.get('addr:district') or tags.get('district') or city
            state = tags.get('addr:state') or tags.get('state') or ''
            pincode = tags.get('addr:postcode') or tags.get('pincode') or ''
            phone = tags.get('phone') or tags.get('contact:phone') or ''

            address = street
            if not address:
                address = f"{name}, {city}" if city else f"{name}, {state}"

            yield {
                'name': name,
                'provider_type': 'PHARMACY',
                'source_name': 'OSM',
                'source_id': source_id,
                'registration_number': source_id,
                'address': address,
                'city': city,
                'district': district,
                'state': state,
                'pincode': str(pincode).strip(),
                'phone': phone,
                'lat': lat,
                'lng': lng,
            }


class ABDMRegistryAdapter(BaseProviderAdapter):
    """
    Adapter for Ayushman Bharat Digital Mission (ABDM) Health Facility Registry (HFR)
    structured extracts.
    """

    def parse(self, source_data: Union[str, List[Dict[str, Any]]]) -> Generator[Dict[str, Any], None, None]:
        facilities = []
        if isinstance(source_data, list):
            facilities = source_data
        elif isinstance(source_data, str):
            if source_data.endswith('.json'):
                with open(source_data, mode='r', encoding='utf-8') as f:
                    data = json.load(f)
                    facilities = data if isinstance(data, list) else data.get('facilities', [])
            elif source_data.endswith('.csv'):
                with open(source_data, mode='r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    facilities = list(reader)

        for item in facilities:
            name = item.get('facilityName') or item.get('name') or ''
            hfr_id = item.get('hfrId') or item.get('facilityId') or item.get('source_id') or ''
            source_id = f"HFR-{hfr_id}" if hfr_id and not str(hfr_id).startswith('HFR-') else str(hfr_id)

            raw_type = str(item.get('facilityType') or item.get('provider_type') or 'HOSPITAL').upper()
            provider_type = 'PHARMACY' if 'PHARMACY' in raw_type or 'CHEMIST' in raw_type else 'HOSPITAL'

            yield {
                'name': name,
                'provider_type': provider_type,
                'source_name': 'ABDM',
                'source_id': source_id,
                'registration_number': source_id,
                'address': item.get('address') or f"{name}, {item.get('city', '')}",
                'city': item.get('city') or '',
                'district': item.get('district') or item.get('city') or '',
                'state': item.get('state') or '',
                'pincode': str(item.get('pincode') or '').strip(),
                'phone': item.get('contactNumber') or item.get('phone') or '',
                'lat': item.get('latitude') or item.get('lat'),
                'lng': item.get('longitude') or item.get('lng'),
            }
