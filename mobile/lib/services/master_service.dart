import '../models/outlet.dart';
import '../models/product.dart';
import 'api_client.dart';

class MasterService {
  final ApiClient _client;
  MasterService(this._client);

  Future<Map<String, dynamic>> fetchBeatPlan(int beatId) async {
    final response = await _client.dio.get(
      '/beats/daily-plan',
      queryParameters: {'beat_id': beatId},
    );
    final data = response.data as Map<String, dynamic>;
    return {
      'beat': data['beat'] != null ? Beat.fromJson(data['beat']) : null,
      'outlets': (data['outlets'] as List)
          .map((o) => Outlet.fromJson(o))
          .toList(),
    };
  }

  Future<List<Outlet>> fetchOutlets({int? beatId, int page = 1}) async {
    final response = await _client.dio.get(
      '/outlets',
      queryParameters: {
        if (beatId != null) 'beat_id': beatId,
        'page': page,
        'per_page': 100,
      },
    );
    final items = response.data['items'] as List;
    return items.map((o) => Outlet.fromJson(o)).toList();
  }

  Future<List<Product>> fetchProducts() async {
    final response = await _client.dio.get('/products');
    final items = response.data['items'] as List;
    return items.map((p) => Product.fromJson(p)).toList();
  }

  Future<List<Beat>> fetchBeats() async {
    final response = await _client.dio.get('/beats');
    final items = response.data['items'] as List;
    return items.map((b) => Beat.fromJson(b)).toList();
  }

  Future<Beat> createBeat({
    required String name,
    required String code,
    required String beatType,
    String? beatGrade,
    int? territoryId,
  }) async {
    final response = await _client.dio.post(
      '/beats',
      data: {
        'name': name,
        'code': code,
        'beat_type': beatType,
        if (beatGrade != null) 'beat_grade': beatGrade,
        if (territoryId != null) 'territory_id': territoryId,
      },
    );
    return Beat.fromJson(response.data);
  }

  Future<Outlet> createOutlet({
    required String name,
    required int beatId,
    String? code,
    String? ownerName,
    String? mobile,
    String? address,
    String? pincode,
    String? gstin,
    String? channel,
    String? shopType,
    int? territoryId,
    double? gpsLat,
    double? gpsLng,
  }) async {
    final response = await _client.dio.post(
      '/outlets',
      data: {
        'name': name,
        'beat_id': beatId,
        if (code != null && code.isNotEmpty) 'code': code,
        if (ownerName != null && ownerName.isNotEmpty) 'owner_name': ownerName,
        if (mobile != null && mobile.isNotEmpty) 'mobile': mobile,
        if (address != null && address.isNotEmpty) 'address': address,
        if (pincode != null && pincode.isNotEmpty) 'pincode': pincode,
        if (gstin != null && gstin.isNotEmpty) 'gstin': gstin,
        if (channel != null && channel.isNotEmpty) 'channel': channel,
        if (shopType != null && shopType.isNotEmpty) 'shop_type': shopType,
        if (territoryId != null) 'territory_id': territoryId,
        if (gpsLat != null) 'gps_lat': gpsLat,
        if (gpsLng != null) 'gps_lng': gpsLng,
      },
    );
    return Outlet.fromJson(response.data);
  }

  Future<List<Beat>> fetchL1Beats() async {
    final response = await _client.dio.get('/beats/l1-positions');
    final items = response.data['items'] as List;
    return items.map((b) => Beat.fromJson(b)).toList();
  }

  Future<Map<String, dynamic>> requestOutletEdit(int outletId, Map<String, dynamic> data) async {
    final response = await _client.dio.post('/outlets/$outletId/edit-request', data: data);
    return response.data;
  }
}

