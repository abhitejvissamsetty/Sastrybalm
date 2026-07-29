import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../models/product.dart';
import '../../providers/auth_provider.dart';
import '../../providers/beat_provider.dart';
import '../../services/operations_service.dart';
import '../../utils/currency_formatter.dart';
import '../../widgets/numeric_osk_widget.dart';

final channelPartnersProvider = FutureProvider<List<dynamic>>((ref) async {
  final client = ref.watch(apiClientProvider);
  final response = await client.dio.get('/channel-partners');
  return response.data['items'] as List;
});

class CreatePrimaryScreen extends ConsumerStatefulWidget {
  const CreatePrimaryScreen({super.key});

  @override
  ConsumerState<CreatePrimaryScreen> createState() =>
      _CreatePrimaryScreenState();
}

class _CreatePrimaryScreenState extends ConsumerState<CreatePrimaryScreen> {
  final List<OrderItem> _cart = [];
  final _addressCtrl = TextEditingController();
  final _notesCtrl = TextEditingController();
  final _searchCtrl = TextEditingController();

  dynamic _selectedPartner;
  String _searchQuery = '';
  bool _submitting = false;
  bool _loadingWarehouse = true;
  int? _warehouseId;
  String? _warehouseName;

  int? _activeProductId;
  String _oskInput = '';

  double get _total =>
      _cart.fold(0.0, (sum, item) => sum + item.unitPrice * item.quantity);

  @override
  void initState() {
    super.initState();
    _loadWarehouse();
  }

  Future<void> _loadWarehouse() async {
    try {
      final data =
          await OrderService(ref.read(apiClientProvider)).getWarehouseContext();
      if (mounted) {
        setState(() {
          _warehouseId = data['warehouse_id'] as int;
          _warehouseName = data['warehouse_name']?.toString();
          _loadingWarehouse = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _loadingWarehouse = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text('Warehouse resolution failed: $e'),
              backgroundColor: Colors.red),
        );
      }
    }
  }

