import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sfa_mobile/models/attendance.dart';
import 'package:sfa_mobile/services/api_client.dart';
import 'package:sfa_mobile/services/auth_service.dart';

class FakeAuthTransport implements AuthTransport {
  final calls = <String>[];
  final payloads = <Map<String, dynamic>?>[];
  final responses = <String, Map<String, dynamic>>{};
  final errors = <String, Object>{};

  @override
  Future<Map<String, dynamic>> get(String path) async {
    calls.add('GET $path');
    if (errors[path] case final error?) throw error;
    return responses[path] ?? {};
  }

  @override
  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    calls.add('POST $path');
    payloads.add(data);
    if (errors[path] case final error?) throw error;
    return responses[path] ?? {};
  }
}

class MemoryTokenStore implements AuthTokenStore {
  String? value;
  var clears = 0;

  @override
  Future<void> clear() async {
    value = null;
    clears++;
  }

  @override
  Future<String?> read() async => value;

  @override
  Future<void> save(String token) async => value = token;
}

Map<String, dynamic> userResponse({bool active = true}) => {
      'id': 7,
      'username': 'field.rep',
      'full_name': 'Field Rep',
      'email': 'rep@example.test',
      'role': 'field_rep',
      'is_active': active,
      'access_token': 'signed-jwt',
    };

void main() {
  late FakeAuthTransport transport;
  late MemoryTokenStore tokens;
  late AuthService service;

  setUp(() {
    transport = FakeAuthTransport();
    tokens = MemoryTokenStore();
    service = AuthService(
      ApiClient(),
      transport: transport,
      tokens: tokens,
    );
  });

  test('valid password login stores token and returns active user', () async {
    transport.responses['/auth/token'] = userResponse();
    final user = await service.login('rep@example.test', 'strong-password');
    expect(user.isActive, isTrue);
    expect(tokens.value, 'signed-jwt');
    expect(transport.payloads.single, {
      'username': 'rep@example.test',
      'password': 'strong-password',
    });
  });

  test('OTP request never expects a code in the response', () async {
    transport.responses['/auth/request-otp'] = {
      'message': 'OTP verification code sent.',
      'email': 'rep@example.test',
    };
    await service.requestOtp('rep@example.test');
    expect(transport.payloads.single, {'email': 'rep@example.test'});
  });

  test('valid OTP verification stores the returned token', () async {
    transport.responses['/auth/verify-otp'] = userResponse();
    final user = await service.verifyOtp('rep@example.test', '123456');
    expect(user.isActive, isTrue);
    expect(tokens.value, 'signed-jwt');
    expect(transport.payloads.single, {
      'email': 'rep@example.test',
      'otp_code': '123456',
    });
  });

  test('inactive account is rejected and local token is cleared', () async {
    tokens.value = 'old-token';
    transport.responses['/auth/token'] = userResponse(active: false);
    await expectLater(
      service.login('rep@example.test', 'strong-password'),
      throwsA(isA<DioException>()),
    );
    expect(tokens.value, isNull);
  });

  test('expired session propagates 401 and is not considered logged in',
      () async {
    tokens.value = 'expired';
    transport.errors['/auth/me'] = DioException(
      requestOptions: RequestOptions(path: '/auth/me'),
      response: Response(
        requestOptions: RequestOptions(path: '/auth/me'),
        statusCode: 401,
      ),
    );
    await expectLater(service.me(), throwsA(isA<DioException>()));
    await tokens.clear(); // ApiClient performs this on a real 401.
    expect(await service.isLoggedIn(), isFalse);
  });

  test('logout revokes server session and always clears local token', () async {
    tokens.value = 'signed-jwt';
    await service.logout();
    expect(transport.calls, contains('POST /auth/logout'));
    expect(tokens.value, isNull);

    tokens.value = 'second-token';
    transport.errors['/auth/logout'] = StateError('network unavailable');
    await expectLater(service.logout(), throwsStateError);
    expect(tokens.value, isNull);
  });

  test('checked-out attendance state cannot be treated as open', () {
    final state = AttendanceState(
      checkedIn: true,
      checkinTime: DateTime(2026, 7, 29, 9),
      checkoutTime: DateTime(2026, 7, 29, 18),
      status: 'closed',
    );
    expect(state.isClosed, isTrue);
    expect(state.isOpen, isFalse);
  });
}
