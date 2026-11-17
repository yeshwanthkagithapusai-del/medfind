from django.contrib import admin
from .models import Inventory

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('pharmacy', 'medicine', 'quantity', 'availability_status', 'updated_at')
    list_filter = ('availability_status', 'pharmacy__city')
    search_fields = ('pharmacy__pharmacy_name', 'medicine__medicine_name', 'medicine__generic_name')
