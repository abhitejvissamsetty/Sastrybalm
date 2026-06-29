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

  /// Get current GPS location with full permission handling
  static Future<Position> getCurrentPosition() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      throw Exception('Location services are disabled. Please enable GPS.');
    }

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        throw Exception('Location permission denied.');
      }
    }
    if (permission == LocationPermission.deniedForever) {
      throw Exception(
          'Location permissions are permanently denied. Enable them in Settings.');
    }

    return await Geolocator.getCurrentPosition(
      desiredAccuracy: LocationAccuracy.high,
      timeLimit: const Duration(seconds: 10),
    );
  }
}
