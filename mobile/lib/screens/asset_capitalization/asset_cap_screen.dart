import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../providers/beat_provider.dart';
import '../../services/operations_service.dart';

final assetCapServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return AssetCapitalizationService(client);
});

class AssetCapitalizationScreen extends ConsumerStatefulWidget {
  const AssetCapitalizationScreen({super.key});

  @override
  ConsumerState<AssetCapitalizationScreen> createState() =>
      _AssetCapitalizationScreenState();
}

class _AssetCapitalizationScreenState
    extends ConsumerState<AssetCapitalizationScreen> {
  final _itemNameCtrl = TextEditingController();
  final _itemCodeCtrl = TextEditingController();
  final _warehouseCtrl = TextEditingController();
  final _notesCtrl = TextEditingController();
  final _quantityCtrl = TextEditingController(text: '1');

  String _deployedBy = 'rep';
  bool _submitting = false;

  @override
  void dispose() {
    _itemNameCtrl.dispose();
    _itemCodeCtrl.dispose();
    _warehouseCtrl.dispose();
    _notesCtrl.dispose();
    _quantityCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final outlet = ref.read(selectedOutletProvider);
    if (outlet == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text(
                'Please select an outlet from the beat plan first')),
      );
      return;
    }

    final itemName = _itemNameCtrl.text.trim();
    if (itemName.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter an item name')),
      );
      return;
    }

    final quantity = int.tryParse(_quantityCtrl.text.trim()) ?? 1;
    if (quantity <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Quantity must be at least 1')),
      );
      return;
    }

    setState(() => _submitting = true);
    try {
      final service = ref.read(assetCapServiceProvider);
      final response = await service.createCapitalization(
        outletId: outlet.id,
        itemName: itemName,
        itemCode: _itemCodeCtrl.text.trim().isNotEmpty
            ? _itemCodeCtrl.text.trim()
            : null,
        quantity: quantity,
        warehouseName: _warehouseCtrl.text.trim().isNotEmpty
            ? _warehouseCtrl.text.trim()
            : null,
        deployedBy: _deployedBy,
        notes: _notesCtrl.text.trim().isNotEmpty
            ? _notesCtrl.text.trim()
            : null,
      );

      if (mounted) {
        final acNumber = response['ac_number'] ?? '#${response['id']}';
        final syncStatus = response['sync_status'] ?? 'pending';

        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Asset Capitalization Recorded'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Item: $itemName'),
                const SizedBox(height: 6),
                Text('AC Number: $acNumber'),
                const SizedBox(height: 6),
                Row(
                  children: [
                    const Text('CMMS Sync: '),
                    _SyncStatusBadge(syncStatus),
                  ],
                ),
                if (syncStatus == 'pending' || syncStatus == 'failed') ...[
                  const SizedBox(height: 10),
                  Text(
                    'The record has been saved. CMMS sync will be retried automatically.',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.orange.shade700,
                    ),
                  ),
                ],
              ],
            ),
            actions: [
              TextButton(
                child: const Text('Done'),
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
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to submit: $e'),
            backgroundColor: Colors.red.shade700,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final outlet = ref.watch(selectedOutletProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Asset Capitalization'),
      ),
      body: _submitting
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Outlet context card
                    if (outlet != null) ...[
                      Card(
                        elevation: 2,
                        shadowColor:
                            theme.colorScheme.shadow.withOpacity(0.04),
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Row(
                            children: [
                              Icon(Icons.storefront_rounded,
                                  color: theme.colorScheme.primary, size: 20),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.start,
                                  children: [
                                    Text('Deploying to Outlet',
                                        style: theme.textTheme.bodySmall),
                                    Text(
                                      outlet.name,
                                      style: theme.textTheme.titleMedium
                                          ?.copyWith(
                                              fontWeight: FontWeight.bold),
                                    ),
                                    Text(outlet.code,
                                        style: theme.textTheme.bodySmall),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),
                    ] else ...[
                      Card(
                        color: Colors.orange.shade50,
                        child: Padding(
                          padding: const EdgeInsets.all(14.0),
                          child: Row(
                            children: [
                              Icon(Icons.warning_amber_rounded,
                                  color: Colors.orange.shade700),
                              const SizedBox(width: 10),
                              const Expanded(
                                child: Text(
                                  'No outlet selected. Go to Beat Plan and select an outlet first.',
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),
                    ],

                    // Item Name (required)
                    TextField(
                      controller: _itemNameCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Asset / Item Name *',
                        hintText: 'e.g. Display Cooler, Counter Stand',
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Item Code (optional)
                    TextField(
                      controller: _itemCodeCtrl,
                      decoration: const InputDecoration(
                        labelText: 'CMMS Item Code (Optional)',
                        hintText: 'e.g. COOLER-MED-100L',
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Quantity
                    TextField(
                      controller: _quantityCtrl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Quantity',
                        hintText: '1',
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Warehouse (optional)
                    TextField(
                      controller: _warehouseCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Source Warehouse (Optional)',
                        hintText: 'Leave blank to use company default',
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Deployed By
                    DropdownButtonFormField<String>(
                      value: _deployedBy,
                      dropdownColor: theme.cardTheme.color,
                      style: theme.textTheme.bodyLarge,
                      decoration:
                          const InputDecoration(labelText: 'Deployed By'),
                      items: const [
                        DropdownMenuItem(
                            value: 'rep', child: Text('Sales Representative')),
                        DropdownMenuItem(
                            value: 'manager',
                            child: Text('Territory Manager')),
                        DropdownMenuItem(
                            value: 'vendor', child: Text('Vendor / Supplier')),
                      ],
                      onChanged: (v) {
                        if (v != null) setState(() => _deployedBy = v);
                      },
                    ),
                    const SizedBox(height: 16),

                    // Notes
                    TextField(
                      controller: _notesCtrl,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        labelText: 'Notes (Optional)',
                        hintText: 'e.g. Placed at entrance near billing counter',
                      ),
                    ),
                    const SizedBox(height: 28),

                    // Info banner
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.primary.withOpacity(0.06),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: theme.colorScheme.primary.withOpacity(0.15),
                        ),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.info_outline_rounded,
                              size: 18,
                              color: theme.colorScheme.primary),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              'This will create an Asset Capitalization record in the system and trigger a CMMS Material Request automatically.',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.primary,
                                height: 1.5,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),

                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        icon: const Icon(Icons.inventory_2_rounded),
                        label: const Text('Submit Asset Capitalization'),
                        onPressed: outlet != null ? _submit : null,
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}

class _SyncStatusBadge extends StatelessWidget {
  final String status;
  const _SyncStatusBadge(this.status);

  @override
  Widget build(BuildContext context) {
    final (color, label) = switch (status) {
      'synced' => (Colors.green.shade700, 'Synced ✓'),
      'failed' => (Colors.red.shade700, 'Failed — Retry queued'),
      _ => (Colors.orange.shade700, 'Pending'),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Text(
        label,
        style: TextStyle(
            color: color, fontWeight: FontWeight.bold, fontSize: 12),
      ),
    );
  }
}
