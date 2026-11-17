import logging
from typing import Any, Dict, List
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from inventory.models import Inventory
from inventory.services import get_inventory_counts
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from requests_app.models import AvailabilityRequest, Notification

logger = logging.getLogger('medfind')
User = get_user_model()


def get_home_page_metrics() -> Dict[str, Any]:
    """
    Computes public landing page metrics.
    """
    total_approved_pharmacies = Pharmacy.objects.filter(is_approved=True).count()
    total_medicines = Medicine.objects.count()
    total_in_stock_listings = Inventory.objects.filter(
        pharmacy__is_approved=True,
        availability_status='IN_STOCK'
    ).count()

    categories = Medicine.CATEGORY_CHOICES[:6]
    featured_pharmacies = Pharmacy.objects.filter(is_approved=True).order_by('-created_at')[:3]

    return {
        'total_pharmacies': total_approved_pharmacies,
        'total_medicines': total_medicines,
        'total_in_stock': total_in_stock_listings,
        'categories': categories,
        'featured_pharmacies': featured_pharmacies,
    }


def get_customer_dashboard_metrics(user) -> Dict[str, Any]:
    """
    Computes customer dashboard metrics using a single consolidated aggregate query.
    Eliminates redundant round-trips and includes cancelled counts and unread notifications.
    """
    import datetime
    from django.utils import timezone

    req_counts = AvailabilityRequest.objects.filter(customer=user).aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='PENDING')),
        confirmed=Count('id', filter=Q(status='CONFIRMED')),
        unavailable=Count('id', filter=Q(status='UNAVAILABLE')),
        cancelled=Count('id', filter=Q(status='CANCELLED')),
    )

    recent_requests = AvailabilityRequest.objects.filter(
        customer=user
    ).select_related('pharmacy', 'medicine').order_by('-created_at')[:6]

    recent_notifications = Notification.objects.filter(user=user).order_by('-created_at')[:5]
    unread_notifications_count = Notification.objects.filter(user=user, is_read=False).count()

    # Time-based personalized greeting
    now = timezone.localtime(timezone.now()) if timezone.is_aware(timezone.now()) else datetime.datetime.now()
    current_hour = now.hour
    if current_hour < 12:
        greeting = "Good morning"
    elif current_hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    customer_display_name = (
        user.get_full_name() if user.get_full_name() else (user.first_name or user.username)
    )

    return {
        'greeting': greeting,
        'customer_display_name': customer_display_name,
        'total_requests': req_counts['total'] or 0,
        'pending_requests': req_counts['pending'] or 0,
        'confirmed_requests': req_counts['confirmed'] or 0,
        'unavailable_requests': req_counts['unavailable'] or 0,
        'cancelled_requests': req_counts['cancelled'] or 0,
        'unread_notifications_count': unread_notifications_count,
        'recent_requests': recent_requests,
        'recent_notifications': recent_notifications,
    }


def get_pharmacy_dashboard_metrics(pharmacy: Pharmacy) -> Dict[str, Any]:
    """
    Computes pharmacy dashboard analytics, stock distributions, low-stock monitoring alerts,
    and recent operational activity.
    """
    inv_counts = get_inventory_counts(pharmacy)
    total_catalog_medicines = Medicine.objects.count()

    req_counts = AvailabilityRequest.objects.filter(pharmacy=pharmacy).aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='PENDING')),
        confirmed=Count('id', filter=Q(status='CONFIRMED')),
        unavailable=Count('id', filter=Q(status='UNAVAILABLE')),
    )

    recent_requests = AvailabilityRequest.objects.filter(
        pharmacy=pharmacy
    ).select_related('customer', 'medicine').order_by('-created_at')[:6]

    recent_inventory = Inventory.objects.filter(
        pharmacy=pharmacy
    ).select_related('medicine').order_by('-updated_at')[:6]

    # Dedicated Low Stock & Out of Stock Monitoring List
    low_stock_alerts = Inventory.objects.filter(
        pharmacy=pharmacy,
        availability_status__in=['LOW_STOCK', 'OUT_OF_STOCK']
    ).select_related('medicine').order_by('quantity', '-updated_at')[:6]

    return {
        'pharmacy': pharmacy,
        'total_items': inv_counts['total_count'],
        'in_stock_count': inv_counts['in_stock_count'],
        'low_stock_count': inv_counts['low_stock_count'],
        'out_stock_count': inv_counts['out_stock_count'],
        'total_catalog_medicines': total_catalog_medicines,
        'pending_requests_count': req_counts['pending'] or 0,
        'total_requests_count': req_counts['total'] or 0,
        'recent_requests': recent_requests,
        'recent_inventory': recent_inventory,
        'low_stock_alerts': low_stock_alerts,
        'chart_labels': ['In Stock (>10)', 'Low Stock (1-10)', 'Out of Stock (0)'],
        'chart_data': [
            inv_counts['in_stock_count'],
            inv_counts['low_stock_count'],
            inv_counts['out_stock_count']
        ],
    }


def get_admin_dashboard_metrics() -> Dict[str, Any]:
    """
    Computes system-wide operational metrics using grouped aggregations.
    Consolidates user counts, pharmacy verification counts, and request status breakdowns.
    """
    # 1. Grouped User counts (1 query)
    user_counts = User.objects.aggregate(
        customers=Count('id', filter=Q(role='CUSTOMER')),
        pharmacy_owners=Count('id', filter=Q(role='PHARMACY')),
    )

    # 2. Grouped Pharmacy verification counts (1 query)
    pharmacy_counts = Pharmacy.objects.aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(is_approved=False)),
        approved=Count('id', filter=Q(is_approved=True)),
    )

    # 3. Grouped request status counts (1 query)
    request_counts = AvailabilityRequest.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(status='PENDING')),
        confirmed=Count('id', filter=Q(status='CONFIRMED')),
        unavailable=Count('id', filter=Q(status='UNAVAILABLE')),
        cancelled=Count('id', filter=Q(status='CANCELLED')),
    )

    total_medicines = Medicine.objects.count()
    total_inventory = Inventory.objects.count()

    pending_pharmacies_list = Pharmacy.objects.filter(
        is_approved=False
    ).select_related('owner').order_by('-created_at')[:5]

    recent_requests = AvailabilityRequest.objects.select_related(
        'customer', 'pharmacy', 'medicine'
    ).order_by('-created_at')[:6]

    # Category breakdown for Chart.js
    category_counts = Medicine.objects.values('category').annotate(
        count=Count('id')
    ).order_by('-count')[:6]

    cat_labels = [c['category'] for c in category_counts]
    cat_data = [c['count'] for c in category_counts]

    # Completed = confirmed + unavailable (pharmacy responded)
    completed_requests = (request_counts['confirmed'] or 0) + (request_counts['unavailable'] or 0)

    return {
        'total_customers': user_counts['customers'] or 0,
        'total_pharmacy_owners': user_counts['pharmacy_owners'] or 0,
        'total_pharmacies': pharmacy_counts['total'] or 0,
        'pending_approvals': pharmacy_counts['pending'] or 0,
        'approved_pharmacies': pharmacy_counts['approved'] or 0,
        'total_medicines': total_medicines,
        'total_inventory': total_inventory,
        'total_requests': request_counts['total'] or 0,
        'active_requests': request_counts['active'] or 0,
        'completed_requests': completed_requests,
        'cancelled_requests': request_counts['cancelled'] or 0,
        'pending_pharmacies_list': pending_pharmacies_list,
        'recent_requests': recent_requests,
        'cat_labels': cat_labels,
        'cat_data': cat_data,
    }
