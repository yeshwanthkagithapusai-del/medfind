import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from accounts.decorators import customer_required, pharmacy_required
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from pharmacies.services import get_pharmacy_for_user
from .forms import AvailabilityRequestCreateForm, PharmacyResponseForm
from .models import AvailabilityRequest
from .services import (
    cancel_availability_inquiry,
    create_availability_inquiry,
    get_pharmacy_inbox_counts,
    respond_to_availability_inquiry,
)

logger = logging.getLogger('medfind')


@customer_required
def create_request_view(request, pharmacy_id, medicine_id):
    """Submits a customer availability inquiry to an approved pharmacy."""
    pharmacy = get_object_or_404(Pharmacy.objects.select_related('owner'), pk=pharmacy_id, is_approved=True)
    medicine = get_object_or_404(Medicine, pk=medicine_id)

    # Pharmacy owners cannot send requests to their own pharmacy
    if request.user == pharmacy.owner:
        messages.warning(request, "You cannot send an availability request to your own pharmacy.")
        return redirect('search_medicines')

    if request.method == 'POST':
        form = AvailabilityRequestCreateForm(request.POST)
        if form.is_valid():
            req = create_availability_inquiry(
                customer=request.user,
                pharmacy=pharmacy,
                medicine=medicine,
                quantity_requested=form.cleaned_data['quantity_requested'],
                request_message=form.cleaned_data.get('request_message', '')
            )
            messages.success(
                request,
                f"Your request for '{medicine.medicine_name}' has been sent to {pharmacy.pharmacy_name}. You can track responses in your dashboard."
            )
            return redirect('customer_requests')
    else:
        form = AvailabilityRequestCreateForm()

    return render(request, 'requests/create.html', {
        'form': form,
        'pharmacy': pharmacy,
        'medicine': medicine,
    })


@customer_required
def customer_requests_list_view(request):
    """Displays the customer's request history with status filters, counts, and pagination."""
    requests_qs = AvailabilityRequest.objects.filter(
        customer=request.user
    ).select_related('pharmacy', 'medicine').order_by('-created_at')

    status_filter = request.GET.get('status', '').strip().upper()
    valid_statuses = {'PENDING', 'CONFIRMED', 'UNAVAILABLE', 'CANCELLED'}
    if status_filter in valid_statuses:
        requests_qs = requests_qs.filter(status=status_filter)
    else:
        status_filter = ''

    # Compute status breakdown counts for customer tabs in a single query
    counts = AvailabilityRequest.objects.filter(customer=request.user).aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='PENDING')),
        confirmed=Count('id', filter=Q(status='CONFIRMED')),
        unavailable=Count('id', filter=Q(status='UNAVAILABLE')),
        cancelled=Count('id', filter=Q(status='CANCELLED')),
    )

    # Paginate requests: 10 per page
    paginator = Paginator(requests_qs, 10)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    # Preserve status parameter in pagination URLs
    query_dict = request.GET.copy()
    query_dict.pop('page', None)
    query_string = query_dict.urlencode()

    return render(request, 'requests/customer_list.html', {
        'requests': page_obj,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'counts': counts,
        'query_string': query_string,
        'total_count': counts['total'] or 0,
    })


@pharmacy_required
def pharmacy_inbox_view(request):
    """Displays incoming requests for the authenticated pharmacy with status badges and pagination."""
    pharmacy = get_pharmacy_for_user(request.user)
    if not pharmacy:
        messages.error(request, "No pharmacy record found for your account.")
        return redirect('dashboard')

    inbox_qs = AvailabilityRequest.objects.filter(
        pharmacy=pharmacy
    ).select_related('customer', 'medicine').order_by('-created_at')

    status_filter = request.GET.get('status', 'PENDING').strip().upper()
    if status_filter not in ('ALL', ''):
        inbox_qs = inbox_qs.filter(status=status_filter)
    else:
        status_filter = 'ALL'

    # Consolidated single aggregate query for inbox status counts
    counts = get_pharmacy_inbox_counts(pharmacy)

    paginator = Paginator(inbox_qs, 10)
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

    return render(request, 'requests/pharmacy_inbox.html', {
        'requests': page_obj,
        'page_obj': page_obj,
        'pharmacy': pharmacy,
        'status_filter': status_filter,
        'query_string': query_string,
        'total_count': counts['total_count'],
        'pending_count': counts['pending_count'],
        'confirmed_count': counts['confirmed_count'],
        'unavailable_count': counts['unavailable_count'],
        'cancelled_count': counts['cancelled_count'],
    })


@pharmacy_required
def respond_request_view(request, pk):
    """Allows pharmacy owners to confirm, decline, or provide notes on requests."""
    pharmacy = get_pharmacy_for_user(request.user)
    req_obj = get_object_or_404(
        AvailabilityRequest.objects.select_related('customer', 'medicine'),
        pk=pk,
        pharmacy=pharmacy
    )

    if req_obj.status == 'CANCELLED':
        messages.warning(request, f"Request #{req_obj.id} was cancelled by the customer and cannot be modified.")
        return redirect('pharmacy_inbox')

    if request.method == 'POST':
        form = PharmacyResponseForm(request.POST, instance=req_obj)
        if form.is_valid():
            try:
                respond_to_availability_inquiry(
                    request_id=pk,
                    pharmacy=pharmacy,
                    status=form.cleaned_data['status'],
                    pharmacy_response=form.cleaned_data.get('pharmacy_response', '')
                )
                messages.success(request, f"Response recorded for Request #{req_obj.id}.")
                return redirect('pharmacy_inbox')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = PharmacyResponseForm(instance=req_obj)

    return render(request, 'requests/respond.html', {
        'form': form,
        'req_obj': req_obj,
        'pharmacy': pharmacy,
    })


@customer_required
@require_POST
def cancel_request_view(request, pk):
    """Allows customers to cancel pending requests via POST."""
    success, msg = cancel_availability_inquiry(pk, request.user)
    if success:
        messages.success(request, msg)
    else:
        messages.error(request, msg)
    return redirect('customer_requests')
