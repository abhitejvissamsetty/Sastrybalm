import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../utils/currency_formatter.dart';
import '../orders/order_create_screen.dart';
import '../../providers/attendance_provider.dart';

final myOrdersProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final service = ref.watch(orderServiceProvider);
  return service.getMyOrders();
});

class OrderListScreen extends ConsumerWidget {
  const OrderListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final attendanceAsync = ref.watch(attendanceProvider);
    final isCheckedIn = attendanceAsync.valueOrNull?.checkedIn ?? false;
    final ordersAsync = ref.watch(myOrdersProvider);
    final theme = Theme.of(context);

    if (!isCheckedIn) {
      return Scaffold(
        appBar: AppBar(title: const Text('Order History')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.lock_outline_rounded,
                    size: 64, color: Color(0xFF09090B)),
                const SizedBox(height: 16),
                Text(
                  'Workday Not Active',
                  style: theme.textTheme.titleLarge
                      ?.copyWith(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Text(
                  'You must Begin Workday on the Dashboard before accessing Orders.',
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
        ),
      );
    }

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
                final amount =
                    (order['total_amount'] as num?)?.toDouble() ?? 0.0;
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
                    statusColor =
                        theme.colorScheme.onSurface.withValues(alpha: 0.6);
                }

                return Card(
                  elevation: 2,
                  shadowColor: theme.colorScheme.shadow.withValues(alpha: 0.04),
                  child: ListTile(
                    onTap: () => context.push('/order/${order['id']}'),
                    contentPadding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
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
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: statusColor.withValues(alpha: 0.1),
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
