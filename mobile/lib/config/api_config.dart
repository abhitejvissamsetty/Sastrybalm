// App-wide constants
class ApiConfig {
  // Android emulator → 10.0.2.2 maps to host machine's localhost
  // Physical device on same WiFi → use your Mac's local IP
  // iOS Simulator / local server → http://127.0.0.1:8090/api/v1/
  static const String baseUrl = 'http://127.0.0.1:8090/api/v1/';

  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 30);
}
