import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/attendance.dart';
import '../services/attendance_service.dart';
import 'auth_provider.dart';

final attendanceServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return AttendanceService(client);
});

final attendanceProvider = StateNotifierProvider<AttendanceNotifier, AsyncValue<AttendanceState>>((ref) {
  return AttendanceNotifier(ref.read(attendanceServiceProvider));
});

class AttendanceNotifier extends StateNotifier<AsyncValue<AttendanceState>> {
  final AttendanceService _service;

  AttendanceNotifier(this._service) : super(const AsyncValue.loading()) {
    refresh();
  }

  Future<void> refresh() async {
    try {
      final today = await _service.fetchToday();
      state = AsyncValue.data(today);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
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