  void _onProductTap(Product product) {
    if (!product.isStockableItem || product.warehouseStockQty <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(
                '${product.name} is unavailable in ${_warehouseName ?? 'the resolved warehouse'}.')),
      );
      return;
    }
    setState(() {
      _activeProductId = product.id;
      final existingQty = _getQty(product.id);
      _oskInput = existingQty > 0 ? '$existingQty' : '';
    });
  }

  void _updateQtyFromOsk(String val) {
    if (_activeProductId == null) return;
    if (_oskInput.length >= 4) return;
    setState(() {
      _oskInput += val;
      final newQty = int.tryParse(_oskInput) ?? 0;
      final products =
          ref.read(warehouseProductsProvider(_warehouseId)).valueOrNull ?? [];
      final selected = products.where((p) => p.id == _activeProductId).first;
      final cappedQty = newQty > selected.warehouseStockQty
          ? selected.warehouseStockQty
          : newQty;
      _setProductQty(_activeProductId!, cappedQty);
    });
  }

  void _onOskDelete() {
    if (_activeProductId == null) return;
    setState(() {
      if (_oskInput.isNotEmpty) {
        _oskInput = _oskInput.substring(0, _oskInput.length - 1);
        final newQty = int.tryParse(_oskInput) ?? 0;
        _setProductQty(_activeProductId!, newQty);
      }
    });
  }

  void _setProductQty(int productId, int qty) {
    final index = _cart.indexWhere((item) => item.productId == productId);
    if (index >= 0) {
      if (qty <= 0) {
        _cart.removeAt(index);
      } else {
        _cart[index].quantity = qty;
      }
    }
  }

  int _getQty(int productId) {
    final index = _cart.indexWhere((item) => item.productId == productId);
    return index >= 0 ? _cart[index].quantity : 0;
  }

  Future<void> _submitPrimaryOrder() async {
    if (_selectedPartner == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a Channel Partner.')),
      );
      return;
    }
    if (_addressCtrl.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter delivery address details.')),
      );
      return;
    }
    if (_cart.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Please add at least one product to the order.')),
      );
      return;
    }
    if (_warehouseId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content:
                Text('No L3 warehouse is available for this Primary Order.')),
      );
      return;
    }

    setState(() => _submitting = true);
    try {
      final service = OrderService(ref.read(apiClientProvider));

      final partnerId = _selectedPartner['id'] as int;

      final res = await service.createOrder(
        channelPartnerId: partnerId,
        partyId: partnerId,
        partyType: 'Channel Partner',
        orderType: 'Primary',
        items: _cart,
        warehouseId: _warehouseId,
        isCompanyOrder: true,
        isPaid: false,
        paymentType: 'Credit',
        deliveryAddress: _addressCtrl.text.trim(),
        notes: _notesCtrl.text.trim(),
      );

      final orderId = res['id'] as int;
      await service.submitOrder(orderId);

      if (mounted) {
        if (!mounted) return;
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Primary Order Created'),
            content: Text(
                'Primary Order ${res['order_number'] ?? '#$orderId'} placed against ${_selectedPartner['name']}.'),
            actions: [
              TextButton(
                child: const Text('OK'),
                onPressed: () {
                  Navigator.pop(ctx);
                  context.pop();
                },
              ),
            ],
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text('Primary order creation failed: $e'),
            backgroundColor: Colors.red.shade700),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  void dispose() {
    _addressCtrl.dispose();
    _notesCtrl.dispose();
    _searchCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final partnersAsync = ref.watch(channelPartnersProvider);
    final productsAsync = ref.watch(warehouseProductsProvider(_warehouseId));
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Create Primary Order'),
      ),
      body: _submitting || _loadingWarehouse
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Column(
                    children: [
                      partnersAsync.when(
                        data: (partners) {
                          return DropdownButtonFormField<dynamic>(
                            initialValue: _selectedPartner,
                            hint: const Text('Select Channel Partner'),
                            items: partners.map((p) {
                              return DropdownMenuItem(
                                value: p,
                                child:
                                    Text('${p['name']} (${p['code'] ?? ''})'),
                              );
                            }).toList(),
                            onChanged: (v) {
                              setState(() {
                                _selectedPartner = v;
                                if (v != null && v['address'] != null) {
                                  _addressCtrl.text = v['address'].toString();
                                }
                              });
                            },
                            decoration: const InputDecoration(
                              labelText: 'Channel Partner',
                              border: OutlineInputBorder(),
                            ),
                          );
                        },
                        loading: () => const LinearProgressIndicator(),
                        error: (e, _) => Text('Error loading partners: $e'),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _addressCtrl,
                        decoration: const InputDecoration(
                          labelText: 'Address Details',
                          hintText: 'Enter partner delivery address...',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _searchCtrl,
                        decoration: const InputDecoration(
                          hintText: 'Search products...',
                          prefixIcon: Icon(Icons.search_rounded),
                        ),
                        onChanged: (v) => setState(
                            () => _searchQuery = v.trim().toLowerCase()),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: productsAsync.when(
                    data: (products) {
                      final filtered = products.where((p) {
                        final isSale =
                            p.categoryScope.toLowerCase().contains('sale');
                        final matches = p.name
                                .toLowerCase()
                                .contains(_searchQuery) ||
                            (p.sku != null &&
                                p.sku!.toLowerCase().contains(_searchQuery));
                        return isSale && matches;
                      }).toList();

                      return ListView.builder(
                        itemCount: filtered.length,
                        itemBuilder: (ctx, idx) {
                          final product = filtered[idx];
                          final qty = _getQty(product.id);
                          final isSelected = _activeProductId == product.id;

                          return Container(
                            color: isSelected ? Colors.blue.shade50 : null,
                            child: ListTile(
                              onTap: () => _onProductTap(product),
                              title: Text(product.name,
                                  style: const TextStyle(
                                      fontWeight: FontWeight.bold)),
                              subtitle: Text(
                                'MRP: ${CurrencyFormatter.format(product.mrp ?? 0.0)} | '
                                '${_warehouseName ?? 'Warehouse'} Stock: ${product.warehouseStockQty}',
                              ),
                              trailing: Text('Qty: $qty',
                                  style: theme.textTheme.titleMedium
                                      ?.copyWith(fontWeight: FontWeight.bold)),
                            ),
                          );
                        },
                      );
                    },
                    loading: () =>
                        const Center(child: CircularProgressIndicator()),
                    error: (e, _) => Text('Error: $e'),
                  ),
                ),
                if (_cart.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.all(12),
                    color: Colors.grey.shade200,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('Total: ${CurrencyFormatter.format(_total)}',
                            style: theme.textTheme.titleLarge
                                ?.copyWith(fontWeight: FontWeight.bold)),
                        ElevatedButton(
                          onPressed: _submitPrimaryOrder,
                          child: const Text('Submit Primary Order'),
                        ),
                      ],
                    ),
                  ),
                if (_activeProductId != null)
                  NumericOskWidget(
                    onKeyPress: _updateQtyFromOsk,
                    onDelete: _onOskDelete,
                    onNext: () => setState(() => _activeProductId = null),
                    nextLabel: 'DONE',
                  ),
              ],
            ),
    );
  }
}
