import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import '../../providers/auth_provider.dart';
import '../../services/operations_service.dart';
import '../../services/image_picker_service.dart';
import '../../utils/date_formatter.dart';

final expenseServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return ExpenseService(client);
});

final myExpensesProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final service = ref.watch(expenseServiceProvider);
  return service.getMyExpenses();
});

class ExpenseScreen extends ConsumerStatefulWidget {
  const ExpenseScreen({super.key});

  @override
  ConsumerState<ExpenseScreen> createState() => _ExpenseScreenState();
}

class _ExpenseScreenState extends ConsumerState<ExpenseScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _amountCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  String _category = 'travel';
  bool _submitting = false;
  XFile? _selectedReceiptFile;

  final List<Map<String, dynamic>> _categories = [
    {'key': 'travel', 'label': 'Travel', 'icon': Icons.commute_rounded, 'color': const Color(0xFF3B82F6)},
    {'key': 'food', 'label': 'Food', 'icon': Icons.local_cafe_rounded, 'color': const Color(0xFFF59E0B)},
    {'key': 'accommodation', 'label': 'Accommodation', 'icon': Icons.king_bed_rounded, 'color': const Color(0xFF10B981)},
    {'key': 'misc', 'label': 'Miscellaneous', 'icon': Icons.grid_view_rounded, 'color': const Color(0xFF8B5CF6)},
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    _amountCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

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
        _amountCtrl.clear();
        _descCtrl.clear();
        ref.refresh(myExpensesProvider);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Expense logged successfully!'), backgroundColor: Color(0xFF22C55E)),
        );
        _tabController.animateTo(1);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to log expense: $e'), backgroundColor: const Color(0xFFDC2626)),
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final expensesAsync = ref.watch(myExpensesProvider);

    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      appBar: AppBar(
        title: const Text('Expenses & Reimbursements'),
        elevation: 0,
        bottom: TabBar(
          controller: _tabController,
          labelColor: const Color(0xFF09090B),
          unselectedLabelColor: const Color(0xFF71717A),
          indicatorColor: const Color(0xFF09090B),
          tabs: const [
            Tab(text: 'Log Expense'),
            Tab(text: 'My Expense Claims'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          // ── Tab 1: Log Expense ─────────────────────────────────────────────
          SingleChildScrollView(
            padding: const EdgeInsets.all(20.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Choose Category', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Color(0xFF09090B))),
                const SizedBox(height: 12),
                GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    childAspectRatio: 1.6,
                    crossAxisSpacing: 10,
                    mainAxisSpacing: 10,
                  ),
                  itemCount: _categories.length,
                  itemBuilder: (context, i) {
                    final cat = _categories[i];
                    final isSel = _category == cat['key'];
                    return InkWell(
                      onTap: () => setState(() => _category = cat['key']),
                      borderRadius: BorderRadius.circular(12),
                      child: Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: isSel ? (cat['color'] as Color).withOpacity(0.12) : Colors.white,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: isSel ? cat['color'] as Color : const Color(0xFFE4E4E7),
                            width: isSel ? 2 : 1,
                          ),
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(cat['icon'] as IconData, color: cat['color'] as Color, size: 24),
                            const SizedBox(height: 6),
                            Text(
                              cat['label'] as String,
                              style: TextStyle(
                                color: isSel ? cat['color'] as Color : const Color(0xFF09090B),
                                fontWeight: isSel ? FontWeight.bold : FontWeight.w500,
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
                const SizedBox(height: 20),
                const Text('Amount (₹)', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Color(0xFF09090B))),
                const SizedBox(height: 8),
                TextField(
                  controller: _amountCtrl,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    hintText: 'e.g. 450.00',
                    prefixText: '₹ ',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                const Text('Description / Purpose', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Color(0xFF09090B))),
                const SizedBox(height: 8),
                TextField(
                  controller: _descCtrl,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    hintText: 'e.g. Travel allowance for outlet visits in Sector 4',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                const Text('Receipt Image Proof', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Color(0xFF09090B))),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size(double.infinity, 48),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: const Icon(Icons.add_a_photo_outlined, size: 18, color: Color(0xFF09090B)),
                  label: Text(
                    _selectedReceiptFile == null
                        ? 'Attach Receipt (Camera / Gallery)'
                        : 'Receipt Attached: ${_selectedReceiptFile!.name}',
                    style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF09090B)),
                  ),
                  onPressed: () async {
                    final picker = ImagePickerService();
                    final file = await picker.showImageSourceDialog(context);
                    if (file != null) {
                      setState(() => _selectedReceiptFile = file);
                    }
                  },
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF09090B),
                      foregroundColor: Colors.white,
                      minimumSize: const Size(double.infinity, 50),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    onPressed: _submitting ? null : _submitExpense,
                    child: _submitting
                        ? const CircularProgressIndicator(color: Colors.white)
                        : const Text('Submit Expense Claim', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                  ),
                ),
              ],
            ),
          ),

          // ── Tab 2: Expense Claims History ──────────────────────────────────
          RefreshIndicator(
            color: const Color(0xFF09090B),
            onRefresh: () async => ref.refresh(myExpensesProvider),
            child: expensesAsync.when(
              data: (items) {
                if (items.isEmpty) {
                  return const Center(
                    child: Text('No expense claims submitted yet.', style: TextStyle(color: Color(0xFF71717A))),
                  );
                }

                return ListView.separated(
                  padding: const EdgeInsets.all(20),
                  itemCount: items.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (context, i) {
                    final exp = items[i];
                    final cat = (exp['category'] ?? 'misc').toString().toUpperCase();
                    final status = (exp['status'] ?? 'submitted').toString().toUpperCase();
                    final expDateStr = DateFormatter.formatDate(DateTime.parse(exp['expense_date']));

                    return Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: const Color(0xFFE4E4E7)),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(cat, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Color(0xFF09090B))),
                              const SizedBox(height: 4),
                              Text(expDateStr, style: const TextStyle(color: Color(0xFF71717A), fontSize: 11)),
                              if (exp['description'] != null && exp['description'].toString().isNotEmpty) ...[
                                const SizedBox(height: 4),
                                Text(exp['description'], style: const TextStyle(color: Color(0xFF3F3F46), fontSize: 12)),
                              ],
                            ],
                          ),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text('₹${exp['amount']}', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: Color(0xFF09090B))),
                              const SizedBox(height: 4),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: status == 'APPROVED' ? const Color(0xFFDCFCE7) : const Color(0xFFFEF3C7),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  status,
                                  style: TextStyle(
                                    color: status == 'APPROVED' ? const Color(0xFF15803D) : const Color(0xFFD97706),
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    );
                  },
                );
              },
              loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFF09090B))),
              error: (e, __) => Center(child: Text('Error: $e', style: const TextStyle(color: Colors.red))),
            ),
          ),
        ],
      ),
    );
  }
}
