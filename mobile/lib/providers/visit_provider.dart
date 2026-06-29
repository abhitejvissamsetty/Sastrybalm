import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/attendance.dart';
import '../services/operations_service.dart';
import 'auth_provider.dart';

final visitServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return VisitService(client);
});

// Map of outletId to active VisitRecord
final activeVisitProvider = StateProvider<Map<int, VisitRecord>>((ref) => {});

// Active visit id provider
final currentVisitIdProvider = StateProvider<int?>((ref) => null);
