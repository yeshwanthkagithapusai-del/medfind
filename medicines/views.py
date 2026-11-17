import logging
from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from accounts.decorators import admin_required
from .forms import MedicineForm
from .models import Medicine
from .services import get_medicine_detail_data, get_search_filter_options, search_medicine_inventory

logger = logging.getLogger('medfind')


def search_medicines_view(request):
    """Public search view supporting keyword, category, dosage form, strength, city, distance radius, and geolocation filtering with pagination."""
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    dosage_form = request.GET.get('dosage_form', '').strip()
    strength = request.GET.get('strength', '').strip()
    city = request.GET.get('city', '').strip()
    pincode = request.GET.get('pincode', '').strip()
    stock_status = request.GET.get('status', '').strip()
    radius = request.GET.get('radius', '').strip()
    user_lat = request.GET.get('lat', '').strip()
    user_lng = request.GET.get('lng', '').strip()
    sort_by = request.GET.get('sort', '').strip()
    page = request.GET.get('page', '1').strip()

    page_obj, has_user_coords, map_pins, total_results, user_coords = search_medicine_inventory(
        query=query,
        category=category,
        dosage_form=dosage_form,
        strength=strength,
        city=city,
        pincode=pincode,
        stock_status=stock_status,
        radius_km=radius,
        user_lat=user_lat,
        user_lng=user_lng,
        sort_by=sort_by,
        page=int(page) if page.isdigit() else 1,
        per_page=10
    )

    categories, cities, dosage_forms = get_search_filter_options()

    # Query string for preserving filters across pagination links
    query_dict = request.GET.copy()
    query_dict.pop('page', None)
    query_string = query_dict.urlencode()

    context = {
        'results': page_obj,
        'page_obj': page_obj,
        'query': query,
        'category': category,
        'dosage_form': dosage_form,
        'strength': strength,
        'city': city,
        'pincode': pincode,
        'status': stock_status,
        'radius': radius,
        'categories': categories,
        'cities': cities,
        'dosage_forms': dosage_forms,
        'map_pins': map_pins,
        'total_results': total_results,
        'user_lat': user_lat,
        'user_lng': user_lng,
        'user_coords': user_coords,
        'sort_by': sort_by,
        'has_user_coords': has_user_coords,
        'query_string': query_string,
    }
    return render(request, 'medicines/search.html', context)


def medicine_detail_view(request, pk):
    """Public view showing medicine specifications and verified pharmacy stock availability."""
    medicine, stock_records, map_pins = get_medicine_detail_data(pk)

    context = {
        'medicine': medicine,
        'stock_records': stock_records,
        'map_pins': map_pins,
    }
    return render(request, 'medicines/detail.html', context)


@admin_required
def manage_medicines_view(request):
    """Admin-only master medicine catalogue list view with search and pagination."""
    search_q = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()

    medicines = Medicine.objects.all()
    if search_q:
        medicines = medicines.filter(
            Q(medicine_name__icontains=search_q) |
            Q(generic_name__icontains=search_q) |
            Q(category__icontains=search_q)
        )
    if category_filter:
        medicines = medicines.filter(category__icontains=category_filter)

    medicines = medicines.order_by('medicine_name')

    paginator = Paginator(medicines, 20)
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

    return render(request, 'medicines/manage_list.html', {
        'medicines': page_obj,
        'page_obj': page_obj,
        'search_q': search_q,
        'category_filter': category_filter,
        'query_string': query_string,
        'total_count': paginator.count,
        'categories': Medicine.CATEGORY_CHOICES,
    })


@admin_required
def add_medicine_view(request):
    """Admin view for registering a new medicine in the global catalog."""
    if request.method == 'POST':
        form = MedicineForm(request.POST)
        if form.is_valid():
            med = form.save()
            logger.info("New medicine added to catalog: '%s' by admin: %s", med.medicine_name, request.user.username)
            messages.success(request, f"Medicine '{med.medicine_name}' added to master catalogue.")
            return redirect('manage_medicines')
    else:
        form = MedicineForm()
    return render(request, 'medicines/form.html', {'form': form, 'title': 'Add New Medicine'})


@admin_required
def edit_medicine_view(request, pk):
    """Admin view for updating medicine catalog metadata."""
    medicine = get_object_or_404(Medicine, pk=pk)
    if request.method == 'POST':
        form = MedicineForm(request.POST, instance=medicine)
        if form.is_valid():
            form.save()
            logger.info("Medicine catalog updated: '%s' by admin: %s", medicine.medicine_name, request.user.username)
            messages.success(request, f"Medicine '{medicine.medicine_name}' updated successfully.")
            return redirect('manage_medicines')
    else:
        form = MedicineForm(instance=medicine)
    return render(request, 'medicines/form.html', {'form': form, 'title': f"Edit: {medicine.medicine_name}"})
