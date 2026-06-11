import json
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from datetime import timedelta
from products.models import Product
from suppliers.models import Supplier
from inventory.models import Batch, StockTransaction, Alert

def get_product_stock(product_name: str, clinic=None) -> str:
    """Retrieve current stock levels and details for a specific product by name."""
    products = Product.objects.filter(name__icontains=product_name)
    if clinic:
        products = products.filter(clinic=clinic)

    if not products.exists():
        return json.dumps({"error": f"No product found matching '{product_name}'"})
    
    results = []
    for product in products:
        batch_filter = Q(condition='available')
        if clinic:
            batch_filter &= Q(clinic=clinic)
            
        total_qty = product.batches.filter(batch_filter).aggregate(Sum('quantity'))['quantity__sum'] or 0
        active_batches = list(product.batches.filter(batch_filter, quantity__gt=0).values('batch_number', 'quantity', 'expiry_date'))
        
        # Format dates as strings
        for b in active_batches:
            b['expiry_date'] = b['expiry_date'].strftime('%Y-%m-%d') if b['expiry_date'] else None
            
        results.append({
            "product_name": product.name,
            "product_code": product.code,
            "total_quantity": total_qty,
            "min_stock_level": product.min_stock_level,
            "active_batches": active_batches
        })
    return json.dumps(results)

def get_low_stock_products(clinic=None) -> str:
    """Retrieve a list of all products whose total available quantity is below their minimum stock level."""
    products = Product.objects.all()
    if clinic:
        products = products.filter(clinic=clinic)
        
    low_stock = []
    
    for product in products:
        batch_filter = Q(condition='available')
        if clinic:
            batch_filter &= Q(clinic=clinic)
            
        total_qty = product.batches.filter(batch_filter).aggregate(Sum('quantity'))['quantity__sum'] or 0
        if total_qty < product.min_stock_level:
            low_stock.append({
                "product_name": product.name,
                "current_quantity": total_qty,
                "minimum_required": product.min_stock_level,
                "deficit": product.min_stock_level - total_qty
            })
            
    return json.dumps(low_stock)

def get_expiring_products(days: int, clinic=None) -> str:
    """Retrieve products with batches expiring within the specified number of days."""
    today = timezone.now().date()
    target_date = today + timedelta(days=days)
    
    batch_filter = Q(
        condition='available',
        quantity__gt=0,
        expiry_date__lte=target_date,
        expiry_date__gte=today
    )
    if clinic:
        batch_filter &= Q(clinic=clinic)
        
    expiring_batches = Batch.objects.filter(batch_filter).select_related('product').order_by('expiry_date')
    
    results = []
    for batch in expiring_batches:
        days_left = (batch.expiry_date - today).days
        results.append({
            "product_name": batch.product.name,
            "batch_number": batch.batch_number,
            "quantity": batch.quantity,
            "expiry_date": batch.expiry_date.strftime('%Y-%m-%d'),
            "days_remaining": days_left
        })
    return json.dumps(results)

def get_expired_batches(clinic=None) -> str:
    """Retrieve all batches that have expired but still have physical quantity in the system."""
    today = timezone.now().date()
    
    cond1 = Q(quantity__gt=0, condition='expired')
    cond2 = Q(quantity__gt=0, expiry_date__lt=today)
    
    expired_batches = Batch.objects.filter(cond1 | cond2).select_related('product')
    if clinic:
        expired_batches = expired_batches.filter(clinic=clinic)
        
    expired_batches = expired_batches.distinct().order_by('expiry_date')
    
    results = []
    for batch in expired_batches:
        results.append({
            "product_name": batch.product.name,
            "batch_number": batch.batch_number,
            "quantity": batch.quantity,
            "expiry_date": batch.expiry_date.strftime('%Y-%m-%d')
        })
    return json.dumps(results)

def get_inventory_summary(clinic=None) -> str:
    """Get a high-level summary of the entire inventory health."""
    products = Product.objects.all()
    if clinic:
        products = products.filter(clinic=clinic)
        
    total_products = products.count()
    
    # Calculate low stock
    low_stock_count = 0
    for p in products:
        batch_filter = Q(condition='available')
        if clinic:
            batch_filter &= Q(clinic=clinic)
        qty = p.batches.filter(batch_filter).aggregate(Sum('quantity'))['quantity__sum'] or 0
        if qty < p.min_stock_level:
            low_stock_count += 1
    
    today = timezone.now().date()
    
    exp_filter = Q(
        condition='available', quantity__gt=0, 
        expiry_date__lte=today + timedelta(days=30),
        expiry_date__gte=today
    )
    if clinic:
        exp_filter &= Q(clinic=clinic)
    expiring_30_days = Batch.objects.filter(exp_filter).count()
    
    expired_filter = Q(quantity__gt=0, expiry_date__lt=today)
    if clinic:
        expired_filter &= Q(clinic=clinic)
    expired_qty = Batch.objects.filter(expired_filter).aggregate(Sum('quantity'))['quantity__sum'] or 0
    
    alert_filter = Q(status='unresolved')
    if clinic:
        alert_filter &= Q(clinic=clinic)
    unresolved_alerts = Alert.objects.filter(alert_filter).count()
    
    summary = {
        "total_unique_products": total_products,
        "products_low_on_stock": low_stock_count,
        "batches_expiring_in_30_days": expiring_30_days,
        "total_expired_units_awaiting_disposal": expired_qty,
        "active_system_alerts": unresolved_alerts
    }
    return json.dumps(summary)

