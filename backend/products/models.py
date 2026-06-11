from django.db import models
from clinics.models import Clinic

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='categories', null=True)

    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ('name', 'clinic')

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    unit_type = models.CharField(max_length=50, help_text="e.g., Box, Bottle, Tablet, Unit")
    description = models.TextField(blank=True, null=True)
    barcode = models.CharField(max_length=255, blank=True, null=True)
    qr_code = models.CharField(max_length=255, blank=True, null=True)
    min_stock_level = models.PositiveIntegerField(default=10)
    max_stock_level = models.PositiveIntegerField(default=1000)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='products', null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('code', 'clinic')

    def __str__(self):
        return f"{self.name} ({self.code})"
