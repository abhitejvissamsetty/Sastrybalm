import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/outlet.dart';
import '../models/product.dart';
import '../services/master_service.dart';
import 'auth_provider.dart';

final masterServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return MasterService(client);
});

final beatPlanProvider =
    FutureProvider.family<Map<String, dynamic>, int?>((ref, beatId) async {
  if (beatId == null) {
    return {'beat': null, 'outlets': <Outlet>[]};
  }
  final service = ref.watch(masterServiceProvider);
  return service.fetchBeatPlan(beatId);
});

final selectedOutletProvider = StateProvider<Outlet?>((ref) => null);

final productsProvider = FutureProvider<List<Product>>((ref) async {
  final service = ref.watch(masterServiceProvider);
  return service.fetchProducts();
});

final warehouseProductsProvider =
    FutureProvider.family<List<Product>, int?>((ref, warehouseId) async {
  final service = ref.watch(masterServiceProvider);
  return service.fetchProducts(warehouseId: warehouseId);
});

final beatsProvider = FutureProvider<List<Beat>>((ref) async {
  final service = ref.watch(masterServiceProvider);
  return service.fetchBeats();
});

final selectedBeatIdProvider = StateProvider<int?>((ref) => null);
