import 'package:dio/dio.dart';

import '../models/user.dart';
import 'api_client.dart';

abstract class AuthTransport {
  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? data,
  });
  Future<Map<String, dynamic>> get(String path);
}

class ApiClientAuthTransport implements AuthTransport {
  final ApiClient client;

  ApiClientAuthTransport(this.client);

  @override
  Future<Map<String, dynamic>> get(String path) async =>
      Map<String, dynamic>.from((await client.dio.get(path)).data as Map);

  @override
  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? data,
  }) async =>
      Map<String, dynamic>.from(
        (await client.dio.post(path, data: data)).data as Map? ?? {},
      );
}

abstract class AuthTokenStore {
  Future<void> save(String token);
  Future<String?> read();
  Future<void> clear();
}

class SecureAuthTokenStore implements AuthTokenStore {
  final ApiClient client;

  SecureAuthTokenStore(this.client);

  @override
  Future<void> clear() => client.clearToken();

  @override
  Future<String?> read() => client.getToken();

  @override
  Future<void> save(String token) => client.saveToken(token);
}

class AuthService {
  final AuthTransport _transport;
  final AuthTokenStore _tokens;

  AuthService(
    ApiClient client, {
    AuthTransport? transport,
    AuthTokenStore? tokens,
  })  : _transport = transport ?? ApiClientAuthTransport(client),
        _tokens = tokens ?? SecureAuthTokenStore(client);

  Future<void> requestOtp(String emailOrLogin) async {
    await _transport.post('/auth/request-otp', data: {'email': emailOrLogin});
  }

  Future<AppUser> verifyOtp(String emailOrLogin, String otpCode) async {
    final data = await _transport.post('/auth/verify-otp', data: {
      'email': emailOrLogin,
      'otp_code': otpCode,
    });
    final user = AppUser.fromJson(data);
    final token = data['access_token'] as String?;
    if (!user.isActive || token == null || token.isEmpty) {
      await _tokens.clear();
      throw StateError('Inactive or invalid account.');
    }
    await _tokens.save(token);
    return user;
  }

  Future<AppUser> login(String username, String password) async {
    final data = await _transport.post('/auth/token', data: {
      'username': username,
      'password': password,
    });
    final user = AppUser.fromJson(data);
    final token = data['access_token'] as String?;
    if (!user.isActive || token == null || token.isEmpty) {
      await _tokens.clear();
      throw DioException(
        requestOptions: RequestOptions(path: '/auth/token'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/auth/token'),
          statusCode: 403,
          data: {'detail': 'Inactive or invalid account.'},
        ),
      );
    }
    await _tokens.save(token);
    return user;
  }

  Future<AppUser> me() async {
    final data = await _transport.get('/auth/me');
    final user = AppUser.fromJson(data);
    if (!user.isActive) {
      await _tokens.clear();
      throw StateError('Inactive account.');
    }
    return user;
  }

  Future<AppConfig> fetchConfig() async {
    return AppConfig.fromJson(await _transport.get('/config'));
  }

  Future<void> logout() async {
    try {
      await _transport.post('/auth/logout');
    } finally {
      await _tokens.clear();
    }
  }

  Future<bool> isLoggedIn() async {
    final token = await _tokens.read();
    return token != null;
  }
}
