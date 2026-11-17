import logging
from typing import Any, Dict, Optional, Tuple
from django.db import IntegrityError
from django.db.models import Count, Q, QuerySet
from django.shortcuts import get_object_or_404
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from .models import Inventory

logger = logging.getLogger('medfind')


def get_inventory_counts(pharmacy: Pharmacy) -> Dict[str, int]:
    """
    Computes stock counts for a pharmacy using a single consolidated aggregate query.
    Eliminates 3 redundant database round-trips.
    """
    aggregated = Inventory.objects.filter(pharmacy=pharmacy).aggregate(
        total=Count('id'),
        in_stock=Count('id', filter=Q(availability_status='IN_STOCK')),
        low_stock=Count('id', filter=Q(availability_status='LOW_STOCK')),
        out_stock=Count('id', filter=Q(availability_status='OUT_OF_STOCK')),
    )

    return {
        'total_count': aggregated['total'] or 0,
        'in_stock_count': aggregated['in_stock'] or 0,
        'low_stock_count': aggregated['low_stock'] or 0,
        'out_stock_count': aggregated['out_stock'] or 0,
    }


def get_filtered_inventory(
    pharmacy: Pharmacy,
    query: str = '',
    status_filter: str = '',
    sort_by: str = 'updated'
) -> QuerySet:
    """
    Retrieves inventory items for a pharmacy with optional keyword, status, and sort filters.
    Applies select_related on medicine to avoid N+1 queries.
    """
    items = Inventory.objects.filter(pharmacy=pharmacy).select_related('medicine')

    if query:
        items = items.filter(
            Q(medicine__medicine_name__icontains=query) |
            Q(medicine__generic_name__icontains=query) |
            Q(medicine__category__icontains=query)
        )

    if status_filter:
        items = items.filter(availability_status=status_filter)

    if sort_by == 'name':
        items = items.order_by('medicine__medicine_name')
    elif sort_by == 'qty_asc':
        items = items.order_by('quantity', 'medicine__medicine_name')
    elif sort_by == 'qty_desc':
        items = items.order_by('-quantity', 'medicine__medicine_name')
    else:
        items = items.order_by('-updated_at')

    return items


def add_or_update_inventory(
    pharmacy: Pharmacy,
    medicine: Medicine,
    quantity: int
) -> Tuple[Inventory, bool]:
    """
    Safely adds a medicine to a pharmacy's inventory or updates stock quantity if already present.
    Returns (inventory_item, created).
    """
    existing = Inventory.objects.filter(pharmacy=pharmacy, medicine=medicine).first()
    if existing:
        existing.quantity = quantity
        existing.save()
        logger.info(
            "Inventory stock updated: pharmacy='%s', medicine='%s', new_quantity=%d",
            pharmacy.pharmacy_name, medicine.medicine_name, quantity
        )
        return existing, False

    inventory_item = Inventory(pharmacy=pharmacy, medicine=medicine, quantity=quantity)
    inventory_item.save()
    logger.info(
        "New inventory item added: pharmacy='%s', medicine='%s', quantity=%d",
        pharmacy.pharmacy_name, medicine.medicine_name, quantity
    )
    return inventory_item, True


def delete_inventory_item(pharmacy: Pharmacy, pk: int) -> Tuple[bool, str]:
    """
    Deletes an inventory record ensuring strict multi-tenant ownership scoping.
    Uses select_related('medicine') to retrieve the medicine name without secondary queries.
    """
    inventory_item = get_object_or_404(
        Inventory.objects.select_related('medicine'),
        pk=pk,
        pharmacy=pharmacy
    )
    med_name = inventory_item.medicine.medicine_name
    inventory_item.delete()
    logger.info(
        "Inventory item deleted: pharmacy='%s', medicine='%s'",
        pharmacy.pharmacy_name, med_name
    )
    return True, med_name
