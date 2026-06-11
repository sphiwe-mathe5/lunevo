from django.db import models
from clinics.models import Clinic

class Supplier(models.Model):
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    physical_address = models.TextField(blank=True, null=True)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='suppliers', null=True)
    notes = models.TextField(blank=True, null=True)
    notify_on_min_stock = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class SupplierNotificationLog(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='notification_logs')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='supplier_notifications')
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='supplier_notifications', null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('supplier', 'product', 'clinic')

    def __str__(self):
        return f"Notified {self.supplier.name} about {self.product.name} at {self.timestamp}"
