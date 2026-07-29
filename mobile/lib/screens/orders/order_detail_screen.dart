import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../utils/currency_formatter.dart';
import '../orders/order_create_screen.dart';

final orderDetailProvider = FutureProvider.family
    .autoDispose<Map<String, dynamic>, int>((ref, orderId) async {
  final service = ref.watch(orderServiceProvider);
  return service.getOrder(orderId);
});

class OrderDetailScreen extends ConsumerWidget {
  final int orderId;
  const OrderDetailScreen({super.key, required this.orderId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final orderAsync = ref.watch(orderDetailProvider(orderId));
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        title: const Text('Order Details'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.refresh(orderDetailProvider(orderId)),
          ),
        ],
      ),
      body: orderAsync.when(
        data: (order) {
          final orderNo = order['order_number'] ?? '#$orderId';
          final status = order['status'] ?? 'unknown';
          final outlet = order['outlet_name'] ?? 'General Outlet';
          final amount = (order['total_amount'] as num?)?.toDouble() ?? 0.0;
          final date = order['order_date'] ?? '';
          final notes = order['notes'] as String?;
          final items = order['items'] as List<dynamic>? ?? [];

          Color statusColor;
          switch (status.toLowerCase()) {
            case 'submitted':
            case 'approved':
              statusColor = const Color(0xFF10B981); // Emerald
              break;
            case 'draft':
              statusColor = const Color(0xFFF59E0B); // Amber
              break;
            case 'rejected':
            case 'cancelled':
              statusColor = const Color(0xFFEF4444); // Red
              break;
            default:
              statusColor = theme.colorScheme.onSurface.withValues(alpha: 0.6);
          }

          return SafeArea(
            child: Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(20.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Header info card
                        Container(
                          width: double.infinity,
                          decoration: BoxDecoration(
                            color: theme.colorScheme.surface,
                            borderRadius: BorderRadius.circular(24),
                            border: Border.all(
                              color: theme.colorScheme.primary
                                  .withValues(alpha: 0.08),
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withValues(alpha: 0.02),
                                blurRadius: 10,
                                offset: const Offset(0, 4),
                              ),
                            ],
                          ),
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    orderNo,
                                    style:
                                        theme.textTheme.titleMedium?.copyWith(
                                      fontWeight: FontWeight.w900,
                                      fontSize: 18,
                                    ),
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 10, vertical: 4),
                                    decoration: BoxDecoration(
                                      color:
                                          statusColor.withValues(alpha: 0.08),
                                      borderRadius: BorderRadius.circular(12),
                                      border: Border.all(
                                        color:
                                            statusColor.withValues(alpha: 0.15),
                                        width: 1,
                                      ),
                                    ),
                                    child: Text(
                                      status.toUpperCase(),
                                      style:
                                          theme.textTheme.labelSmall?.copyWith(
                                        color: statusColor,
                                        fontWeight: FontWeight.bold,
                                        fontSize: 10,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const Divider(height: 24),
                              Text(
                                outlet,
                                style: theme.textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 16,
                                ),
                              ),
                              const SizedBox(height: 6),
                              Row(
                                children: [
                                  Icon(Icons.calendar_today_rounded,
                                      size: 14,
                                      color: theme.colorScheme.onSurface
                                          .withValues(alpha: 0.4)),
                                  const SizedBox(width: 6),
                                  Text(
                                    date,
                                    style: theme.textTheme.bodyMedium?.copyWith(
                                      fontSize: 13,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 14),
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    'Grand Total',
                                    style: theme.textTheme.bodyMedium?.copyWith(
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  Text(
                                    CurrencyFormatter.format(amount),
                                    style: theme.textTheme.titleLarge?.copyWith(
                                      fontWeight: FontWeight.w900,
                                      color: theme.colorScheme.primary,
                                      fontSize: 20,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 24),

                        // Items Section Title
                        Text(
                          'Items Summary (${items.length})',
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 12),

                        // Items List
                        ListView.separated(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: items.length,
                          separatorBuilder: (context, index) =>
                              const SizedBox(height: 10),
                          itemBuilder: (context, index) {
                            final item = items[index];
                            final prodName =
                                item['product_name'] ?? 'Unknown Product';
                            final qty = item['quantity'] ?? 1;
                            final price =
                                (item['unit_price'] as num?)?.toDouble() ?? 0.0;
                            final lineTotal =
                                (item['line_total'] as num?)?.toDouble() ??
                                    (price * qty);

                            return Container(
                              decoration: BoxDecoration(
                                color: theme.colorScheme.surface,
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(
                                  color: theme.colorScheme.primary
                                      .withValues(alpha: 0.06),
                                ),
                              ),
                              padding: const EdgeInsets.all(16),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.center,
                                children: [
                                  Container(
                                    padding: const EdgeInsets.all(10),
                                    decoration: BoxDecoration(
                                      color: theme.colorScheme.primary
                                          .withValues(alpha: 0.06),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Icon(Icons.inventory_2_outlined,
                                        color: theme.colorScheme.primary,
                                        size: 20),
                                  ),
                                  const SizedBox(width: 14),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          prodName,
                                          style: theme.textTheme.titleMedium
                                              ?.copyWith(
                                            fontSize: 14,
                                            fontWeight: FontWeight.bold,
                                          ),
                                          maxLines: 2,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          '${CurrencyFormatter.format(price)} × $qty',
                                          style: theme.textTheme.bodyMedium
                                              ?.copyWith(
                                            fontSize: 12,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  Text(
                                    CurrencyFormatter.format(lineTotal),
                                    style:
                                        theme.textTheme.titleMedium?.copyWith(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 14,
                                    ),
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                        const SizedBox(height: 24),

                        // Notes card
                        if (notes != null && notes.isNotEmpty) ...[
                          Text(
                            'Order Notes',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              fontSize: 16,
                            ),
                          ),
                          const SizedBox(height: 12),
                          Container(
                            width: double.infinity,
                            decoration: BoxDecoration(
                              color: theme.colorScheme.surface,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(
                                color: theme.colorScheme.primary
                                    .withValues(alpha: 0.06),
                              ),
                            ),
                            padding: const EdgeInsets.all(16),
                            child: Text(
                              notes,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                height: 1.4,
                              ),
                            ),
                          ),
                          const SizedBox(height: 24),
                        ],
                      ],
                    ),
                  ),
                ),

                // Submit order action block
                if (status.toLowerCase() == 'draft')
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 20, vertical: 16),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.surface,
                      border: Border(
                        top: BorderSide(
                          color:
                              theme.colorScheme.primary.withValues(alpha: 0.08),
                          width: 1,
                        ),
                      ),
                    ),
                    child: ElevatedButton(
                      onPressed: () async {
                        try {
                          final service = ref.read(orderServiceProvider);
                          await service.submitOrder(orderId);
                          if (!context.mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Order submitted successfully'),
                              backgroundColor: Colors.green,
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                          ref.invalidate(orderDetailProvider(orderId));
                        } catch (e) {
                          if (!context.mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('Submission failed: $e'),
                              backgroundColor: Colors.red.shade700,
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                        }
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: theme.colorScheme.primary,
                        minimumSize: const Size(double.infinity, 52),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      child: const Text('Submit Draft Order'),
                    ),
                  ),
              ],
            ),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, __) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('Error loading details: $e'),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: () => ref.refresh(orderDetailProvider(orderId)),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
