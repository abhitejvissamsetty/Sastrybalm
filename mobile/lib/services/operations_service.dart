import 'package:dio/dio.dart';
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

  Future<Map<String, dynamic>> checkOut(
    int visitId, {
    String? notes,
    String? noOrderReason,
  }) async {
    final response = await _client.dio.post(
      '/visits/$visitId/checkout',
      queryParameters: {
        if (notes != null) 'notes': notes,
        if (noOrderReason != null) 'no_order_reason': noOrderReason,
      },
    );
    return response.data;
  }
}

class OrderService {
  final ApiClient _client;
  OrderService(this._client);

  Future<Map<String, dynamic>> createOrder({
    int? outletId,
    int? channelPartnerId,
    int? partyId,
    String? partyType,
    String orderType = "Secondary",
    required List<OrderItem> items,
    int? warehouseId,
    bool isCompanyOrder = false,
    bool isPaid = false,
    String? paymentType,
    String? paymentMode,
    String? paymentReference,
    String? deliveryAddress,
    int? visitId,
    int? beatId,
    String? notes,
  }) async {
    final response = await _client.dio.post(
      '/orders',
      queryParameters: {
        'order_type': orderType,
        if (outletId != null) 'outlet_id': outletId,
        if (channelPartnerId != null) 'channel_partner_id': channelPartnerId,
        if (partyId != null) 'party_id': partyId,
        if (partyType != null) 'party_type': partyType,
        if (warehouseId != null) 'warehouse_id': warehouseId,
        'is_company_order': isCompanyOrder,
        'is_paid': isPaid,
        if (paymentType != null) 'payment_type': paymentType,
        if (paymentMode != null) 'payment_mode': paymentMode,
        if (paymentReference != null) 'payment_reference': paymentReference,
        if (deliveryAddress != null) 'delivery_address': deliveryAddress,
        if (visitId != null) 'visit_id': visitId,
        if (beatId != null) 'beat_id': beatId,
        if (notes != null) 'notes': notes,
      },
      data: items.map((i) => i.toJson()).toList(),
    );
    return response.data;
  }

  Future<Map<String, dynamic>> getWarehouseContext({
    int? outletId,
    int? beatId,
  }) async {
    final response = await _client.dio.get(
      '/orders/warehouse-context',
      queryParameters: {
        if (outletId != null) 'outlet_id': outletId,
        if (beatId != null) 'beat_id': beatId,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> submitOrder(int orderId) async {
    final response = await _client.dio.patch('/orders/$orderId/submit');
    return response.data;
  }

  Future<List<dynamic>> getOutletTodayL1Orders(int outletId) async {
    final response = await _client.dio.get(
      '/orders/outlet-today-l1-orders',
      queryParameters: {'outlet_id': outletId},
    );
    return response.data['orders'] as List;
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

  Future<Map<String, dynamic>> getContext(int outletId) async {
    final response =
        await _client.dio.get('/outlets/$outletId/material-request-context');
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> submitRequest({
    required int outletId,
    required int productId,
    required String description,
    double? length,
    double? width,
    double? height,
    double? depth,
    String unit = 'cm',
    required String presentOutletImagePath,
    required String installationPlaceImagePath,
    required String customerApprovalLetterImagePath,
  }) async {
    final data = FormData.fromMap({
      'outlet_id': outletId,
      'product_id': productId,
      'description': description,
      if (length != null) 'dimension_length': length,
      if (width != null) 'dimension_width': width,
      if (height != null) 'dimension_height': height,
      if (depth != null) 'dimension_depth': depth,
      'dimension_unit': unit,
      'present_outlet_image':
          await MultipartFile.fromFile(presentOutletImagePath),
      'installation_place_image':
          await MultipartFile.fromFile(installationPlaceImagePath),
      'customer_approval_letter_image':
          await MultipartFile.fromFile(customerApprovalLetterImagePath),
    });
    final response = await _client.dio.post(
      '/material-requests',
      data: data,
    );
    return response.data as Map<String, dynamic>;
  }
}

class AssetCapitalizationService {
  final ApiClient _client;
  AssetCapitalizationService(this._client);

  Future<Map<String, dynamic>> getProducts(int outletId) async {
    final response = await _client.dio.get('/outlets/$outletId/asset-products');
    return response.data as Map<String, dynamic>;
  }

  Future<List<dynamic>> getAssets(int outletId) async {
    final response = await _client.dio.get('/outlets/$outletId/assets');
    return response.data['items'] as List<dynamic>;
  }

  Future<Map<String, dynamic>> createCapitalization({
    required int outletId,
    required int productId,
    int quantity = 1,
    String? notes,
    String? imagePath,
  }) async {
    final data = FormData.fromMap({
      'outlet_id': outletId,
      'product_id': productId,
      'quantity': quantity,
      if (notes != null && notes.isNotEmpty) 'notes': notes,
      if (imagePath != null) 'image': await MultipartFile.fromFile(imagePath),
    });
    final response = await _client.dio.post(
      '/asset-capitalizations',
      data: data,
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
    required String duration,
    String? halfDaySession,
    String? reason,
  }) async {
    final response = await _client.dio.post(
      '/leaves',
      data: {
        'leave_type': leaveType,
        'start_date': startDate,
        'end_date': endDate,
        'duration': duration,
        if (halfDaySession != null) 'half_day_session': halfDaySession,
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
