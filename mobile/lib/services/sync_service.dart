import 'package:hive/hive.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';
import 'api_client.dart';

typedef SyncRequestSender = Future<dynamic> Function(
  String method,
  String path,
  Map<String, dynamic>? queryParameters,
  dynamic data,
  String idempotencyKey,
);

class SyncService {
  final ApiClient _client;
  final HiveAesCipher? _cipher;
  final Future<bool> Function() _hasConnection;
  final DateTime Function() _now;
  final SyncRequestSender? _requestSender;
  final int maxAttempts;

  SyncService(
    this._client, {
    HiveAesCipher? cipher,
    Future<bool> Function()? hasConnection,
    DateTime Function()? now,
    SyncRequestSender? requestSender,
    this.maxAttempts = 5,
  })  : _cipher = cipher,
        _hasConnection = hasConnection ?? _defaultConnectivityCheck,
        _now = now ?? DateTime.now,
        _requestSender = requestSender;
  static const _uuid = Uuid();

  static Future<bool> _defaultConnectivityCheck() async {
    final result = await Connectivity().checkConnectivity();
    return result.isNotEmpty && !result.contains(ConnectivityResult.none);
  }

  Future<Box> _openBox(String name) async {
    if (_cipher != null) {
      return Hive.openBox(name, encryptionCipher: _cipher);
    }
    return Hive.openBox(name);
  }

  Future<void> queueOperation({
    required String method,
    required String path,
    Map<String, dynamic>? queryParameters,
    dynamic data,
    Map<String, dynamic>? extra,
  }) async {
    final box = await _openBox('pending_ops');
    await box.add({
      'method': method,
      'path': path,
      'queryParameters': queryParameters,
      'data': data,
      'extra': extra,
      'idempotencyKey': _uuid.v4(),
      'timestamp': _now().toIso8601String(),
      'attemptCount': 0,
      'nextAttemptAt': _now().toIso8601String(),
    });
  }

  Future<void> processPendingOps() async {
    if (!await _hasConnection()) return;

    final box = await _openBox('pending_ops');
    final keys = box.keys.toList();

    for (final key in keys) {
      final op = box.get(key) as Map;
      final nextAttemptAt =
          DateTime.tryParse(op['nextAttemptAt'] as String? ?? '');
      if (nextAttemptAt != null && nextAttemptAt.isAfter(_now())) {
        break;
      }
      try {
        final method = op['method'] as String;
        final path = op['path'] as String;
        final queryParameters = op['queryParameters'] != null
            ? Map<String, dynamic>.from(op['queryParameters'] as Map)
            : null;
        final data = op['data'];
        final extra = op['extra'] != null
            ? Map<String, dynamic>.from(op['extra'] as Map)
            : null;
        var idempotencyKey = op['idempotencyKey'] as String?;
        if (idempotencyKey == null) {
          idempotencyKey = _uuid.v4();
          final upgraded = Map<String, dynamic>.from(op);
          upgraded['idempotencyKey'] = idempotencyKey;
          await box.put(key, upgraded);
        }
        final requestOptions = Options(
          headers: {'Idempotency-Key': idempotencyKey},
        );

        final responseData = _requestSender != null
            ? await _requestSender(
                method, path, queryParameters, data, idempotencyKey)
            : await _send(method, path, queryParameters, data, requestOptions);

        if (extra != null &&
            extra['temp_payment_id'] != null &&
            responseData != null &&
            responseData is Map) {
          final tempId = extra['temp_payment_id'] as int;
          final realId = responseData['id'] as int;
          final realRef = responseData['payment_ref'] ?? '#$realId';

          final payBox = _cipher != null
              ? await Hive.openBox('unsubmitted_payments',
                  encryptionCipher: _cipher)
              : await Hive.openBox('unsubmitted_payments');
          final paymentData = payBox.get(tempId);
          if (paymentData != null && paymentData is Map) {
            final updated = Map<String, dynamic>.from(paymentData);
            updated['id'] = realId;
            updated['payment_ref'] = realRef;
            await payBox.put(realId, updated);
            await payBox.delete(tempId);
          }
        }

        await box.delete(key);
      } catch (error) {
        final updated = Map<String, dynamic>.from(op);
        final attempts = (updated['attemptCount'] as int? ?? 0) + 1;
        updated['attemptCount'] = attempts;
        updated['lastError'] = error.runtimeType.toString();
        final isConflict =
            error is DioException && error.response?.statusCode == 409;
        if (isConflict || attempts >= maxAttempts) {
          updated['deadLetteredAt'] = _now().toIso8601String();
          updated['failureReason'] =
              isConflict ? 'conflict' : 'retry_exhausted';
          final deadLetters = await _openBox('dead_letter_ops');
          await deadLetters.add(updated);
          await box.delete(key);
          continue;
        }
        final exponent = (attempts - 1).clamp(0, 8);
        final delaySeconds = 1 << exponent;
        updated['nextAttemptAt'] =
            _now().add(Duration(seconds: delaySeconds)).toIso8601String();
        await box.put(key, updated);
        break; // Preserve operation ordering until this item succeeds or expires.
      }
    }
  }

  Future<dynamic> _send(
    String method,
    String path,
    Map<String, dynamic>? queryParameters,
    dynamic data,
    Options options,
  ) async {
    switch (method) {
      case 'POST':
        return (await _client.dio.post(path,
                queryParameters: queryParameters, data: data, options: options))
            .data;
      case 'PATCH':
        return (await _client.dio.patch(path,
                queryParameters: queryParameters, data: data, options: options))
            .data;
      case 'PUT':
        return (await _client.dio.put(path,
                queryParameters: queryParameters, data: data, options: options))
            .data;
      default:
        throw StateError('Unsupported queued method: $method');
    }
  }

  Future<int> getPendingCount() async {
    final box = await _openBox('pending_ops');
    return box.length;
  }

  Future<int> getDeadLetterCount() async {
    final box = await _openBox('dead_letter_ops');
    return box.length;
  }
}
