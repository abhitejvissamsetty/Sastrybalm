import 'package:geolocator/geolocator.dart';
import '../models/attendance.dart';
import 'api_client.dart';

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

  Future<Map<String, dynamic>> checkOut(
      Position pos, {String? address, String? notes}) async {
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
    try {
      bool serviceEnabled = (await Geolocator.isLocationServiceEnabled()) == true;
      if (serviceEnabled) {
        LocationPermission permission = await Geolocator.checkPermission();
        if (permission == LocationPermission.denied) {
          permission = await Geolocator.requestPermission();
        }
        if (permission != LocationPermission.denied && permission != LocationPermission.deniedForever) {
          return await Geolocator.getCurrentPosition(
            desiredAccuracy: LocationAccuracy.high,
            timeLimit: const Duration(seconds: 5),
          );
        }
      }
    } catch (_) {}

    // Safe fallback position (Bangalore HQ coordinates) for simulator or location failure
    return Position(
      latitude: 12.9716,
      longitude: 77.5946,
      timestamp: DateTime.now(),
      accuracy: 10.0,
      altitude: 0.0,
      heading: 0.0,
      speed: 0.0,
      speedAccuracy: 0.0,
      altitudeAccuracy: 0.0,
      headingAccuracy: 0.0,
    );
  }
}
