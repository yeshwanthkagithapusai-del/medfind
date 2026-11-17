import logging
from typing import Any, Dict, List, Optional, Tuple
from django.core.paginator import EmptyPage, Page, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from inventory.models import Inventory
from pharmacies.services import calculate_haversine_distance, is_valid_coordinate
from .models import Medicine

logger = logging.getLogger('medfind')


def search_medicine_inventory(
    query: str = '',
    category: str = '',
    dosage_form: str = '',
    strength: str = '',
    city: str = '',
    pincode: str = '',
    stock_status: str = '',
    radius_km: Optional[Any] = None,
    user_lat: Optional[Any] = None,
    user_lng: Optional[Any] = None,
    sort_by: str = '',
    page: int = 1,
    per_page: int = 10,
) -> Tuple[Page, bool, List[Dict[str, Any]], int, Optional[Dict[str, float]]]:
    """
    Searches inventory records for approved pharmacies matching search filters.
    Calculates proximity distances, applies radius bounds, extracts map pin metadata,
    and paginates results.
    """
    # Base queryset: strictly include stock only from verified/approved pharmacies!
    inventory_qs = Inventory.objects.filter(
        pharmacy__is_approved=True
    ).select_related('medicine', 'pharmacy')

    if query:
        inventory_qs = inventory_qs.filter(
            Q(medicine__medicine_name__icontains=query) |
            Q(medicine__generic_name__icontains=query) |
            Q(medicine__strength__icontains=query) |
            Q(medicine__dosage_form__icontains=query) |
            Q(medicine__category__icontains=query) |
            Q(medicine__description__icontains=query) |
            Q(pharmacy__pharmacy_name__icontains=query)
        )

    if category:
        inventory_qs = inventory_qs.filter(medicine__category=category)

    if dosage_form:
        inventory_qs = inventory_qs.filter(medicine__dosage_form=dosage_form)

    if strength:
        inventory_qs = inventory_qs.filter(medicine__strength__icontains=strength)

    if city:
        inventory_qs = inventory_qs.filter(pharmacy__city__icontains=city.strip())

    if pincode:
        inventory_qs = inventory_qs.filter(pharmacy__pincode__icontains=pincode.strip())

    if stock_status:
        inventory_qs = inventory_qs.filter(availability_status=stock_status)

    inventory_results: List[Inventory] = list(
        inventory_qs.order_by('-availability_status', '-updated_at')
    )

    # Proximity calculation & Radius filtering
    has_user_coords = is_valid_coordinate(user_lat, user_lng)
    user_coords_dict: Optional[Dict[str, float]] = None

    if has_user_coords:
        u_lat = float(user_lat)
        u_lng = float(user_lng)
        user_coords_dict = {'lat': u_lat, 'lng': u_lng}

        for item in inventory_results:
            if is_valid_coordinate(item.pharmacy.latitude, item.pharmacy.longitude):
                item.distance_km = calculate_haversine_distance(
                    u_lat, u_lng, item.pharmacy.latitude, item.pharmacy.longitude
                )
            else:
                item.distance_km = None

        # Radius cutoff filter
        if radius_km not in (None, '', 'all'):
            try:
                max_radius = float(radius_km)
                if max_radius > 0:
                    inventory_results = [
                        item for item in inventory_results
                        if item.distance_km is not None and item.distance_km <= max_radius
                    ]
            except (ValueError, TypeError):
                pass

        if sort_by == 'distance':
            inventory_results.sort(
                key=lambda x: (
                    x.distance_km is None,
                    x.distance_km if x.distance_km is not None else float('inf')
                )
            )
    else:
        for item in inventory_results:
            item.distance_km = None

    # Map pins for Leaflet.js
    map_pins: List[Dict[str, Any]] = []
    seen_pharmacies = set()
    for item in inventory_results:
        p = item.pharmacy
        if p.id not in seen_pharmacies:
            seen_pharmacies.add(p.id)
            if is_valid_coordinate(p.latitude, p.longitude):
                dist = getattr(item, 'distance_km', None)
                map_pins.append({
                    'id': p.id,
                    'name': p.pharmacy_name,
                    'address': f"{p.address}, {p.city}",
                    'phone': p.phone_number,
                    'lat': float(p.latitude),
                    'lng': float(p.longitude),
                    'medicine': item.medicine.medicine_name,
                    'status': item.get_availability_status_display(),
                    'freshness_tier': getattr(item, 'freshness_tier', 'FRESH'),
                    'freshness_label': getattr(item, 'freshness_label', 'Verified Fresh (< 24h)'),
                    'distance_km': dist,
                })

    total_results = len(inventory_results)

    # Pagination
    paginator = Paginator(inventory_results, per_page)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    logger.info(
        "Medicine search executed: query='%s', category='%s', city='%s', radius='%s', results_count=%d",
        query, category, city, radius_km, total_results
    )
    return page_obj, has_user_coords, map_pins, total_results, user_coords_dict


def get_search_filter_options() -> Tuple[List[str], List[str], List[str]]:
    """
    Retrieves distinct categories, approved pharmacy cities, and dosage forms for search dropdowns.
    Optimized: queries Pharmacy directly using the (is_approved, city) composite index,
    avoiding an expensive full-table scan and join across the entire Inventory table.
    """
    from pharmacies.models import Pharmacy
    categories = [choice[0] for choice in Medicine.CATEGORY_CHOICES]
    dosage_forms = [choice[0] for choice in Medicine.DOSAGE_FORM_CHOICES]
    raw_cities = (
        Pharmacy.objects.filter(is_approved=True)
        .order_by('city')
        .values_list('city', flat=True)
        .distinct()
    )
    cities = sorted(list({c.strip() for c in raw_cities if c and c.strip()}))
    return categories, cities, dosage_forms


def get_medicine_detail_data(medicine_id: int):
    """
    Retrieves medicine details, approved pharmacy inventory, and map pins.
    """
    medicine = get_object_or_404(Medicine, pk=medicine_id)
    stock_records = Inventory.objects.filter(
        medicine=medicine,
        pharmacy__is_approved=True
    ).select_related('pharmacy').order_by('-availability_status', '-updated_at')

    map_pins = []
    for item in stock_records:
        p = item.pharmacy
        if p.latitude and p.longitude:
            map_pins.append({
                'id': p.id,
                'name': p.pharmacy_name,
                'address': f"{p.address}, {p.city}",
                'phone': p.phone_number,
                'lat': float(p.latitude),
                'lng': float(p.longitude),
                'medicine': medicine.medicine_name,
                'status': item.get_availability_status_display(),
            })

    return medicine, stock_records, map_pins
