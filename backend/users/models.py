from django.db import models
from django.contrib.auth.models import AbstractUser
from clinics.models import Clinic

class User(AbstractUser):
    ROLE_CHOICES = [
        ('nurse', 'Nurse'),
        ('inventory_officer', 'Inventory Officer'),
        ('clinic_manager', 'Clinic Manager'),
        ('clinic_administrator', 'Clinic Administrator'),
    ]

    staff_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='nurse')
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='users', null=True)
    
    # Override email to make it unique
    email = models.EmailField(unique=True)

    # Preferences
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    email_notifications = models.BooleanField(default=True)
    low_stock_alerts = models.BooleanField(default=True)
    expiry_alerts = models.CharField(max_length=20, default='30_days')
    table_view = models.CharField(max_length=20, default='comfortable')

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"
