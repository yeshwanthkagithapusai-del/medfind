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
    discover_healthcare_providers,
    discover_nearby_pharmacies,
    get_pharmacy_detail_data,
    get_pharmacy_for_user,
    get_provider_filter_options,
    toggle_pharmacy_approval,
)

logger = logging.getLogger('medfind')
User = get_user_model()


def pharmacy_discovery_view(request):
    """
    Public directory and geospatial discovery view for healthcare providers (Hospitals & Pharmacies).
    Supports GPS geolocation distance calculation, radius filtering, state/district/city/pincode search,
    provider type filtering (Hospital vs Pharmacy), verification status badges, and Leaflet map rendering.
    """
    search_query = request.GET.get('q', '').strip()
    provider_type = request.GET.get('type', 'ALL').strip().upper()
    state = request.GET.get('state', '').strip()
    district = request.GET.get('district', '').strip()
    city = request.GET.get('city', '').strip()
    pincode = request.GET.get('pincode', '').strip()
    radius = request.GET.get('radius', '').strip()
    availability = request.GET.get('availability', 'all').strip().lower()
    if availability not in ('all', 'in_stock'):
        availability = 'all'
    user_lat = request.GET.get('lat', '').strip()
    user_lng = request.GET.get('lng', '').strip()
    sort_by = request.GET.get('sort', 'distance').strip()
    page = request.GET.get('page', '1').strip()

    # Intelligent default verification:
    # If user explicitly asked for Hospitals and did not specify verification, default to 'all' so genuine pilot hospitals are visible.
    # Otherwise, default to 'approved' to preserve backward compatibility and strict approval filtering.
    default_verification = 'all' if provider_type == Pharmacy.ProviderType.HOSPITAL else 'approved'
    verification = request.GET.get('verification', default_verification).strip().lower()
    if verification not in ('approved', 'all', 'pending'):
        verification = default_verification

    page_obj, has_user_coords, map_pins, total_results, user_coords = discover_healthcare_providers(
        user_lat=user_lat,
        user_lng=user_lng,
        radius_km=radius,
        city=city,
        district=district,
        state=state,
        pincode=pincode,
        search_query=search_query,
        provider_type=provider_type,
        verification_status=verification,
        only_approved=(verification == 'approved'),
        availability=availability,
        sort_by=sort_by,
        page=int(page) if page.isdigit() else 1,
        per_page=9
    )

    filter_options = get_provider_filter_options()

    query_dict = request.GET.copy()
    query_dict.pop('page', None)
    query_string = query_dict.urlencode()

    context = {
        'page_obj': page_obj,
        'pharmacies': page_obj,  # Kept for backward compatibility with existing templates
        'providers': page_obj,
        'search_query': search_query,
        'provider_type': provider_type,
        'verification': verification,
        'availability': availability,
        'state': state,
        'district': district,
        'city': city,
        'pincode': pincode,
        'radius': radius,
        'filter_options': filter_options,
        'cities': filter_options['cities'],
        'pincodes': filter_options['pincodes'],
        'states': filter_options['states'],
        'districts': filter_options['districts'],
        'availability_options': filter_options.get('availability_options', []),
        'radius_options': filter_options.get('radius_options', []),
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
    """
    Public detail view for healthcare facilities.
    Hospitals and approved pharmacies are accessible to the public.
    Unapproved registered pharmacies are restricted to store owner or administrators.
    """
    pharmacy, inventory_items, map_pin, is_authorized = get_pharmacy_detail_data(pk, request.user)
    if not is_authorized:
        messages.error(request, "This healthcare facility is pending administrative verification.")
        return redirect('pharmacy_discovery')

    return render(request, 'pharmacies/detail.html', {
        'pharmacy': pharmacy,
        'inventory_items': inventory_items,
        'map_pin': map_pin,
    })


@login_required
@pharmacy_required
def edit_pharmacy_profile_view(request):
    """
    View for pharmacy owners to update store address, contact details, and coordinates.
    """
    pharmacy = get_pharmacy_for_user(request.user)
    if not pharmacy:
        messages.error(request, "No pharmacy profile found linked to your account.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = PharmacyEditForm(request.POST, instance=pharmacy)
        if form.is_valid():
            form.save()
            messages.success(request, "Your pharmacy profile and location coordinates have been updated successfully.")
            return redirect('pharmacy_dashboard')
    else:
        form = PharmacyEditForm(instance=pharmacy)

    return render(request, 'pharmacies/edit_profile.html', {
        'form': form,
        'pharmacy': pharmacy,
    })

# Alias for backwards compatibility
pharmacy_edit_profile_view = edit_pharmacy_profile_view


@login_required
@admin_required
def admin_pharmacy_list_view(request):
    """
    Governance console for administrators to view, audit, and approve/revoke healthcare providers.
    """
    search_q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all').strip()
    type_filter = request.GET.get('type', 'all').strip()
    source_filter = request.GET.get('source', 'all').strip().upper()

    qs = Pharmacy.objects.all().order_by('-created_at')

    if search_q:
        qs = qs.filter(
            Q(pharmacy_name__icontains=search_q) |
            Q(registration_number__icontains=search_q) |
            Q(source_id__icontains=search_q) |
            Q(owner__username__icontains=search_q) |
            Q(city__icontains=search_q) |
            Q(district__icontains=search_q) |
            Q(state__icontains=search_q)
        )

    if status_filter == 'approved':
        qs = qs.filter(is_approved=True)
    elif status_filter == 'pending':
        qs = qs.filter(is_approved=False)

    if type_filter.upper() in (Pharmacy.ProviderType.HOSPITAL, Pharmacy.ProviderType.PHARMACY):
        qs = qs.filter(provider_type=type_filter.upper())

    if source_filter in {s.value for s in Pharmacy.DataSource}:
        qs = qs.filter(source_name=source_filter)

    total_count = qs.count()
    approved_count = Pharmacy.objects.filter(is_approved=True).count()
    pending_count = Pharmacy.objects.filter(is_approved=False).count()
    hospitals_count = Pharmacy.objects.filter(provider_type=Pharmacy.ProviderType.HOSPITAL).count()
    pharmacies_count = Pharmacy.objects.filter(provider_type=Pharmacy.ProviderType.PHARMACY).count()
    genuine_count = Pharmacy.objects.filter(is_demo=False).count()
    demo_count = Pharmacy.objects.filter(is_demo=True).count()

    paginator = Paginator(qs, 15)
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
        'page_obj': page_obj,
        'pharmacies': page_obj,
        'search_q': search_q,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'source_filter': source_filter,
        'total_count': total_count,
        'approved_count': approved_count,
        'pending_count': pending_count,
        'hospitals_count': hospitals_count,
        'pharmacies_count': pharmacies_count,
        'genuine_count': genuine_count,
        'demo_count': demo_count,
        'query_string': query_string,
    })


