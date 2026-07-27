import 'dart:io';

// App-wide constants
class ApiConfig {
  // Android emulator → 10.0.2.2 maps to host machine's localhost (port 8090)
  // iOS Simulator / local server → 127.0.0.1:8090/api/v1/
  static String get baseUrl {
    if (Platform.isAndroid) {
      return 'http://10.0.2.2:8090/api/v1/';
    }
    return 'http://127.0.0.1:8090/api/v1/';
  }

  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 30);
}
