import logging
from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from accounts.decorators import pharmacy_required
from pharmacies.services import get_pharmacy_for_user
from .forms import InventoryAddForm, InventoryEditForm
from .models import Inventory
from .services import (
    add_or_update_inventory,
    delete_inventory_item,
    get_filtered_inventory,
    get_inventory_counts,
)

logger = logging.getLogger('medfind')


@pharmacy_required
def inventory_list_view(request):
    """Displays pharmacy inventory with search, status filtering, sorting, pagination, and stock counts."""
    pharmacy = get_pharmacy_for_user(request.user)
    if not pharmacy:
        messages.error(request, "No pharmacy record found for your user account.")
        return redirect('dashboard')

    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    sort_by = request.GET.get('sort', 'updated').strip()

    items = get_filtered_inventory(pharmacy, query=query, status_filter=status_filter, sort_by=sort_by)
    counts = get_inventory_counts(pharmacy)

    paginator = Paginator(items, 10)
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

    context = {
        'pharmacy': pharmacy,
        'items': page_obj,
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'query_string': query_string,
        'total_count': counts['total_count'],
        'in_stock_count': counts['in_stock_count'],
        'low_stock_count': counts['low_stock_count'],
        'out_stock_count': counts['out_stock_count'],
    }
    return render(request, 'inventory/list.html', context)


@pharmacy_required
def inventory_add_view(request):
    """Allows pharmacy owners to stock medicines from the global catalog."""
    pharmacy = get_pharmacy_for_user(request.user)
    if not pharmacy:
        messages.error(request, "You must have a registered pharmacy to manage inventory.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = InventoryAddForm(request.POST)
        if form.is_valid():
            medicine = form.cleaned_data['medicine']
            quantity = form.cleaned_data['quantity']

            try:
                item, created = add_or_update_inventory(pharmacy, medicine, quantity)
                if not created:
                    messages.info(
                        request,
                        f"'{medicine.medicine_name}' was already in your inventory. Stock quantity was updated to {quantity} units."
                    )
                else:
                    messages.success(
                        request,
                        f"Added {medicine.medicine_name} ({quantity} units) to inventory."
                    )
                return redirect('inventory_list')
            except IntegrityError:
                logger.warning("Integrity error caught while adding inventory item for pharmacy %s", pharmacy.pharmacy_name)
                messages.error(request, "An inventory record for this medicine already exists.")
    else:
        form = InventoryAddForm()

    return render(request, 'inventory/add.html', {'form': form, 'pharmacy': pharmacy})


@pharmacy_required
def inventory_edit_view(request, pk):
    """Allows pharmacy owners to modify stock quantities for owned items."""
    pharmacy = get_pharmacy_for_user(request.user)
    # Enforce multi-tenant isolation: cannot edit inventory of other pharmacies!
    inventory_item = get_object_or_404(
        Inventory.objects.select_related('medicine'),
        pk=pk,
        pharmacy=pharmacy
    )

    if request.method == 'POST':
        form = InventoryEditForm(request.POST, instance=inventory_item)
        if form.is_valid():
            form.save()
            logger.info(
                "Inventory stock edited: pharmacy='%s', medicine='%s', quantity=%d",
                pharmacy.pharmacy_name, inventory_item.medicine.medicine_name, inventory_item.quantity
            )
            messages.success(
                request,
                f"Updated {inventory_item.medicine.medicine_name} stock to {inventory_item.quantity} units ({inventory_item.get_availability_status_display()})."
            )
            return redirect('inventory_list')
    else:
        form = InventoryEditForm(instance=inventory_item)

    return render(request, 'inventory/edit.html', {
        'form': form,
        'inventory_item': inventory_item,
        'pharmacy': pharmacy,
    })


@pharmacy_required
def inventory_delete_view(request, pk):
    """Prompts and executes inventory item deletion with ownership verification."""
    pharmacy = get_pharmacy_for_user(request.user)
    inventory_item = get_object_or_404(
        Inventory.objects.select_related('medicine'),
        pk=pk,
        pharmacy=pharmacy
    )

    if request.method == 'POST':
        _, med_name = delete_inventory_item(pharmacy, pk)
        messages.success(request, f"Removed '{med_name}' from pharmacy inventory.")
        return redirect('inventory_list')

    return render(request, 'inventory/delete_confirm.html', {
        'inventory_item': inventory_item,
        'pharmacy': pharmacy,
    })
