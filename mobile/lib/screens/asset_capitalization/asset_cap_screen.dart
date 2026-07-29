import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../services/image_picker_service.dart';
import '../../services/operations_service.dart';

final assetCapServiceProvider =
    Provider((ref) => AssetCapitalizationService(ref.watch(apiClientProvider)));

class AssetListScreen extends ConsumerWidget {
  final int outletId;
  const AssetListScreen({super.key, required this.outletId});
  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
        appBar: AppBar(title: const Text('Outlet Assets')),
        floatingActionButton: FloatingActionButton.extended(
            onPressed: () => context.push('/outlet/$outletId/assets/new'),
            icon: const Icon(Icons.add),
            label: const Text('New Asset')),
        body: FutureBuilder<List<dynamic>>(
          future: ref.read(assetCapServiceProvider).getAssets(outletId),
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return Center(
                  child: Text('Unable to load assets: ${snapshot.error}'));
            }
            final items = snapshot.data ?? [];
            if (items.isEmpty) {
              return const Center(
                  child: Text('No assets deployed to this outlet.'));
            }
            return RefreshIndicator(
              onRefresh: () async => (context as Element).markNeedsBuild(),
              child: ListView.builder(
                  itemCount: items.length,
                  itemBuilder: (_, i) {
                    final item = items[i] as Map<String, dynamic>;
                    return ListTile(
                      leading: const CircleAvatar(
                          child: Icon(Icons.inventory_2_outlined)),
                      title: Text(item['item_name'] ?? 'Asset'),
                      subtitle: Text(
                          '${item['ac_number']} • ${item['warehouse_name'] ?? 'Warehouse unavailable'}'),
                      trailing: Text('× ${item['quantity']}'),
                    );
                  }),
            );
          },
        ),
      );
}

class AssetCapitalizationScreen extends ConsumerStatefulWidget {
  final int outletId;
  const AssetCapitalizationScreen({super.key, required this.outletId});
  @override
  ConsumerState<AssetCapitalizationScreen> createState() =>
      _AssetCapitalizationScreenState();
}

class _AssetCapitalizationScreenState
    extends ConsumerState<AssetCapitalizationScreen> {
  final _quantity = TextEditingController(text: '1');
  final _notes = TextEditingController();
  Map<String, dynamic>? _context;
  int? _productId;
  String? _imagePath;
  bool _loading = true, _submitting = false;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      _context =
          await ref.read(assetCapServiceProvider).getProducts(widget.outletId);
    } catch (e) {
      if (mounted) _message('Unable to load warehouse products: $e');
    }
    if (mounted) setState(() => _loading = false);
  }

  void _message(String value) => ScaffoldMessenger.of(context)
      .showSnackBar(SnackBar(content: Text(value)));
  Future<void> _pick() async {
    final file = await ImagePickerService().showImageSourceDialog(context);
    if (file != null && mounted) setState(() => _imagePath = file.path);
  }

  Future<void> _submit() async {
    final quantity = int.tryParse(_quantity.text) ?? 0;
    if (_productId == null || quantity <= 0) {
      _message('Select a product and enter a positive quantity.');
      return;
    }
    setState(() => _submitting = true);
    try {
      final result =
          await ref.read(assetCapServiceProvider).createCapitalization(
                outletId: widget.outletId,
                productId: _productId!,
                quantity: quantity,
                notes: _notes.text.trim(),
                imagePath: _imagePath,
              );
      if (mounted) {
        _message('Asset ${result['ac_number']} deployed.');
        context.pop();
      }
    } catch (e) {
      if (mounted) _message('Asset deployment failed: $e');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final warehouse = _context?['warehouse'] as Map<String, dynamic>?;
    final products = (_context?['products'] as List?) ?? [];
    return Scaffold(
      appBar: AppBar(title: const Text('New Outlet Asset')),
      body: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Card(
                  child: ListTile(
                leading: const Icon(Icons.warehouse_outlined),
                title: Text(warehouse?['name'] ?? 'No warehouse'),
                subtitle:
                    Text('Resolved L3 warehouse • ${warehouse?['code'] ?? ''}'),
              )),
              const SizedBox(height: 16),
              DropdownButtonFormField<int>(
                initialValue: _productId,
                decoration: const InputDecoration(
                    labelText: 'Marketing Stock Product *'),
                items: products
                    .map<DropdownMenuItem<int>>((p) => DropdownMenuItem(
                          value: p['id'],
                          child: Text(
                              '${p['name']} • ${p['available_quantity']} available'),
                        ))
                    .toList(),
                onChanged: (v) => setState(() => _productId = v),
              ),
              const SizedBox(height: 16),
              TextField(
                  controller: _quantity,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Quantity *')),
              const SizedBox(height: 16),
              TextField(
                  controller: _notes,
                  maxLines: 3,
                  decoration:
                      const InputDecoration(labelText: 'Deployment Notes')),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                  onPressed: _pick,
                  icon: const Icon(Icons.add_a_photo_outlined),
                  label: Text(_imagePath == null
                      ? 'Add Deployment Image'
                      : 'Replace Deployment Image')),
              const SizedBox(height: 20),
              ElevatedButton(
                  onPressed: _submitting ? null : _submit,
                  child: Text(_submitting ? 'Deploying…' : 'Deploy Asset')),
            ],
          )),
    );
  }
}
