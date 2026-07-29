import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:hive/hive.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import '../../main.dart' show hiveCipher;
import '../../providers/auth_provider.dart';
import '../../providers/beat_provider.dart';
import '../../providers/sync_provider.dart';
import '../../services/operations_service.dart';
import '../../widgets/denomination_input.dart';
import '../../utils/currency_formatter.dart';

final paymentServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return PaymentService(client);
});

class PaymentCollectScreen extends ConsumerStatefulWidget {
  const PaymentCollectScreen({super.key});

  @override
  ConsumerState<PaymentCollectScreen> createState() =>
      _PaymentCollectScreenState();
}

class _PaymentCollectScreenState extends ConsumerState<PaymentCollectScreen> {
  final _amountCtrl = TextEditingController();
  final _refCtrl = TextEditingController();
  String _method = 'cash';
  Map<String, int> _denominations = {};
  bool _submitting = false;

  @override
  void dispose() {
    _amountCtrl.dispose();
    _refCtrl.dispose();
    super.dispose();
  }

  double get _amount => double.tryParse(_amountCtrl.text.trim()) ?? 0.0;

  bool get _isDenominationMandatory {
    final config = ref.read(appConfigProvider);
    return (config?.denominationMandatory ?? false) && _method == 'cash';
  }

  bool get _isDenominationSumValid {
    if (!_isDenominationMandatory) return true;
    const denoms = [2000, 500, 200, 100, 50, 20, 10];
    final sum = denoms.fold(
        0.0, (acc, d) => acc + d * (_denominations[d.toString()] ?? 0));
    return sum == _amount;
  }

  Future<bool> _isOnline() async {
    try {
      final result = await Connectivity().checkConnectivity();
      return result.isNotEmpty && !result.contains(ConnectivityResult.none);
    } catch (_) {
      return false;
    }
  }

  Future<void> _collectPayment() async {
    final outlet = ref.read(selectedOutletProvider);
    if (outlet == null) return;

    if (_amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a valid amount')),
      );
      return;
    }

    if (!_isDenominationSumValid) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Denomination totals must match the payment amount')),
      );
      return;
    }

    setState(() => _submitting = true);

    final online = await _isOnline();

    try {
      if (online) {
        // ── Online path: direct API call ──────────────────────────────────
        final service = ref.read(paymentServiceProvider);
        final response = await service.collectPayment(
          outletId: outlet.id,
          amount: _amount,
          method: _method,
          transactionRef:
              _refCtrl.text.trim().isNotEmpty ? _refCtrl.text.trim() : null,
          denominations: _method == 'cash' ? _denominations : {},
        );

        final paymentId = response['id'] as int;
        await _storeLocalPayment(
          paymentId: paymentId,
          paymentRef: response['payment_ref'] ?? '#$paymentId',
          outletName: outlet.name,
        );

        if (mounted) _showSuccessDialog(outlet.name, queued: false);
      } else {
        // ── Offline path: queue and store a temp local record ─────────────
        final syncNotifier = ref.read(syncProvider.notifier);
        final denominations =
            _method == 'cash' ? _denominations : <String, int>{};

        // Create a temporary local ID (negative timestamp) so the UI can track it
        final tempId = -DateTime.now().millisecondsSinceEpoch;

        await syncNotifier.queueOp(
          method: 'POST',
          path: '/payments',
          queryParameters: {
            'outlet_id': outlet.id,
            'amount': _amount,
            'method': _method,
            if (_refCtrl.text.trim().isNotEmpty)
              'transaction_ref': _refCtrl.text.trim(),
            'denom_2000': denominations['2000'] ?? 0,
            'denom_500': denominations['500'] ?? 0,
            'denom_200': denominations['200'] ?? 0,
            'denom_100': denominations['100'] ?? 0,
            'denom_50': denominations['50'] ?? 0,
            'denom_20': denominations['20'] ?? 0,
            'denom_10': denominations['10'] ?? 0,
          },
          extra: {
            'temp_payment_id': tempId,
          },
        );

        await _storeLocalPayment(
          paymentId: tempId,
          paymentRef: 'OFFLINE-${DateTime.now().millisecondsSinceEpoch}',
          outletName: outlet.name,
        );

        if (mounted) _showSuccessDialog(outlet.name, queued: true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text('Failed to collect payment: $e'),
              backgroundColor: Colors.red.shade700),
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _storeLocalPayment({
    required int paymentId,
    required String paymentRef,
    required String outletName,
  }) async {
    final box = hiveCipher != null
        ? await Hive.openBox('unsubmitted_payments',
            encryptionCipher: hiveCipher)
        : await Hive.openBox('unsubmitted_payments');
    await box.put(paymentId, {
      'id': paymentId,
      'payment_ref': paymentRef,
      'amount': _amount,
      'outlet_name': outletName,
      'method': _method,
    });
  }

  void _showSuccessDialog(String outletName, {required bool queued}) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(queued ? 'Payment Queued (Offline)' : 'Payment Collected'),
        content: Text(
          queued
              ? 'You are offline. ${CurrencyFormatter.format(_amount)} from $outletName has been saved locally and will be submitted automatically when connectivity is restored.'
              : 'Collected ${CurrencyFormatter.format(_amount)} from $outletName.\n\nDo you want to submit payments to the manager now?',
        ),
        actions: [
          TextButton(
            child: const Text('Later'),
            onPressed: () {
              Navigator.pop(ctx);
              context.pop();
            },
          ),
          if (!queued)
            TextButton(
              child: const Text('Submit Now'),
              onPressed: () {
                Navigator.pop(ctx);
                context.pushReplacement('/payment/submit');
              },
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final outlet = ref.watch(selectedOutletProvider);
    final isDenomMandatory = _isDenominationMandatory;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text('Collect Payment: ${outlet?.name ?? ''}'),
      ),
      body: _submitting
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    TextField(
                      controller: _amountCtrl,
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(
                        labelText: 'Amount (₹)',
                        hintText: 'Enter amount collected',
                      ),
                      onChanged: (_) => setState(() {}),
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<String>(
                      initialValue: _method,
                      dropdownColor: theme.cardTheme.color,
                      style: theme.textTheme.bodyLarge,
                      decoration: const InputDecoration(
                        labelText: 'Payment Method',
                      ),
                      items: const [
                        DropdownMenuItem(value: 'cash', child: Text('Cash')),
                        DropdownMenuItem(value: 'upi', child: Text('UPI')),
                        DropdownMenuItem(
                            value: 'bank_transfer',
                            child: Text('Bank Transfer')),
                        DropdownMenuItem(
                            value: 'cheque', child: Text('Cheque')),
                      ],
                      onChanged: (v) {
                        if (v != null) {
                          setState(() {
                            _method = v;
                          });
                        }
                      },
                    ),
                    const SizedBox(height: 16),
                    if (_method != 'cash') ...[
                      TextField(
                        controller: _refCtrl,
                        decoration: InputDecoration(
                          labelText: _method == 'cheque'
                              ? 'Cheque Number'
                              : 'UPI Reference ID / Transaction Ref',
                          hintText: 'Enter reference number',
                        ),
                      ),
                      const SizedBox(height: 24),
                    ],
                    if (isDenomMandatory && _amount > 0) ...[
                      Text(
                        'Cash Denominations',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 12),
                      DenominationInput(
                        totalAmount: _amount,
                        onChanged: (counts) {
                          setState(() {
                            _denominations = counts;
                          });
                        },
                      ),
                      const SizedBox(height: 24),
                    ],
                    ElevatedButton(
                      onPressed: _collectPayment,
                      child: const Text('Record Payment'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
