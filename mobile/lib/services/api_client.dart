import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../config/api_config.dart';

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal();

  late final Dio _dio;
  final _storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  /// Broadcast stream: emits `true` whenever the server returns a 401.
  /// AuthNotifier listens to this and calls logout() so GoRouter redirects.
  final _unauthorizedController = StreamController<bool>.broadcast();
  Stream<bool> get onUnauthorized => _unauthorizedController.stream;

  void init() {
    _dio = Dio(BaseOptions(
      baseUrl: ApiConfig.baseUrl,
      connectTimeout: ApiConfig.connectTimeout,
      receiveTimeout: ApiConfig.receiveTimeout,
      headers: {'Content-Type': 'application/json'},
    ));

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          if (options.path.startsWith('/')) {
            options.path = options.path.substring(1);
          }
          final token = await _storage.read(key: 'jwt_token');
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
        onError: (DioException error, handler) async {
          final path = error.requestOptions.path;
          final isAuthRequest = path.contains('/auth/token') ||
              path.contains('/auth/request-otp') ||
              path.contains('/auth/verify-otp');

          if (error.response?.statusCode == 401 && !isAuthRequest) {
            // Clear stored credentials immediately
            await _storage.delete(key: 'jwt_token');
            // Notify listeners (AuthNotifier) so the app navigates to /login
            _unauthorizedController.add(true);
          }
          return handler.next(error);
        },
      ),
    );
  }

  Dio get dio => _dio;

  Future<void> saveToken(String token) =>
      _storage.write(key: 'jwt_token', value: token);

  Future<String?> getToken() => _storage.read(key: 'jwt_token');

  Future<void> clearToken() => _storage.delete(key: 'jwt_token');

  void dispose() {
    _unauthorizedController.close();
  }
}
