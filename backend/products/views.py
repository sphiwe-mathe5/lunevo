from rest_framework import viewsets
from rest_framework.filters import SearchFilter
from django.db.models import Sum, Q, Min
from django.db.models.functions import Coalesce
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError
from .models import Product, Category
from .serializers import ProductSerializer, CategorySerializer

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        user_clinic = self.request.user.clinic if hasattr(self.request.user, 'clinic') else None
        qs = Category.objects.all()
        if user_clinic:
            qs = qs.filter(clinic=user_clinic)
        return qs

    def perform_create(self, serializer):
        clinic = self.request.user.clinic if hasattr(self.request.user, 'clinic') else None
        try:
            serializer.save(clinic=clinic)
        except IntegrityError:
            raise ValidationError({"name": "A category with this name already exists for your clinic."})

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'code', 'barcode']

    def get_queryset(self):
        user_clinic = self.request.user.clinic if hasattr(self.request.user, 'clinic') else None
        
        if user_clinic:
            batch_filter = Q(batches__condition='available', batches__clinic=user_clinic)
        else:
            batch_filter = Q(batches__condition='available')

        qs = Product.objects.all()
        if user_clinic:
            qs = qs.filter(clinic=user_clinic)

        qs = qs.annotate(
            total_quantity=Coalesce(Sum('batches__quantity', filter=batch_filter), 0),
            nearest_expiry_date=Min('batches__expiry_date', filter=batch_filter & Q(batches__quantity__gt=0))
        )
        
        ordering = self.request.query_params.get('ordering')
        if ordering:
            if ordering == '-created_at':
                qs = qs.order_by('-created_at')
            elif ordering == 'name':
                qs = qs.order_by('name')
            elif ordering == '-total_quantity':
                qs = qs.order_by('-total_quantity')
            elif ordering == 'total_quantity':
                qs = qs.order_by('total_quantity')
            elif ordering == 'nearest_expiry_date':
                qs = qs.order_by(F('nearest_expiry_date').asc(nulls_last=True))
                
        return qs

    def perform_create(self, serializer):
        clinic = self.request.user.clinic if hasattr(self.request.user, 'clinic') else None
        serializer.save(clinic=clinic)
