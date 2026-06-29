import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../utils/currency_formatter.dart';
import '../orders/order_create_screen.dart';

final myOrdersProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final service = ref.watch(orderServiceProvider);
  return service.getMyOrders();
});

class OrderListScreen extends ConsumerWidget {
  const OrderListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(myOrdersProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Order History'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.refresh(myOrdersProvider),
          ),
        ],
      ),
      body: ordersAsync.when(
        data: (orders) {
          if (orders.isEmpty) {
            return Center(
              child: Text(
                'No orders placed yet.',
                style: theme.textTheme.bodyMedium,
              ),
            );
          }

          return RefreshIndicator(
            onRefresh: () async => ref.refresh(myOrdersProvider),
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              itemCount: orders.length,
              itemBuilder: (ctx, idx) {
                final order = orders[idx];

                final orderNo = order['order_number'] ?? '#${order['id']}';
                final status = order['status'] ?? 'unknown';
                final outlet = order['outlet_name'] ?? 'General Outlet';
                final amount = (order['total_amount'] as num?)?.toDouble() ?? 0.0;
                final date = order['order_date'] ?? '';

                Color statusColor;
                switch (status.toLowerCase()) {
                  case 'submitted':
                  case 'approved':
                    statusColor = Colors.green.shade600;
                    break;
                  case 'draft':
                    statusColor = Colors.amber.shade700;
                    break;
                  case 'rejected':
                    statusColor = Colors.red.shade600;
                    break;
                  default:
                    statusColor = theme.colorScheme.onSurface.withOpacity(0.6);
                }

                return Card(
                  elevation: 2,
                  shadowColor: theme.colorScheme.shadow.withOpacity(0.04),
                  child: ListTile(
                    onTap: () => context.push('/order/${order['id']}'),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    title: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          orderNo,
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: statusColor.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            status.toUpperCase(),
                            style: theme.textTheme.labelSmall?.copyWith(
                              color: statusColor,
                              fontWeight: FontWeight.bold,
                              fontSize: 10,
                            ),
                          ),
                        ),
                      ],
                    ),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SizedBox(height: 6),
                        Text(
                          outlet,
                          style: theme.textTheme.bodyLarge?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          date,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                    trailing: Text(
                      CurrencyFormatter.format(amount),
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: theme.colorScheme.primary,
                      ),
                    ),
                  ),
                );
              },
            ),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, __) => Center(child: Text('Error loading orders: $e')),
      ),
    );
  }
}
