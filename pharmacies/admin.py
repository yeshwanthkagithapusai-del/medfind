from django.contrib import admin
from .models import Pharmacy

@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display = ('pharmacy_name', 'registration_number', 'city', 'state', 'phone_number', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'city', 'state')
    search_fields = ('pharmacy_name', 'registration_number', 'city', 'pincode', 'phone_number')
    actions = ['approve_pharmacies', 'revoke_approval']

    @admin.action(description="Approve selected pharmacies")
    def approve_pharmacies(self, request, queryset):
        count = queryset.update(is_approved=True)
        self.message_user(request, f"Successfully approved {count} pharmacies.")

    @admin.action(description="Revoke approval for selected pharmacies")
    def revoke_approval(self, request, queryset):
        count = queryset.update(is_approved=False)
        self.message_user(request, f"Revoked approval for {count} pharmacies.")
