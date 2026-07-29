import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../models/product.dart';
import '../../providers/beat_provider.dart';
import '../../providers/auth_provider.dart';
import '../../providers/visit_provider.dart';
import '../../services/operations_service.dart';
import '../../utils/currency_formatter.dart';
import '../../widgets/numeric_osk_widget.dart';

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
  final Map<int, bool> _stockableMap = {};
  final _searchCtrl = TextEditingController();
  final _notesCtrl = TextEditingController();
  final _refCtrl = TextEditingController();

  String _searchQuery = '';
  bool _submitting = false;
  bool _loadingWarehouse = true;
  int? _warehouseId;
  String? _warehouseName;

  // OSK state
  int? _activeProductId;
  String _oskInput = '';

  // Fulfillment & Payment State
  int _step = 1; // 1 = Items, 2 = Fulfillment, 3 = Payment
  String _fulfillmentOption =
      'Channel Partner'; // 'Channel Partner', 'Company Order'
  String _paymentType = 'Credit'; // 'Credit', 'Full', 'Partial'
  String _paymentMode = 'Cash'; // 'Cash', 'UPI', 'NEFT/RTGS', 'Others'

  double get _total => _cart.fold(0.0, (sum, item) {
        return sum +
            item.unitPrice * item.quantity * (1 - item.discountPct / 100);
      });

  bool get _hasUnavailableCompanyItem {
    for (final item in _cart) {
      final products =
          ref.read(warehouseProductsProvider(_warehouseId)).valueOrNull ?? [];
      final matches = products.where((p) => p.id == item.productId);
      final product = matches.isEmpty ? null : matches.first;
      if (_stockableMap[item.productId] == false ||
          product == null ||
          product.warehouseStockQty < item.quantity) {
        return true;
      }
    }
    return false;
  }

  @override
  void initState() {
    super.initState();
    _loadWarehouse();
  }

  Future<void> _loadWarehouse() async {
    final outlet = ref.read(selectedOutletProvider);
    final beatId = ref.read(selectedBeatIdProvider);
    if (outlet == null) return;
    try {
      final context = await ref.read(orderServiceProvider).getWarehouseContext(
            outletId: outlet.id,
            beatId: beatId,
          );
      if (mounted) {
        setState(() {
          _warehouseId = context['warehouse_id'] as int;
          _warehouseName = context['warehouse_name']?.toString();
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
    setState(() {
      _stockableMap[product.id] = product.isStockableItem;
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
      _setProductQty(_activeProductId!, newQty);
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

  void _updateQtyButton(Product product, int delta) {
    setState(() {
      _stockableMap[product.id] = product.isStockableItem;
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
      _activeProductId = product.id;
      _oskInput = '${_getQty(product.id)}';
    });
  }

  int _getQty(int productId) {
    final index = _cart.indexWhere((item) => item.productId == productId);
    return index >= 0 ? _cart[index].quantity : 0;
  }

  void _onOskNext() {
    if (_cart.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content:
                Text('Please select at least one item before proceeding.')),
      );
      return;
    }
    setState(() {
      _activeProductId = null;
      _step = 2; // Move to Fulfillment step
    });
  }

  Future<void> _submitOrder() async {
    if (_cart.isEmpty) return;

    final outlet = ref.read(selectedOutletProvider);
    if (outlet == null) return;

    setState(() => _submitting = true);
    try {
      final service = ref.read(orderServiceProvider);
      final beatId = ref.read(selectedBeatIdProvider);
      final visit = ref.read(activeVisitProvider)[outlet.id];
      if (visit == null) {
        throw StateError(
            'Begin a Visit against this Outlet before placing a Secondary Order.');
      }
      if (_warehouseId == null) {
        throw StateError('No L3 warehouse is available for this order.');
      }
      if (_paymentType != 'Credit' &&
          _paymentMode != 'Cash' &&
          _refCtrl.text.trim().isEmpty) {
        throw StateError(
            'Payment reference is required for non-cash Paid Orders.');
      }

      final isCompany = _fulfillmentOption == 'Company Order';
      final isPaidFlag = isCompany && (_paymentType != 'Credit');

      final orderResult = await service.createOrder(
        outletId: outlet.id,
        partyId: outlet.id,
        partyType: 'Outlet',
        orderType: 'Secondary',
        items: _cart,
        beatId: beatId,
        visitId: visit.id,
        warehouseId: _warehouseId,
        isCompanyOrder: isCompany,
        isPaid: isPaidFlag,
        paymentType: isCompany ? _paymentType : null,
        paymentMode: isCompany && isPaidFlag ? _paymentMode : null,
        paymentReference:
            _refCtrl.text.trim().isNotEmpty ? _refCtrl.text.trim() : null,
        notes: _notesCtrl.text.trim(),
      );

      final orderId = orderResult['id'] as int;
      await service.submitOrder(orderId);

      if (mounted) {
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Order Submitted Successfully'),
            content: Text(
                'Order ${orderResult['order_number'] ?? '#$orderId'} has been placed.'),
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
            content: Text('Order submission failed: $e'),
            backgroundColor: Colors.red.shade700),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    _notesCtrl.dispose();
    _refCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final productsAsync = ref.watch(warehouseProductsProvider(_warehouseId));
    final outlet = ref.watch(selectedOutletProvider);
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: Text(_step == 1
            ? 'New Order: ${outlet?.name ?? ''}'
            : (_step == 2 ? 'Fulfillment Options' : 'Payment Collection')),
        leading: _step > 1
            ? IconButton(
                icon: const Icon(Icons.arrow_back_rounded),
                onPressed: () => setState(() => _step--),
              )
            : null,
      ),
      body: _submitting || _loadingWarehouse
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                if (_step == 1) ...[
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
                                  setState(() => _searchQuery = '');
                                },
                              )
                            : null,
                      ),
                      onChanged: (v) =>
                          setState(() => _searchQuery = v.trim().toLowerCase()),
                    ),
                  ),
                  Expanded(
                    child: productsAsync.when(
                      data: (products) {
                        final filtered = products.where((p) {
                          final isSale =
                              p.categoryScope.toLowerCase().contains('sale');
                          final matchesSearch = p.name
                                  .toLowerCase()
                                  .contains(_searchQuery) ||
                              (p.sku != null &&
                                  p.sku!.toLowerCase().contains(_searchQuery));
                          return isSale && matchesSearch;
                        }).toList();

                        if (filtered.isEmpty) {
                          return const Center(
                              child: Text('No Sale products found'));
                        }

                        return ListView.builder(
                          itemCount: filtered.length,
                          itemBuilder: (ctx, idx) {
                            final product = filtered[idx];
                            final qty = _getQty(product.id);
                            final isSelected = _activeProductId == product.id;

                            return Container(
                              color: isSelected
                                  ? (isDark
                                      ? const Color(0xFF27272A)
                                      : Colors.blue.shade50)
                                  : null,
                              child: ListTile(
                                onTap: () => _onProductTap(product),
                                title: Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        product.name,
                                        style: theme.textTheme.titleMedium
                                            ?.copyWith(
                                                fontWeight: FontWeight.bold),
                                      ),
                                    ),
                                    if (!product.isStockableItem)
                                      Container(
                                        padding: const EdgeInsets.symmetric(
                                            horizontal: 6, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: Colors.amber.shade800,
                                          borderRadius:
                                              BorderRadius.circular(4),
                                        ),
                                        child: const Text(
                                          'Non-Stockable',
                                          style: TextStyle(
                                              color: Colors.white,
                                              fontSize: 10,
                                              fontWeight: FontWeight.bold),
                                        ),
                                      ),
                                  ],
                                ),
                                subtitle: Text(
                                  'MRP: ${CurrencyFormatter.format(product.mrp ?? 0.0)} | '
                                  'GST: ${product.gstRate.toStringAsFixed(0)}% | '
                                  '${_warehouseName ?? 'Warehouse'} Stock: ${product.warehouseStockQty}',
                                ),
                                trailing: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    if (qty > 0) ...[
                                      IconButton(
                                        icon: Icon(
                                            Icons.remove_circle_outline_rounded,
                                            color: theme.colorScheme.error),
                                        onPressed: () =>
                                            _updateQtyButton(product, -1),
                                      ),
                                      Text('$qty',
                                          style: theme.textTheme.titleMedium
                                              ?.copyWith(
                                                  fontWeight: FontWeight.bold)),
                                    ],
                                    IconButton(
                                      icon: const Icon(
                                          Icons.add_circle_outline_rounded,
                                          color: Colors.green),
                                      onPressed: () =>
                                          _updateQtyButton(product, 1),
                                    ),
                                  ],
                                ),
                              ),
                            );
                          },
                        );
                      },
                      loading: () =>
                          const Center(child: CircularProgressIndicator()),
                      error: (e, __) =>
                          Center(child: Text('Error loading products: $e')),
                    ),
                  ),

                  // Bottom Summary & OSK
                  if (_cart.isNotEmpty)
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 10),
                      color: isDark
                          ? const Color(0xFF18181B)
                          : const Color(0xFFF4F4F5),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('${_cart.length} Line Items',
                                  style: theme.textTheme.bodySmall),
                              Text(
                                CurrencyFormatter.format(_total),
                                style: theme.textTheme.titleLarge?.copyWith(
                                    fontWeight: FontWeight.bold,
                                    color: theme.colorScheme.primary),
                              ),
                            ],
                          ),
                          ElevatedButton(
                            onPressed: _onOskNext,
                            child: const Text('Fulfillment Step →'),
                          ),
                        ],
                      ),
                    ),

                  if (_activeProductId != null)
                    NumericOskWidget(
                      onKeyPress: _updateQtyFromOsk,
                      onDelete: _onOskDelete,
                      onNext: _onOskNext,
                      nextLabel: 'NEXT STEP',
                    ),
                ] else if (_step == 2) ...[
                  // Step 2: Fulfillment Choice
                  Expanded(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (_hasUnavailableCompanyItem)
                            Container(
                              margin: const EdgeInsets.only(bottom: 16),
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: Colors.amber.shade900
                                    .withValues(alpha: 0.15),
                                border:
                                    Border.all(color: Colors.amber.shade700),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Row(
                                children: [
                                  Icon(Icons.warning_amber_rounded,
                                      color: Colors.amber.shade700),
                                  const SizedBox(width: 10),
                                  const Expanded(
                                    child: Text(
                                      'One or more selected products are non-stockable or do not have enough stock in the resolved L3 warehouse. Company Order is disabled.',
                                      style: TextStyle(
                                          fontSize: 13,
                                          fontWeight: FontWeight.w500),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          Text('Select Fulfillment Method',
                              style: theme.textTheme.titleMedium
                                  ?.copyWith(fontWeight: FontWeight.bold)),
                          const SizedBox(height: 12),
                          RadioGroup<String>(
                            groupValue: _fulfillmentOption,
                            onChanged: (value) {
                              if (value != null) {
                                setState(() => _fulfillmentOption = value);
                              }
                            },
                            child: Column(
                              children: [
                                const RadioListTile<String>(
                                  title: Text('Channel Partner',
                                      style: TextStyle(
                                          fontWeight: FontWeight.bold)),
                                  subtitle: Text(
                                      'Fulfill via local Channel Partner distributor'),
                                  value: 'Channel Partner',
                                ),
                                RadioListTile<String>(
                                  title: Text('Company Order',
                                      style: TextStyle(
                                          fontWeight: FontWeight.bold,
                                          color: _hasUnavailableCompanyItem
                                              ? Colors.grey
                                              : null)),
                                  subtitle: Text(
                                      'Fulfill from ${_warehouseName ?? 'the resolved L3 warehouse'}',
                                      style: TextStyle(
                                          color: _hasUnavailableCompanyItem
                                              ? Colors.grey
                                              : null)),
                                  value: 'Company Order',
                                  enabled: !_hasUnavailableCompanyItem,
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 24),
                          TextField(
                            controller: _notesCtrl,
                            maxLines: 2,
                            decoration: const InputDecoration(
                              labelText: 'Order Notes',
                              hintText: 'Enter optional order instructions...',
                              border: OutlineInputBorder(),
                            ),
                          ),
                          const SizedBox(height: 24),
                          ElevatedButton(
                            style: ElevatedButton.styleFrom(
                                minimumSize: const Size.fromHeight(50)),
                            onPressed: () {
                              if (_fulfillmentOption == 'Company Order') {
                                setState(() => _step = 3);
                              } else {
                                _submitOrder();
                              }
                            },
                            child: Text(_fulfillmentOption == 'Company Order'
                                ? 'Proceed to Payment Details →'
                                : 'Submit Order Now'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ] else if (_step == 3) ...[
                  // Step 3: Payment Details
                  Expanded(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Company Order Payment Details',
                              style: theme.textTheme.titleMedium
                                  ?.copyWith(fontWeight: FontWeight.bold)),
                          const SizedBox(height: 16),
                          Text('Order Payment Type',
                              style: theme.textTheme.bodyMedium
                                  ?.copyWith(fontWeight: FontWeight.bold)),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Expanded(
                                child: ChoiceChip(
                                  label: const Text('Credit Order'),
                                  selected: _paymentType == 'Credit',
                                  onSelected: (sel) => setState(() {
                                    if (sel) {
                                      _paymentType = 'Credit';
                                    }
                                  }),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: ChoiceChip(
                                  label: const Text('Full Paid'),
                                  selected: _paymentType == 'Full',
                                  onSelected: (sel) => setState(() {
                                    if (sel) {
                                      _paymentType = 'Full';
                                    }
                                  }),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: ChoiceChip(
                                  label: const Text('Partial Paid'),
                                  selected: _paymentType == 'Partial',
                                  onSelected: (sel) => setState(() {
                                    if (sel) {
                                      _paymentType = 'Partial';
                                    }
                                  }),
                                ),
                              ),
                            ],
                          ),
                          if (_paymentType != 'Credit') ...[
                            const SizedBox(height: 20),
                            Text('Payment Mode',
                                style: theme.textTheme.bodyMedium
                                    ?.copyWith(fontWeight: FontWeight.bold)),
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 8,
                              children: ['Cash', 'UPI', 'NEFT/RTGS', 'Others']
                                  .map((mode) {
                                return ChoiceChip(
                                  label: Text(mode),
                                  selected: _paymentMode == mode,
                                  onSelected: (sel) =>
                                      setState(() => _paymentMode = mode),
                                );
                              }).toList(),
                            ),
                            const SizedBox(height: 16),
                            TextField(
                              controller: _refCtrl,
                              decoration: const InputDecoration(
                                labelText: 'Payment Reference / Transaction ID',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ],
                          const SizedBox(height: 30),
                          ElevatedButton(
                            style: ElevatedButton.styleFrom(
                                minimumSize: const Size.fromHeight(50)),
                            onPressed: _submitOrder,
                            child: const Text('Complete & Submit Order'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
    );
  }
}
