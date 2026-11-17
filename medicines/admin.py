from django.contrib import admin
from .models import Medicine

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('medicine_name', 'generic_name', 'strength', 'dosage_form', 'category', 'created_at')
    list_filter = ('category', 'dosage_form')
    search_fields = ('medicine_name', 'generic_name', 'strength')
