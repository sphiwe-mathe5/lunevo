from django.utils import timezone
from django.db.models import Sum, Q, F
from django.db.models.functions import Coalesce
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import Batch, Alert
from products.models import Product
from suppliers.models import SupplierNotificationLog
from clinics.models import Clinic

def sync_alerts_system_wide():
    """
    Synchronizes alerts across all clinics. Used by the background notification engine
    and the manual sync API endpoint.
    """
    clinics = list(Clinic.objects.all()) + [None]

    for clinic in clinics:
        # 1. Low Stock Logic
        batch_filter = Q(batches__condition='available')
        if clinic:
            batch_filter &= Q(batches__clinic=clinic)

        products = Product.objects.annotate(
            total_quantity=Coalesce(Sum('batches__quantity', filter=batch_filter), 0)
        )
        
        for p in products:
            if p.total_quantity == 0:
                # Check if this clinic has EVER received this product.
                # If not, it shouldn't show as "Out of stock" randomly.
                has_received = Batch.objects.filter(product=p)
                if clinic:
                    has_received = has_received.filter(clinic=clinic)
                if has_received.exists():
                    _create_or_update_alert('critical', f"{p.name} is completely out of stock.", product=p, clinic=clinic)
                    _trigger_supplier_notification(p, clinic)
            elif p.total_quantity <= p.min_stock_level:
                _create_or_update_alert('warning', f"{p.name} is running low (Qty: {p.total_quantity}, Min: {p.min_stock_level}).", product=p, clinic=clinic)
                _trigger_supplier_notification(p, clinic)
            else:
                _resolve_auto_alerts(product=p, severity_list=['critical', 'warning'], message_contains="stock", clinic=clinic)

        # 2. Expiry Logic
        today = timezone.now().date()
        batches = Batch.objects.filter(quantity__gt=0, condition='available')
        if clinic:
            batches = batches.filter(clinic=clinic)

        for b in batches:
            days_to_expiry = (b.expiry_date - today).days
            if days_to_expiry < 0:
                b.condition = 'expired'
                b.save()
                _create_or_update_alert('critical', f"Batch {b.batch_number} of {b.product.name} has expired and needs write-off.", product=b.product, batch=b, clinic=b.clinic)
            elif days_to_expiry <= 7:
                _create_or_update_alert('critical', f"Batch {b.batch_number} of {b.product.name} expires in {days_to_expiry} days.", product=b.product, batch=b, clinic=b.clinic)
            elif days_to_expiry <= 30:
                _create_or_update_alert('warning', f"Batch {b.batch_number} of {b.product.name} expires in {days_to_expiry} days.", product=b.product, batch=b, clinic=b.clinic)
            else:
                _resolve_auto_alerts(batch=b, message_contains="expire", clinic=b.clinic)

        # 3. Damaged/Quarantined Logic
        bad_batches = Batch.objects.exclude(condition='available').filter(quantity__gt=0)
        if clinic:
            bad_batches = bad_batches.filter(clinic=clinic)

        for b in bad_batches:
            if b.condition == 'damaged':
                _create_or_update_alert('critical', f"Batch {b.batch_number} of {b.product.name} is marked as damaged.", product=b.product, batch=b, clinic=b.clinic)
            elif b.condition == 'quarantined':
                _create_or_update_alert('warning', f"Batch {b.batch_number} of {b.product.name} is quarantined.", product=b.product, batch=b, clinic=b.clinic)
            elif b.condition == 'expired':
                _create_or_update_alert('critical', f"Batch {b.batch_number} of {b.product.name} has expired and needs write-off.", product=b.product, batch=b, clinic=b.clinic)

def _create_or_update_alert(severity, message, product=None, batch=None, clinic=None):
    Alert.objects.get_or_create(
        severity=severity,
        message=message,
        product=product,
        batch=batch,
        clinic=clinic,
        status='unresolved'
    )

def _resolve_auto_alerts(product=None, batch=None, severity_list=None, message_contains=None, clinic=None):
    qs = Alert.objects.filter(status='unresolved')
    if product: qs = qs.filter(product=product)
    if batch: qs = qs.filter(batch=batch)
    if severity_list: qs = qs.filter(severity__in=severity_list)
    if message_contains: qs = qs.filter(message__icontains=message_contains)
    if clinic: qs = qs.filter(clinic=clinic)
    
    for alert in qs:
        alert.status = 'resolved'
        alert.resolved_at = timezone.now()
        alert.save()

def _trigger_supplier_notification(product, clinic):
    # Find the most recent batch for this product in this clinic
    recent_batch = Batch.objects.filter(product=product).order_by('-created_at')
    if clinic:
        recent_batch = recent_batch.filter(clinic=clinic)
    recent_batch = recent_batch.first()
    
    if not recent_batch or not recent_batch.supplier:
        return
        
    supplier = recent_batch.supplier
    if not supplier.notify_on_min_stock or not supplier.email:
        return
        
    # Check deduplication: Don't email if we already emailed in the last 7 days
    seven_days_ago = timezone.now() - timezone.timedelta(days=7)
    recent_log = SupplierNotificationLog.objects.filter(
        supplier=supplier,
        product=product,
        clinic=clinic,
        timestamp__gte=seven_days_ago
    ).exists()
    
    if recent_log:
        return
        
    # Send email
    context = {
        'supplier': supplier,
        'product': product,
        'clinic': clinic,
        'recent_batch': recent_batch
    }
    html_message = render_to_string('emails/supplier_restock.html', context)
    plain_message = strip_tags(html_message)
    
    clinic_name = clinic.name if clinic else "Lunevo Campus"
    
    try:
        msg = EmailMultiAlternatives(
            subject=f"Restock Request from {clinic_name}: {product.name}",
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[supplier.email],
        )
        msg.attach_alternative(html_message, "text/html")
        msg.send()
        
        # Log it
        SupplierNotificationLog.objects.create(
            supplier=supplier,
            product=product,
            clinic=clinic
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send supplier restock email to {supplier.email}: {e}")
