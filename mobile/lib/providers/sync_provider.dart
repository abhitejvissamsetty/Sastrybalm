import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import '../main.dart' show hiveCipher;
import '../services/sync_service.dart';
import 'auth_provider.dart';

final syncServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return SyncService(client, cipher: hiveCipher);
});

final connectivityStreamProvider = StreamProvider<List<ConnectivityResult>>((ref) {
  return Connectivity().onConnectivityChanged;
});

final syncProvider = StateNotifierProvider<SyncNotifier, int>((ref) {
  final service = ref.watch(syncServiceProvider);
  return SyncNotifier(service, ref);
});

class SyncNotifier extends StateNotifier<int> {
  final SyncService _service;
  final Ref _ref;

  SyncNotifier(this._service, this._ref) : super(0) {
    _init();
  }

  void _init() {
    _ref.listen(connectivityStreamProvider, (previous, next) {
      next.whenData((results) {
        if (results.isNotEmpty && !results.contains(ConnectivityResult.none)) {
          triggerSync();
        }
      });
    });
    updatePendingCount();
  }

  Future<void> triggerSync() async {
    await _service.processPendingOps();
    await updatePendingCount();
  }

  Future<void> queueOp({
    required String method,
    required String path,
    Map<String, dynamic>? queryParameters,
    dynamic data,
    Map<String, dynamic>? extra,
  }) async {
    await _service.queueOperation(
      method: method,
      path: path,
      queryParameters: queryParameters,
      data: data,
      extra: extra,
    );
    await updatePendingCount();
  }

  Future<void> updatePendingCount() async {
    state = await _service.getPendingCount();
  }
}
