from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from medicines.models import Medicine
from pharmacies.models import Pharmacy

class AvailabilityRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Pharmacy Review'),
        ('CONFIRMED', 'Confirmed Available'),
        ('UNAVAILABLE', 'Reported Unavailable'),
        ('CANCELLED', 'Cancelled by Customer'),
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_requests'
    )
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name='pharmacy_requests'
    )
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name='availability_requests'
    )
    quantity_requested = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1, message="Must request at least 1 unit.")]
    )
    request_message = models.TextField(
        blank=True,
        help_text="Optional note for the pharmacist (e.g., dosage urgency, preferred pickup time)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    pharmacy_response = models.TextField(
        blank=True,
        help_text="Response message or pickup instructions from the pharmacist"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Availability Request"
        verbose_name_plural = "Availability Requests"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status'], name='req_cust_status_idx'),
            models.Index(fields=['customer', '-created_at'], name='req_cust_created_idx'),
            models.Index(fields=['pharmacy', 'status'], name='req_pharm_status_idx'),
            models.Index(fields=['pharmacy', '-created_at'], name='req_pharm_created_idx'),
        ]

    def __str__(self):
        return f"Req #{self.id}: {self.medicine.medicine_name} from {self.customer.username} -> {self.pharmacy.pharmacy_name} ({self.status})"


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read'], name='notif_user_read_idx'),
            models.Index(fields=['user', '-created_at'], name='notif_user_created_idx'),
        ]

    def __str__(self):
        read_badge = "Read" if self.is_read else "Unread"
        return f"[{read_badge}] For {self.user.username}: {self.message[:40]}"
