import logging
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from accounts.decorators import admin_required, pharmacy_required
from pharmacies.services import get_pharmacy_for_user
from .services import (
    get_admin_dashboard_metrics,
    get_customer_dashboard_metrics,
    get_home_page_metrics,
    get_pharmacy_dashboard_metrics,
)

logger = logging.getLogger('medfind')
User = get_user_model()


def home_view(request):
    """Public homepage highlighting platform metrics and featured medicine categories."""
    context = get_home_page_metrics()
    return render(request, 'home.html', context)


@login_required
def dashboard_dispatcher_view(request):
    """Directs authenticated users to their corresponding role dashboard."""
    if request.user.is_admin_user:
        return redirect('admin_dashboard')
    elif request.user.is_pharmacy_owner:
        return redirect('pharmacy_dashboard')
    else:
        return redirect('customer_dashboard')


@login_required
def customer_dashboard_view(request):
    """Customer dashboard displaying inquiry metrics, recent activity, and notifications."""
    context = get_customer_dashboard_metrics(request.user)
    return render(request, 'dashboard/customer_dashboard.html', context)


@pharmacy_required
def pharmacy_dashboard_view(request):
    """Pharmacy dashboard displaying stock distributions, low-stock warnings, and inquiries."""
    pharmacy = get_pharmacy_for_user(request.user)
    if not pharmacy:
        messages.error(request, "No pharmacy profile found linked to your account.")
        return redirect('home')

    context = get_pharmacy_dashboard_metrics(pharmacy)
    return render(request, 'dashboard/pharmacy_dashboard.html', context)


@admin_required
def admin_dashboard_view(request):
    """System administrator dashboard displaying verification queues and catalog analytics."""
    context = get_admin_dashboard_metrics()
    return render(request, 'dashboard/admin_dashboard.html', context)
