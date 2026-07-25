import '../models/user.dart';
import 'api_client.dart';

class AuthService {
  final ApiClient _client;
  AuthService(this._client);

  Future<Map<String, dynamic>> requestOtp(String emailOrLogin) async {
    final response = await _client.dio.post('/auth/request-otp', data: {
      'email': emailOrLogin,
    });
    return response.data as Map<String, dynamic>;
  }

  Future<AppUser> verifyOtp(String emailOrLogin, String otpCode) async {
    final response = await _client.dio.post('/auth/verify-otp', data: {
      'email': emailOrLogin,
      'otp_code': otpCode,
    });
    final data = response.data as Map<String, dynamic>;
    await _client.saveToken(data['access_token']);
    return AppUser.fromJson(data);
  }

  Future<AppUser> me() async {
    final response = await _client.dio.get('/auth/me');
    return AppUser.fromJson(response.data);
  }

  Future<AppConfig> fetchConfig() async {
    final response = await _client.dio.get('/config');
    return AppConfig.fromJson(response.data);
  }

  Future<void> logout() => _client.clearToken();

  Future<bool> isLoggedIn() async {
    final token = await _client.getToken();
    return token != null;
  }
}
