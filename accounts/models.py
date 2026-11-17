from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('CUSTOMER', 'Customer'),
        ('PHARMACY', 'Pharmacy Owner'),
        ('ADMIN', 'Administrator'),
    )
    
    email = models.EmailField(unique=True, verbose_name="Email Address")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CUSTOMER', db_index=True)
    phone_number = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['role', '-date_joined'], name='user_role_joined_idx'),
        ]

    @property
    def is_customer(self):
        return self.role == 'CUSTOMER'
        
    @property
    def is_pharmacy_owner(self):
        return self.role == 'PHARMACY'
        
    @property
    def is_admin_user(self):
        return self.role == 'ADMIN' or self.is_superuser or self.is_staff

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
