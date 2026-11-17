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


def get_pharmacy_filter_options() -> Tuple[List[str], List[str]]:
    """
    Retrieves distinct approved pharmacy cities and pincodes for search filters.
    """
    approved = Pharmacy.objects.filter(is_approved=True)
    raw_cities = approved.order_by('city').values_list('city', flat=True).distinct()
    raw_pincodes = approved.order_by('pincode').values_list('pincode', flat=True).distinct()
    cities = sorted(list({c.strip() for c in raw_cities if c and c.strip()}))
    pincodes = sorted(list({p.strip() for p in raw_pincodes if p and p.strip()}))
    return cities, pincodes


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
) -> Tuple[Page, bool, List[Dict[str, Any]], int, Optional[Dict[str, float]]]:
    """
    Discovers approved pharmacies with distance calculations, radius filtering,
    manual city/pincode criteria, and Leaflet map pin metadata.
    """
    # Base queryset: strictly enforce approved pharmacies in public discovery
    # Note: select_related('owner') omitted here to prevent unnecessary JOINs on public queries
    qs = Pharmacy.objects.all()
    if only_approved:
        qs = qs.filter(is_approved=True)

    if search_query:
        qs = qs.filter(
            Q(pharmacy_name__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(registration_number__icontains=search_query)
        )

    if city:
        qs = qs.filter(city__icontains=city.strip())

    if pincode:
        qs = qs.filter(pincode__icontains=pincode.strip())

    pharmacies_list: List[Pharmacy] = list(qs)

    has_user_coords = is_valid_coordinate(user_lat, user_lng)
    user_coords_dict: Optional[Dict[str, float]] = None

    if has_user_coords:
        u_lat = float(user_lat)
        u_lng = float(user_lng)
        user_coords_dict = {'lat': u_lat, 'lng': u_lng}

        for p in pharmacies_list:
            if is_valid_coordinate(p.latitude, p.longitude):
                p.distance_km = calculate_haversine_distance(
                    u_lat, u_lng, p.latitude, p.longitude
                )
            else:
                p.distance_km = None

        # Filter by radius if provided and valid
        if radius_km not in (None, '', 'all'):
            try:
                max_radius = float(radius_km)
                if max_radius > 0:
                    pharmacies_list = [
                        p for p in pharmacies_list
                        if p.distance_km is not None and p.distance_km <= max_radius
                    ]
            except (ValueError, TypeError):
                pass

        # Sort by nearest distance first
        if sort_by == 'distance' or not sort_by:
            pharmacies_list.sort(
                key=lambda p: (
                    p.distance_km is None,
                    p.distance_km if p.distance_km is not None else float('inf'),
                    p.pharmacy_name
                )
            )
        elif sort_by == 'name':
            pharmacies_list.sort(key=lambda p: p.pharmacy_name.lower())
        else:
            pharmacies_list.sort(key=lambda p: p.created_at, reverse=True)
    else:
        for p in pharmacies_list:
            p.distance_km = None
        if sort_by == 'name':
            pharmacies_list.sort(key=lambda p: p.pharmacy_name.lower())
        else:
            pharmacies_list.sort(key=lambda p: p.created_at, reverse=True)

    # Prepare map pins for Leaflet.js
    map_pins: List[Dict[str, Any]] = []
    for p in pharmacies_list:
        if is_valid_coordinate(p.latitude, p.longitude):
            map_pins.append({
                'id': p.id,
                'name': p.pharmacy_name,
                'address': f"{p.address}, {p.city} - {p.pincode}",
                'phone': p.phone_number,
                'lat': float(p.latitude),
                'lng': float(p.longitude),
                'distance_km': getattr(p, 'distance_km', None),
                'is_approved': p.is_approved,
            })

    total_results = len(pharmacies_list)

    # Paginate results
    paginator = Paginator(pharmacies_list, per_page)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    logger.info(
        "Pharmacy discovery executed: query='%s', city='%s', pincode='%s', radius='%s', results=%d",
        search_query, city, pincode, radius_km, total_results
    )

    return page_obj, has_user_coords, map_pins, total_results, user_coords_dict


def get_pharmacy_for_user(user) -> Optional[Pharmacy]:
    """
    Retrieves the Pharmacy entity associated with an authenticated user.
    """
    if not user.is_authenticated:
        return None
    return Pharmacy.objects.filter(owner=user).first()


def toggle_pharmacy_approval(pharmacy_id: int, admin_user) -> Tuple[Pharmacy, bool, str]:
    """
    Toggles the approval status of a pharmacy facility and dispatches an audit notification.
    Uses select_related('owner') to avoid an N+1 query when dispatching owner notification.
    """
    pharmacy = get_object_or_404(Pharmacy.objects.select_related('owner'), pk=pharmacy_id)
    pharmacy.is_approved = not pharmacy.is_approved
    pharmacy.save(update_fields=['is_approved'])

    status_str = "Approved" if pharmacy.is_approved else "Revoked Approval"

    # Notify pharmacy owner
    Notification.objects.create(
        user=pharmacy.owner,
        message=f"Your pharmacy '{pharmacy.pharmacy_name}' has been {status_str.lower()} by the MediFind Administrator."
    )

    logger.info(
        "Pharmacy approval status updated: '%s' (id=%d) -> %s by admin '%s'",
        pharmacy.pharmacy_name, pharmacy.id, status_str, admin_user.username
    )
    return pharmacy, pharmacy.is_approved, status_str


def get_pharmacy_detail_data(pharmacy_id: int, user) -> Tuple[Optional[Pharmacy], Optional[QuerySet], Optional[Dict[str, Any]], bool]:
    """
    Retrieves pharmacy profile, inventory records, and map pin.
    Enforces privacy rule: unapproved pharmacies are only visible to owner or admins.
    Uses select_related('owner') to check ownership without secondary queries.
    Returns (pharmacy, inventory_items, map_pin, is_authorized).
    """
    from inventory.models import Inventory
    pharmacy = get_object_or_404(Pharmacy.objects.select_related('owner'), pk=pharmacy_id)

    if not pharmacy.is_approved:
        is_owner_or_admin = user.is_authenticated and (user == pharmacy.owner or getattr(user, 'is_admin_user', False))
        if not is_owner_or_admin:
            return pharmacy, None, None, False

    inventory_items = Inventory.objects.filter(pharmacy=pharmacy).select_related('medicine').order_by('-updated_at')

    map_pin = None
    if pharmacy.latitude and pharmacy.longitude:
        map_pin = {
            'id': pharmacy.id,
            'name': pharmacy.pharmacy_name,
            'address': f"{pharmacy.address}, {pharmacy.city}",
            'phone': pharmacy.phone_number,
            'lat': float(pharmacy.latitude),
            'lng': float(pharmacy.longitude),
        }

    return pharmacy, inventory_items, map_pin, True
