import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

const _baseUrl = String.fromEnvironment('E2E_BASE_URL');

Dio _client(String token) => Dio(BaseOptions(
      baseUrl: _baseUrl,
      headers: {'Authorization': 'Bearer $token'},
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(seconds: 10),
    ));

void main() {
  setUpAll(() {
    // Flutter's unit-test binding replaces HttpClient with a 400-only fake.
    // This suite is explicitly invoked with a deterministic live backend.
    HttpOverrides.global = null;
  });

  final configured = _baseUrl.isNotEmpty;
  final roleTokens = {
    'admin': const String.fromEnvironment('E2E_ADMIN_TOKEN'),
    'territory_manager_l4': const String.fromEnvironment('E2E_L4_TOKEN'),
    'territory_manager_l3': const String.fromEnvironment('E2E_L3_TOKEN'),
    'territory_manager_l2': const String.fromEnvironment('E2E_L2_TOKEN'),
    'field_rep': const String.fromEnvironment('E2E_L1_TOKEN'),
    'vendor_admin': const String.fromEnvironment('E2E_VENDOR_ADMIN_TOKEN'),
    'vendor_technician':
        const String.fromEnvironment('E2E_VENDOR_TECHNICIAN_TOKEN'),
    'qc_manager': const String.fromEnvironment('E2E_QC_MANAGER_TOKEN'),
  };

  test('every deterministic role authenticates against the real backend',
      () async {
    expect(configured, isTrue, reason: 'E2E_BASE_URL is required');
    for (final entry in roleTokens.entries) {
      expect(entry.value, isNotEmpty, reason: '${entry.key} token is required');
      final response = await _client(entry.value).get('/auth/me');
      expect(response.statusCode, 200, reason: entry.key);
      final role = response.data['role'] as String;
      if (entry.key.startsWith('territory_manager')) {
        expect(role, 'territory_manager');
      } else {
        expect(role, entry.key);
      }
    }
  }, skip: !configured);

  test('master-data synchronization is paginated and deterministic', () async {
    final response = await _client(roleTokens['field_rep']!).get(
      '/outlets',
      queryParameters: {'page': 1, 'per_page': 1},
    );
    expect(response.statusCode, 200);
    expect(response.data['page'], 1);
    expect(response.data['per_page'], 1);
    expect(response.data['total'], greaterThanOrEqualTo(1));
    expect(response.data['items'], hasLength(1));
  }, skip: !configured);

  test('field representative cannot mutate restricted beat configuration',
      () async {
    try {
      await _client(roleTokens['field_rep']!).post('/beats', data: {
        'name': 'Forbidden E2E Beat',
        'code': 'FORBIDDEN-E2E',
        'beat_type': 'GT',
      });
      fail('restricted mutation unexpectedly succeeded');
    } on DioException catch (error) {
      expect(error.response?.statusCode, 403);
    }
  }, skip: !configured);

  test('cross-territory outlet lookup fails closed', () async {
    const deniedId = String.fromEnvironment('E2E_DENIED_OUTLET_ID');
    try {
      await _client(roleTokens['field_rep']!).get('/outlets/$deniedId');
      fail('cross-territory lookup unexpectedly succeeded');
    } on DioException catch (error) {
      expect(error.response?.statusCode, anyOf(403, 404));
    }
  }, skip: !configured);

  test('vendor and QC roles can read their scoped procurement workspaces',
      () async {
    for (final key in [
      'vendor_admin',
      'vendor_technician',
      'qc_manager',
    ]) {
      final response = await _client(roleTokens[key]!).get(
        '/procurement/material-requests',
        queryParameters: {'page': 1, 'per_page': 5},
      );
      expect(response.statusCode, 200, reason: key);
      expect(response.data['items'], isA<List<dynamic>>());
    }
  }, skip: !configured);
}
