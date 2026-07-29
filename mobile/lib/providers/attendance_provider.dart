import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/attendance.dart';
import '../models/user.dart';
import '../services/attendance_service.dart';
import 'auth_provider.dart';

final attendanceServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return AttendanceService(client);
});

final attendanceProvider =
    StateNotifierProvider<AttendanceNotifier, AsyncValue<AttendanceState>>(
        (ref) {
  final notifier = AttendanceNotifier(ref.read(attendanceServiceProvider), ref);
  ref.listen<AsyncValue<AppUser?>>(authStateProvider, (prev, next) {
    if (next.value != null) {
      notifier.refresh();
    }
  });
  return notifier;
});

class AttendanceNotifier extends StateNotifier<AsyncValue<AttendanceState>> {
  final AttendanceService _service;
  final Ref _ref;

  AttendanceNotifier(this._service, this._ref)
      : super(AsyncValue.data(AttendanceState.notCheckedIn())) {
    refresh();
  }

  Future<void> refresh() async {
    final authState = _ref.read(authStateProvider);
    if (authState.value == null) {
      state = AsyncValue.data(AttendanceState.notCheckedIn());
      return;
    }

    try {
      final today = await _service.fetchToday();
      state = AsyncValue.data(today);
    } catch (e) {
      // Fallback to notCheckedIn state gracefully so UI is never stuck/blank
      state = AsyncValue.data(AttendanceState.notCheckedIn());
    }
  }

  Future<void> checkIn() async {
    state = const AsyncValue.loading();
    try {
      final pos = await AttendanceService.getCurrentPosition();
      final result = await _service.checkIn(pos);
      state = AsyncValue.data(result);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      rethrow;
    }
  }

  Future<void> checkOut({String? notes}) async {
    state = const AsyncValue.loading();
    try {
      final pos = await AttendanceService.getCurrentPosition();
      await _service.checkOut(pos, notes: notes);
      final today = await _service.fetchToday();
      state = AsyncValue.data(today);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      rethrow;
    }
  }
}
