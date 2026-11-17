import logging
import math
from typing import Any, Dict, List, Optional, Tuple
from django.core.paginator import EmptyPage, Page, PageNotAnInteger, Paginator
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from requests_app.models import Notification
from .models import Pharmacy

logger = logging.getLogger('medfind')


def is_valid_coordinate(lat: Any, lon: Any) -> bool:
    """
    Validates whether latitude and longitude are valid decimal degree geographic coordinates.
    Latitude must be between -90.0 and 90.0 degrees.
    Longitude must be between -180.0 and 180.0 degrees.
    Rejects None, empty strings, non-numeric values, NaN, and Inf.
    """
    if lat is None or lon is None:
        return False
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        return False
    if math.isnan(lat_f) or math.isnan(lon_f) or math.isinf(lat_f) or math.isinf(lon_f):
        return False
    return -90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0


def calculate_haversine_distance(lat1: Any, lon1: Any, lat2: Any, lon2: Any) -> Optional[float]:
    """
    Calculate the great circle distance between two geographic coordinates
    (in decimal degrees) using the standard Haversine formula:
        a = sin²(Δφ/2) + cos(φ1) * cos(φ2) * sin²(Δλ/2)
        c = 2 * atan2(√a, √(1-a))
        Distance = R * c
    Where R = 6371.0 km (Earth's volumetric mean radius).

    Returns:
        float: Distance in kilometers rounded to two decimal places,
               or None if coordinates are missing, non-numeric, or outside valid ranges.
    """
    if not is_valid_coordinate(lat1, lon1) or not is_valid_coordinate(lat2, lon2):
        return None

    lat1_f = float(lat1)
    lon1_f = float(lon1)
    lat2_f = float(lat2)
    lon2_f = float(lon2)

    # Earth's volumetric mean radius in kilometers
    R = 6371.0

    dlat = math.radians(lat2_f - lat1_f)
    dlon = math.radians(lon2_f - lon1_f)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1_f)) * math.cos(math.radians(lat2_f)) *
         math.sin(dlon / 2.0) ** 2)

    # Clamp 'a' to [0.0, 1.0] to guard against floating-point precision domain errors
    a = max(0.0, min(1.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    distance = R * c
    return round(distance, 2)


def build_external_directions_url(
    dest_lat: Any,
    dest_lng: Any,
    user_lat: Optional[Any] = None,
    user_lng: Optional[Any] = None,
    service: str = 'google'
) -> str:
    """
    Constructs an external navigation URL (Google Maps or OpenStreetMap)
    to provide legitimate routing directions without simulating or fabricating routes.
    Distinguishes cases where user origin coordinates are present vs absent.
    """
    if not is_valid_coordinate(dest_lat, dest_lng):
        return ''

    d_lat = float(dest_lat)
    d_lng = float(dest_lng)
    has_user = is_valid_coordinate(user_lat, user_lng)

    if service.lower() == 'osm':
        if has_user:
            u_lat = float(user_lat)
            u_lng = float(user_lng)
            return f"https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route={u_lat}%2C{u_lng}%3B{d_lat}%2C{d_lng}"
        return f"https://www.openstreetmap.org/?mlat={d_lat}&mlon={d_lng}#map=16/{d_lat}/{d_lng}"
    else:
        # Default: Google Maps Web & Mobile Intent
        if has_user:
            u_lat = float(user_lat)
            u_lng = float(user_lng)
            return f"https://www.google.com/maps/dir/?api=1&origin={u_lat},{u_lng}&destination={d_lat},{d_lng}&travelmode=driving"
        return f"https://www.google.com/maps/search/?api=1&query={d_lat},{d_lng}"


def get_pharmacy_filter_options() -> Tuple[List[str], List[str]]:
    """
    Backward-compatible helper retrieving distinct cities and pincodes.
    """
    cities, pincodes, _, _ = get_provider_filter_options_tuple()
    return cities, pincodes


def get_provider_filter_options_tuple() -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Retrieves distinct active cities, pincodes, states, and districts across all healthcare providers.
    """
    qs = Pharmacy.objects.filter(is_active=True)
    raw_cities = qs.order_by('city').values_list('city', flat=True).distinct()
    raw_pincodes = qs.order_by('pincode').values_list('pincode', flat=True).distinct()
    raw_states = qs.order_by('state').values_list('state', flat=True).distinct()
    raw_districts = qs.order_by('district').values_list('district', flat=True).distinct()

    cities = sorted(list({c.strip() for c in raw_cities if c and c.strip()}))
    pincodes = sorted(list({p.strip() for p in raw_pincodes if p and p.strip()}))
    states = sorted(list({s.strip() for s in raw_states if s and s.strip()}))
    districts = sorted(list({d.strip() for d in raw_districts if d and d.strip()}))

    return cities, pincodes, states, districts


def get_provider_filter_options() -> Dict[str, Any]:
    """
    Returns structured dictionary of filter choices for template rendering.
    """
    cities, pincodes, states, districts = get_provider_filter_options_tuple()
    return {
        'cities': cities,
        'pincodes': pincodes,
        'states': states,
        'districts': districts,
        'provider_types': [
            ('ALL', 'All Facilities (Hospitals & Pharmacies)'),
            ('HOSPITAL', 'Hospitals & Medical Centers'),
            ('PHARMACY', 'Pharmacies & Chemists'),
        ],
        'verification_options': [
            ('approved', 'Verified Partners Only'),
            ('all', 'All Providers (Include Directory Listings)'),
            ('pending', 'Pending Verification Only'),
        ],
        'availability_options': [
            ('all', 'All Facilities (Any Stock Status)'),
            ('in_stock', 'Pharmacies with Available Stock Only'),
        ],
        'radius_options': [
            ('', 'Any Distance'),
            ('5', 'Within 5 km'),
            ('10', 'Within 10 km'),
            ('15', 'Within 15 km'),
            ('25', 'Within 25 km'),
            ('50', 'Within 50 km'),
            ('100', 'Within 100 km'),
        ],
    }


def discover_healthcare_providers(
    user_lat: Optional[Any] = None,
    user_lng: Optional[Any] = None,
    radius_km: Optional[Any] = None,
    city: str = '',
    district: str = '',
    state: str = '',
    pincode: str = '',
    search_query: str = '',
    provider_type: str = 'ALL',
    verification_status: str = 'approved',
    only_approved: bool = False,
    availability: str = 'all',
    available_only: bool = False,
    sort_by: str = 'distance',
    page: int = 1,
    per_page: int = 9,
) -> Tuple[Page, bool, List[Dict[str, Any]], int, Optional[Dict[str, float]]]:
    """
    Unified healthcare provider geospatial discovery service.
    Supports hospital search, pharmacy search, combined search,
    inventory availability filtering, state/district/city/pincode filtering,
    Haversine distance sorting, radius threshold bounds, distinct Leaflet map pins,
    external directions routing URLs, and pagination.
    """
    from inventory.models import Inventory

    qs = Pharmacy.objects.filter(is_active=True)

    # 1. Provider Type Filter ('ALL', 'HOSPITAL', 'PHARMACY')
    raw_type = (provider_type or 'ALL').upper().strip()
    if raw_type in (Pharmacy.ProviderType.HOSPITAL, Pharmacy.ProviderType.PHARMACY):
        qs = qs.filter(provider_type=raw_type)

    # 2. Verification Status Filter
    # Strict compliance: only_approved=True overrides to strictly approved
    if only_approved or verification_status == 'approved':
        qs = qs.filter(is_approved=True)
    elif verification_status == 'pending':
        qs = qs.filter(is_approved=False)
    # else 'all' includes both approved and unapproved (each clearly badged)

    # 3. Medicine Inventory Availability Filter
    # Strict compliance: based strictly on current MediFind database inventory records
    active_stock_pharmacy_ids = set(
        Inventory.objects.filter(
            availability_status__in=['IN_STOCK', 'LOW_STOCK'],
            quantity__gt=0
        ).values_list('pharmacy_id', flat=True).distinct()
    )

    if available_only or availability == 'in_stock':
        qs = qs.filter(id__in=active_stock_pharmacy_ids, provider_type=Pharmacy.ProviderType.PHARMACY)

    # 4. Text Search Query
    if search_query:
        qs = qs.filter(
            Q(pharmacy_name__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(registration_number__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(district__icontains=search_query) |
            Q(state__icontains=search_query)
        )

    # 5. Administrative Hierarchy Filters
    if state:
        qs = qs.filter(state__icontains=state.strip())
    if district:
        qs = qs.filter(district__icontains=district.strip())
    if city:
        qs = qs.filter(city__icontains=city.strip())
    if pincode:
        qs = qs.filter(pincode__icontains=pincode.strip())

    providers_list: List[Pharmacy] = list(qs)

    # 6. Geolocation Proximity & Distance Sorting
    has_user_coords = is_valid_coordinate(user_lat, user_lng)
    user_coords_dict: Optional[Dict[str, float]] = None

    if has_user_coords:
        u_lat = float(user_lat)
        u_lng = float(user_lng)
        user_coords_dict = {'lat': u_lat, 'lng': u_lng}

        for p in providers_list:
            if is_valid_coordinate(p.latitude, p.longitude):
                p.distance_km = calculate_haversine_distance(
                    u_lat, u_lng, p.latitude, p.longitude
                )
            else:
                p.distance_km = None

        # Radius Cutoff Filter
        if radius_km not in (None, '', 'all'):
            try:
                max_radius = float(radius_km)
                if max_radius > 0:
                    providers_list = [
                        p for p in providers_list
                        if p.distance_km is not None and p.distance_km <= max_radius
                    ]
            except (ValueError, TypeError):
                pass

        # Sort Order
        if sort_by == 'distance' or not sort_by:
            providers_list.sort(
                key=lambda p: (
                    p.distance_km is None,
                    p.distance_km if p.distance_km is not None else float('inf'),
                    p.pharmacy_name
                )
            )
        elif sort_by == 'name':
            providers_list.sort(key=lambda p: p.pharmacy_name.lower())
        else:
            providers_list.sort(key=lambda p: p.created_at, reverse=True)
    else:
        for p in providers_list:
            p.distance_km = None
        if sort_by == 'name':
            providers_list.sort(key=lambda p: p.pharmacy_name.lower())
        else:
            providers_list.sort(key=lambda p: p.created_at, reverse=True)

    # Attach inventory availability & external directions URLs to provider models
    for p in providers_list:
        p.has_active_inventory = (p.id in active_stock_pharmacy_ids)
        p.directions_url_google = build_external_directions_url(
            p.latitude, p.longitude, user_lat, user_lng, 'google'
        )
        p.directions_url_osm = build_external_directions_url(
            p.latitude, p.longitude, user_lat, user_lng, 'osm'
        )

    # 7. Prepare Distinct Map Pins for Leaflet.js
    map_pins: List[Dict[str, Any]] = []
    for p in providers_list:
        if is_valid_coordinate(p.latitude, p.longitude):
            is_hospital = p.provider_type == Pharmacy.ProviderType.HOSPITAL
            map_pins.append({
                'id': p.id,
                'name': p.pharmacy_name,
                'provider_type': p.provider_type,
                'icon_type': 'hospital' if is_hospital else 'pharmacy',
                'address': f"{p.address}, {p.city} - {p.pincode}",
                'district': p.district or p.city,
                'state': p.state,
                'phone': p.phone_number,
                'lat': float(p.latitude),
                'lng': float(p.longitude),
                'distance_km': getattr(p, 'distance_km', None),
                'is_approved': p.is_approved,
                'source_name': p.source_name,
                'source_display': p.get_source_name_display(),
                'is_demo': p.is_demo,
                'has_active_inventory': (p.id in active_stock_pharmacy_ids),
                'verification_label': 'Verified Partner' if p.is_approved else 'Directory Listing',
                'directions_url_google': build_external_directions_url(
                    p.latitude, p.longitude, user_lat, user_lng, 'google'
                ),
                'directions_url_osm': build_external_directions_url(
                    p.latitude, p.longitude, user_lat, user_lng, 'osm'
                ),
            })

    total_results = len(providers_list)

    # 7. Paginate Results
    paginator = Paginator(providers_list, per_page)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    logger.info(
        "Provider discovery executed: type='%s', verification='%s', query='%s', state='%s', city='%s', pincode='%s', radius='%s', results=%d",
        raw_type, verification_status, search_query, state, city, pincode, radius_km, total_results
    )

    return page_obj, has_user_coords, map_pins, total_results, user_coords_dict


def discover_nearby_pharmacies(
    user_lat: Optional[Any] = None,
    user_lng: Optional[Any] = None,
    radius_km: Optional[Any] = None,
    city: str = '',
    pincode: str = '',
    search_query: str = '',
    sort_by: str = 'distance',
    only_approved: bool = True,
    page: int = 1,
    per_page: int = 10,
    **kwargs: Any
) -> Tuple[Page, bool, List[Dict[str, Any]], int, Optional[Dict[str, float]]]:
    """
    Backward-compatible discovery interface specifically targeting retail pharmacies.
    """
    provider_type = kwargs.get('provider_type', Pharmacy.ProviderType.PHARMACY)
    verification_status = kwargs.get('verification_status', 'approved' if only_approved else 'all')
    state = kwargs.get('state', '')
    district = kwargs.get('district', '')

    return discover_healthcare_providers(
        user_lat=user_lat,
        user_lng=user_lng,
        radius_km=radius_km,
        city=city,
        district=district,
        state=state,
        pincode=pincode,
        search_query=search_query,
        provider_type=provider_type,
        verification_status=verification_status,
        only_approved=only_approved,
        sort_by=sort_by,
        page=page,
        per_page=per_page,
    )


def get_pharmacy_for_user(user) -> Optional[Pharmacy]:
    """
    Retrieves the Pharmacy entity associated with an authenticated user.
    """
    if not user.is_authenticated:
        return None
    return Pharmacy.objects.filter(owner=user).first()


def toggle_pharmacy_approval(pharmacy_id: int, admin_user) -> Tuple[Pharmacy, bool, str]:
    """
    Toggles the approval status of a healthcare facility and dispatches an audit notification if an owner exists.
    """
    pharmacy = get_object_or_404(Pharmacy.objects.select_related('owner'), pk=pharmacy_id)
    pharmacy.is_approved = not pharmacy.is_approved
    pharmacy.save(update_fields=['is_approved'])

    status_str = "Approved" if pharmacy.is_approved else "Revoked Approval"

    if pharmacy.owner:
        Notification.objects.create(
            user=pharmacy.owner,
            message=f"Your facility '{pharmacy.pharmacy_name}' has been {status_str.lower()} by the MediFind Administrator."
        )

    logger.info(
        "Provider approval status updated: '%s' (id=%d) -> %s by admin '%s'",
        pharmacy.pharmacy_name, pharmacy.id, status_str, admin_user.username
    )
    return pharmacy, pharmacy.is_approved, status_str


def get_pharmacy_detail_data(pharmacy_id: int, user) -> Tuple[Optional[Pharmacy], Optional[QuerySet], Optional[Dict[str, Any]], bool]:
    """
    Retrieves provider profile, inventory records, and map pin.
    Enforces privacy rules:
    - Hospitals are public healthcare institutions: public view is authorized.
    - Approved pharmacies are public: public view is authorized.
    - Unapproved pharmacies with a registered owner account are restricted to owner or admins.
    - Public directory unapproved facilities are viewable with unverified badge.
    """
    from inventory.models import Inventory
    pharmacy = get_object_or_404(Pharmacy.objects.select_related('owner'), pk=pharmacy_id)

    is_hospital = pharmacy.provider_type == Pharmacy.ProviderType.HOSPITAL
    is_owner_or_admin = user.is_authenticated and (user == pharmacy.owner or getattr(user, 'is_admin_user', False))

    if not is_hospital and not pharmacy.is_approved and not is_owner_or_admin and pharmacy.owner is not None:
        return pharmacy, None, None, False

    inventory_items = Inventory.objects.filter(pharmacy=pharmacy).select_related('medicine').order_by('-updated_at')

    map_pin = None
    if pharmacy.latitude and pharmacy.longitude:
        google_url = build_external_directions_url(pharmacy.latitude, pharmacy.longitude, service='google')
        osm_url = build_external_directions_url(pharmacy.latitude, pharmacy.longitude, service='osm')
        pharmacy.directions_url_google = google_url
        pharmacy.directions_url_osm = osm_url
        map_pin = {
            'id': pharmacy.id,
            'name': pharmacy.pharmacy_name,
            'provider_type': pharmacy.provider_type,
            'icon_type': 'hospital' if is_hospital else 'pharmacy',
            'address': f"{pharmacy.address}, {pharmacy.city}",
            'district': pharmacy.district or pharmacy.city,
            'state': pharmacy.state,
            'phone': pharmacy.phone_number,
            'lat': float(pharmacy.latitude),
            'lng': float(pharmacy.longitude),
            'is_approved': pharmacy.is_approved,
            'source_name': pharmacy.source_name,
            'source_display': pharmacy.get_source_name_display(),
            'directions_url_google': google_url,
            'directions_url_osm': osm_url,
        }

    return pharmacy, inventory_items, map_pin, True
