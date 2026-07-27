import '../utils/date_formatter.dart';
import '../models/attendance.dart';
import '../models/product.dart';
import 'api_client.dart';

class VisitService {
  final ApiClient _client;
  VisitService(this._client);

  Future<VisitRecord> checkIn({
    required int outletId,
    required double lat,
    required double lng,
    String? purpose,
  }) async {
    final response = await _client.dio.post(
      '/visits',
      queryParameters: {
        'outlet_id': outletId,
        'gps_lat': lat,
        'gps_lng': lng,
        if (purpose != null) 'purpose': purpose,
      },
    );
    final data = response.data as Map<String, dynamic>;
    return VisitRecord(
      id: data['id'],
      outletId: outletId,
      distanceFromOutlet: (data['distance_from_outlet'] as num?)?.toDouble(),
      visitTime: DateFormatter.parseDateTime(data['visit_time']),
    );
  }

  Future<Map<String, dynamic>> checkOut(int visitId) async {
    final response = await _client.dio.post('/visits/$visitId/checkout');
    return response.data;
  }
}

class OrderService {
  final ApiClient _client;
  OrderService(this._client);

  Future<Map<String, dynamic>> createOrder({
    required int outletId,
    required List<OrderItem> items,
    int? beatId,
    String? notes,
  }) async {
    final response = await _client.dio.post(
      '/orders',
      queryParameters: {
        'outlet_id': outletId,
        if (beatId != null) 'beat_id': beatId,
        if (notes != null) 'notes': notes,
      },
      data: items.map((i) => i.toJson()).toList(),
    );
    return response.data;
  }

  Future<Map<String, dynamic>> submitOrder(int orderId) async {
    final response = await _client.dio.patch('/orders/$orderId/submit');
    return response.data;
  }

  Future<List<dynamic>> getMyOrders({int page = 1}) async {
    final response = await _client.dio.get(
      '/orders/my',
      queryParameters: {'page': page, 'per_page': 20},
    );
    return response.data['items'] as List;
  }

  Future<Map<String, dynamic>> getOrder(int orderId) async {
    final response = await _client.dio.get('/orders/$orderId');
    return response.data as Map<String, dynamic>;
  }
}

class PaymentService {
  final ApiClient _client;
  PaymentService(this._client);

  Future<Map<String, dynamic>> collectPayment({
    required int outletId,
    required double amount,
    required String method,
    int? orderId,
    String? transactionRef,
    Map<String, int> denominations = const {},
  }) async {
    final response = await _client.dio.post(
      '/payments',
      queryParameters: {
        'outlet_id': outletId,
        'amount': amount,
        'method': method,
        if (orderId != null) 'order_id': orderId,
        if (transactionRef != null) 'transaction_ref': transactionRef,
        'denom_2000': denominations['2000'] ?? 0,
        'denom_500': denominations['500'] ?? 0,
        'denom_200': denominations['200'] ?? 0,
        'denom_100': denominations['100'] ?? 0,
        'denom_50': denominations['50'] ?? 0,
        'denom_20': denominations['20'] ?? 0,
        'denom_10': denominations['10'] ?? 0,
      },
    );
    return response.data;
  }

  Future<Map<String, dynamic>> submitPayments({
    required List<int> paymentIds,
    String? notes,
  }) async {
    final response = await _client.dio.post(
      '/payment-submissions',
      data: {
        'payment_ids': paymentIds,
        if (notes != null) 'notes': notes,
      },
    );
    return response.data;
  }
}

class ExpenseService {
  final ApiClient _client;
  ExpenseService(this._client);

  Future<Map<String, dynamic>> logExpense({
    required String category,
    required double amount,
    String? description,
    String? expenseDate,
  }) async {
    final response = await _client.dio.post(
      '/expenses',
      queryParameters: {
        'category': category,
        'amount': amount,
        if (description != null) 'description': description,
        if (expenseDate != null) 'expense_date': expenseDate,
      },
    );
    return response.data;
  }

  Future<List<dynamic>> getMyExpenses() async {
    final response = await _client.dio.get('/expenses/my-expenses');
    return response.data['items'] as List;
  }
}

class MaterialRequestService {
  final ApiClient _client;
  MaterialRequestService(this._client);

  Future<Map<String, dynamic>> submitRequest({
    required int outletId,
    required String description,
    String? category,
    String? approxDimensions,
    String? clientNotes,
    String? materialSpecifications,
  }) async {
    final response = await _client.dio.post(
      '/material-requests',
      queryParameters: {
        'outlet_id': outletId,
        'description': description,
        if (category != null) 'category': category,
        if (approxDimensions != null) 'approx_dimensions': approxDimensions,
        if (clientNotes != null) 'client_notes': clientNotes,
        if (materialSpecifications != null) 'material_specifications': materialSpecifications,
      },
    );
    return response.data;
  }
}

class AssetCapitalizationService {
  final ApiClient _client;
  AssetCapitalizationService(this._client);

  Future<Map<String, dynamic>> createCapitalization({
    required int outletId,
    required String itemName,
    String? itemCode,
    int quantity = 1,
    String? warehouseName,
    String deployedBy = 'rep',
    String? notes,
  }) async {
    final response = await _client.dio.post(
      '/asset-capitalizations',
      queryParameters: {
        'outlet_id': outletId,
        'item_name': itemName,
        if (itemCode != null && itemCode.isNotEmpty) 'item_code': itemCode,
        'quantity': quantity,
        if (warehouseName != null && warehouseName.isNotEmpty)
          'warehouse_name': warehouseName,
        'deployed_by': deployedBy,
        if (notes != null && notes.isNotEmpty) 'notes': notes,
      },
    );
    return response.data as Map<String, dynamic>;
  }
}

class LeaveService {
  final ApiClient _client;
  LeaveService(this._client);

  Future<Map<String, dynamic>> applyLeave({
    required String leaveType,
    required String startDate,
    required String endDate,
    String? reason,
  }) async {
    final response = await _client.dio.post(
      '/leaves',
      data: {
        'leave_type': leaveType,
        'start_date': startDate,
        'end_date': endDate,
        if (reason != null) 'reason': reason,
      },
    );
    return response.data;
  }

  Future<List<dynamic>> getMyLeaves() async {
    final response = await _client.dio.get('/leaves/my-leaves');
    return response.data['items'] as List;
  }
}

class AnalyticsService {
  final ApiClient _client;
  AnalyticsService(this._client);

  Future<Map<String, dynamic>> getEis() async {
    final response = await _client.dio.get('/analytics/eis');
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getMis() async {
    final response = await _client.dio.get('/analytics/mis');
    return response.data as Map<String, dynamic>;
  }
}


