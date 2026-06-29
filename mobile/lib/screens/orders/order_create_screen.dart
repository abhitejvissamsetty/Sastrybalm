import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../models/product.dart';
import '../../providers/beat_provider.dart';
import '../../providers/auth_provider.dart';
import '../../services/operations_service.dart';
import '../../utils/currency_formatter.dart';

final orderServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return OrderService(client);
});

class OrderCreateScreen extends ConsumerStatefulWidget {
  const OrderCreateScreen({super.key});

  @override
  ConsumerState<OrderCreateScreen> createState() => _OrderCreateScreenState();
}

class _OrderCreateScreenState extends ConsumerState<OrderCreateScreen> {
  final List<OrderItem> _cart = [];
  final _searchCtrl = TextEditingController();
  final _notesCtrl = TextEditingController();
  String _searchQuery = '';
  bool _submitting = false;

  double get _total => _cart.fold(0.0, (sum, item) {
        return sum + item.unitPrice * item.quantity * (1 - item.discountPct / 100);
      });

  double get _subtotal => _cart.fold(0.0, (sum, item) {
        final lineTotalWithGst = item.unitPrice * item.quantity * (1 - item.discountPct / 100);
        return sum + (lineTotalWithGst / (1 + item.gstRate / 100));
      });

  double get _gst => _total - _subtotal;

  void _updateQty(Product product, int delta) {
    setState(() {
      final index = _cart.indexWhere((item) => item.productId == product.id);
      if (index >= 0) {
        _cart[index].quantity += delta;
        if (_cart[index].quantity <= 0) {
          _cart.removeAt(index);
        }
      } else if (delta > 0) {
        _cart.add(OrderItem(
          productId: product.id,
          productName: product.name,
          quantity: delta,
          unitPrice: product.mrp ?? 0.0,
          gstRate: product.gstRate,
        ));
      }
    });
  }

  int _getQty(int productId) {
    final index = _cart.indexWhere((item) => item.productId == productId);
    return index >= 0 ? _cart[index].quantity : 0;
  }

  Future<void> _submitOrder() async {
    if (_cart.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Cannot place an empty order')),
      );
      return;
    }

    final outlet = ref.read(selectedOutletProvider);
    if (outlet == null) return;

    setState(() => _submitting = true);
    try {
      final service = ref.read(orderServiceProvider);
      final beatId = ref.read(selectedBeatIdProvider);
      
      final orderResult = await service.createOrder(
        outletId: outlet.id,
        items: _cart,
        beatId: beatId,
        notes: _notesCtrl.text.trim(),
      );

      final orderId = orderResult['id'] as int;
      await service.submitOrder(orderId);

      if (mounted) {
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Order Placed'),
            content: Text('Order ${orderResult['order_number'] ?? '#$orderId'} has been submitted successfully.'),
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
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Order creation failed: $e'), backgroundColor: Colors.red.shade700),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    _notesCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final productsAsync = ref.watch(productsProvider);
    final outlet = ref.watch(selectedOutletProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text('New Order: ${outlet?.name ?? ''}'),
      ),
      body: _submitting
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: TextField(
                    controller: _searchCtrl,
                    decoration: InputDecoration(
                      hintText: 'Search products...',
                      prefixIcon: const Icon(Icons.search_rounded),
                      suffixIcon: _searchQuery.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear_rounded),
                              onPressed: () {
                                _searchCtrl.clear();
                                setState(() {
                                  _searchQuery = '';
                                });
                              },
                            )
                          : null,
                    ),
                    onChanged: (v) {
                      setState(() {
                        _searchQuery = v.trim().toLowerCase();
                      });
                    },
                  ),
                ),
                Expanded(
                  child: productsAsync.when(
                    data: (products) {
                      final filtered = products.where((p) {
                        return p.name.toLowerCase().contains(_searchQuery) ||
                            (p.sku != null && p.sku!.toLowerCase().contains(_searchQuery));
                      }).toList();

                      if (filtered.isEmpty) {
                        return Center(
                          child: Text(
                            'No products found',
                            style: theme.textTheme.bodyMedium,
                          ),
                        );
                      }

                      return ListView.builder(
                        itemCount: filtered.length,
                        itemBuilder: (ctx, idx) {
                          final product = filtered[idx];
                          final qty = _getQty(product.id);

                          return ListTile(
                            title: Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    product.name,
                                    style: theme.textTheme.titleMedium?.copyWith(
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                                if (product.mustSell)
                                  Container(
                                    margin: const EdgeInsets.only(left: 6),
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: Colors.orange.shade700,
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: const Text(
                                      'Must Sell',
                                      style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                                    ),
                                  ),
                              ],
                            ),
                            subtitle: Text(
                              'MRP: ${CurrencyFormatter.format(product.mrp ?? 0.0)} | GST: ${product.gstRate.toStringAsFixed(0)}%',
                              style: theme.textTheme.bodyMedium,
                            ),
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                if (qty > 0) ...[
                                  IconButton(
                                    icon: Icon(Icons.remove_circle_outline_rounded, color: theme.colorScheme.error),
                                    onPressed: () => _updateQty(product, -1),
                                  ),
                                  Text(
                                    '$qty',
                                    style: theme.textTheme.titleMedium?.copyWith(
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ],
                                IconButton(
                                  icon: const Icon(Icons.add_circle_outline_rounded, color: Colors.green),
                                  onPressed: () => _updateQty(product, 1),
                                ),
                              ],
                            ),
                          );
                        },
                      );
                    },
                    loading: () => const Center(child: CircularProgressIndicator()),
                    error: (e, __) => Center(child: Text('Error loading products: $e')),
                  ),
                ),
                if (_cart.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: theme.cardTheme.color,
                      border: Border(top: BorderSide(color: theme.dividerColor, width: 1.0)),
                      boxShadow: [
                        BoxShadow(
                          color: theme.colorScheme.shadow.withOpacity(0.05),
                          blurRadius: 10,
                          offset: const Offset(0, -4),
                        ),
                      ],
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        TextField(
                          controller: _notesCtrl,
                          decoration: const InputDecoration(
                            hintText: 'Add order notes...',
                            border: InputBorder.none,
                            enabledBorder: InputBorder.none,
                            focusedBorder: InputBorder.none,
                            fillColor: Colors.transparent,
                          ),
                        ),
                        const Divider(),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('Subtotal', style: theme.textTheme.bodyMedium),
                            Text(CurrencyFormatter.format(_subtotal), style: theme.textTheme.bodyLarge),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('GST', style: theme.textTheme.bodyMedium),
                            Text(CurrencyFormatter.format(_gst), style: theme.textTheme.bodyLarge),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Grand Total',
                              style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold, fontSize: 18),
                            ),
                            Text(
                              CurrencyFormatter.format(_total),
                              style: theme.textTheme.titleLarge?.copyWith(
                                fontWeight: FontWeight.bold,
                                fontSize: 18,
                                color: theme.colorScheme.primary,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _submitOrder,
                          child: const Text('Submit Order'),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
    );
  }
}