def get_top_issued_products(clinic=None) -> str:
    """Retrieve the most issued products in the last 30 days to identify fast movers."""
    last_30_days = timezone.now() - timedelta(days=30)
    
    tx_filter = Q(transaction_type='issue', timestamp__gte=last_30_days)
    if clinic:
        tx_filter &= Q(clinic=clinic)
        
    top_issued = StockTransaction.objects.filter(tx_filter).values('product__name').annotate(
        total_issued=Sum('quantity')
    ).order_by('-total_issued')[:10]
    
    results = [{"product_name": item['product__name'], "total_issued_30_days": item['total_issued']} for item in top_issued]
    return json.dumps(results)

def get_supplier_statistics(clinic=None) -> str:
    """Retrieve statistics on which suppliers have provided the most stock."""
    batch_filter = ~Q(supplier__isnull=True)
    if clinic:
        batch_filter &= Q(clinic=clinic)
        
    stats = Batch.objects.filter(batch_filter).values('supplier__name').annotate(
        total_batches=Count('id'),
        total_units_supplied=Sum('quantity')
    ).order_by('-total_units_supplied')[:10]
    
    results = [{"supplier_name": item['supplier__name'], "total_batches": item['total_batches'], "total_units": item['total_units_supplied']} for item in stats]
    return json.dumps(results)

def get_recent_stock_movements(clinic=None) -> str:
    """Retrieve the 10 most recent stock issues or receipts."""
    qs = StockTransaction.objects.select_related('product', 'user')
    if clinic:
        qs = qs.filter(clinic=clinic)
        
    recent_txs = qs.order_by('-timestamp')[:10]
    
    results = []
    for tx in recent_txs:
        results.append({
            "action": tx.transaction_type,
            "product_name": tx.product.name,
            "quantity": tx.quantity,
            "user": tx.user.get_full_name() if tx.user else "System",
            "time": tx.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    return json.dumps(results)

def get_write_off_summary(clinic=None) -> str:
    """Retrieve a summary of recent stock write-offs / disposals."""
    qs = StockTransaction.objects.filter(transaction_type='issue', reason='expired').select_related('product')
    if clinic:
        qs = qs.filter(clinic=clinic)
        
    write_offs = qs.order_by('-timestamp')[:10]
    
    results = []
    for w in write_offs:
        results.append({
            "product_name": w.product.name,
            "quantity_disposed": w.quantity,
            "date": w.timestamp.strftime('%Y-%m-%d'),
            "user": w.user.get_full_name() if w.user else "System",
            "notes": w.notes
        })
    return json.dumps(results)

# Map of tool names to their actual python functions
AI_TOOLS_MAP = {
    "get_product_stock": get_product_stock,
    "get_low_stock_products": get_low_stock_products,
    "get_expiring_products": get_expiring_products,
    "get_expired_batches": get_expired_batches,
    "get_inventory_summary": get_inventory_summary,
    "get_top_issued_products": get_top_issued_products,
    "get_supplier_statistics": get_supplier_statistics,
    "get_recent_stock_movements": get_recent_stock_movements,
    "get_write_off_summary": get_write_off_summary,
}

# OpenAI JSON Schemas for these tools
AI_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_product_stock",
            "description": "Get current stock levels, active batches, and expiry dates for a specific product by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The name of the product (e.g., 'Panado')"
                    }
                },
                "required": ["product_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_low_stock_products",
            "description": "Get a list of all products that are currently below their minimum required stock level.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_expiring_products",
            "description": "Get a list of product batches that will expire within the specified number of days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days from today to check for expiry (e.g., 7, 30)"
                    }
                },
                "required": ["days"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_expired_batches",
            "description": "Get a list of all batches that have already expired but still have physical stock in the system.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_summary",
            "description": "Get a high-level summary of the entire inventory health, including counts of low stock items, expiring items, and active alerts.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_issued_products",
            "description": "Get a list of the most frequently issued (fastest moving) products over the last 30 days.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_supplier_statistics",
            "description": "Get statistics on which suppliers have provided the most stock.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_stock_movements",
            "description": "Get a log of the most recent stock issues and receipts.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_write_off_summary",
            "description": "Get a summary of recent stock write-offs and disposals.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]
