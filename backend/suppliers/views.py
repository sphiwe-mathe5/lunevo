from rest_framework import viewsets
from rest_framework.filters import SearchFilter
from .models import Supplier
from .serializers import SupplierSerializer

class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'contact_person', 'email']

    def get_queryset(self):
        user_clinic = self.request.user.clinic if hasattr(self.request.user, 'clinic') else None
        qs = Supplier.objects.all()
        if user_clinic:
            qs = qs.filter(clinic=user_clinic)
        return qs

    def perform_create(self, serializer):
        clinic = self.request.user.clinic if hasattr(self.request.user, 'clinic') else None
        serializer.save(clinic=clinic)
