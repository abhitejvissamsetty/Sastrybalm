import 'package:geolocator/geolocator.dart';
import '../models/attendance.dart';
import 'api_client.dart';
import 'location_service.dart';

class AttendanceService {
  final ApiClient _client;
  AttendanceService(this._client);

  Future<AttendanceState> fetchToday() async {
    final response = await _client.dio.get('/attendance/today');
    return AttendanceState.fromJson(response.data);
  }

  Future<AttendanceState> checkIn(Position pos, {String? address}) async {
    final response = await _client.dio.post(
      '/attendance/checkin',
      queryParameters: {
        'gps_lat': pos.latitude,
        'gps_lng': pos.longitude,
        if (address != null) 'address': address,
      },
    );
    return AttendanceState.fromJson({
      'checked_in': true,
      ...response.data,
    });
  }

  Future<Map<String, dynamic>> checkOut(Position pos,
      {String? address, String? notes}) async {
    final response = await _client.dio.post(
      '/attendance/checkout',
      queryParameters: {
        'gps_lat': pos.latitude,
        'gps_lng': pos.longitude,
        if (address != null) 'address': address,
        if (notes != null) 'notes': notes,
      },
    );
    return response.data;
  }

  /// Get current GPS location with full permission and fallback handling
  static Future<Position> getCurrentPosition() async {
    return LocationService().verifiedCurrentPosition();
  }
}
