from django.conf import settings
from django.db import models

class Pharmacy(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pharmacies'
    )
    pharmacy_name = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Pharmacy Name"
    )
    registration_number = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name="Registration / License Number"
    )
    address = models.TextField(verbose_name="Street Address")
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20, db_index=True)
    phone_number = models.CharField(max_length=15)
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
    is_approved = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Admin Approval Status"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pharmacy"
        verbose_name_plural = "Pharmacies"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_approved', 'city'], name='pharm_appr_city_idx'),
            models.Index(fields=['is_approved', 'pincode'], name='pharm_appr_pincode_idx'),
            models.Index(fields=['is_approved', '-created_at'], name='pharm_appr_created_idx'),
        ]

    def __str__(self):
        approval_str = "Approved" if self.is_approved else "Pending Approval"
        return f"{self.pharmacy_name} - {self.city} ({approval_str})"
