import logging
from typing import Any, Dict, Optional, Tuple
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, QuerySet
from django.shortcuts import get_object_or_404
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from .models import AvailabilityRequest, Notification

logger = logging.getLogger('medfind')


def create_availability_inquiry(
    customer,
    pharmacy: Pharmacy,
    medicine: Medicine,
    quantity_requested: int,
    request_message: str = ''
) -> AvailabilityRequest:
    """
    Creates a new customer availability request and notifies the recipient pharmacy owner.
    """
    req = AvailabilityRequest.objects.create(
        customer=customer,
        pharmacy=pharmacy,
        medicine=medicine,
        quantity_requested=quantity_requested,
        request_message=request_message,
        status='PENDING'
    )

    # Dispatch notification to pharmacy owner
    Notification.objects.create(
        user=pharmacy.owner,
        message=f"New availability request for '{medicine.medicine_name}' ({quantity_requested} units) from {customer.username}."
    )

    logger.info(
        "Availability request #%d created: customer='%s', pharmacy='%s', medicine='%s', qty=%d",
        req.id, customer.username, pharmacy.pharmacy_name, medicine.medicine_name, quantity_requested
    )
    return req


def get_pharmacy_inbox_counts(pharmacy: Pharmacy) -> Dict[str, int]:
    """
    Aggregates pending, confirmed, unavailable, and cancelled request counts in a single query.
    Eliminates redundant round-trips.
    """
    aggregated = AvailabilityRequest.objects.filter(pharmacy=pharmacy).aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='PENDING')),
        confirmed=Count('id', filter=Q(status='CONFIRMED')),
        unavailable=Count('id', filter=Q(status='UNAVAILABLE')),
        cancelled=Count('id', filter=Q(status='CANCELLED')),
    )

    return {
        'total_count': aggregated['total'] or 0,
        'pending_count': aggregated['pending'] or 0,
        'confirmed_count': aggregated['confirmed'] or 0,
        'unavailable_count': aggregated['unavailable'] or 0,
        'cancelled_count': aggregated['cancelled'] or 0,
    }


def respond_to_availability_inquiry(
    request_id: int,
    pharmacy: Pharmacy,
    status: str,
    pharmacy_response: str
) -> AvailabilityRequest:
    """
    Records a pharmacy's availability response and alerts the inquiring customer.
    Enforces multi-tenant ownership, validates state transition rules, and uses
    select_related('customer', 'medicine') to avoid N+1 queries during notification.
    """
    req_obj = get_object_or_404(
        AvailabilityRequest.objects.select_related('customer', 'medicine'),
        pk=request_id,
        pharmacy=pharmacy
    )

    # State Transition Protection: Cannot respond to cancelled requests!
    if req_obj.status == 'CANCELLED':
        raise ValidationError("Cannot respond to a request that has already been cancelled by the customer.")

    if status not in ('CONFIRMED', 'UNAVAILABLE'):
        raise ValidationError(f"Invalid status transition: '{status}'. Pharmacy can only set CONFIRMED or UNAVAILABLE.")

    req_obj.status = status
    req_obj.pharmacy_response = pharmacy_response
    req_obj.save()

    # Notify customer
    status_text = req_obj.get_status_display()
    Notification.objects.create(
        user=req_obj.customer,
        message=f"{pharmacy.pharmacy_name} updated your request for '{req_obj.medicine.medicine_name}' to: {status_text}."
    )

    logger.info(
        "Availability request #%d responded by '%s': status=%s",
        req_obj.id, pharmacy.pharmacy_name, status
    )
    return req_obj


def cancel_availability_inquiry(request_id: int, customer) -> Tuple[bool, str]:
    """
    Cancels a pending inquiry ensuring customer ownership verification.
    """
    req_obj = get_object_or_404(AvailabilityRequest, pk=request_id, customer=customer)
    if req_obj.status == 'PENDING':
        req_obj.status = 'CANCELLED'
        req_obj.save(update_fields=['status'])
        logger.info("Availability request #%d cancelled by customer: %s", req_obj.id, customer.username)
        return True, f"Request #{req_obj.id} has been cancelled."
    return False, "Only pending requests can be cancelled."
