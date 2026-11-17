import logging
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from accounts.decorators import admin_required, pharmacy_required
from .forms import PharmacyEditForm
from .models import Pharmacy
from .services import (
    discover_nearby_pharmacies,
    get_pharmacy_detail_data,
    get_pharmacy_filter_options,
    get_pharmacy_for_user,
    toggle_pharmacy_approval,
)

logger = logging.getLogger('medfind')
User = get_user_model()


def pharmacy_discovery_view(request):
    """
    Public directory and nearby discovery view for approved pharmacies.
    Supports GPS geolocation distance calculation, radius filtering, manual city/pincode search,
    and Leaflet map rendering.
    """
    search_query = request.GET.get('q', '').strip()
    city = request.GET.get('city', '').strip()
    pincode = request.GET.get('pincode', '').strip()
    radius = request.GET.get('radius', '').strip()
    user_lat = request.GET.get('lat', '').strip()
    user_lng = request.GET.get('lng', '').strip()
    sort_by = request.GET.get('sort', 'distance').strip()
    page = request.GET.get('page', '1').strip()

    page_obj, has_user_coords, map_pins, total_results, user_coords = discover_nearby_pharmacies(
        user_lat=user_lat,
        user_lng=user_lng,
        radius_km=radius,
        city=city,
        pincode=pincode,
        search_query=search_query,
        sort_by=sort_by,
        only_approved=True,
        page=int(page) if page.isdigit() else 1,
        per_page=9
    )

    cities, pincodes = get_pharmacy_filter_options()

    query_dict = request.GET.copy()
    query_dict.pop('page', None)
    query_string = query_dict.urlencode()

    context = {
        'page_obj': page_obj,
        'pharmacies': page_obj,
        'search_query': search_query,
        'city': city,
        'pincode': pincode,
        'radius': radius,
        'cities': cities,
        'pincodes': pincodes,
        'map_pins': map_pins,
        'total_results': total_results,
        'user_lat': user_lat,
        'user_lng': user_lng,
        'user_coords': user_coords,
        'sort_by': sort_by,
        'has_user_coords': has_user_coords,
        'query_string': query_string,
    }
    return render(request, 'pharmacies/discovery.html', context)


def pharmacy_detail_view(request, pk):
    """Public detail view for approved pharmacies; unapproved pharmacies restricted to owner/admin."""
    pharmacy, inventory_items, map_pin, is_authorized = get_pharmacy_detail_data(pk, request.user)

    if not is_authorized:
        messages.warning(request, "This pharmacy is pending administrative verification.")
        return redirect('search_medicines')

    return render(request, 'pharmacies/detail.html', {
        'pharmacy': pharmacy,
        'inventory_items': inventory_items,
        'map_pin': map_pin,
    })


@pharmacy_required
def edit_pharmacy_profile_view(request):
    """Allows pharmacy owners to update their facility details and coordinates."""
    pharmacy = get_pharmacy_for_user(request.user)
    if not pharmacy:
        messages.error(request, "No pharmacy profile found linked to your account.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = PharmacyEditForm(request.POST, instance=pharmacy)
        if form.is_valid():
            form.save()
            logger.info("Pharmacy profile updated: '%s' by owner: %s", pharmacy.pharmacy_name, request.user.username)
            messages.success(request, "Pharmacy profile updated successfully.")
            return redirect('pharmacy_dashboard')
    else:
        form = PharmacyEditForm(instance=pharmacy)

    return render(request, 'pharmacies/edit_profile.html', {
        'form': form,
        'pharmacy': pharmacy,
    })


@admin_required
def admin_pharmacy_list_view(request):
    """Admin-only pharmacy directory with approval filtering, search, and pagination."""
    status_filter = request.GET.get('status', 'all').strip().lower()
    search_q = request.GET.get('q', '').strip()

    pharmacies = Pharmacy.objects.select_related('owner').order_by('-created_at')

    if status_filter == 'pending':
        pharmacies = pharmacies.filter(is_approved=False)
    elif status_filter == 'approved':
        pharmacies = pharmacies.filter(is_approved=True)

    if search_q:
        pharmacies = pharmacies.filter(
            Q(pharmacy_name__icontains=search_q) |
            Q(registration_number__icontains=search_q) |
            Q(city__icontains=search_q) |
            Q(owner__username__icontains=search_q) |
            Q(owner__email__icontains=search_q)
        )

    paginator = Paginator(pharmacies, 15)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    query_dict = request.GET.copy()
    query_dict.pop('page', None)
    query_string = query_dict.urlencode()

    return render(request, 'pharmacies/admin_list.html', {
        'pharmacies': page_obj,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_q': search_q,
        'query_string': query_string,
        'total_count': paginator.count,
    })


@admin_required
@require_POST
def toggle_pharmacy_approval_view(request, pk):
    """Toggles pharmacy verification state via POST."""
    pharmacy, is_approved, status_str = toggle_pharmacy_approval(pk, request.user)
    messages.success(request, f"Pharmacy '{pharmacy.pharmacy_name}' status changed to: {status_str}.")
    return redirect('admin_pharmacy_list')


@admin_required
def admin_user_list_view(request):
    """Admin-only view listing all users (customers and pharmacy owners) with search and pagination."""
    from django.db.models import Q
    role_filter = request.GET.get('role', 'all').strip().lower()
    search_q = request.GET.get('q', '').strip()

    users = User.objects.exclude(role='ADMIN').order_by('-date_joined')

    if role_filter == 'customer':
        users = users.filter(role='CUSTOMER')
    elif role_filter == 'pharmacy':
        users = users.filter(role='PHARMACY')

    if search_q:
        users = users.filter(
            Q(username__icontains=search_q) |
            Q(email__icontains=search_q) |
            Q(first_name__icontains=search_q) |
            Q(last_name__icontains=search_q) |
            Q(phone_number__icontains=search_q)
        )

    paginator = Paginator(users, 20)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    query_dict = request.GET.copy()
    query_dict.pop('page', None)
    query_string = query_dict.urlencode()

    return render(request, 'pharmacies/admin_user_list.html', {
        'users': page_obj,
        'page_obj': page_obj,
        'role_filter': role_filter,
        'search_q': search_q,
        'query_string': query_string,
        'total_count': paginator.count,
    })


@admin_required
def admin_request_monitor_view(request):
    """Admin-only view for monitoring all platform availability requests with status filter and pagination."""
    from requests_app.models import AvailabilityRequest
    from django.db.models import Q

    status_filter = request.GET.get('status', 'all').strip().upper()
    search_q = request.GET.get('q', '').strip()

    requests_qs = AvailabilityRequest.objects.select_related(
        'customer', 'pharmacy', 'medicine'
    ).order_by('-created_at')

    if status_filter and status_filter != 'ALL':
        requests_qs = requests_qs.filter(status=status_filter)

    if search_q:
        requests_qs = requests_qs.filter(
            Q(customer__username__icontains=search_q) |
            Q(pharmacy__pharmacy_name__icontains=search_q) |
            Q(medicine__medicine_name__icontains=search_q)
        )

    paginator = Paginator(requests_qs, 15)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    query_dict = request.GET.copy()
    query_dict.pop('page', None)
    query_string = query_dict.urlencode()

    return render(request, 'pharmacies/admin_request_monitor.html', {
        'requests': page_obj,
        'page_obj': page_obj,
        'status_filter': status_filter if status_filter != 'ALL' else 'all',
        'search_q': search_q,
        'query_string': query_string,
        'total_count': paginator.count,
    })
