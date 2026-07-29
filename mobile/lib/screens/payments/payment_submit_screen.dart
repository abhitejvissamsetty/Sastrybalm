import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:hive/hive.dart';
import '../../main.dart' show hiveCipher;
import '../../utils/currency_formatter.dart';
import 'payment_collect_screen.dart';

class PaymentSubmitScreen extends ConsumerStatefulWidget {
  const PaymentSubmitScreen({super.key});

  @override
  ConsumerState<PaymentSubmitScreen> createState() =>
      _PaymentSubmitScreenState();
}

class _PaymentSubmitScreenState extends ConsumerState<PaymentSubmitScreen> {
  final List<Map<String, dynamic>> _payments = [];
  final Set<int> _selectedIds = {};
  final _notesCtrl = TextEditingController();
  bool _loading = false;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _loadUnsubmittedPayments();
  }

  Future<void> _loadUnsubmittedPayments() async {
    setState(() => _loading = true);
    final box = hiveCipher != null
        ? await Hive.openBox('unsubmitted_payments',
            encryptionCipher: hiveCipher)
        : await Hive.openBox('unsubmitted_payments');
    final List<Map<String, dynamic>> list = [];
    for (final key in box.keys) {
      final value = box.get(key);
      if (value is Map) {
        list.add(Map<String, dynamic>.from(value));
      }
    }
    if (mounted) {
      setState(() {
        _payments.clear();
        _payments.addAll(list);
        _selectedIds.clear();
        _selectedIds.addAll(list.map((p) => p['id'] as int));
        _loading = false;
      });
    }
  }

  double get _selectedTotal => _payments
      .where((p) => _selectedIds.contains(p['id']))
      .fold(0.0, (sum, p) => sum + (p['amount'] as num).toDouble());

  Future<void> _submitPayments() async {
    if (_selectedIds.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Please select at least one payment to submit')),
      );
      return;
    }

    setState(() => _submitting = true);
    try {
      final service = ref.read(paymentServiceProvider);
      // Clean up negative/temp payment IDs by filtering them out or preventing them
      // In this setup, synced offline payments will be reconciled by SyncService.
      // Unsynced ones (still having negative IDs) shouldn't be submitted yet.
      final validIds = _selectedIds.where((id) => id >= 0).toList();
      if (validIds.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text(
                  'Offline collections must sync with the server before submission.')),
        );
        return;
      }

      final response = await service.submitPayments(
        paymentIds: validIds,
        notes:
            _notesCtrl.text.trim().isNotEmpty ? _notesCtrl.text.trim() : null,
      );

      final box = hiveCipher != null
          ? await Hive.openBox('unsubmitted_payments',
              encryptionCipher: hiveCipher)
          : await Hive.openBox('unsubmitted_payments');
      for (final id in validIds) {
        await box.delete(id);
      }

      if (mounted) {
        if (!mounted) return;
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Payments Submitted'),
            content: Text(
              'Submitted ${validIds.length} payments totaling ${CurrencyFormatter.format(_selectedTotal)} to manager.\n\nRef: ${response['submission_ref'] ?? ''}',
            ),
            actions: [
              TextButton(
                child: const Text('OK'),
                onPressed: () {
                  Navigator.pop(ctx);
                  context.go('/home');
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
            content: Text('Submission failed: $e'),
            backgroundColor: Colors.red.shade700),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Submit Payments'),
      ),
      body: _loading || _submitting
          ? const Center(child: CircularProgressIndicator())
          : _payments.isEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24.0),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.check_circle_outline_rounded,
                            size: 64, color: Colors.green),
                        const SizedBox(height: 16),
                        Text(
                          'All Cleared!',
                          style: theme.textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'No unsubmitted payments in your collection bag.',
                          textAlign: TextAlign.center,
                          style: theme.textTheme.bodyMedium,
                        ),
                        const SizedBox(height: 24),
                        ElevatedButton(
                          onPressed: () => context.go('/home'),
                          child: const Text('Go to Dashboard'),
                        ),
                      ],
                    ),
                  ),
                )
              : Column(
                  children: [
                    Expanded(
                      child: ListView.builder(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 8),
                        itemCount: _payments.length,
                        itemBuilder: (ctx, idx) {
                          final payment = _payments[idx];
                          final id = payment['id'] as int;
                          final refNo = payment['payment_ref'] ?? '';
                          final outlet = payment['outlet_name'] ?? '';
                          final amount = (payment['amount'] as num).toDouble();
                          final method = payment['method'] as String;
                          final isSelected = _selectedIds.contains(id);

                          return Card(
                            elevation: 2,
                            shadowColor: theme.colorScheme.shadow
                                .withValues(alpha: 0.04),
                            child: CheckboxListTile(
                              value: isSelected,
                              onChanged: (val) {
                                setState(() {
                                  if (val == true) {
                                    _selectedIds.add(id);
                                  } else {
                                    _selectedIds.remove(id);
                                  }
                                });
                              },
                              activeColor: theme.colorScheme.primary,
                              title: Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    refNo,
                                    style:
                                        theme.textTheme.titleMedium?.copyWith(
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  Text(
                                    CurrencyFormatter.format(amount),
                                    style:
                                        theme.textTheme.titleMedium?.copyWith(
                                      fontWeight: FontWeight.bold,
                                      color: theme.colorScheme.primary,
                                    ),
                                  ),
                                ],
                              ),
                              subtitle: Padding(
                                padding: const EdgeInsets.only(top: 4.0),
                                child: Text(
                                  '$outlet (${method.toUpperCase()})',
                                  style: theme.textTheme.bodyMedium,
                                ),
                              ),
                              controlAffinity: ListTileControlAffinity.leading,
                            ),
                          );
                        },
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: theme.cardTheme.color,
                        border: Border(
                            top: BorderSide(
                                color: theme.dividerColor, width: 1.0)),
                        boxShadow: [
                          BoxShadow(
                            color: theme.colorScheme.shadow
                                .withValues(alpha: 0.05),
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
                              labelText: 'Notes',
                              hintText: 'e.g. End of day cash submission',
                            ),
                          ),
                          const SizedBox(height: 16),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                'Selected (${_selectedIds.length})',
                                style: theme.textTheme.bodyMedium
                                    ?.copyWith(fontWeight: FontWeight.w600),
                              ),
                              Text(
                                CurrencyFormatter.format(_selectedTotal),
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
                            onPressed: _submitPayments,
                            child: const Text('Submit to Manager'),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
    );
  }
}
