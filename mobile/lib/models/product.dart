class Product {
  final int id;
  final String name;
  final String? erpId;
  final String? sku;
  final String? division;
  final String? primaryCategory;
  final String? secondaryCategory;
  final double? mrp;
  final double gstRate;
  final bool mustSell;
  final bool isStockableItem;
  final String categoryScope;
  final int? warehouseId;
  final int warehouseStockQty;

  Product({
    required this.id,
    required this.name,
    this.erpId,
    this.sku,
    this.division,
    this.primaryCategory,
    this.secondaryCategory,
    this.mrp,
    required this.gstRate,
    required this.mustSell,
    this.isStockableItem = true,
    this.categoryScope = "Sale",
    this.warehouseId,
    this.warehouseStockQty = 0,
  });

  factory Product.fromJson(Map<String, dynamic> json) => Product(
        id: json['id'],
        name: json['name'],
        erpId: json['erp_id'],
        sku: json['sku'],
        division: json['division'],
        primaryCategory: json['primary_category'],
        secondaryCategory: json['secondary_category'],
        mrp: (json['mrp'] as num?)?.toDouble(),
        gstRate: (json['gst_rate'] as num?)?.toDouble() ?? 0.0,
        mustSell: json['must_sell'] ?? false,
        isStockableItem: json['is_stockable_item'] == 1 ||
            json['is_stockable_item'] == true ||
            json['is_stockable_item'] == null,
        categoryScope:
            json['category_scope'] ?? json['category_type'] ?? "Sale",
        warehouseId: json['warehouse_id'] as int?,
        warehouseStockQty: (json['warehouse_stock_qty'] as num?)?.toInt() ?? 0,
      );
}

class OrderItem {
  final int productId;
  final String productName;
  int quantity;
  final double unitPrice;
  final double gstRate;
  final double discountPct;

  OrderItem({
    required this.productId,
    required this.productName,
    required this.quantity,
    required this.unitPrice,
    required this.gstRate,
    this.discountPct = 0,
  });

  double get lineTotal {
    final baseWithGst = unitPrice * quantity * (1 - discountPct / 100);
    return baseWithGst;
  }

  Map<String, dynamic> toJson() => {
        'product_id': productId,
        'quantity': quantity,
        'unit_price': unitPrice,
        'gst_rate': gstRate,
        'discount_pct': discountPct,
      };
}

class Order {
  final int id;
  final String orderNumber;
  final String status;
  final String? outletName;
  final double totalAmount;
  final String orderDate;

  Order({
    required this.id,
    required this.orderNumber,
    required this.status,
    this.outletName,
    required this.totalAmount,
    required this.orderDate,
  });

  factory Order.fromJson(Map<String, dynamic> json) => Order(
        id: json['id'],
        orderNumber: json['order_number'],
        status: json['status'],
        outletName: json['outlet_name'],
        totalAmount: (json['total_amount'] as num?)?.toDouble() ?? 0.0,
        orderDate: json['order_date'],
      );
}
