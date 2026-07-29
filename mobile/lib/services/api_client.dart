import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';
import '../config/api_config.dart';
import 'retry_policy.dart';

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal();

  late final Dio _dio;
  final _storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );
  static const _uuid = Uuid();
  final _retryPolicy = RetryPolicy();

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
          if (const {'POST', 'PUT', 'PATCH'}.contains(options.method) &&
              !options.headers.containsKey('Idempotency-Key')) {
            options.headers['Idempotency-Key'] = _uuid.v4();
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
          final isTransient = error.type == DioExceptionType.connectionError ||
              error.type == DioExceptionType.connectionTimeout ||
              error.type == DioExceptionType.receiveTimeout ||
              (error.response?.statusCode ?? 0) >= 500;
          if (isTransient &&
              error.requestOptions.extra['_boundedRetry'] != true) {
            try {
              final retryOptions = error.requestOptions.copyWith(
                extra: {
                  ...error.requestOptions.extra,
                  '_boundedRetry': true,
                },
              );
              final response = await _retryPolicy.execute(
                () => _dio.fetch(retryOptions),
                shouldRetry: (failure) =>
                    failure is DioException &&
                    (failure.type == DioExceptionType.connectionError ||
                        failure.type == DioExceptionType.connectionTimeout ||
                        failure.type == DioExceptionType.receiveTimeout ||
                        (failure.response?.statusCode ?? 0) >= 500),
              );
              return handler.resolve(response);
            } catch (_) {
              // Return the original failure after the bounded retry policy.
            }
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
