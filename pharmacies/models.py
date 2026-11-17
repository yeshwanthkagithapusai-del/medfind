from django.conf import settings
from django.db import models


class Pharmacy(models.Model):
    class ProviderType(models.TextChoices):
        PHARMACY = 'PHARMACY', 'Pharmacy'
        HOSPITAL = 'HOSPITAL', 'Hospital'

    class DataSource(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual User Registration'
        DATA_GOV_IN = 'DATA_GOV_IN', 'National Hospital Directory (data.gov.in)'
        ABDM = 'ABDM', 'ABDM Health Facility Registry'
        OSM = 'OSM', 'OpenStreetMap'
        DEMO = 'DEMO', 'Demonstration Seed Data'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pharmacies',
        verbose_name="Store Owner / Administrator"
    )
    provider_type = models.CharField(
        max_length=20,
        choices=ProviderType.choices,
        default=ProviderType.PHARMACY,
        db_index=True,
        verbose_name="Provider Type"
    )
    pharmacy_name = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Provider Name"
    )
    registration_number = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name="Registration / License Number"
    )
    address = models.TextField(verbose_name="Street Address")
    city = models.CharField(max_length=100, db_index=True)
    district = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name="District"
    )
    state = models.CharField(max_length=100, db_index=True)
    pincode = models.CharField(max_length=20, db_index=True)
    phone_number = models.CharField(max_length=50, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate for map display"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate for map display"
    )
    source_name = models.CharField(
        max_length=50,
        choices=DataSource.choices,
        default=DataSource.MANUAL,
        db_index=True,
        verbose_name="Original Data Source"
    )
    source_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name="External Source Identifier",
        help_text="Stable identifier from origin registry (e.g. NIN code or OSM node ID)"
    )
    is_approved = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Admin Approval Status"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Active Status"
    )
    is_demo = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Demo Record Flag"
    )
    last_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last Verified Date"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Import / Registration Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Last Updated Date")

    class Meta:
        verbose_name = "Healthcare Provider / Pharmacy"
        verbose_name_plural = "Healthcare Providers & Pharmacies"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_approved', 'city'], name='pharm_appr_city_idx'),
            models.Index(fields=['is_approved', 'pincode'], name='pharm_appr_pincode_idx'),
            models.Index(fields=['is_approved', '-created_at'], name='pharm_appr_created_idx'),
            models.Index(fields=['provider_type', 'is_approved', 'city'], name='prov_type_appr_city_idx'),
            models.Index(fields=['provider_type', 'is_approved', 'pincode'], name='prov_type_appr_pin_idx'),
            models.Index(fields=['state', 'district', 'city'], name='prov_geo_idx'),
            models.Index(fields=['latitude', 'longitude'], name='prov_coords_idx'),
            models.Index(fields=['source_name', 'source_id'], name='prov_source_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['source_name', 'source_id'],
                condition=models.Q(source_id__gt=''),
                name='unique_source_facility'
            )
        ]

    def __str__(self):
        type_str = "Hospital" if self.provider_type == self.ProviderType.HOSPITAL else "Pharmacy"
        approval_str = "Approved" if self.is_approved else "Pending Approval"
        return f"{self.pharmacy_name} ({type_str}) - {self.city} ({approval_str})"

    @property
    def provider_name(self):
        """Aliases pharmacy_name for generic healthcare provider contexts."""
        return self.pharmacy_name