@login_required
@admin_required
@require_POST
def toggle_pharmacy_approval_view(request, pk):
    """
    POST-only action for administrators to approve or revoke a healthcare facility.
    """
    pharmacy, is_approved, status_str = toggle_pharmacy_approval(pk, request.user)
    if is_approved:
        messages.success(request, f"Facility '{pharmacy.pharmacy_name}' has been Approved.")
    else:
        messages.warning(request, f"Approval for facility '{pharmacy.pharmacy_name}' has been Revoked.")
    return redirect(request.META.get('HTTP_REFERER', 'admin_pharmacy_list'))

# Alias for backwards compatibility
admin_toggle_approval_view = toggle_pharmacy_approval_view


@login_required
@admin_required
def admin_user_list_view(request):
    """
    Administrative portal view for managing user accounts across roles.
    """
    role_filter = request.GET.get('role', 'ALL').strip().upper()
    search_q = request.GET.get('q', '').strip()

    users_qs = User.objects.all().order_by('-date_joined')

    if role_filter in ('CUSTOMER', 'PHARMACY', 'ADMIN'):
        users_qs = users_qs.filter(role=role_filter)

    if search_q:
        users_qs = users_qs.filter(
            Q(username__icontains=search_q) |
            Q(email__icontains=search_q) |
            Q(first_name__icontains=search_q) |
            Q(last_name__icontains=search_q)
        )

    total_users = User.objects.count()
    customer_count = User.objects.filter(role='CUSTOMER').count()
    pharmacy_count = User.objects.filter(role='PHARMACY').count()
    admin_count = User.objects.filter(role='ADMIN').count()

    paginator = Paginator(users_qs, 15)
    page_num = request.GET.get('page', 1)
    try:
        users_page = paginator.page(page_num)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    return render(request, 'pharmacies/admin_user_list.html', {
        'users_page': users_page,
        'page_obj': users_page,
        'users': users_page,
        'role_filter': role_filter,
        'search_q': search_q,
        'total_users': total_users,
        'customer_count': customer_count,
        'pharmacy_count': pharmacy_count,
        'admin_count': admin_count,
    })

# Alias for backwards compatibility
admin_user_management_view = admin_user_list_view


@login_required
@admin_required
def admin_request_monitor_view(request):
    """
    Platform-wide activity monitor for administrators.
    """
    from requests_app.models import AvailabilityRequest
    status_filter = request.GET.get('status', 'ALL').strip().upper()
    search_q = request.GET.get('q', '').strip()

    requests_qs = AvailabilityRequest.objects.select_related(
        'customer', 'pharmacy', 'medicine'
    ).order_by('-created_at')

    if status_filter in ('PENDING', 'CONFIRMED', 'UNAVAILABLE', 'CANCELLED'):
        requests_qs = requests_qs.filter(status=status_filter)

    if search_q:
        requests_qs = requests_qs.filter(
            Q(customer__username__icontains=search_q) |
            Q(pharmacy__pharmacy_name__icontains=search_q) |
            Q(medicine__medicine_name__icontains=search_q)
        )

    total_requests = AvailabilityRequest.objects.count()
    pending_count = AvailabilityRequest.objects.filter(status='PENDING').count()
    confirmed_count = AvailabilityRequest.objects.filter(status='CONFIRMED').count()
    unavailable_count = AvailabilityRequest.objects.filter(status='UNAVAILABLE').count()
    cancelled_count = AvailabilityRequest.objects.filter(status='CANCELLED').count()

    paginator = Paginator(requests_qs, 15)
    page_num = request.GET.get('page', 1)
    try:
        requests_page = paginator.page(page_num)
    except PageNotAnInteger:
        requests_page = paginator.page(1)
    except EmptyPage:
        requests_page = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    return render(request, 'pharmacies/admin_request_monitor.html', {
        'requests_page': requests_page,
        'page_obj': requests_page,
        'requests': requests_page,
        'status_filter': status_filter,
        'search_q': search_q,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'confirmed_count': confirmed_count,
        'unavailable_count': unavailable_count,
        'cancelled_count': cancelled_count,
    })
