from django.db import models

class Clinic(models.Model):
    SUBSCRIPTION_CHOICES = [
        ('trial', 'Trial'),
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True)
    contact_person = models.CharField(max_length=255)
    contact_email = models.EmailField()
    contact_number = models.CharField(max_length=50)
    physical_address = models.TextField()
    
    subscription_plan = models.CharField(max_length=50, choices=SUBSCRIPTION_CHOICES, default='trial')
    subscription_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
