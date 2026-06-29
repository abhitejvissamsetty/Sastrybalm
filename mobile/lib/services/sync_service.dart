import 'package:hive/hive.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'api_client.dart';

class SyncService {
  final ApiClient _client;
  final HiveAesCipher? _cipher;

  SyncService(this._client, {HiveAesCipher? cipher}) : _cipher = cipher;

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
      'timestamp': DateTime.now().toIso8601String(),
    });
  }

  Future<void> processPendingOps() async {
    final connectivityResult = await Connectivity().checkConnectivity();
    final hasConnection = connectivityResult.isNotEmpty &&
        !connectivityResult.contains(ConnectivityResult.none);

    if (!hasConnection) return;

    final box = await _openBox('pending_ops');
    final keys = box.keys.toList();

    for (final key in keys) {
      final op = box.get(key) as Map;
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

        dynamic responseData;
        if (method == 'POST') {
          final res = await _client.dio
              .post(path, queryParameters: queryParameters, data: data);
          responseData = res.data;
        } else if (method == 'PATCH') {
          final res = await _client.dio
              .patch(path, queryParameters: queryParameters, data: data);
          responseData = res.data;
        } else if (method == 'PUT') {
          final res = await _client.dio
              .put(path, queryParameters: queryParameters, data: data);
          responseData = res.data;
        }

        if (extra != null && extra['temp_payment_id'] != null && responseData != null && responseData is Map) {
          final tempId = extra['temp_payment_id'] as int;
          final realId = responseData['id'] as int;
          final realRef = responseData['payment_ref'] ?? '#$realId';

          final payBox = _cipher != null
              ? await Hive.openBox('unsubmitted_payments', encryptionCipher: _cipher)
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
      } catch (_) {
        // Keep in queue, stop processing to preserve ordering
        break;
      }
    }
  }

  Future<int> getPendingCount() async {
    final box = await _openBox('pending_ops');
    return box.length;
  }
}
