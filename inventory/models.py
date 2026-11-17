from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from medicines.models import Medicine
from pharmacies.models import Pharmacy

class Inventory(models.Model):
    STATUS_CHOICES = (
        ('IN_STOCK', 'In Stock'),
        ('LOW_STOCK', 'Low Stock (< 10 units)'),
        ('OUT_OF_STOCK', 'Out of Stock'),
    )

    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name='inventories'
    )
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name='pharmacy_inventories'
    )
    quantity = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0, message="Stock quantity cannot be negative.")]
    )
    availability_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='OUT_OF_STOCK',
        db_index=True
    )
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"
        unique_together = ('pharmacy', 'medicine')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['pharmacy', 'availability_status'], name='inv_pharm_status_idx'),
            models.Index(fields=['pharmacy', '-updated_at'], name='inv_pharm_updated_idx'),
            models.Index(fields=['availability_status', '-updated_at'], name='inv_status_updated_idx'),
        ]

    def clean(self):
        super().clean()
        if self.quantity is not None and self.quantity < 0:
            raise ValidationError({'quantity': "Stock quantity cannot be negative."})

    def save(self, *args, **kwargs):
        # Auto-compute status on save
        if self.quantity > 10:
            self.availability_status = 'IN_STOCK'
        elif self.quantity > 0:
            self.availability_status = 'LOW_STOCK'
        else:
            self.availability_status = 'OUT_OF_STOCK'
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicine.medicine_name} at {self.pharmacy.pharmacy_name}: {self.quantity} ({self.get_availability_status_display()})"

    @property
    def is_stale(self):
        """Returns True if the inventory record has not been updated within 24 hours."""
        import datetime
        from django.utils import timezone
        if not self.updated_at:
            return False
        return (timezone.now() - self.updated_at) > datetime.timedelta(hours=24)

    @property
    def freshness_tier(self):
        """
        Classifies stock updates into three distinct clinical freshness tiers:
        - 'FRESH': updated within 24 hours
        - 'MODERATE': updated between 24 and 48 hours
        - 'STALE': updated > 48 hours ago (requires customer inquiry to confirm)
        """
        import datetime
        from django.utils import timezone
        if not self.updated_at:
            return 'STALE'
        elapsed = timezone.now() - self.updated_at
        if elapsed <= datetime.timedelta(hours=24):
            return 'FRESH'
        elif elapsed <= datetime.timedelta(hours=48):
            return 'MODERATE'
        else:
            return 'STALE'

    @property
    def freshness_label(self):
        tier = self.freshness_tier
        if tier == 'FRESH':
            return 'Verified Fresh (< 24h)'
        elif tier == 'MODERATE':
            return 'Moderate (24-48h ago)'
        else:
            return 'Stale Stock (> 48h ago)'
