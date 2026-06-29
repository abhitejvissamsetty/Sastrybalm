import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../services/operations_service.dart';

final expenseServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return ExpenseService(client);
});

class ExpenseScreen extends ConsumerStatefulWidget {
  const ExpenseScreen({super.key});

  @override
  ConsumerState<ExpenseScreen> createState() => _ExpenseScreenState();
}

class _ExpenseScreenState extends ConsumerState<ExpenseScreen> {
  final _amountCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  String _category = 'travel';
  bool _submitting = false;

  final List<Map<String, dynamic>> _categories = [
    {
      'key': 'travel',
      'label': 'Travel',
      'icon': Icons.directions_car_rounded,
      'color': const Color(0xFF3B82F6), // Blue
    },
    {
      'key': 'food',
      'label': 'Food',
      'icon': Icons.restaurant_rounded,
      'color': const Color(0xFFF59E0B), // Amber
    },
    {
      'key': 'accommodation',
      'label': 'Accommodation',
      'icon': Icons.hotel_rounded,
      'color': const Color(0xFF10B981), // Emerald
    },
    {
      'key': 'misc',
      'label': 'Miscellaneous',
      'icon': Icons.more_horiz_rounded,
      'color': const Color(0xFF8B5CF6), // Violet
    },
  ];

  Future<void> _submitExpense() async {
    final amount = double.tryParse(_amountCtrl.text.trim()) ?? 0.0;
    if (amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a valid amount')),
      );
      return;
    }

    setState(() => _submitting = true);
    try {
      final service = ref.read(expenseServiceProvider);
      await service.logExpense(
        category: _category,
        amount: amount,
        description: _descCtrl.text.trim().isNotEmpty ? _descCtrl.text.trim() : null,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Expense logged successfully'), backgroundColor: Colors.green),
        );
        context.pop();
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to log expense: $e'), backgroundColor: Colors.red.shade700),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  void dispose() {
    _amountCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        title: const Text('Log Expense'),
      ),
      body: _submitting
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Choose Category',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 12),
                    GridView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 2,
                        crossAxisSpacing: 12,
                        mainAxisSpacing: 12,
                        childAspectRatio: 1.45,
                      ),
                      itemCount: _categories.length,
                      itemBuilder: (context, index) {
                        final cat = _categories[index];
                        final isSelected = _category == cat['key'];
                        final Color catColor = cat['color'];
                        return InkWell(
                          onTap: () {
                            setState(() {
                              _category = cat['key'];
                            });
                          },
                          borderRadius: BorderRadius.circular(16),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 200),
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: isSelected
                                  ? catColor.withOpacity(0.08)
                                  : theme.colorScheme.surface,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(
                                color: isSelected
                                    ? catColor
                                    : theme.colorScheme.primary.withOpacity(0.08),
                                width: isSelected ? 2.0 : 1.0,
                              ),
                              boxShadow: isSelected
                                  ? [
                                      BoxShadow(
                                        color: catColor.withOpacity(0.12),
                                        blurRadius: 10,
                                        offset: const Offset(0, 4),
                                      )
                                    ]
                                  : [],
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.all(8),
                                      decoration: BoxDecoration(
                                        color: isSelected
                                            ? catColor
                                            : theme.colorScheme.primary.withOpacity(0.06),
                                        shape: BoxShape.circle,
                                      ),
                                      child: Icon(
                                        cat['icon'],
                                        color: isSelected ? Colors.white : catColor,
                                        size: 20,
                                      ),
                                    ),
                                    if (isSelected)
                                      Icon(
                                        Icons.check_circle_rounded,
                                        color: catColor,
                                        size: 20,
                                      ),
                                  ],
                                ),
                                Text(
                                  cat['label'],
                                  style: theme.textTheme.titleMedium?.copyWith(
                                    fontWeight: isSelected ? FontWeight.bold : FontWeight.w600,
                                    fontSize: 15,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 28),
                    Text(
                      'Expense Details',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _amountCtrl,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(
                        labelText: 'Amount (₹)',
                        hintText: 'Enter expense amount',
                        prefixIcon: Icon(Icons.currency_rupee_rounded),
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _descCtrl,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        labelText: 'Description / Purpose',
                        hintText: 'e.g. Bus fare for beat route',
                        prefixIcon: Icon(Icons.description_outlined),
                      ),
                    ),
                    const SizedBox(height: 32),
                    ElevatedButton(
                      onPressed: _submitExpense,
                      style: ElevatedButton.styleFrom(
                        shadowColor: theme.colorScheme.primary.withOpacity(0.25),
                        elevation: 4,
                      ),
                      child: const Text('Submit Expense'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
